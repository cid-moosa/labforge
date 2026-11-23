#!/usr/bin/env python3
"""
scripts/verify_master.py
Project LabForge: Master Lab Record QA & Teacher Compliance Auditor.

Audits consolidated Master Lab Record PDFs against all 7 teacher requirement categories:
1. Exactly 6 practicals, 9 TOC entries, Foremost & Scalpel combined in Practical 6 (no Practical 7).
2. Visible 0.5pt outer page border on Page 2 (Certificate) and all content pages.
3. Index table (Page 3) 4 columns: ["SI No.", "Date", "Name of the Tool", "Page Number"] (rejecting "Name of the Experiment").
4. 6 practical dates (05-08-2026, 02-09-2026, 16-09-2026, 23-09-2026, 07-10-2026, 28-10-2026) in Index table and stamped on practical start pages.
5. Subject title: "Introduction to Digital Forensics and Tools" across headers (pages 3-42) and PDF document metadata (title and subject).
6. Academic batch year: "2026 – 2030" on certificate, "2026-30" or "2026‑30" in footers, 0 occurrences of "2025".
7. Complete footers: "GIAL Vadavathoor" on every content page on a single line unbroken.
8. Continuous sequential page numbering ("3 | Page" to "42 | Page").
"""

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:
    try:
        import pymupdf as fitz
    except ImportError:
        sys.exit("Error: 'pymupdf' is not installed in this environment. Run: uv pip install pymupdf")


OFFICIAL_DATES = {
    4: "05-08-2026",
    12: "02-09-2026",
    20: "16-09-2026",
    24: "23-09-2026",
    29: "07-10-2026",
    36: "28-10-2026",
}

EXPECTED_PRACTICALS = [
    ("Practical 1", "FTK Imager", "05-08-2026", 4),
    ("Practical 2", "Autopsy", "02-09-2026", 12),
    ("Practical 3", "RegRipper", "16-09-2026", 20),
    ("Practical 4", "Guymager", "23-09-2026", 24),
    ("Practical 5", "Steghide", "07-10-2026", 29),
    ("Practical 6", "File Carving", "28-10-2026", 36),
]


def check_page_has_border(page: fitz.Page) -> bool:
    """
    Checks if a page has a visible outer page border.
    Requires either a full bounding rectangle (width > 500 and height > 700)
    or all 4 boundary strokes (top, bottom, left, right).
    """
    has_top = False
    has_bottom = False
    has_left = False
    has_right = False
    for d in page.get_drawings():
        r = d.get("rect")
        if not r:
            continue
        if r.width > 500 and r.height > 700:
            return True
        if r.width > 500 and r.y0 < 35:
            has_top = True
        if r.width > 500 and r.y1 > 800:
            has_bottom = True
        if r.height > 700 and r.x0 < 35:
            has_left = True
        if r.height > 700 and r.x1 > 550:
            has_right = True
    return bool(has_top and has_bottom and has_left and has_right)


def extract_header_footer_text(page: fitz.Page) -> Tuple[str, str]:
    """
    Extracts header and footer text using spatial bounding boxes matching verify_pdf.py:
    - header_text: text from blocks where b[3] <= 95 (or b[1] <= 95)
    - footer_text: text from blocks where b[1] >= (page.rect.height - 90)
    """
    page_height = page.rect.height
    header_text = ""
    footer_text = ""
    for b in page.get_text("blocks"):
        y0 = b[1]
        y1 = b[3]
        text_s = b[4].strip()
        if not text_s:
            continue
        if y1 <= 95:
            header_text += " " + text_s
        elif y0 >= (page_height - 90):
            footer_text += " " + text_s
    return header_text, footer_text


