"""
tests/helpers/sample_factory.py
Synthetic test fixture generator for Project LabForge.
Generates programmatic, isolated test documents (.docx) and test images (.png)
exclusively within temporary/test directories.
"""

import os
from typing import Optional, Tuple
from PIL import Image, ImageDraw
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


def create_synthetic_image(
    output_path: str,
    width: int = 800,
    height: int = 600,
    image_type: str = "dialog",
    margin_color: Optional[str] = None,
    margin_px: int = 0,
) -> str:
    """
    Creates a deterministic synthetic test image and saves it to output_path.

    Supported image_types:
    - 'dialog': Simulated UI dialog box with title bar and form fields (aspect ~1.33).
    - 'widescreen': Simulated widescreen full-desktop window (1920x1080, aspect ~1.78).
    - 'padded_white': Active content block centered inside white margin border.
    - 'padded_black': Active content block centered inside black margin border.
    - 'rgba': Transparent RGBA image with translucent colored boxes.
    - 'low_contrast': Narrow dynamic range image (values 100-140).
    - 'solid': Uniform color block.
    """
    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    if image_type == "widescreen":
        w, h = 1920, 1080
        img = Image.new("RGB", (w, h), (30, 30, 30))
        draw = ImageDraw.Draw(img)
        # Title bar
        draw.rectangle([0, 0, w, 40], fill=(50, 50, 50))
        draw.rectangle([10, 10, 30, 30], fill=(220, 50, 50))
        draw.rectangle([40, 10, 60, 30], fill=(220, 180, 50))
        draw.rectangle([70, 10, 90, 30], fill=(50, 200, 50))
        # Terminal area
        draw.rectangle([50, 80, w - 50, h - 80], fill=(15, 15, 15), outline=(70, 70, 70), width=2)
        # Simulated prompt text line
        draw.rectangle([70, 100, 400, 120], fill=(0, 255, 100))

    elif image_type == "dialog":
        w, h = width, height
        img = Image.new("RGB", (w, h), (240, 240, 240))
        draw = ImageDraw.Draw(img)
        # Dialog header
        draw.rectangle([0, 0, w, 35], fill=(30, 100, 200))
        # Input boxes
        draw.rectangle([40, 60, w - 40, 100], fill=(255, 255, 255), outline=(180, 180, 180), width=1)
        draw.rectangle([40, 120, w - 40, 160], fill=(255, 255, 255), outline=(180, 180, 180), width=1)
        # Action button
        draw.rectangle([w - 150, h - 50, w - 40, h - 20], fill=(0, 120, 215))

    elif image_type == "padded_white":
        w, h = width, height
        m = margin_px if margin_px > 0 else 100
        img = Image.new("RGB", (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        # Centered colored content
        draw.rectangle([m, m, w - m, h - m], fill=(40, 120, 220), outline=(20, 60, 140), width=3)
        draw.rectangle([m + 30, m + 30, w - m - 30, h - m - 30], fill=(240, 160, 40))

    elif image_type == "padded_black":
        w, h = width, height
        m = margin_px if margin_px > 0 else 80
        img = Image.new("RGB", (w, h), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle([m, m, w - m, h - m], fill=(60, 180, 75))

    elif image_type == "rgba":
        w, h = width, height
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Semi-transparent rectangle
        draw.rectangle([50, 50, w - 50, h - 50], fill=(200, 50, 50, 180))
        draw.rectangle([100, 100, w - 100, h - 100], fill=(50, 50, 200, 220))

    elif image_type == "low_contrast":
        w, h = width, height
        # Fill with values between 110 and 130
        img = Image.new("RGB", (w, h), (120, 120, 120))
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 50, w - 50, h - 50], fill=(125, 125, 125))
        draw.rectangle([100, 100, w - 100, h - 100], fill=(130, 130, 130))

    else:
        # Default solid / custom
        bg_col = (200, 200, 200)
        img = Image.new("RGB", (width, height), bg_col)
        draw = ImageDraw.Draw(img)
        draw.rectangle([20, 20, width - 20, height - 20], fill=(100, 150, 200))

    # Apply extra margin if requested and not already padded
    if margin_px > 0 and image_type not in ("padded_white", "padded_black"):
        col = (255, 255, 255) if margin_color in ("white", None) else (0, 0, 0)
        new_w = img.width + (2 * margin_px)
        new_h = img.height + (2 * margin_px)
        canvas = Image.new(img.mode, (new_w, new_h), col)
        canvas.paste(img, (margin_px, margin_px))
        img = canvas

    img.save(output_path)
    return output_path


def create_synthetic_docx(
    output_path: str,
    scenario: str = "standard",
    target_keyword: str = "Ubuntu",
    replacement_keyword: str = "Kali Linux",
) -> str:
    """
    Creates a deterministic synthetic test .docx document and saves it to output_path.

    Supported scenarios:
    - 'standard': Heading, procedure steps with Ubuntu in body, bold run, and table.
    - 'clean': Document with 0 occurrences of target_keyword.
    - 'multiple': Document with 4 occurrences of target_keyword across paragraphs.
    - 'split_runs': Target keyword split across adjacent runs ('Ub' + 'untu').
    - 'table_merged': Merged table cells containing target keyword.
    - 'header_footer': Target keyword in section header and footer.
    """
    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    doc = docx.Document()

    if scenario == "standard":
        p0 = doc.add_paragraph("LAB RECORD 1: NETWORK RECONNAISSANCE")
        p0.style = doc.styles["Heading 1"]

        p1 = doc.add_paragraph("AIM: To capture and analyze network packets.")

        p2 = doc.add_paragraph(f"The captured packets were analyzed in {target_keyword} operating system.")

        p3 = doc.add_paragraph()
        r0 = p3.add_run("Run the terminal command on ")
        r1 = p3.add_run(target_keyword)
        r1.bold = True
        r1.font.name = "Times New Roman"
        r2 = p3.add_run(" to start the background daemon.")

        p4 = doc.add_paragraph("Procedure steps:")
        p5 = doc.add_paragraph(f"1. Open Terminal in {target_keyword}.")
        p6 = doc.add_paragraph("2. Type guymager and press Enter.")

        # Table
        t = doc.add_table(rows=2, cols=2)
        t.rows[0].cells[0].text = "Parameter"
        t.rows[0].cells[1].text = "Target Value"
        t.rows[1].cells[0].text = "OS Platform"
        t.rows[1].cells[1].text = f"{target_keyword} Linux"

    elif scenario == "clean":
        p0 = doc.add_paragraph("LAB RECORD: VERIFIED CLEAN")
        p0.style = doc.styles["Heading 1"]
        p1 = doc.add_paragraph(f"AIM: Perform analysis strictly using {replacement_keyword}.")
        p2 = doc.add_paragraph(f"All operations were verified inside {replacement_keyword} environment.")

    elif scenario == "multiple":
        doc.add_paragraph("MULTIPLE DISCREPANCIES TEST DOCUMENT")
        for i in range(1, 5):
            p = doc.add_paragraph(f"Occurrence {i}: Open the application in {target_keyword} distro.")

    elif scenario == "split_runs":
        doc.add_paragraph("SPLIT RUN BOUNDARY TEST")
        p = doc.add_paragraph()
        # Split target into two runs: 'Ub' and 'untu'
        half = len(target_keyword) // 2
        part1 = target_keyword[:half]
        part2 = target_keyword[half:]

        p.add_run("Please launch the terminal in ")
        r_part1 = p.add_run(part1)
        r_part2 = p.add_run(part2)
        r_part2.bold = True
        r_part2.font.name = "Courier New"
        p.add_run(" to complete the task.")

    elif scenario == "table_merged":
        doc.add_paragraph("MERGED TABLE CELLS TEST")
        table = doc.add_table(rows=3, cols=3)
        # Merge top row across 3 columns
        a = table.cell(0, 0)
        b = table.cell(0, 2)
        a.merge(b)
        a.paragraphs[0].text = f"Primary System: {target_keyword} Forensics"

        table.cell(1, 0).text = "Module A"
        table.cell(1, 1).text = f"Runs on {target_keyword}"
        table.cell(1, 2).text = "Status: Active"

    elif scenario == "header_footer":
        section = doc.sections[0]
        section.header.paragraphs[0].text = f"Forensic Guide - {target_keyword} Edition"
        section.footer.paragraphs[0].text = f"Confidential {target_keyword} Documentation"
        p = doc.add_paragraph("Body paragraph content.")

    else:
        doc.add_paragraph(f"Generic test document with {target_keyword}.")

    doc.save(output_path)
    return output_path
