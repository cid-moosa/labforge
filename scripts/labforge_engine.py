#!/usr/bin/env python3
"""
scripts/labforge_engine.py
Project LabForge: Autonomous OOXML Alignment & PDF Generation Engine.

Applies all 7 mandatory teacher-grade OOXML rules:
1. Strips <w:numPr> / <w:tabs> and sets clean left-aligned hanging indentation (0.3" main steps, 0.6" sub-bullets).
2. Removes <w:contextualSpacing/> and enforces explicit spacing (Pt(16) before, Pt(12) after on steps; Pt(12) before, Pt(24) after on screenshots).
3. Resets screenshots to 'Normal' style, centered, zeroed horizontal indents, stripping inherited list properties.
4. Glues step text to screenshot with keep_with_next=True and keep_together=True; cleans blank spacer paragraphs.
5. Injects multi-bullet step screenshots after the final sub-bullet (e.g. after 'd. AFF').
6. 1px black border in memory + aspect-ratio bounding boxes (5.80x2.65" Step 1, 5.80x3.00" Step 2, 4.80x2.60" dialogs, 4.80x2.00" OUTPUT).
7. Unified dynamic headers (1| Page through N| Page), single-line 2025‑29 footers, zero trailing blank pages, and automatic LibreOffice PDF export.
"""

import argparse
import copy
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional

try:
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import parse_xml
    from PIL import Image, ImageOps
    from lxml import etree
except ImportError as e:
    sys.exit(f"Error: Missing required dependency ({e}). Run: uv pip install python-docx Pillow lxml")

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
LIBREOFFICE_PATHS = [
    r"C:\Program Files\LibreOffice\program\soffice.com",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.com",
    "soffice",
    "libreoffice"
]


def resolve_image_path(raw_path: str, base_dirs: List[str]) -> str:
    """Finds image file checking raw path and relative base directories."""
    candidates = [raw_path]
    for b in base_dirs:
        if b:
            candidates.append(os.path.join(b, raw_path))

    for cand in candidates:
        norm = os.path.normpath(cand)
        if os.path.isfile(norm):
            return norm

    clean_raw = raw_path.replace("\\", "/").strip("/")
    parts = clean_raw.split("/")
    filename = parts[-1]

    for b in base_dirs:
        if not b or not os.path.isdir(b):
            continue
        for root, _, files in os.walk(b):
            for f in files:
                if f.lower() == filename.lower():
                    return os.path.normpath(os.path.join(root, f))

    raise FileNotFoundError(f"Cannot resolve image file: {raw_path}")


def calculate_image_dimensions(
    w_px: int,
    h_px: int,
    max_width_inches: float = 4.80,
    max_height_inches: float = 2.60
) -> Tuple[float, float]:
    """Scales image inside bounding box while strictly preserving aspect ratio."""
    target_w = max_width_inches
    target_h = target_w * (h_px / w_px)

    if target_h > max_height_inches:
        target_h = max_height_inches
        target_w = target_h * (w_px / h_px)

    return target_w, target_h


