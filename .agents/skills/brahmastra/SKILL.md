---
name: brahmastra
description: Zero-touch autonomous lab record automation engine. Injects screenshots into .docx documents using teacher-approved OOXML alignment, 1px black borders, smart bounding boxes, unified headers/footers, and exports verified PDFs.
---

# Project Brahmastra: Autonomous Lab Record Automation Standard

Project Brahmastra is a permanent, zero-touch lab record automation engine designed to produce teacher-grade B.Sc. Cyber Forensics lab records on the first pass without intermediate test variants.

Whenever the user prompts **"Fire Brahmastra"**, **"Run Brahmastra"**, or **"Run Sudarshana"** (or specifies a lab folder), execute the entire 4-stage pipeline autonomously—inspecting the `.docx`, viewing screenshots with multimodal vision, generating the mapping, building the final `.docx` and `.pdf` in `output/`, and printing the QA audit report—without asking intermediate questions.

---

## 1. The Divine Weapon Architecture

1. **Kavacha (The Impenetrable Read-Only Armor):**
   - Source files in `input/` (`.docx` templates and screenshots) are strictly **READ-ONLY**.
   - **Zero Text Edits**: Never edit, rewrite, delete, spellcheck, re-word, or reformat any existing text or headings in the source document. The text is sacred and immutable.

2. **Sudarshana (`Su-Darshana` Clear-Vision Targeting Discus):**
   - Uses multimodal AI vision to inspect every raw screenshot in `input/<Lab_Folder>/`.
   - Reads window titles, active UI dialog tabs, CLI commands, and red highlight boxes to map each image to its exact target `paragraph_index` in the `.docx`.

3. **Gandiva (The Unerring OOXML Alignment Bow):**
   - Operates directly at the OpenXML (`wordprocessingML`) level.
   - Enforces left-aligned hanging step indentations, disables contextual spacing, wraps images in 1px crisp black borders, calculates aspect-ratio bounding boxes, unifies headers/footers, and exports verified `.docx` and `.pdf` files.

4. **Brahmastra (The Master Execution Strike):**
   - Runs the end-to-end pipeline—from auto-discovering unbuilt lab folders in `input/` to exporting the final `.docx` and `.pdf` in `output/` and auditing the PDF with zero intermediate questions.

---

## 2. Root-Cause Post-Mortem & The 7 Mandatory Rules

Every rule below fixes a real Word/PDF layout bug that our teacher or we rejected during earlier drafts:

### Bug 1: The "Step Numbers Hanging in the Middle of the Page" Bug
- **What went wrong:** In the original `.docx` template, numbered steps (`1.`, `5.`, `9.`) used Word's internal `<w:numPr>` list numbering (`word/numbering.xml`), which pushed the step numbers almost 2 inches toward the center of the page with a huge tab gap before the text (e.g., `9.          Click Start.`). Setting `paragraph_format.left_indent` in `python-docx` did nothing because `<w:numPr>` overrides normal paragraph indents.
- **The Mandatory Fix:** For every numbered procedure step (`1.` to `N.`) and lettered sub-bullet (`a.` to `z.`):
  1. Ensure the literal number or letter prefix (`"1. "`, `"2. "`, ..., `"a. "`, `"b. "`) is explicitly present at the start of `p.text` so the number does not vanish when XML numbering is removed.
  2. Strip the `<w:numPr>` element and any custom `<w:tabs>` element directly from `p._p.pPr` (and from its style if inherited).
  3. Apply clean left-aligned hanging indentation:
     - Main numbered steps (`1.`–`N.`): `left_indent = Inches(0.3)`, `first_line_indent = Inches(-0.3)`, `alignment = WD_ALIGN_PARAGRAPH.LEFT`.
     - Lettered sub-bullets (`a.`–`z.`): `left_indent = Inches(0.6)`, `first_line_indent = Inches(-0.25)`, `alignment = WD_ALIGN_PARAGRAPH.LEFT`.

### Bug 2: The "Missing Space / Congested Text & Images" Bug (`<w:contextualSpacing/>`)
- **What went wrong:** The record initially looked congested, and even when `space_before` and `space_after` were set in `python-docx`, headings like `OUTPUT` were pressed right against Step 11 with zero gap, and step text was touching the top of screenshots. This happened because Word's `styles.xml` had `<w:contextualSpacing/>` ("Don't add space between paragraphs of the same style") enabled, which silently cancelled out `space_before` and `space_after`.
- **The Mandatory Fix:**
  1. Loop through every style in `doc.styles` and every paragraph in `doc.paragraphs`.
  2. Remove all `<w:contextualSpacing>` tags from `style.element` and `p._p.pPr`, and explicitly insert `<w:contextualSpacing w:val="0"/>` inside `p._p.get_or_add_pPr()`.
  3. Apply these exact vertical spacing values:
     - **Section Headings (`PRACTICAL`, `AIM`, `TOOLS USED`, `OUTPUT`, tool headings):** `space_before = Pt(16)`, `space_after = Pt(6)`, `line_spacing = 1.15`, `keep_with_next = True`.
     - **Theory / Body Paragraphs:** `space_before = Pt(4)`, `space_after = Pt(8)`, `line_spacing = 1.2`.
     - **Main Procedure Steps (`1.`–`N.`):** `space_before = Pt(16)` (clear visual separation from preceding image), `space_after = Pt(12)` (clear gap before its own screenshot), `line_spacing = 1.15`, `keep_with_next = True`, `keep_together = True`.
     - **Inserted Screenshot Paragraphs:** `space_before = Pt(12)`, `space_after = Pt(20)` to `Pt(24)` (`Pt(0)` on Step 1 and the final `OUTPUT` image), `keep_with_next = False`.
     - **Quick Reference Summary:** `space_before = Pt(2)`, `space_after = Pt(2)`, `line_spacing = 1.05`.

