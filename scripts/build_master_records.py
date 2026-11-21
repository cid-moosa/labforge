#!/usr/bin/env python3
"""
scripts/build_master_records.py
Assembles teacher-grade consolidated Master Lab Records for B.Sc. Cyber Forensics.
Includes:
- Page 1: Official Front Cover (GIAL Department of Computer Applications & Cyber Forensics)
- Page 2: Official Certificate (GIAL Crest Logo, Bonafide declaration, Signatures)
- Page 3: Official Index Table with required columns: Sl. No., Date, Name of the Tool, Page No., Teacher's Sign
- Pages 4+: All 6 Practical records (Labs 1 to 6)
"""

import os
import sys
import shutil
import tempfile
import docx
import fitz

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from docx.oxml import parse_xml
from scripts.labforge_engine import convert_docx_to_pdf, W_NS
from scripts.generate_index import generate_index_document

REFERANCE_DOCX = os.path.join(PROJECT_ROOT, "input", "referance", "BCF Certification pages.docx")
FALLBACK_TEMPLATE_DOCX = os.path.join(PROJECT_ROOT, "templates", "college_record_cover_template.docx")
TEMPLATE_DOCX = REFERANCE_DOCX if os.path.exists(REFERANCE_DOCX) else FALLBACK_TEMPLATE_DOCX

STUDENTS = {
    "cidmoosa": {
        "display_name": os.getenv("LABFORGE_STUDENT_NAME", "ARUN P S"),
        "reg_no": os.getenv("LABFORGE_STUDENT_REGNO", "MG26101A3144"),
        "output_dir": os.path.join(PROJECT_ROOT, "output", "cidmoosa"),
    },
    "asna": {
        "display_name": "ASNA SAJI",
        "reg_no": "",
        "output_dir": os.path.join(PROJECT_ROOT, "output", "asna"),
    },
    "arjun": {
        "display_name": "ARJUN K BINOY",
        "reg_no": "",
        "output_dir": os.path.join(PROJECT_ROOT, "output", "arjun"),
    },
}

LAB_FILES = [
    ("Practical 1: Exterro FTK Imager (05-08-2026)", "IDFT Lab 1 FTK Imager.pdf"),
    ("Practical 2: Autopsy (02-09-2026)", "IDFT Lab 2 Autopsy.pdf"),
    ("Practical 3: RegRipper (16-09-2026)", "IDFT Lab 3 Rig ripper.pdf"),
    ("Practical 4: Guymager (23-09-2026)", "IDFT Lab 4 Guymager.pdf"),
    ("Practical 5: Steghide (07-10-2026)", "IDFT Lab 5 Steghide.pdf"),
    ("Practical 6: File Carving (Foremost, Scalpel) (28-10-2026)", "IDFT Lab 6 File Carving.pdf"),
]


def create_cover_and_certificate(out_pdf_path: str):
    """Generates the 2-page Cover and Certificate PDF directly from the official college template, standardizing Certificate page borders to thin single border."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        temp_docx = os.path.join(tmpdir, "cover.docx")
        temp_pdf = os.path.join(tmpdir, "cover.pdf")
        
        doc = docx.Document(TEMPLATE_DOCX)
        if len(doc.sections) > 1:
            sectPr = doc.sections[1]._sectPr
            for child in list(sectPr):
                if child.tag.endswith('pgBorders'):
                    sectPr.remove(child)
            pgBorders = parse_xml(f'''
                <w:pgBorders xmlns:w="{W_NS}" w:offsetFrom="page">
                    <w:top w:val="single" w:sz="4" w:space="24" w:color="000000"/>
                    <w:left w:val="single" w:sz="4" w:space="24" w:color="000000"/>
                    <w:bottom w:val="single" w:sz="4" w:space="24" w:color="000000"/>
                    <w:right w:val="single" w:sz="4" w:space="24" w:color="000000"/>
                </w:pgBorders>
            ''')
            sectPr.append(pgBorders)
        
        doc.save(temp_docx)
        convert_docx_to_pdf(temp_docx, temp_pdf)
        shutil.copyfile(temp_pdf, out_pdf_path)


def create_index_sheet(student_name: str, reg_no: str, out_pdf_path: str):
    """Generates the 1-page Index sheet PDF."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        temp_docx = os.path.join(tmpdir, "index.docx")
        temp_pdf = os.path.join(tmpdir, "index.pdf")
        generate_index_document(temp_docx, temp_pdf, student_name=student_name, reg_no=reg_no)
        shutil.copyfile(temp_pdf, out_pdf_path)


