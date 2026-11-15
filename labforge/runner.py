#!/usr/bin/env python3
"""
labforge.runner
Autonomous Orchestrator & CLI Runner for Project LabForge.
"""

import sys
import os
import argparse
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.inspect_record import scan_input_directory, inspect_document, inspect_screenshots
from scripts.labforge_engine import build_aligned_record, convert_docx_to_pdf
from scripts.verify_pdf import audit_pdf


def run_pipeline(input_dir: str = "input", output_dir: str = "output", mappings_dir: str = "mappings"):
    labs = scan_input_directory(input_dir)
    print("=" * 60)
    print("🚀 Project LabForge: Autonomous Execution Engine")
    print("=" * 60)

    if not labs:
        print(f"No lab folders found in '{input_dir}'.")
        print(f"Create folders like '{input_dir}/lab 1' with your .docx template and screenshots.")
        return

    unbuilt_ready = [l for l in labs if l["docx_files"] and l["screenshot_count"] > 0]
    print(f"Found {len(labs)} lab folders ({len(unbuilt_ready)} ready with .docx and screenshots).\n")

    for lab in labs:
        lab_name = lab["lab_folder"]
        print(f"📂 Processing: {lab_name}")
        if not lab["docx_files"]:
            print(f"   ⚠️  Skipped: No .docx file found in '{lab['folder_path']}'")
            continue
        if lab["screenshot_count"] == 0:
            print(f"   ⚠️  Skipped: No screenshots found in '{lab['folder_path']}' (waiting for images)")
            continue

        docx_path = lab["docx_files"][0]
        # Look for mapping
        clean_name = lab_name.lower().replace(" ", "")
        mapping_file = os.path.join(mappings_dir, f"{clean_name}_map.json")
        if not os.path.exists(mapping_file):
            print(f"   ℹ️  No existing mapping found at '{mapping_file}'. Run VisionTarget or provide mapping.")
            continue

        base_name = os.path.splitext(os.path.basename(docx_path))[0]
        lab_out_dir = os.path.join(output_dir, lab_name)
        out_docx = os.path.join(lab_out_dir, f"{base_name} - Final.docx")
        final_pdf_dir = os.path.join(lab_out_dir, "final")
        out_pdf = os.path.join(final_pdf_dir, f"{base_name} - Final.pdf")

        os.makedirs(lab_out_dir, exist_ok=True)
        os.makedirs(final_pdf_dir, exist_ok=True)

        print(f"   📐 LayoutEngine: Formatting {docx_path} -> {out_docx}")
        try:
            build_aligned_record(docx_path, mapping_file, out_docx)
            convert_docx_to_pdf(out_docx, out_pdf)
            print(f"   🖨️  PDF Exported: {out_pdf}")

            print(f"   🔍 QA Audit: Auditing {out_pdf}")
            audit_result = audit_pdf(out_pdf, mapping_file)
            print(f"   📊 Verdict: {audit_result['verdict']} | Pages: {audit_result['total_pages']} | Images: {audit_result['total_images_found']}")
            for gate_name, gate_info in audit_result["gates"].items():
                mark = "✅ PASS" if gate_info["passed"] else "❌ FAIL"
                print(f"      - {gate_name}: {mark}")
        except Exception as e:
            print(f"   ❌ Error processing {lab_name}: {e}")

    print("=" * 60)
    print("Execution complete.")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="LabForge Autonomous Runner")
    parser.add_argument("--scan", action="store_true", help="Scan input/ folder and exit")
    parser.add_argument("--input", default="input", help="Path to input directory")
    parser.add_argument("--output", default="output", help="Path to output directory")
    parser.add_argument("--mappings", default="mappings", help="Path to mappings directory")
    args = parser.parse_args()

    if args.scan:
        labs = scan_input_directory(args.input)
        print(f"Scan complete: Found {len(labs)} lab folders in '{args.input}'.")
        for lab in labs:
            status = "READY" if (lab["docx_files"] and lab["screenshot_count"] > 0) else "PENDING"
            print(f" - {lab['lab_folder']}: {len(lab['docx_files'])} docx, {lab['screenshot_count']} images [{status}]")
    else:
        run_pipeline(args.input, args.output, args.mappings)


if __name__ == "__main__":
    main()