def fix_header_and_footer(doc: Document):
    """
    Standardizes margins and preserves original header/footer XML architecture:
    - Sets left_margin = 1.0 in, right_margin = 0.75 in.
    - Sets unified headers/footers across entire document.
    - Connects default header/footer references to real content if default was empty.
    - Wraps header page numbers dynamically in Word <w:fldSimple w:instr="PAGE">.
    - Widens footer 2025-29 textbox and ensures non-breaking single line.
    """
    for section in doc.sections:
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(0.75)
        section.top_margin = Inches(0.90)
        section.bottom_margin = Inches(0.85)
        section.header_distance = Inches(0.45)
        section.footer_distance = Inches(0.40)
        section.odd_and_even_pages_header_footer = False
        section.different_first_page_header_footer = False

        # Ensure default header/footer reference points to content if default is empty
        headers = {h.attrib.get(f"{{{W_NS}}}type"): h for h in section._sectPr.findall(f"{{{W_NS}}}headerReference")}
        if "default" in headers and "even" in headers:
            def_rel_id = headers["default"].attrib.get(f"{{{R_NS}}}id")
            even_rel_id = headers["even"].attrib.get(f"{{{R_NS}}}id")
            if def_rel_id in doc.part.rels and even_rel_id in doc.part.rels:
                def_part = doc.part.rels[def_rel_id].target_part
                even_part = doc.part.rels[even_rel_id].target_part
                def_text = "".join([t.text for t in def_part._element.findall(f".//{{{W_NS}}}t") if t.text]).strip()
                even_text = "".join([t.text for t in even_part._element.findall(f".//{{{W_NS}}}t") if t.text]).strip()
                if not def_text and even_text:
                    headers["default"].attrib[f"{{{R_NS}}}id"] = even_rel_id

        footers = {f.attrib.get(f"{{{W_NS}}}type"): f for f in section._sectPr.findall(f"{{{W_NS}}}footerReference")}
        if "default" in footers and "even" in footers:
            def_rel_id = footers["default"].attrib.get(f"{{{R_NS}}}id")
            even_rel_id = footers["even"].attrib.get(f"{{{R_NS}}}id")
            if def_rel_id in doc.part.rels and even_rel_id in doc.part.rels:
                def_part = doc.part.rels[def_rel_id].target_part
                even_part = doc.part.rels[even_rel_id].target_part
                def_text = "".join([t.text for t in def_part._element.findall(f".//{{{W_NS}}}t") if t.text]).strip()
                even_text = "".join([t.text for t in even_part._element.findall(f".//{{{W_NS}}}t") if t.text]).strip()
                if not def_text and even_text:
                    footers["default"].attrib[f"{{{R_NS}}}id"] = even_rel_id

        # Zero right indent on footer paragraphs
        for ftr in [section.footer, section.even_page_footer]:
            if ftr is not None:
                for p in ftr.paragraphs:
                    p.paragraph_format.right_indent = Pt(0)

    # 1. Dynamic PAGE field in headers
    for part in doc.part.related_parts.values():
        if "header" in part.partname:
            root = part._element
            for p in root.findall(f".//{{{W_NS}}}p"):
                runs = list(p.findall(f"{{{W_NS}}}r"))
                pipe_run_idx = -1
                for idx, r in enumerate(runs):
                    t = r.find(f"{{{W_NS}}}t")
                    if t is not None and t.text and "|" in t.text:
                        pipe_run_idx = idx
                        break

                if pipe_run_idx != -1:
                    # Check if paragraph already has an existing dynamic PAGE field
                    instr = p.find(f".//{{{W_NS}}}instrText")
                    has_page_instr = (instr is not None and "PAGE" in (instr.text or "").upper())

                    # Find runs before pipe that contain digits
                    digit_runs = []
                    for idx in range(pipe_run_idx):
                        r = runs[idx]
                        t = r.find(f"{{{W_NS}}}t")
                        if t is not None and t.text and re.search(r"\d", t.text):
                            digit_runs.append((idx, r))

                    if has_page_instr:
                        # Existing dynamic PAGE field present; remove rogue hardcoded prefix runs (e.g. '3')
                        for _, r in digit_runs:
                            # Only remove run if it is outside/before the fldChar
                            if r.find(f"{{{W_NS}}}fldChar") is None:
                                p.remove(r)
                    elif digit_runs:
                        first_idx, first_r = digit_runs[0]
                        # Remove other digit runs
                        for _, r in digit_runs[1:]:
                            p.remove(r)
                        r_idx = list(p).index(first_r)
                        p.remove(first_r)
                        fld = etree.Element(f"{{{W_NS}}}fldSimple")
                        fld.set(f"{{{W_NS}}}instr", "PAGE")
                        new_r = etree.Element(f"{{{W_NS}}}r")
                        new_t = etree.Element(f"{{{W_NS}}}t")
                        new_t.text = "1"
                        new_r.append(new_t)
                        fld.append(new_r)
                        p.insert(r_idx, fld)

    # 2. Fix 2025-29 single line in footers
    for part in doc.part.related_parts.values():
        if "footer" in part.partname:
            root = part._element

            # Clean text runs
            for p in root.findall(f".//{{{W_NS}}}p"):
                t_nodes = p.findall(f".//{{{W_NS}}}t")
                for t in t_nodes:
                    if t.text:
                        if "GIAL" in t.text and "29" in t.text:
                            t.text = t.text.replace(" 29", "")
                        elif "2025" in t.text:
                            t.text = "2025\u201129"
                        elif t.text.strip() == "29":
                            t.text = ""

            # Expand width of 2025-29 textbox in VML
            for shape in root.findall(".//{urn:schemas-microsoft-com:vml}shape"):
                style = shape.attrib.get("style", "")
                if "506" in style or "495" in style or "width:27" in style or "width:38" in style:
                    new_style = re.sub(r"width:[^;]+", "width:55pt", style)
                    new_style = re.sub(r"margin-left:[^;]+", "margin-left:485pt", new_style)
                    shape.attrib["style"] = new_style

            # Expand width of modern wp:anchor
            for a in root.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}anchor"):
                posH = a.find("{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}positionH")
                if posH is not None:
                    offset = posH.find("{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}posOffset")
                    if offset is not None and int(offset.text or 0) > 5500000:
                        offset.text = str(int(485 * 12700))
                        extent = a.find("{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent")
                        if extent is not None:
                            extent.set("cx", str(int(55 * 12700)))
                        for ext in a.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}ext"):
                            ext.set("cx", str(int(55 * 12700)))