### Bug 3: The "Off-Center Screenshots" Bug (Inherited List Indentation)
- **What went wrong:** When a new paragraph for a screenshot was inserted right after an indented list step, it inherited the list style's `left_indent`, causing "centered" screenshots to sit off-center to the right.
- **The Mandatory Fix:** Every inserted screenshot paragraph MUST be assigned `img_p.style = doc.styles['Normal']`, `img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER`, and have all horizontal indents explicitly zeroed out:
  - `img_p.paragraph_format.left_indent = Pt(0)`
  - `img_p.paragraph_format.right_indent = Pt(0)`
  - `img_p.paragraph_format.first_line_indent = Pt(0)`
  - Strip any inherited `<w:ind>`, `<w:numPr>`, and `<w:tabs>` from `img_p._p.pPr`.

### Bug 4: The "Orphaned Step Text at the Bottom of Pages" Bug
- **What went wrong:** Steps sat stranded at the bottom of pages while their screenshots landed at the top of the next page, even though `keep_with_next = True` was set! Why? Because there was an empty blank paragraph sitting between the step text and the screenshot paragraph, so Word glued the step to the blank paragraph instead of the screenshot.
- **The Mandatory Fix:**
  1. Delete any empty/blank paragraphs between a step's text and its inserted screenshot.
  2. Set `keep_with_next = True` and `keep_together = True` on the step text paragraph (and all its sub-bullets), and `keep_with_next = False` on the screenshot paragraph itself. That way, if a screenshot cannot fit at the bottom of a page, Word automatically pulls the step text onto the next page with its image.

### Bug 5: The "Split Multi-Bullet Step" Bug (Step 6 `a, b, c, d`)
- **What went wrong:** Step 6 had an intro line (`6. Now select the image type... Select E01.`) followed by `a. Raw(dd)`, `b. SMART`, `c. E01`, `d. AFF`. In an early run, the AI inserted the screenshot right after the intro line, splitting Step 6 above its `a, b, c, d` definitions.
- **The Mandatory Fix:** During **Sudarshana** vision mapping, whenever a numbered step is followed by sub-bullets (`a, b, c, d`) or explanatory lines belonging to that same step, always map the screenshot **after the final sub-bullet (`d.`)**, and set `keep_with_next = True` on the main step line and all sub-bullets `a` through `d`.

### Bug 6: The "Tiny Unreadable Screenshots vs. Giant Page-Breaking Screenshots" Bug
- **What went wrong:**
  - Squeezing screenshots to `MAX_HEIGHT = 2.0 inches` made square dialog boxes only ~2.2 inches wide and left the bottom third of the page blank.
  - Making all screenshots `width = 5.8 inches` caused square dialogs to explode vertically to 5+ inches, colliding with footers.
  - Step 1 widescreen jumping to Page 2 left Page 1 half empty.
