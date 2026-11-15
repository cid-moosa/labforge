#!/usr/bin/env python3
"""
scripts/inspect_record.py
Project Sanjaya: Read-Only Inspector & Screenshot Cataloger for Lab Records.

Scans input/ for lab folders, extracts non-empty paragraph indices/styles/text
from .docx templates without modifying source files, and catalogs all screenshots
with their exact pixel dimensions (width_px, height_px) and aspect ratios.
"""

import argparse
import json
import os
import re
import sys
from typing import List, Dict, Any, Optional

try:
    from docx import Document
    from PIL import Image
except ImportError as e:
    sys.exit(f"Error: Missing required dependency ({e}). Run: uv pip install python-docx Pillow")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}


def scan_input_directory(input_dir: str = "input") -> List[Dict[str, Any]]:
    """Discovers all lab folders and documents inside input/."""
    if not os.path.exists(input_dir):
        return []

    labs = []
    for item in os.listdir(input_dir):
        item_path = os.path.join(input_dir, item)
        if os.path.isdir(item_path):
            docx_files = []
            image_files = []
            for root, _, files in os.walk(item_path):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, os.getcwd()).replace("\\", "/")
                    if ext == ".docx" and not f.startswith("~$"):
                        docx_files.append(rel_p)
                    elif ext in IMAGE_EXTENSIONS:
                        image_files.append(rel_p)

            labs.append({
                "lab_folder": item,
                "folder_path": item_path.replace("\\", "/"),
                "docx_files": docx_files,
                "screenshot_count": len(image_files),
                "screenshots": image_files
            })

    return labs


def inspect_screenshots(image_paths: List[str]) -> List[Dict[str, Any]]:
    """Catalogs screenshots with their pixel dimensions and aspect ratios."""
    catalog = []
    # Natural sort
    def natural_sort_key(s):
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

    sorted_paths = sorted(image_paths, key=natural_sort_key)

    for p in sorted_paths:
        if not os.path.isfile(p):
            continue
        try:
            with Image.open(p) as img:
                w_px, h_px = img.size
                aspect = round(w_px / h_px, 2)
                if aspect >= 1.45:
                    classification = "widescreen"
                else:
                    classification = "dialog_box"

                catalog.append({
                    "filename": os.path.basename(p),
                    "path": p.replace("\\", "/"),
                    "width_px": w_px,
                    "height_px": h_px,
                    "aspect_ratio": aspect,
                    "classification": classification,
                    "size_kb": round(os.path.getsize(p) / 1024, 1)
                })
        except Exception as e:
            catalog.append({
                "filename": os.path.basename(p),
                "path": p.replace("\\", "/"),
                "error": str(e)
            })

    return catalog


def inspect_document(docx_path: str, include_empty: bool = False) -> List[Dict[str, Any]]:
    """Extracts non-empty paragraph indices, styles, and text from .docx."""
    if not os.path.exists(docx_path):
        raise FileNotFoundError(f"Input document not found: {docx_path}")

    doc = Document(docx_path)
    records = []

    for idx, p in enumerate(doc.paragraphs):
        raw_text = p.text
        stripped_text = raw_text.strip()

        if not include_empty and not stripped_text:
            continue

        style_name = p.style.name if p.style else "Normal"
        txt_u = stripped_text.upper()

        # Categorize structural role for helper context
        category = "body"
        if any(txt_u.startswith(kw) for kw in ("PRACTICAL:", "AIM:", "TOOLS USED:", "FTK IMAGER", "FORENSIC IMAGE")):
            category = "heading"
        elif re.match(r"^(\d+[\.\)]|[a-d][\.\)])\s+", stripped_text):
            category = "procedure_step"
        elif "QUICK REFERENCE" in txt_u or "STEPS – QUICK" in txt_u or "STEPS - QUICK" in txt_u:
            category = "quick_reference"
        elif "OUTPUT" in txt_u:
            category = "output_heading"

        records.append({
            "paragraph_index": idx,
            "style": style_name,
            "category": category,
            "text": stripped_text,
            "char_count": len(stripped_text)
        })

    return records