def convert_docx_to_pdf(docx_path: str, output_pdf_path: str):
    """Converts a .docx document to .pdf via headless LibreOffice."""
    soffice_bin = None
    for cand in LIBREOFFICE_PATHS:
        if os.path.isfile(cand):
            soffice_bin = cand
            break

    if not soffice_bin:
        import shutil
        soffice_bin = shutil.which("soffice") or shutil.which("libreoffice")

    if not soffice_bin:
        print("[WARNING] LibreOffice binary not found. PDF export skipped.")
        return False

    out_dir = os.path.dirname(os.path.abspath(output_pdf_path))
    if not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    cmd = [
        soffice_bin,
        "--headless",
        "--convert-to", "pdf",
        os.path.abspath(docx_path),
        "--outdir", out_dir
    ]

    print(f"Running LibreOffice headless conversion: {os.path.basename(docx_path)} -> PDF...")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"[ERROR] LibreOffice conversion failed: {res.stderr}")
        return False

    expected_default_pdf = os.path.splitext(os.path.basename(docx_path))[0] + ".pdf"
    generated_pdf_path = os.path.join(out_dir, expected_default_pdf)

    if os.path.exists(generated_pdf_path) and os.path.abspath(generated_pdf_path) != os.path.abspath(output_pdf_path):
        if os.path.exists(output_pdf_path):
            os.remove(output_pdf_path)
        os.rename(generated_pdf_path, output_pdf_path)

    if os.path.exists(output_pdf_path):
        print(f"Successfully generated PDF: {output_pdf_path}")
        return True
    return False