- **The Mandatory Fix (Aspect-Ratio & Context-Aware Bounding Boxes):**
  1. Wrap every screenshot in a crisp **1px solid black border** in memory (`PIL.ImageOps.expand(img, border=1, fill='black')`) without cropping any edge pixels (ensuring bottom buttons like Step 9's `Start` button are never clipped).
  2. Calculate `aspect = width_px / height_px` using `Pillow` and scale proportionally inside these exact teacher-approved bounding boxes:
     - **Page 1 Widescreen Screenshot (`Step 1`):** `MAX_WIDTH = Inches(5.80)`, `MAX_HEIGHT = Inches(2.65)` (`space_after = Pt(0)`). Fits cleanly on Page 1 below theory without clipping the left edge.
     - **Other Widescreen Full-Window Screenshots (`aspect >= 1.45`, e.g., Step 2 / Kali terminals):** `MAX_WIDTH = Inches(5.80)`, `MAX_HEIGHT = Inches(2.80)` to `Inches(3.00)`.
     - **Standard Dialog Box Screenshots (`aspect < 1.45`, e.g., Steps 3–11):** `MAX_WIDTH = Inches(4.80)`, `MAX_HEIGHT = Inches(2.60)`.
     - **Dense Pages with Multi-Bullets (e.g. Page 4 Steps 6 & 7):** `MAX_WIDTH = Inches(4.80)`, `MAX_HEIGHT = Inches(2.30)`.
     - **Quick Reference & Final `OUTPUT` Page:** Set `page_break_before = True` on the Quick Reference heading, apply compact spacing (`line_spacing = 1.05`, `space_before = Pt(2)`, `space_after = Pt(2)`), and constrain final `OUTPUT` screenshot to `MAX_WIDTH = Inches(4.80)`, `MAX_HEIGHT = Inches(2.00)` to `Inches(2.40)` with `space_after = Pt(0)` so the summary + final `OUTPUT` image fit together on the last page without spawning a blank trailing page.

### Bug 7: The Repeating `1| Page`, `2| Page` Header & Wrapped `2025-29` Footer Bug
- **What went wrong:** The original template had `odd_and_even_pages_header_footer = True`, which caused odd pages to repeat `1| Page`, even pages to repeat `2| Page`, and `2025-29` in the bottom-right footer of even pages to wrap onto two lines (`2025-` and `29`). In some templates, students typed hardcoded numbers (like `3`) before the dynamic `PAGE` field causing doubled numbers like `11 | P a g e`.
- **The Mandatory Fix:**
  1. Set A4 page dimensions (`8.27 in` x `11.69 in`) with `top_margin = Inches(0.90)`, `bottom_margin = Inches(0.85)`, `left_margin = Inches(1.0)`, `right_margin = Inches(0.75)`, `header_distance = Inches(0.45)`, and `footer_distance = Inches(0.40)`.
  2. Set `section.odd_and_even_pages_header_footer = False` and `section.different_first_page_header_footer = False` so the entire document uses ONE unified header and ONE unified footer. Connect `default` header/footer references to non-empty content parts.
  3. Keep the native dynamic Word `PAGE` field (`1 | Page`, `2 | Page`, ... up to the last page) in the top-right header, stripping any hardcoded prefix digits.
  4. Keep `GIAL Vadavathoor` on the bottom-left footer and `2025\u201129` (using a non-breaking hyphen and expanded textbox to `55pt` at `margin-left: 485pt` / posOffset) on the bottom-right footer so it never splits across two lines.
  5. Strip any trailing empty paragraphs at the end of `doc.paragraphs` so no blank extra page is created at the end.

---

## 3. Autonomous Execution Protocol ("Fire Brahmastra")

When the user says **"Fire Brahmastra"**, **"Run Brahmastra"**, or **"Run Sudarshana"**:

1. **Stage 1: Scan & Inspect Document (Sudarshana):**
   ```powershell
   .venv\Scripts\python.exe scripts/inspect_record.py --dir "input/<Lab_Folder>" --out "mappings/<lab_name>_inspection.json"
   ```
2. **Stage 2: Multimodal Vision Mapping (Sudarshana):**
   - Inspect the raw screenshots and map each to the exact step paragraph in `.docx`.
   - Ensure sub-bullet steps map after the last bullet (`d.`).
   - Map the final completed status image to `OUTPUT`.
   - Save to `mappings/<lab_name>_map.json`.
3. **Stage 3: Gandiva OOXML Alignment & Automatic PDF Export (Brahmastra):**
   ```powershell
   .venv\Scripts\python.exe scripts/brahmastra_engine.py --docx "input/<Lab_Folder>/<record>.docx" --mapping "mappings/<lab_name>_map.json" --out "output/<Record_Name> - Final.docx"
   ```
4. **Stage 4: Automated PDF QA Audit:**
   ```powershell
   .venv\Scripts\python.exe scripts/verify_pdf.py --pdf "output/<Record_Name> - Final.pdf" --mapping "mappings/<lab_name>_map.json"
   ```
5. Confirm that all 5 gates pass (`zero_trailing_blank_page`, `zero_orphaned_steps`, `sequential_headers`, `all_screenshots_present`, `footer_single_line`).

---

## 4. Production Workspace Files

- **`.agents/skills/brahmastra/SKILL.md`**: Official Antigravity skill definition.
- **`scripts/inspect_record.py`**: Paragraph and screenshot cataloger.
- **`scripts/brahmastra_engine.py`**: Locked production OOXML alignment and PDF engine.
- **`scripts/inject_images.py`**: Backwards-compatible wrapper pointing to `brahmastra_engine.py`.
- **`scripts/verify_pdf.py`**: PyMuPDF audit tool enforcing all acceptance gates.
- **`mappings/lab1_map.json`**: Production mapping for Lab 1.
- **`mappings/lab2_map.json`**: Production mapping for Lab 2.
- **`output/lab 1/IDFT Lab 1 FTK Imager - Final.docx`**: Final aligned Word document for Lab 1.
- **`output/lab 1/final/IDFT Lab 1 FTK Imager - Final.pdf`**: Final aligned PDF document for Lab 1.
- **`output/lab 2/IDFT Lab 2 Autopsy - Final.docx`**: Final aligned Word document for Lab 2.
- **`output/lab 2/final/IDFT Lab 2 Autopsy - Final.pdf`**: Final aligned PDF document for Lab 2.
- **`output/lab 4/IDFT Lab 4 Guymager - Final.docx`**: Final aligned Word document for Lab 4.
- **`output/lab 4/final/IDFT Lab 4 Guymager - Final.pdf`**: Final aligned PDF document for Lab 4.