def assemble_master_record(student_key: str):
    """Assembles the consolidated master record PDF for a given student."""
    cfg = STUDENTS[student_key]
    out_dir = cfg["output_dir"]
    name = cfg["display_name"]
    reg = cfg["reg_no"]
    master_pdf_path = os.path.join(out_dir, "IDFT Lab Record Master.pdf")

    print(f"\n==========================================")
    print(f" Assembling Master Record: {name} (Roll/Reg No: {reg})")
    print(f"==========================================")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        cover_pdf = os.path.join(tmpdir, f"{student_key}_cover.pdf")
        index_pdf = os.path.join(tmpdir, f"{student_key}_index.pdf")

        print("-> Generating Cover & Certificate...")
        create_cover_and_certificate(cover_pdf)

        print("-> Generating Index Sheet...")
        create_index_sheet(name, reg, index_pdf)

        master_doc = fitz.open()
        toc = [
            [1, "Front Cover Page", 1],
            [1, "Certificate", 2],
            [1, "Lab Record Index", 3],
        ]

        # 1. Insert Cover & Certificate (Pages 1 & 2)
        doc_cover = fitz.open(cover_pdf)
        master_doc.insert_pdf(doc_cover)
        doc_cover.close()

        # 2. Insert Index Sheet (Page 3)
        doc_index = fitz.open(index_pdf)
        master_doc.insert_pdf(doc_index)
        doc_index.close()

        # 3. Insert all Practicals
        page_cursor = 4
        for title, filename in LAB_FILES:
            lab_path = os.path.join(out_dir, filename)
            if not os.path.exists(lab_path):
                raise FileNotFoundError(f"Missing lab PDF: {lab_path}")
            doc_lab = fitz.open(lab_path)
            if "File Carving" in filename:
                # Foremost is 3 pages (pages 36-38), Scalpel is 4 pages (pages 39-42)
                toc.append([1, "Practical 6: Foremost (28-10-2026)", page_cursor])
                toc.append([1, "Practical 7: Scalpel (28-10-2026)", page_cursor + 3])
            else:
                toc.append([1, title, page_cursor])
            master_doc.insert_pdf(doc_lab)
            page_cursor += len(doc_lab)
            doc_lab.close()

        total_pages = len(master_doc)
        total_toc = len(toc)
        master_doc.set_toc(toc)

        # 4. Stamp continuous sequential page numbers and practical dates matching date.md & Index
        practical_dates = {
            4: "05-08-2026",
            12: "02-09-2026",
            20: "16-09-2026",
            24: "23-09-2026",
            29: "07-10-2026",
            36: "28-10-2026",
            39: "28-10-2026",
        }
        for p_num in range(4, total_pages + 1):
            page = master_doc[p_num - 1]
            rect_pg = fitz.Rect(460, 32, 540, 54)
            page.add_redact_annot(rect_pg, fill=(1, 1, 1))
            if p_num == 4:
                rect_date = fitz.Rect(440, 65, 560, 88)
                page.add_redact_annot(rect_date, fill=(1, 1, 1))
            page.apply_redactions()

            pg_str = f"{p_num} | Page"
            page.insert_text(fitz.Point(475, 48), pg_str, fontname="helv", fontsize=11, color=(0, 0, 0))

            if p_num in practical_dates:
                date_str = f"Date: {practical_dates[p_num]}"
                y_pos = 80 if p_num == 4 else 75
                page.insert_text(fitz.Point(445, y_pos), date_str, fontname="times-bold", fontsize=11, color=(0, 0, 0))

            if p_num == 39:
                # Stamp centered PRACTICAL: 7 heading
                page.insert_text(fitz.Point(235, 75), "PRACTICAL: 7", fontname="times-bold", fontsize=13, color=(0, 0, 0))

        # 5. Guarantee thin single page border on every content page (Pages 2 through 42)
        for p_num in range(2, total_pages + 1):
            page = master_doc[p_num - 1]
            has_border = any(d.get('rect') and d['rect'].width > 500 for d in page.get_drawings())
            if not has_border:
                page.draw_rect(fitz.Rect(24.0, 24.0, 571.25, 817.85), color=(0, 0, 0), width=0.5)

        master_doc.save(master_pdf_path, deflate=True)
        master_doc.close()
        print(f"SUCCESS: Generated {master_pdf_path}")
        print(f"Total Pages: {total_pages}, TOC Entries: {total_toc}")


def build_all_master_records():
    for student_key in STUDENTS:
        assemble_master_record(student_key)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target == "all":
        build_all_master_records()
    elif target in STUDENTS:
        assemble_master_record(target)
    else:
        print(f"Unknown target: {target}. Choices: {list(STUDENTS.keys())} or 'all'")
        sys.exit(1)
