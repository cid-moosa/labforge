#!/usr/bin/env python3
"""
labforge.runner
Autonomous Orchestrator & CLI Runner for Project LabForge.
"""

import sys
import os
import argparse
from typing import Optional, Dict, Any, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.inspect_record import scan_input_directory
from scripts.labforge_engine import build_aligned_record, convert_docx_to_pdf
from scripts.verify_pdf import audit_pdf


def matches_lab(lab_name: str, target: str) -> bool:
    """Matches a lab folder name against a user filter (e.g. 'lab 1', 'lab1', '1')."""
    if not target:
        return True
    target_clean = target.strip().lower().replace(" ", "")
    lab_clean = lab_name.strip().lower().replace(" ", "")
    if lab_clean == target_clean or lab_clean == f"lab{target_clean}":
        return True
    return target.strip().lower() in lab_name.strip().lower()


def run_pipeline(
    input_dir: str = "input",
    output_dir: str = "output",
    mappings_dir: str = "mappings",
    lab_filter: Optional[str] = None,
    no_crop: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Executes the autonomous LabForge processing pipeline for all or filtered labs.
    Generates output/<Lab_Folder>/<Record_Name> - Final.docx and .pdf,
    followed by 5-Gate PyMuPDF QA audit verification.
    """
    all_labs = scan_input_directory(input_dir)
    print("=" * 60)
    print("🚀 Project LabForge: Autonomous Execution Engine")
    print("=" * 60)

    if not all_labs:
        print(f"No lab folders found in '{input_dir}'.")
        print(f"Create folders like '{input_dir}/lab 1' with your .docx template and screenshots.")
        return {}

    if lab_filter:
        labs = [l for l in all_labs if matches_lab(l["lab_folder"], lab_filter)]
        if not labs:
            print(f"No lab folder matching filter '{lab_filter}' found in '{input_dir}'.")
            return {}
    else:
        labs = all_labs

    ready_labs = [l for l in labs if l["docx_files"] and l["screenshot_count"] > 0]
    print(f"Found {len(labs)} lab folders ({len(ready_labs)} ready with .docx and screenshots).\n")

    results: Dict[str, Any] = {}

    for lab in labs:
        lab_name = lab["lab_folder"]
        print(f"📂 Processing: {lab_name}")
        if not lab["docx_files"]:
            print(f"   ⚠️  Skipped: No .docx file found in '{lab['folder_path']}'")
            continue
        if lab["screenshot_count"] == 0:
            print(f"   ⚠️  Skipped: No screenshots found in '{lab['folder_path']}' (waiting for images)")
            continue

        # Prefer root docx inside the lab folder if nested duplicates exist
        root_docx = [
            f for f in lab["docx_files"]
            if os.path.dirname(f).replace("\\", "/") == lab["folder_path"].replace("\\", "/")
        ]
        docx_path = root_docx[0] if root_docx else lab["docx_files"][0]

        # Look for mapping
        clean_name = lab_name.lower().replace(" ", "")
        mapping_file = os.path.join(mappings_dir, f"{clean_name}_map.json")
        if not os.path.exists(mapping_file):
            print(f"   ℹ️  No existing mapping found at '{mapping_file}'. Run VisionTarget or provide mapping.")
            continue

        base_name = os.path.splitext(os.path.basename(docx_path))[0]
        lab_out_dir = os.path.join(output_dir, lab_name)
        out_docx = os.path.join(lab_out_dir, f"{base_name} - Final.docx")
        out_pdf = os.path.join(lab_out_dir, f"{base_name} - Final.pdf")

        if not force and os.path.exists(out_docx) and os.path.exists(out_pdf):
            print(f"   ⏩ Skipped: Already built ({out_pdf} exists). Use --force to rebuild.")
            results[lab_name] = {"verdict": "SKIPPED", "docx": out_docx, "pdf": out_pdf}
            continue

        os.makedirs(lab_out_dir, exist_ok=True)

        print(f"   📐 LayoutEngine: Formatting {docx_path} -> {out_docx}")
        try:
            build_aligned_record(docx_path, mapping_file, out_docx, output_pdf=out_pdf, no_crop=no_crop)
            if not os.path.exists(out_pdf):
                convert_docx_to_pdf(out_docx, out_pdf)
            print(f"   🖨️  PDF Exported: {out_pdf}")

            print(f"   🔍 QA Audit: Auditing {out_pdf}")
            audit_result = audit_pdf(out_pdf, mapping_file)
            print(f"   📊 Verdict: {audit_result['verdict']} | Pages: {audit_result['total_pages']} | Images: {audit_result['total_images_found']}")
            for gate_name, gate_info in audit_result["gates"].items():
                mark = "✅ PASS" if gate_info["passed"] else "❌ FAIL"
                print(f"      - {gate_name}: {mark}")
            results[lab_name] = audit_result
        except Exception as e:
            print(f"   ❌ Error processing {lab_name}: {e}")
            results[lab_name] = {"verdict": "ERROR", "error": str(e)}

    print("=" * 60)
    print("Execution complete.")
    print("=" * 60)
    return results


def main():
    parser = argparse.ArgumentParser(description="LabForge Autonomous Runner")
    parser.add_argument("--scan", action="store_true", help="Scan input/ folder and exit")
    parser.add_argument("--input", default="input", help="Path to input directory")
    parser.add_argument("--output", default="output", help="Path to output directory")
    parser.add_argument("--mappings", default="mappings", help="Path to mappings directory")
    parser.add_argument("--lab", default=None, help="Process only the specified lab folder (e.g. 'lab 1' or 'lab1')")
    parser.add_argument("--no-crop", action="store_true", help="Disable automatic terminal window cropping")
    parser.add_argument("--force", action="store_true", help="Force rebuild even if output files already exist")
    args = parser.parse_args()

    if args.scan:
        labs = scan_input_directory(args.input)
        print(f"Scan complete: Found {len(labs)} lab folders in '{args.input}'.")
        for lab in labs:
            status = "READY" if (lab["docx_files"] and lab["screenshot_count"] > 0) else "PENDING"
            print(f" - {lab['lab_folder']}: {len(lab['docx_files'])} docx, {lab['screenshot_count']} images [{status}]")
    else:
        results = run_pipeline(
            input_dir=args.input,
            output_dir=args.output,
            mappings_dir=args.mappings,
            lab_filter=args.lab,
            no_crop=args.no_crop,
            force=args.force,
        )
        # If any processed lab had a non-PASS verdict, exit with non-zero
        failures = [
            name for name, res in results.items()
            if res.get("verdict") not in ("PASS", "SKIPPED")
        ]
        if failures:
            sys.exit(1)


if __name__ == "__main__":
    main()