def ensure_college_headers_and_footers(docx_path: str) -> Tuple[str, Optional[str]]:
    """
    If docx_path lacks header/footer parts, creates a temporary working copy with
    standard college headers & footers extracted from reference templates.
    """
    with zipfile.ZipFile(docx_path, "r") as z:
        names = z.namelist()
        has_header = any("word/header" in n for n in names)
        has_footer = any("word/footer" in n for n in names)

    if has_header and has_footer:
        return docx_path, None

    ref_candidates = [
        "output/lab 1/IDFT Lab 1 FTK Imager - Final.docx",
        "input/lab 1/ftk/IDFT Lab 1 FTK Imager.docx",
        "input/lab 2/IDFT Lab 2 Autopsy.docx",
    ]
    ref_path = None
    for c in ref_candidates:
        if os.path.exists(c):
            ref_path = c
            break

    if not ref_path:
        return docx_path, None

    with zipfile.ZipFile(ref_path, "r") as z_ref:
        h1 = z_ref.read("word/header1.xml") if "word/header1.xml" in z_ref.namelist() else None
        f1 = z_ref.read("word/footer1.xml") if "word/footer1.xml" in z_ref.namelist() else None

    if not h1 or not f1:
        return docx_path, None

    with zipfile.ZipFile(docx_path, "r") as z_in:
        file_map = {name: z_in.read(name) for name in z_in.namelist()}

    file_map["word/header1.xml"] = h1
    file_map["word/footer1.xml"] = f1

    # Content Types
    ct_xml = file_map.get("[Content_Types].xml", b"").decode("utf-8")
    if "header1.xml" not in ct_xml:
        ct_xml = ct_xml.replace(
            "</Types>",
            '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/><Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/></Types>'
        )
        file_map["[Content_Types].xml"] = ct_xml.encode("utf-8")

    # Document rels
    rels_xml = file_map.get("word/_rels/document.xml.rels", b"").decode("utf-8")
    if "header1.xml" not in rels_xml:
        rels_xml = rels_xml.replace(
            "</Relationships>",
            '<Relationship Id="rIdHdrGIAL" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/><Relationship Id="rIdFtrGIAL" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/></Relationships>'
        )
        file_map["word/_rels/document.xml.rels"] = rels_xml.encode("utf-8")

    # SectPr in document.xml
    doc_xml = file_map.get("word/document.xml", b"").decode("utf-8")
    if "rIdHdrGIAL" not in doc_xml:
        hdr_tags = (
            '<w:headerReference xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" w:type="default" r:id="rIdHdrGIAL"/>'
            '<w:footerReference xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" w:type="default" r:id="rIdFtrGIAL"/>'
        )
        doc_xml = re.sub(r"(<w:sectPr[^>]*>)", r"\1" + hdr_tags, doc_xml)
        file_map["word/document.xml"] = doc_xml.encode("utf-8")

    fd, tmp_path = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as z_out:
        for name, data in file_map.items():
            z_out.writestr(name, data)

    return tmp_path, tmp_path