def main():
    parser = argparse.ArgumentParser(
        description="Project Sanjaya: Inspect .docx record paragraphs and catalog lab screenshots."
    )
    parser.add_argument(
        "--docx",
        help="Path to the input .docx file (read-only)."
    )
    parser.add_argument(
        "--dir",
        help="Path to a specific lab folder inside input/ (e.g. input/ftk)."
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan input/ directory for all available lab folders."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON to standard output."
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional path to write the inspected paragraphs & screenshots JSON."
    )
    parser.add_argument(
        "--include-empty",
        action="store_true",
        help="Include blank/whitespace-only paragraphs."
    )

    args = parser.parse_args()

    # 1. Scan mode
    if args.scan or (not args.docx and not args.dir):
        labs = scan_input_directory("input")
        if args.json:
            print(json.dumps({"labs": labs}, indent=2, ensure_ascii=False))
        else:
            print("=== Project Sanjaya: Input Directory Scan ===")
            print(f"Total lab folders found in input/: {len(labs)}\n")
            for lab in labs:
                print(f"• Folder: {lab['lab_folder']}")
                print(f"  Docs: {', '.join(lab['docx_files']) if lab['docx_files'] else 'None'}")
                print(f"  Screenshots: {lab['screenshot_count']} images found")
            print("=" * 60)
        return

    # 2. Folder mode: resolve docx and screenshots
    docx_file = args.docx
    screenshots = []

    if args.dir:
        if not os.path.exists(args.dir):
            sys.exit(f"Directory not found: {args.dir}")
        # Find docx if not explicitly specified
        if not docx_file:
            for root, _, files in os.walk(args.dir):
                for f in files:
                    if f.lower().endswith(".docx") and not f.startswith("~$"):
                        docx_file = os.path.join(root, f)
                        break
                if docx_file:
                    break

        # Find screenshots
        for root, _, files in os.walk(args.dir):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in IMAGE_EXTENSIONS:
                    screenshots.append(os.path.join(root, f))
    elif docx_file:
        # Search sibling/nested directories for screenshots
        parent_dir = os.path.dirname(os.path.abspath(docx_file))
        for root, _, files in os.walk(parent_dir):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in IMAGE_EXTENSIONS:
                    screenshots.append(os.path.join(root, f))

    if not docx_file or not os.path.exists(docx_file):
        sys.exit(f"Error: Could not locate a valid .docx file to inspect.")

    try:
        paragraphs = inspect_document(docx_file, include_empty=args.include_empty)
        catalog = inspect_screenshots(screenshots)
    except Exception as e:
        sys.exit(f"Inspection error: {e}")

    result = {
        "document": {
            "path": docx_file.replace("\\", "/"),
            "total_non_empty_paragraphs": len(paragraphs),
            "paragraphs": paragraphs
        },
        "screenshots": {
            "total_found": len(catalog),
            "catalog": catalog
        }
    }

    if args.out:
        out_dir = os.path.dirname(os.path.abspath(args.out))
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"=== Project Sanjaya: Document Inspection ({os.path.basename(docx_file)}) ===")
        print(f"Total non-empty paragraphs: {len(paragraphs)}")
        print(f"Total screenshots cataloged: {len(catalog)}\n")

        print(f"{'Index':<8} | {'Category':<16} | {'Content'}")
        print("-" * 80)
        for item in paragraphs:
            preview = item["text"].replace("\n", " ")
            if len(preview) > 55:
                preview = preview[:52] + "..."
            print(f"[{item['paragraph_index']:>4}]   | {item['category']:<16} | {preview}")
        print("-" * 80)

        if catalog:
            print("\n=== Screenshot Catalog (Pixel Dimensions & Aspect Ratio) ===")
            print(f"{'Filename':<20} | {'Dimensions':<14} | {'Aspect':<8} | {'Type'}")
            print("-" * 60)
            for img in catalog:
                dims = f"{img.get('width_px', 0)}x{img.get('height_px', 0)}"
                print(f"{img['filename']:<20} | {dims:<14} | {img.get('aspect_ratio', 0):<8} | {img.get('classification', 'unknown')}")
            print("-" * 60)

        if args.out:
            print(f"\nExported inspection and catalog JSON to: {args.out}")


if __name__ == "__main__":
    main()
