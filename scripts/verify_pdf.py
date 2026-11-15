#!/usr/bin/env python3
"""
scripts/verify_pdf.py
Project LabForge: QA Verification Auditor for Lab Record PDFs.

Audits generated PDFs using PyMuPDF (fitz) against the 4 critical acceptance gates:
1. Zero blank trailing page (no empty pages at the end).
2. Zero orphaned step text (no procedure step marooned at page bottom without its screenshot).
3. Sequential page numbering (1 | Page through N | Page without repeating or skipping).
4. All mapped screenshots present and accounted for across the pages.
5. Footer single-line integrity (verifies 2025-29 is not wrapped).
"""

import argparse
import json
import os
import re
import sys
from typing import List, Dict, Any, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:
    try:
        import pymupdf as fitz
    except ImportError:
        sys.exit("Error: 'pymupdf' is not installed in this environment. Run: uv pip install pymupdf")


def audit_pdf(pdf_path: str, mapping_path: str = None) -> Dict[str, Any]:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    expected_image_count = None
    if mapping_path and os.path.exists(mapping_path):
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping_data = json.load(f)
            if isinstance(mapping_data, dict):
                expected_image_count = len(mapping_data.get("images", []))
            elif isinstance(mapping_data, list):
                expected_image_count = len(mapping_data)
        except Exception as e:
            print(f"[WARNING] Could not parse mapping file: {e}")

    page_reports = []
    total_images_found = 0
    detected_page_numbers = []
    orphaned_steps = []
    footer_issues = []

    # Regex for step headings/lines
    step_pattern = re.compile(r"^\s*(\d+[\.\)]|[a-d][\.\)])\s+[A-Z]", re.IGNORECASE)

    for page_idx in range(total_pages):
        page = doc[page_idx]
        page_num = page_idx + 1
        page_rect = page.rect
        page_height = page_rect.height

        # Images on page
        images = page.get_images(full=True)
        img_count = len(images)
        total_images_found += img_count

        # Text blocks: (x0, y0, x1, y1, text, block_no, block_type)
        blocks = page.get_text("blocks")

        header_text = ""
        footer_text = ""
        body_blocks = []

        for b in blocks:
            x0, y0, x1, y1, text, b_no, b_type = b[:7]
            text_s = text.strip()
            if not text_s:
                continue

            if y1 <= 95:
                header_text += " " + text_s
            elif y0 >= (page_height - 90):
                footer_text += " " + text_s
            else:
                body_blocks.append((x0, y0, x1, y1, text_s))

        # Check header page numbering
        # Look for e.g. "1 | P a g e", "1| Page", "1 | Page"
        m_page = re.search(r"(\d+)\s*\|\s*P\s*a\s*g\s*e", header_text, re.IGNORECASE)
        if not m_page:
            m_page = re.search(r"(\d+)\s*\|\s*Page", header_text, re.IGNORECASE)
        if not m_page:
            m_page = re.search(r"Page\s*(\d+)", header_text, re.IGNORECASE)

        num_found = int(m_page.group(1)) if m_page else None
        detected_page_numbers.append(num_found)

        # Check footer wrapping
        if "2025" in footer_text:
            if re.search(r"2025[\-‑]\s*\n\s*29", footer_text):
                footer_issues.append(f"Page {page_num}: 2025-29 wrapped onto two lines.")

        # Check orphaned step:
        # If the page has body text, check the last body block
        if body_blocks and img_count == 0 and page_idx < total_pages - 1:
            last_block = body_blocks[-1]
            last_text = last_block[4].strip()
            lines = [l.strip() for l in last_text.splitlines() if l.strip()]
            if lines:
                last_line = lines[-1]
                if step_pattern.match(last_line) and last_block[3] > 650:
                    orphaned_steps.append({
                        "page": page_num,
                        "text": last_line,
                        "y1": round(last_block[3], 1)
                    })
        elif body_blocks and page_idx < total_pages - 1:
            # Page has images, check if a step line occurs below the lowest image
            # Find lowest image position
            img_infos = page.get_image_info()
            if img_infos:
                lowest_img_y1 = max(info["bbox"][3] for info in img_infos)
                # Check if there are body blocks below lowest_img_y1
                blocks_below_img = [b for b in body_blocks if b[1] > (lowest_img_y1 + 10)]
                if blocks_below_img:
                    lowest_b = blocks_below_img[-1]
                    lines = [l.strip() for l in lowest_b[4].splitlines() if l.strip()]
                    if lines and step_pattern.match(lines[-1]) and lowest_b[3] > (page_height - 120):
                        orphaned_steps.append({
                            "page": page_num,
                            "text": lines[-1],
                            "y1": round(lowest_b[3], 1)
                        })

        page_reports.append({
            "page": page_num,
            "images_count": img_count,
            "body_blocks_count": len(body_blocks),
            "header_page_num": num_found,
            "has_body_text": len(body_blocks) > 0
        })

    # Gate 1: Check Trailing Blank Page
    last_page = page_reports[-1]
    is_last_page_blank = (last_page["images_count"] == 0 and not last_page["has_body_text"])

    # Gate 2: Check Orphaned Steps
    has_orphaned_steps = len(orphaned_steps) > 0

    # Gate 3: Check Sequential Page Numbers
    is_sequential = True
    page_num_errors = []
    for idx, found_num in enumerate(detected_page_numbers):
        expected_num = idx + 1
        if found_num is None:
            is_sequential = False
            page_num_errors.append(f"Page {expected_num}: Missing page number in header.")
        elif found_num != expected_num:
            is_sequential = False
            page_num_errors.append(f"Page {expected_num}: Found '{found_num}', expected '{expected_num}'.")

    # Gate 4: Check Image Count
    images_gate_passed = True
    image_count_msg = f"{total_images_found} screenshots detected."
    if expected_image_count is not None:
        if total_images_found < expected_image_count:
            images_gate_passed = False
            image_count_msg = f"Found {total_images_found} screenshots, expected {expected_image_count} from mapping."

    # Overall Verdict
    passed = (
        not is_last_page_blank
        and not has_orphaned_steps
        and is_sequential
        and images_gate_passed
        and len(footer_issues) == 0
    )

    return {
        "pdf_path": pdf_path,
        "total_pages": total_pages,
        "total_images_found": total_images_found,
        "expected_image_count": expected_image_count,
        "verdict": "PASS" if passed else "FAIL",
        "gates": {
            "zero_trailing_blank_page": {
                "passed": not is_last_page_blank,
                "details": "Last page is empty" if is_last_page_blank else "Last page has content"
            },
            "zero_orphaned_steps": {
                "passed": not has_orphaned_steps,
                "orphaned_steps": orphaned_steps
            },
            "sequential_headers": {
                "passed": is_sequential,
                "detected": detected_page_numbers,
                "errors": page_num_errors
            },
            "all_screenshots_present": {
                "passed": images_gate_passed,
                "details": image_count_msg
            },
            "footer_single_line": {
                "passed": len(footer_issues) == 0,
                "issues": footer_issues
            }
        },
        "page_breakdown": page_reports
    }


