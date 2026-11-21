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


def generate_index_document(output_docx: str, output_pdf: str, student_name: str = "", reg_no: str = ""):
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

    # Title: Clean centered INDEX (Teacher standard)
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(36)
    title_p.paragraph_format.space_after = Pt(28)
    run_title = title_p.add_run("INDEX")
    run_title.font.name = "Calibri"
    run_title.font.size = Pt(16)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

    # Teacher standard 7-row index table with 2026 dates synced
    practicals = [
        ("1.", "05-08-2026", "Exterro FTK Imager", "4-11"),
        ("2.", "02-09-2026", "Autopsy", "12-19"),
        ("3.", "16-09-2026", "RegRipper", "20-23"),
        ("4.", "23-09-2026", "Guymager", "24-28"),
        ("5.", "07-10-2026", "Steghide", "29-35"),
        ("6.", "28-10-2026", "Foremost", "36-38"),
        ("7.", "28-10-2026", "Scalpel", "39-42"),
    ]

    col_widths = [Inches(0.8), Inches(1.3), Inches(3.12), Inches(1.3)]
    headers = ["SL No.", "DATE", "NAME OF EXPERIMENT", "PAGE NO"]

    table = doc.add_table(rows=len(practicals) + 1, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    # Format Header Row
    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].width = col_widths[i]
        set_cell_margins(hdr_cells[i], top=140, bottom=140, left=100, right=100)
        border_spec = {
            'top': {'val': 'single', 'sz': 8, 'color': '000000'},
            'bottom': {'val': 'single', 'sz': 8, 'color': '000000'},
            'left': {'val': 'single', 'sz': 8, 'color': '000000'},
            'right': {'val': 'single', 'sz': 8, 'color': '000000'},
        }
        set_cell_border(hdr_cells[i], **border_spec)

        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(title)
        run.font.name = "Calibri"
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

    # Format Data Rows
    for r_idx, row_data in enumerate(practicals):
        row_cells = table.rows[r_idx + 1].cells
        for c_idx, text in enumerate(row_data):
            row_cells[c_idx].width = col_widths[c_idx]
            row_cells[c_idx].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(row_cells[c_idx], top=130, bottom=130, left=100, right=100)
            
            border_spec = {
                'top': {'val': 'single', 'sz': 4, 'color': '000000'},
                'bottom': {'val': 'single', 'sz': 8 if r_idx == len(practicals)-1 else 4, 'color': '000000'},
                'left': {'val': 'single', 'sz': 8, 'color': '000000'},
                'right': {'val': 'single', 'sz': 8, 'color': '000000'},
            }
            set_cell_border(row_cells[c_idx], **border_spec)

            p = row_cells[c_idx].paragraphs[0]
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER

            run = p.add_run(text)
            run.font.name = "Calibri"
            run.font.size = Pt(11)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

    # Save initial docx
    os.makedirs(os.path.dirname(output_docx), exist_ok=True)
    doc.save(output_docx)
    print(f"Generated initial DOCX: {output_docx}")

    # Inject standard college headers & footers
    temp_copy, _ = ensure_college_headers_and_footers(output_docx)
    if temp_copy and os.path.exists(temp_copy) and temp_copy != output_docx:
        import shutil
        shutil.copyfile(temp_copy, output_docx)

    # Apply header shape width fix, single-line footer fixes, and set start page number = 3
    doc_final = docx.Document(output_docx)
    fix_header_and_footer(doc_final)

    sectPr = doc_final.sections[0]._sectPr
    for pnt in sectPr.findall(f".//{{{W_NS}}}pgNumType"):
        sectPr.remove(pnt)
    pgNumType = parse_xml(f'<w:pgNumType xmlns:w="{W_NS}" w:start="3"/>')
    sectPr.append(pgNumType)

    doc_final.save(output_docx)

    # Convert to PDF
    print(f"Exporting PDF: {output_pdf}")
    convert_docx_to_pdf(output_docx, output_pdf)
    print(f"Index creation complete: {output_docx} & {output_pdf}")


if __name__ == "__main__":
    out_dir = os.path.join(PROJECT_ROOT, "output", "index")
    os.makedirs(out_dir, exist_ok=True)

    docx_path = os.path.join(out_dir, "IDFT Lab Record Index - Final.docx")
    pdf_path = os.path.join(out_dir, "IDFT Lab Record Index - Final.pdf")

    generate_index_document(docx_path, pdf_path)
