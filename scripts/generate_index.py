#!/usr/bin/env python3
"""
scripts/generate_index.py
Generates the official teacher-approved Lab Record Index document (.docx & .pdf)
for Project LabForge.
"""

import os
import sys
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.labforge_engine import ensure_college_headers_and_footers, fix_header_and_footer, convert_docx_to_pdf, W_NS


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Sets internal padding for a table cell in twips."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def set_cell_border(cell, **kwargs):
    """
    Sets cell borders. kwargs can be top, bottom, left, right.
    val: 'single', 'double', 'dashed', etc.
    sz: size in 1/8 pt (e.g. 4 = 0.5pt, 8 = 1pt)
    color: hex color like '000000' or 'CCCCCC'
    """
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = tcPr.first_child_found_in("w:tcBorders")
    if tcBorders is None:
        tcBorders = OxmlElement('w:tcBorders')
        tcPr.append(tcBorders)
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        edge_data = kwargs.get(edge)
        if edge_data:
            tag = f'w:{edge}'
            element = tcBorders.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                tcBorders.append(element)
            for key, val in edge_data.items():
                element.set(qn(f'w:{key}'), str(val))


def set_cell_shading(cell, color_hex):
    """Sets background shading of a cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    tcPr.append(shd)


def generate_index_document(output_docx: str, output_pdf: str):
    doc = docx.Document()

    # Section page setup
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.top_margin = Inches(0.90)
    section.bottom_margin = Inches(0.85)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(0.75)
    section.header_distance = Inches(0.45)
    section.footer_distance = Inches(0.40)

    # Disable contextual spacing
    for style in doc.styles:
        if hasattr(style, 'element') and style.element is not None:
            for cs in style.element.findall(f".//{{{W_NS}}}contextualSpacing"):
                parent = cs.getparent()
                if parent is not None:
                    parent.remove(cs)

    # Document Header Title
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(24)
    title_p.paragraph_format.space_after = Pt(4)
    run_sub = title_p.add_run("B.Sc. CYBER FORENSICS\n")
    run_sub.font.name = "Calibri"
    run_sub.font.size = Pt(13)
    run_sub.font.bold = True
    run_sub.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

    run_title = title_p.add_run("INTRODUCTION TO DIGITAL FORENSICS")
    run_title.font.name = "Calibri"
    run_title.font.size = Pt(15)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(0x00, 0x20, 0x60)

    # Sub-header: INDEX
    idx_p = doc.add_paragraph()
    idx_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    idx_p.paragraph_format.space_before = Pt(12)
    idx_p.paragraph_format.space_after = Pt(20)
    run_idx = idx_p.add_run("LAB RECORD INDEX")
    run_idx.font.name = "Calibri"
    run_idx.font.size = Pt(14)
    run_idx.font.bold = True
    run_idx.underline = True

    # Student Info Box (optional standard header block)
    info_table = doc.add_table(rows=1, cols=2)
    info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    info_table.autofit = False
    
    cell_l = info_table.rows[0].cells[0]
    cell_r = info_table.rows[0].cells[1]
    cell_l.width = Inches(3.5)
    cell_r.width = Inches(2.8)

    p_l = cell_l.paragraphs[0]
    p_l.paragraph_format.space_before = Pt(2)
    p_l.paragraph_format.space_after = Pt(2)
    r = p_l.add_run("Name of Student : _____________________\nReg. No. / Roll No. : _____________________")
    r.font.name = "Calibri"
    r.font.size = Pt(10.5)

    p_r = cell_r.paragraphs[0]
    p_r.paragraph_format.space_before = Pt(2)
    p_r.paragraph_format.space_after = Pt(2)
    p_r.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r2 = p_r.add_run("Academic Year : 2025–29\nSubmission Date : 27-11-2026")
    r2.font.name = "Calibri"
    r2.font.size = Pt(10.5)

    # Empty gap
    gap = doc.add_paragraph()
    gap.paragraph_format.space_before = Pt(12)
    gap.paragraph_format.space_after = Pt(0)

    # Index Table
    # Columns: SI No., Date, Name of the Tool, Page Number, Staff Signature
    practicals = [
        ("1", "05-08-2026", "FTK Imager", "1 – 8"),
        ("2", "02-09-2026", "Autopsy", "9 – 16"),
        ("3", "16-09-2026", "RegRipper", ""),
        ("4", "23-09-2026", "Guymager", "17 – 21"),
        ("5", "07-10-2026", "Steghide", ""),
        ("6", "28-10-2026", "File Carving (Foremost, Scalpel)", ""),
    ]

    col_widths = [Inches(0.7), Inches(1.2), Inches(2.9), Inches(1.0), Inches(1.2)]
    headers = ["Sl. No.", "Date", "Name of the Tool", "Page No.", "Teacher's Sign"]

    table = doc.add_table(rows=len(practicals) + 1, cols=5)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    # Format Header Row
    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].width = col_widths[i]
        set_cell_shading(hdr_cells[i], "E8EEF5")
        set_cell_margins(hdr_cells[i], top=140, bottom=140, left=120, right=120)
        border_spec = {
            'top': {'val': 'single', 'sz': 8, 'color': '000000'},
            'bottom': {'val': 'single', 'sz': 12, 'color': '000000'},
            'left': {'val': 'single', 'sz': 6, 'color': '888888'},
            'right': {'val': 'single', 'sz': 6, 'color': '888888'},
        }
        set_cell_border(hdr_cells[i], **border_spec)

        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(title)
        run.font.name = "Calibri"
        run.font.size = Pt(10.5)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x00, 0x20, 0x60)

    # Format Data Rows
    for r_idx, row_data in enumerate(practicals):
        row_cells = table.rows[r_idx + 1].cells
        # 5 cells: sl, date, tool, page, sign
        cells_data = [row_data[0], row_data[1], row_data[2], row_data[3], ""]

        for c_idx, text in enumerate(cells_data):
            row_cells[c_idx].width = col_widths[c_idx]
            row_cells[c_idx].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(row_cells[c_idx], top=120, bottom=120, left=120, right=120)
            
            border_spec = {
                'top': {'val': 'single', 'sz': 4, 'color': 'BBBBBB'},
                'bottom': {'val': 'single', 'sz': 4 if r_idx < len(practicals)-1 else 8, 'color': '000000' if r_idx == len(practicals)-1 else 'BBBBBB'},
                'left': {'val': 'single', 'sz': 6, 'color': '888888'},
                'right': {'val': 'single', 'sz': 6, 'color': '888888'},
            }
            set_cell_border(row_cells[c_idx], **border_spec)

            p = row_cells[c_idx].paragraphs[0]
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)

            # Alignment
            if c_idx in (0, 1, 3, 4):
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT

            run = p.add_run(text)
            run.font.name = "Calibri"
            run.font.size = Pt(10.5)
            if c_idx == 0:
                run.font.bold = True

    # Note / Instructions Footer Paragraph
    doc.add_paragraph().paragraph_format.space_before = Pt(24)
    note_p = doc.add_paragraph()
    note_p.paragraph_format.space_before = Pt(8)
    note_p.paragraph_format.space_after = Pt(4)
    r_imp = note_p.add_run("Important Submission Note:\n")
    r_imp.font.name = "Calibri"
    r_imp.font.size = Pt(9.5)
    r_imp.font.bold = True

    r_note = note_p.add_run(
        "• Soft copy submission deadline (PDF): 27-11-2026.\n"
        "• Get confirmation on the soft copy PDF before proceeding with hard copy spiral binding.\n"
        "• All practical experiments must be signed by the faculty-in-charge upon verification."
    )
    r_note.font.name = "Calibri"
    r_note.font.size = Pt(9.5)
    r_note.font.italic = True
    r_note.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    # Save initial docx
    os.makedirs(os.path.dirname(output_docx), exist_ok=True)
    doc.save(output_docx)
    print(f"Generated initial DOCX: {output_docx}")

    # Inject standard college headers & footers
    temp_copy, _ = ensure_college_headers_and_footers(output_docx)
    if temp_copy and os.path.exists(temp_copy) and temp_copy != output_docx:
        import shutil
        shutil.copyfile(temp_copy, output_docx)

    # Apply header shape width fix & single-line footer fixes
    doc_final = docx.Document(output_docx)
    fix_header_and_footer(doc_final)
    doc_final.save(output_docx)

    # Convert to PDF
    print(f"Exporting PDF: {output_pdf}")
    convert_docx_to_pdf(output_docx, output_pdf)
    print(f"Index creation complete: {output_docx} & {output_pdf}")


if __name__ == "__main__":
    out_dir = os.path.join(PROJECT_ROOT, "output", "index")
    out_pdf_dir = os.path.join(out_dir, "final")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(out_pdf_dir, exist_ok=True)

    docx_path = os.path.join(out_dir, "IDFT Lab Record Index - Final.docx")
    pdf_path = os.path.join(out_pdf_dir, "IDFT Lab Record Index - Final.pdf")

    generate_index_document(docx_path, pdf_path)