def main():
    parser = argparse.ArgumentParser(
        description="Project LabForge: Audit lab record PDF against the 5 acceptance gates."
    )
    parser.add_argument(
        "--pdf",
        required=True,
        help="Path to the generated PDF to audit."
    )
    parser.add_argument(
        "--mapping",
        default=None,
        help="Optional path to mapping JSON to verify expected image count."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON verification report."
    )

    args = parser.parse_args()

    try:
        report = audit_pdf(args.pdf, args.mapping)
    except Exception as e:
        sys.exit(f"Verification error: {e}")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    print("=" * 70)
    print(" PROJECT LABFORGE: PDF QUALITY & ACCEPTANCE AUDIT REPORT")
    print("=" * 70)
    print(f"Target PDF     : {os.path.basename(report['pdf_path'])}")
    print(f"Total Pages    : {report['total_pages']}")
    print(f"Total Images   : {report['total_images_found']} (Expected: {report['expected_image_count'] or 'N/A'})")
    print("-" * 70)

    gates = report["gates"]

    # Gate 1
    g1 = gates["zero_trailing_blank_page"]
    status1 = "[PASS]" if g1["passed"] else "[FAIL]"
    print(f"1. Zero Trailing Blank Page  : {status1:<7} ({g1['details']})")

    # Gate 2
    g2 = gates["zero_orphaned_steps"]
    status2 = "[PASS]" if g2["passed"] else "[FAIL]"
    print(f"2. Zero Orphaned Steps       : {status2:<7} ({len(g2['orphaned_steps'])} orphaned step texts detected)")
    if not g2["passed"]:
        for o in g2["orphaned_steps"]:
            print(f"   ! Page {o['page']}: '{o['text']}' at y1={o['y1']}")

    # Gate 3
    g3 = gates["sequential_headers"]
    status3 = "[PASS]" if g3["passed"] else "[FAIL]"
    print(f"3. Sequential Page Headers   : {status3:<7} ({g3['detected']})")
    if not g3["passed"]:
        for err in g3["errors"]:
            print(f"   ! {err}")

    # Gate 4
    g4 = gates["all_screenshots_present"]
    status4 = "[PASS]" if g4["passed"] else "[FAIL]"
    print(f"4. Screenshots Accounted For : {status4:<7} ({g4['details']})")

    # Gate 5
    g5 = gates["footer_single_line"]
    status5 = "[PASS]" if g5["passed"] else "[FAIL]"
    print(f"5. Footer Single-Line Format : {status5:<7} (2025‑29 unbroken)")
    if not g5["passed"]:
        for iss in g5["issues"]:
            print(f"   ! {iss}")

    print("-" * 70)
    print(f"OVERALL VERDICT: {report['verdict']}")
    print("=" * 70)

    if report["verdict"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