def audit_master_pdf(pdf_path: str) -> Dict[str, Any]:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    issues: List[str] = []
    checks: Dict[str, Dict[str, Any]] = {}

    # Check 1: Exactly 42 pages
    p_count_pass = (total_pages == 42)
    if not p_count_pass:
        issues.append(f"Total pages: found {total_pages}, expected exactly 42.")
    checks["total_pages"] = {
        "passed": p_count_pass,
        "total_pages": total_pages,
        "expected": 42,
    }

    # Check 2: Table of Contents & Practicals (Exactly 6 practicals, 9 TOC entries, no Practical 7)
    toc = doc.get_toc()
    toc_count = len(toc)
    toc_titles = [entry[1] for entry in toc] if toc else []
    
    # Check for prohibited Practical 7 in TOC and full text
    p7_found = False
    for title in toc_titles:
        if re.search(r"practical\s*[:\-]?\s*7\b", title, re.IGNORECASE):
            p7_found = True
            issues.append(f"Prohibited 'Practical 7' found in TOC: '{title}'")

    for p_idx in range(total_pages):
        p_text = doc[p_idx].get_text()
        if re.search(r"\bpractical\s*[:\-]?\s*7\b", p_text, re.IGNORECASE):
            p7_found = True
            issues.append(f"Prohibited 'Practical 7' found in text on Page {p_idx + 1}")

    # Check Foremost & Scalpel combined under Practical 6
    p6_combined = any(
        ("practical 6" in t.lower() and "file carving" in t.lower() and "foremost" in t.lower() and "scalpel" in t.lower())
        for t in toc_titles
    )
    if not p6_combined:
        issues.append("Practical 6 does not properly combine Foremost and Scalpel in TOC.")

    toc_passed = (toc_count == 9 and not p7_found and p6_combined)
    checks["practicals_and_toc"] = {
        "passed": toc_passed,
        "toc_count": toc_count,
        "expected_toc_count": 9,
        "p7_found": p7_found,
        "p6_combined": p6_combined,
        "toc_entries": toc_titles,
    }

    # Check 3: Page Borders (Page 2 Certificate + Universal all 42 pages)
    missing_borders: List[int] = []
    for p_idx in range(total_pages):
        page_num = p_idx + 1
        if not check_page_has_border(doc[p_idx]):
            missing_borders.append(page_num)

    cert_border_pass = (2 not in missing_borders)
    all_borders_pass = (len(missing_borders) == 0)
    if not cert_border_pass:
        issues.append("Page 2 (Certificate) is missing outer page border.")
    if missing_borders:
        issues.append(f"Pages missing page border: {missing_borders}")

    checks["page_borders"] = {
        "passed": all_borders_pass,
        "cert_border_passed": cert_border_pass,
        "missing_border_pages": missing_borders,
    }

    # Check 4: Index Table Format (Page 3)
    p3_text = doc[2].get_text() if total_pages >= 3 else ""
    col_name_of_tool = "Name of the Tool" in p3_text
    col_experiment_rejected = "Name of the Experiment" not in p3_text
    has_si_no = "SI No." in p3_text or "Sl. No." in p3_text or "SI No" in p3_text
    has_date_col = "Date" in p3_text
    has_page_num_col = "Page Number" in p3_text or "Page No." in p3_text

    index_passed = (
        col_name_of_tool
        and col_experiment_rejected
        and has_si_no
        and has_date_col
        and has_page_num_col
    )
    if not col_name_of_tool:
        issues.append("Index table missing 'Name of the Tool' column header.")
    if not col_experiment_rejected:
        issues.append("Index table contains prohibited 'Name of the Experiment' column header.")

    checks["index_table_format"] = {
        "passed": index_passed,
        "has_name_of_tool": col_name_of_tool,
        "experiment_rejected": col_experiment_rejected,
        "columns_detected": {
            "si_no": has_si_no,
            "date": has_date_col,
            "name_of_the_tool": col_name_of_tool,
            "page_number": has_page_num_col,
        },
    }

    # Check 5: Practical Dates (Index table and stamped on start pages)
    index_dates_passed = True
    missing_index_dates = []
    for exp_p, tool, exp_date, start_p in EXPECTED_PRACTICALS:
        if exp_date not in p3_text:
            index_dates_passed = False
            missing_index_dates.append(f"{tool}: {exp_date}")

    stamped_dates_passed = True
    missing_stamped_dates = []
    for start_p, exp_date in OFFICIAL_DATES.items():
        if start_p <= total_pages:
            p_text = doc[start_p - 1].get_text()
            if exp_date not in p_text:
                stamped_dates_passed = False
                missing_stamped_dates.append(f"Page {start_p}: expected {exp_date}")
        else:
            stamped_dates_passed = False
            missing_stamped_dates.append(f"Page {start_p} does not exist")

    dates_passed = (index_dates_passed and stamped_dates_passed)
    if not index_dates_passed:
        issues.append(f"Index table missing dates: {missing_index_dates}")
    if not stamped_dates_passed:
        issues.append(f"Practical start pages missing dates: {missing_stamped_dates}")

    checks["practical_dates"] = {
        "passed": dates_passed,
        "index_dates_passed": index_dates_passed,
        "missing_index_dates": missing_index_dates,
        "stamped_dates_passed": stamped_dates_passed,
        "missing_stamped_dates": missing_stamped_dates,
    }

    # Check 6: Subject Title Across Headers and Metadata
    header_title_issues = []
    for p_idx in range(2, total_pages):
        page_num = p_idx + 1
        page = doc[p_idx]
        header_text, _ = extract_header_footer_text(page)
        if "Introduction to Digital Forensics and Tools" not in header_text:
            header_title_issues.append(f"Page {page_num}: header missing 'Introduction to Digital Forensics and Tools'")

    meta = doc.metadata or {}
    meta_title = (meta.get("title") or "").strip()
    meta_subject = (meta.get("subject") or "").strip()
    meta_title_pass = ("Introduction to Digital Forensics and Tools" in meta_title)
    meta_subject_pass = ("Introduction to Digital Forensics and Tools" in meta_subject)
    
    if not meta_title_pass:
        issues.append(f"Document metadata 'title' is '{meta_title}', expected 'Introduction to Digital Forensics and Tools'")
    if not meta_subject_pass:
        issues.append(f"Document metadata 'subject' is '{meta_subject}', expected 'Introduction to Digital Forensics and Tools'")
    if header_title_issues:
        issues.extend(header_title_issues)

    subject_passed = (len(header_title_issues) == 0 and meta_title_pass and meta_subject_pass)
    checks["subject_title_and_metadata"] = {
        "passed": subject_passed,
        "header_passed": len(header_title_issues) == 0,
        "header_issues": header_title_issues,
        "metadata_title": meta_title,
        "metadata_subject": meta_subject,
        "metadata_title_passed": meta_title_pass,
        "metadata_subject_passed": meta_subject_pass,
    }

    # Check 7: Academic Batch Year (2026–2030, no 2025)
    p2_text = doc[1].get_text() if total_pages >= 2 else ""
    cert_year_pass = bool(re.search(r"2026\s*[\u2013\u2014\-]\s*2030", p2_text))
    if not cert_year_pass:
        issues.append("Page 2 (Certificate) missing batch year '2026 – 2030'.")

    # Check 0 occurrences of 2025 anywhere in document
    found_2025_pages = []
    for p_idx in range(total_pages):
        if "2025" in doc[p_idx].get_text():
            found_2025_pages.append(p_idx + 1)
    if found_2025_pages:
        issues.append(f"Prohibited obsolete year '2025' found on pages: {found_2025_pages}")

    # Check footer year 2026-30 on pages 3-42
    missing_footer_year = []
    wrapped_footer_year = []
    for p_idx in range(2, total_pages):
        page_num = p_idx + 1
        page = doc[p_idx]
        _, footer_text = extract_header_footer_text(page)
        if not re.search(r"2026[\-‑]30", footer_text):
            missing_footer_year.append(page_num)
        if re.search(r"2026[\-‑]\s*\n\s*30", footer_text):
            wrapped_footer_year.append(page_num)

    if missing_footer_year:
        issues.append(f"Pages missing '2026-30' in footer: {missing_footer_year}")
    if wrapped_footer_year:
        issues.append(f"Pages with wrapped '2026-30' in footer: {wrapped_footer_year}")

    batch_year_passed = (
        cert_year_pass
        and len(found_2025_pages) == 0
        and len(missing_footer_year) == 0
        and len(wrapped_footer_year) == 0
    )
    checks["academic_batch_year"] = {
        "passed": batch_year_passed,
        "cert_year_passed": cert_year_pass,
        "found_2025_pages": found_2025_pages,
        "missing_footer_year_pages": missing_footer_year,
        "wrapped_footer_year_pages": wrapped_footer_year,
    }

    # Check 8: Complete Footers (GIAL Vadavathoor on pages 3-42 unbroken)
    missing_gial = []
    wrapped_gial = []
    for p_idx in range(2, total_pages):
        page_num = p_idx + 1
        page = doc[p_idx]
        _, footer_text = extract_header_footer_text(page)
        if "GIAL Vadavathoor" not in footer_text:
            missing_gial.append(page_num)
        if re.search(r"GIAL\s*\n\s*Vadavathoor", footer_text):
            wrapped_gial.append(page_num)

    if missing_gial:
        issues.append(f"Pages missing 'GIAL Vadavathoor' in footer: {missing_gial}")
    if wrapped_gial:
        issues.append(f"Pages with wrapped 'GIAL Vadavathoor' in footer: {wrapped_gial}")

    footers_passed = (len(missing_gial) == 0 and len(wrapped_gial) == 0)
    checks["complete_footers"] = {
        "passed": footers_passed,
        "missing_gial_pages": missing_gial,
        "wrapped_gial_pages": wrapped_gial,
    }

    # Check 9: Continuous Sequential Page Numbers (3 | Page to 42 | Page)
    page_num_errors = []
    for p_idx in range(2, total_pages):
        page_num = p_idx + 1
        page = doc[p_idx]
        header_text, _ = extract_header_footer_text(page)
        pattern = rf"\b{page_num}\s*\|\s*(?:P\s*a\s*g\s*e|Page)\b"
        if not re.search(pattern, header_text):
            page_num_errors.append(f"Page {page_num}: missing '{page_num} | Page' header")

    if page_num_errors:
        issues.extend(page_num_errors)

    pagination_passed = (len(page_num_errors) == 0)
    checks["sequential_pagination"] = {
        "passed": pagination_passed,
        "errors": page_num_errors,
    }

    # Check 10: Zero AI Captions & Verbatim Text Integrity (No hallucinated Figure labels)
    caption_pages = []
    for p_idx in range(3, total_pages):
        page_num = p_idx + 1
        page = doc[p_idx]
        text = page.get_text()
        if re.search(r"\bFig(?:ure)?\s*\d+\s*:", text, re.IGNORECASE):
            caption_pages.append(page_num)

    if caption_pages:
        issues.append(f"Pages with AI-generated figure captions: {caption_pages}")

    text_integrity_passed = (len(caption_pages) == 0)
    checks["zero_ai_captions"] = {
        "passed": text_integrity_passed,
        "caption_pages": caption_pages,
    }

    all_passed = (
        p_count_pass
        and toc_passed
        and all_borders_pass
        and index_passed
        and dates_passed
        and subject_passed
        and batch_year_passed
        and footers_passed
        and pagination_passed
        and text_integrity_passed
    )

    return {
        "pdf_path": pdf_path,
        "total_pages": total_pages,
        "verdict": "PASS" if all_passed else "FAIL",
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Project LabForge: Master Lab Record QA & Teacher Compliance Auditor."
    )
    parser.add_argument(
        "pdf",
        nargs="?",
        default=None,
        help="Path to the Master PDF to audit."
    )
    parser.add_argument(
        "--pdf",
        dest="pdf_opt",
        default=None,
        help="Optional named argument for Master PDF path."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON verification report."
    )

    args = parser.parse_args()
    target_pdf = args.pdf or args.pdf_opt

    if not target_pdf:
        parser.print_help()
        sys.exit(1)

    try:
        report = audit_master_pdf(target_pdf)
    except Exception as e:
        sys.exit(f"Verification error: {e}")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    print("=" * 76)
    print(" PROJECT LABFORGE: MASTER RECORD TEACHER COMPLIANCE AUDIT REPORT")
    print("=" * 76)
    print(f"Target Master PDF : {report['pdf_path']}")
    print(f"Total Pages       : {report['total_pages']} (Expected: 42)")
    print("-" * 76)

    c = report["checks"]

    # 1. Total Pages
    s1 = "[PASS]" if c["total_pages"]["passed"] else "[FAIL]"
    print(f"1. Total Page Count (42 pages)     : {s1:<7} ({c['total_pages']['total_pages']}/42)")

    # 2. Practicals & TOC
    s2 = "[PASS]" if c["practicals_and_toc"]["passed"] else "[FAIL]"
    print(f"2. 6 Practicals & 9 TOC Entries    : {s2:<7} (No P7, Foremost+Scalpel in P6)")

    # 3. Page Borders
    s3 = "[PASS]" if c["page_borders"]["passed"] else "[FAIL]"
    print(f"3. Page Borders (Cert + All Pages) : {s3:<7} (0.5pt outer border on all 42 pages)")

    # 4. Index Table Format
    s4 = "[PASS]" if c["index_table_format"]["passed"] else "[FAIL]"
    print(f"4. Index Table 4-Column Format     : {s4:<7} ('Name of the Tool', no 'Experiment')")

    # 5. Practical Dates
    s5 = "[PASS]" if c["practical_dates"]["passed"] else "[FAIL]"
    print(f"5. Official Practical Dates (6/6)  : {s5:<7} (All 6 dates in Index & stamped headers)")

    # 6. Subject Title & Metadata
    s6 = "[PASS]" if c["subject_title_and_metadata"]["passed"] else "[FAIL]"
    print(f"6. Subject Title & Metadata        : {s6:<7} ('Introduction to Digital Forensics and Tools')")

    # 7. Academic Batch Year
    s7 = "[PASS]" if c["academic_batch_year"]["passed"] else "[FAIL]"
    print(f"7. Academic Batch Year 2026–2030   : {s7:<7} (2026–2030 Cert, 2026-30 Footers, 0x 2025)")

    # 8. Complete Footers
    s8 = "[PASS]" if c["complete_footers"]["passed"] else "[FAIL]"
    print(f"8. Complete College Footers        : {s8:<7} (Single-line 'GIAL Vadavathoor' on all pages)")

    # 9. Sequential Pagination
    s9 = "[PASS]" if c["sequential_pagination"]["passed"] else "[FAIL]"
    print(f"9. Sequential Header Pagination    : {s9:<7} (Continuous 3 | Page to 42 | Page)")

    # 10. Zero AI Captions
    s10 = "[PASS]" if c.get("zero_ai_captions", {}).get("passed", True) else "[FAIL]"
    print(f"10. Zero AI Captions & Text Parity : {s10:<7} (Zero unprompted Figure labels)")

    print("-" * 76)
    print(f"OVERALL VERDICT: {report['verdict']}")
    print("=" * 76)

    if report["issues"]:
        print("\nCompliance Issues Detected:")
        for iss in report["issues"]:
            print(f"  ! {iss}")
        print()

    if report["verdict"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