def build_aligned_record(
    docx_path: str,
    mapping_path: str,
    output_docx: str,
    output_pdf: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """
    Executes the full Project LabForge alignment pipeline on the given lab record.
    """
    if not os.path.exists(docx_path):
        raise FileNotFoundError(f"Source docx file not found: {docx_path}")
    if not os.path.exists(mapping_path):
        raise FileNotFoundError(f"Mapping file not found: {mapping_path}")

    with open(mapping_path, "r", encoding="utf-8") as f:
        raw_mapping = json.load(f)

    mapping_dir = os.path.dirname(os.path.abspath(mapping_path))
    workspace_dir = os.getcwd()

    explicit_page_breaks = []
    if isinstance(raw_mapping, dict):
        mapping_data = raw_mapping.get("images", [])
        explicit_page_breaks = raw_mapping.get("page_breaks", [])
    elif isinstance(raw_mapping, list):
        mapping_data = raw_mapping
    else:
        raise ValueError("Mapping file must be a JSON array or object with an 'images' key.")

    validated_items = []
    for entry in mapping_data:
        target_idx = entry.get("after_paragraph_index")
        raw_img = entry.get("image_path")
        if target_idx is None or not raw_img:
            continue

        resolved_img = resolve_image_path(raw_img, [mapping_dir, workspace_dir])
        caption = entry.get("caption", "").strip()
        pb = entry.get("page_break_before", False)

        validated_items.append({
            "target_index": int(target_idx),
            "image_path": resolved_img,
            "caption": caption,
            "page_break_before": bool(pb)
        })

    # Read original document (Read-Only Source), ensuring college headers/footers exist
    load_docx_path, tmp_cleanup = ensure_college_headers_and_footers(docx_path)
    try:
        doc = Document(load_docx_path)
    finally:
        if tmp_cleanup and os.path.exists(tmp_cleanup):
            try:
                os.remove(tmp_cleanup)
            except Exception:
                pass

    # 1. Unify section break if present
    for p in doc.paragraphs:
        pPr = p._p.pPr
        if pPr is not None:
            sp = pPr.find(f"{{{W_NS}}}sectPr")
            if sp is not None:
                body_sectPr = doc._body._body.find(f"{{{W_NS}}}sectPr")
                if body_sectPr is not None:
                    doc._body._body.replace(body_sectPr, copy.deepcopy(sp))
                pPr.remove(sp)

    for s in doc.sections:
        pgNum = s._sectPr.find(f"{{{W_NS}}}pgNumType")
        if pgNum is not None:
            s._sectPr.remove(pgNum)

    # 2. Fix header and footer XML architecture
    fix_header_and_footer(doc)

    # 3. Force real vertical spacing via OOXML: disable contextualSpacing across all styles
    for s in doc.styles:
        for cs in s.element.findall(f".//{{{W_NS}}}contextualSpacing"):
            parent = cs.getparent()
            if parent is not None:
                parent.remove(cs)

    # Clean List Paragraph style so it does not enforce inherited indents or tabs
    if "List Paragraph" in doc.styles:
        lp = doc.styles["List Paragraph"]
        lp_pPr = lp.element.find(f"{{{W_NS}}}pPr")
        if lp_pPr is not None:
            for tag in ("ind", "tabs", "numPr"):
                el = lp_pPr.find(f"{{{W_NS}}}{tag}")
                if el is not None:
                    lp_pPr.remove(el)

    # Helper for resolving numFmt from numbering_part
    num_root = None
    for part in doc.part.related_parts.values():
        if "numbering" in part.partname:
            num_root = part._element
            break

    def get_format(num_id: str, ilvl: int) -> str:
        if num_root is None:
            return "decimal" if ilvl == 0 else "lowerLetter"
        num_el = num_root.find(f".//{{{W_NS}}}num[@{{{W_NS}}}numId='{num_id}']")
        if num_el is None:
            return "decimal" if ilvl == 0 else "lowerLetter"
        abs_id_el = num_el.find(f"{{{W_NS}}}abstractNumId")
        if abs_id_el is None:
            return "decimal" if ilvl == 0 else "lowerLetter"
        abs_id = abs_id_el.attrib.get(f"{{{W_NS}}}val")
        abs_el = num_root.find(f".//{{{W_NS}}}abstractNum[@{{{W_NS}}}abstractNumId='{abs_id}']")
        if abs_el is None:
            return "decimal" if ilvl == 0 else "lowerLetter"
        lvl_el = abs_el.find(f".//{{{W_NS}}}lvl[@{{{W_NS}}}ilvl='{ilvl}']")
        if lvl_el is None:
            return "decimal" if ilvl == 0 else "lowerLetter"
        fmt_el = lvl_el.find(f"{{{W_NS}}}numFmt")
        if fmt_el is not None:
            return fmt_el.attrib.get(f"{{{W_NS}}}val", "decimal")
        return "decimal" if ilvl == 0 else "lowerLetter"

    # 4. Clean hanging list alignment: left-align all steps cleanly & ensure literal prefixes exist
    step_counter = 0
    bullet_counter = 0

    for p in doc.paragraphs:
        txt = p.text.strip()
        txt_u = txt.upper()
        if any(kw in txt_u for kw in ("QUICK REFERENCE", "STEPS – QUICK", "STEPS - QUICK", "GENERATING REPORT")):
            step_counter = 0
            bullet_counter = 0

        pPr = p._p.get_or_add_pPr()

        # Disable contextualSpacing on every paragraph
        for cs in pPr.findall(f"{{{W_NS}}}contextualSpacing"):
            pPr.remove(cs)
        cs_zero = parse_xml(f'<w:contextualSpacing xmlns:w="{W_NS}" w:val="0"/>')
        pPr.append(cs_zero)

        numPr = pPr.find(f"{{{W_NS}}}numPr")
        if numPr is not None:
            nid = numPr.find(f"{{{W_NS}}}numId").attrib.get(f"{{{W_NS}}}val", "1")
            ilvl_elem = numPr.find(f"{{{W_NS}}}ilvl")
            ilvl = int(ilvl_elem.attrib.get(f"{{{W_NS}}}val", "0")) if ilvl_elem is not None else 0
            fmt = get_format(nid, ilvl)

            if fmt == "decimal":
                step_counter += 1
                bullet_counter = 0
                prefix = f"{step_counter}. "
                left_indent = Inches(0.3)
                first_line_indent = Inches(-0.3)
            elif fmt == "lowerLetter":
                prefix = f"{chr(ord('a') + bullet_counter)}. "
                bullet_counter += 1
                left_indent = Inches(0.6)
                first_line_indent = Inches(-0.25)
            else:
                if ilvl == 0:
                    step_counter += 1
                    bullet_counter = 0
                    prefix = f"{step_counter}. "
                    left_indent = Inches(0.3)
                    first_line_indent = Inches(-0.3)
                else:
                    prefix = f"{chr(ord('a') + bullet_counter)}. "
                    bullet_counter += 1
                    left_indent = Inches(0.6)
                    first_line_indent = Inches(-0.25)

            pPr.remove(numPr)
            tabs = pPr.find(f"{{{W_NS}}}tabs")
            if tabs is not None:
                pPr.remove(tabs)
            ind = pPr.find(f"{{{W_NS}}}ind")
            if ind is not None:
                pPr.remove(ind)

            clean_text = p.text.lstrip()
            if not clean_text.startswith(prefix):
                m_existing = re.match(r"^(\d+[\.\)]|[a-d][\.\)])\s*", clean_text)
                if not m_existing:
                    if p.runs:
                        p.runs[0].text = prefix + p.runs[0].text.lstrip("\t ")
                    else:
                        p.add_run(prefix)

            p.paragraph_format.left_indent = left_indent
            p.paragraph_format.first_line_indent = first_line_indent
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    initial_paragraphs = list(doc.paragraphs)
    total_paragraphs = len(initial_paragraphs)

    # Identify structural boundaries
    qr_start = -1
    qr_end = -1
    for i, p in enumerate(initial_paragraphs):
        txt_u = p.text.strip().upper()
        if "QUICK REFERENCE" in txt_u or "STEPS – QUICK" in txt_u or "STEPS - QUICK" in txt_u:
            qr_start = i
        elif "OUTPUT" in txt_u and qr_start != -1 and qr_end == -1:
            qr_end = i

    headings_kw = (
        "PRACTICAL", "AIM:", "TOOLS USED:", "TOOL USED:",
        "FTK IMAGER", "AUTOPSY", "FORENSIC IMAGE", "WHY MAKE",
        "CREATING A", "HOW TO USE", "GENERATING REPORT"
    )

    # 5. Apply explicit paragraph category spacing
    for i, p in enumerate(initial_paragraphs):
        txt = p.text.strip()
        txt_u = txt.upper()
        if not txt:
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = Pt(1)
            continue

        if qr_start != -1 and i >= qr_start:
            if i == qr_start:
                # Steps – Quick reference
                p.paragraph_format.space_before = Pt(12)
                p.paragraph_format.space_after = Pt(4)
                p.paragraph_format.line_spacing = 1.15
                p.paragraph_format.page_break_before = True
                p.paragraph_format.keep_with_next = True
            elif "OUTPUT" in txt_u:
                # OUTPUT heading
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(4)
                p.paragraph_format.line_spacing = 1.15
                p.paragraph_format.keep_with_next = True
            elif qr_end != -1 and i > qr_end:
                # Result text under OUTPUT
                p.paragraph_format.space_before = Pt(3)
                p.paragraph_format.space_after = Pt(4)
                p.paragraph_format.line_spacing = 1.15
                p.paragraph_format.keep_with_next = True
                p.paragraph_format.keep_together = True
            else:
                # Quick reference list items
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.line_spacing = 1.05
        else:
            is_heading = any(txt_u.startswith(kw) or txt_u == kw for kw in headings_kw) or (p.style and p.style.name.startswith("Heading")) or (txt_u == "OUTPUT")
            is_step = bool(re.match(r"^(\d+[\.\)]|[a-d][\.\)])\s+", txt))

            if is_heading:
                p.paragraph_format.space_before = Pt(16)
                p.paragraph_format.space_after = Pt(6)
                p.paragraph_format.line_spacing = 1.15
                p.paragraph_format.keep_with_next = True
            elif is_step:
                p.paragraph_format.space_before = Pt(16)
                p.paragraph_format.space_after = Pt(12)
                p.paragraph_format.line_spacing = 1.15
                p.paragraph_format.keep_with_next = True
                p.paragraph_format.keep_together = True
            else:
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(8)
                p.paragraph_format.line_spacing = 1.2
                if "THE DIFFERENT FORMATS" in txt_u or "SELECT THE IMAGE TYPE" in txt_u:
                    p.paragraph_format.keep_with_next = True
                    p.paragraph_format.keep_together = True

    # 6. Apply explicit page breaks from mapping if present
    for pb_idx in explicit_page_breaks:
        if 0 <= pb_idx < total_paragraphs:
            initial_paragraphs[pb_idx].paragraph_format.page_break_before = True

    # 7. Perform Image Injection with Visual Polish Dimensions & 1px Black Border
    grouped = defaultdict(list)
    for item in validated_items:
        grouped[item["target_index"]].append(item)

    for target_idx, items in grouped.items():
        anchor_p = initial_paragraphs[target_idx]
        anchor_p.paragraph_format.keep_with_next = True
        anchor_p.paragraph_format.keep_together = True
        current_elem = anchor_p._p

        for item in items:
            img_path = item["image_path"]
            caption_text = item["caption"]
            img_page_break_before = item.get("page_break_before", False)

            with Image.open(img_path) as raw_img:
                if raw_img.mode not in ("RGB", "RGBA"):
                    raw_img = raw_img.convert("RGBA" if "transparency" in raw_img.info else "RGB")

                # 1px crisp solid black border without cropping any edge pixels
                bordered_img = ImageOps.expand(raw_img, border=1, fill="black")
                w_px, h_px = bordered_img.size
                aspect = w_px / h_px

                is_step_1 = (target_idx in (15, 8) or "OPEN EXTERRO" in anchor_p.text.upper() or "RUN AUTOPSY" in anchor_p.text.upper())
                is_step_2 = (target_idx == 16 and "CREATE DISK IMAGE" in anchor_p.text.upper())
                is_output_img = (target_idx in (52, 33) or (qr_end != -1 and target_idx >= qr_end) or "OUTPUT" in anchor_p.text.upper() or "SUCCESSFULLY" in anchor_p.text.upper())
                is_page_4_step = (target_idx in (25, 27) and "AFF" in anchor_p.text.upper())

                # Context-Aware Bounding Boxes
                if is_step_1:
                    cur_max_w = 5.80
                    cur_max_h = 2.65
                    cur_space_after = Pt(0)
                elif is_step_2 or aspect >= 1.45:
                    cur_max_w = 5.80
                    cur_max_h = 2.80
                    cur_space_after = Pt(20)
                elif is_output_img:
                    cur_max_w = 4.80
                    cur_max_h = 2.40
                    cur_space_after = Pt(0)
                elif is_page_4_step:
                    cur_max_w = 4.80
                    cur_max_h = 2.30
                    cur_space_after = Pt(20)
                else:
                    cur_max_w = 4.80
                    cur_max_h = 2.60
                    cur_space_after = Pt(20)

                target_w, target_h = calculate_image_dimensions(
                    w_px, h_px,
                    max_width_inches=cur_max_w,
                    max_height_inches=cur_max_h
                )

                img_buffer = io.BytesIO()
                bordered_img.save(img_buffer, format="PNG")
                img_buffer.seek(0)

            # Insert image paragraph
            img_p = doc.add_paragraph()
            img_p.style = doc.styles["Normal"]
            img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            img_p.paragraph_format.left_indent = Pt(0)
            img_p.paragraph_format.right_indent = Pt(0)
            img_p.paragraph_format.first_line_indent = Pt(0)
            img_p.paragraph_format.space_before = Pt(12)
            img_p.paragraph_format.space_after = cur_space_after
            img_p.paragraph_format.line_spacing = 1.0
            img_p.paragraph_format.keep_with_next = False
            if img_page_break_before:
                img_p.paragraph_format.page_break_before = True

            # Wipe any list indents and numbering inherited at the XML level
            pPr = img_p._p.get_or_add_pPr()
            for tag in ("ind", "numPr", "tabs"):
                el = pPr.find(f"{{{W_NS}}}{tag}")
                if el is not None:
                    pPr.remove(el)

            img_run = img_p.add_run()
            img_run.add_picture(img_buffer, width=Inches(target_w))

            current_elem.addnext(img_p._p)
            current_elem = img_p._p

            if caption_text:
                cap_p = doc.add_paragraph()
                cap_p.style = doc.styles["Normal"]
                cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap_p.paragraph_format.left_indent = Pt(0)
                cap_p.paragraph_format.right_indent = Pt(0)
                cap_p.paragraph_format.first_line_indent = Pt(0)
                cap_p.paragraph_format.space_before = Pt(4)
                cap_p.paragraph_format.space_after = Pt(12)
                cap_run = cap_p.add_run(caption_text)
                cap_run.italic = True
                cap_run.font.size = Pt(9.5)
                current_elem.addnext(cap_p._p)
                current_elem = cap_p._p

    # 8. Remove empty spacer paragraphs between step text and screenshots
    to_remove = []
    for p in doc.paragraphs:
        txt = p.text.strip()
        has_drawing = len(p._p.findall(f".//{{{W_NS}}}drawing")) > 0
        if not txt and not has_drawing:
            to_remove.append(p._p)

    for p_elem in to_remove:
        parent = p_elem.getparent()
        if parent is not None:
            parent.remove(p_elem)

    # 9. Strip trailing blank paragraphs at end of document
    while doc.paragraphs:
        last = doc.paragraphs[-1]
        has_drawing = len(last._p.findall(f".//{{{W_NS}}}drawing")) > 0
        if not last.text.strip() and not has_drawing:
            doc._body._body.remove(last._p)
        else:
            break

    # Save to output directory
    out_dir = os.path.dirname(os.path.abspath(output_docx))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    doc.save(output_docx)
    print(f"Successfully generated aligned document: {output_docx}")
    print(f"Injected Screenshots: {len(validated_items)}")

    # 10. Automatically export PDF if requested
    actual_pdf = None
    if output_pdf:
        success = convert_docx_to_pdf(output_docx, output_pdf)
        if success:
            actual_pdf = output_pdf

    return output_docx, actual_pdf


def main():
    parser = argparse.ArgumentParser(
        description="Project LabForge: OOXML Alignment and PDF Generation Engine."
    )
    parser.add_argument(
        "--docx",
        required=True,
        help="Path to source .docx document (read-only)."
    )
    parser.add_argument(
        "--mapping",
        required=True,
        help="Path to JSON mapping file specifying paragraph indices and screenshots."
    )
    parser.add_argument(
        "--out",
        "--out-docx",
        dest="out_docx",
        required=True,
        help="Path for generated output .docx document."
    )
    parser.add_argument(
        "--out-pdf",
        dest="out_pdf",
        default=None,
        help="Optional path for generated output .pdf document (auto-derived if not passed)."
    )

    args = parser.parse_args()

    pdf_target = args.out_pdf
    if not pdf_target:
        out_dir = os.path.dirname(args.out_docx)
        filename_no_ext = os.path.splitext(os.path.basename(args.out_docx))[0]
        pdf_target = os.path.join(out_dir, "final", filename_no_ext + ".pdf")

    try:
        build_aligned_record(
            docx_path=args.docx,
            mapping_path=args.mapping,
            output_docx=args.out_docx,
            output_pdf=pdf_target
        )
    except Exception as e:
        sys.exit(f"LabForge Engine error: {e}")


if __name__ == "__main__":
    main()
