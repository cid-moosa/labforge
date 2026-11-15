# ⚡ Project LabForge

**Zero-touch autonomous lab record automation engine & AI skill for Microsoft Word (`.docx`) and verified PDF generation.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/cid-moosa/labforge/blob/main/LabForge_Mobile.ipynb)
[![OOXML Engine](https://img.shields.io/badge/OOXML-Engine-orange.svg)](#the-7-solved-ooxml-layout-bugs)
[![AI Agent Ready](https://img.shields.io/badge/Agent%20Skill-Antigravity%20%7C%20Gemini-purple.svg)](.agents/skills/labforge/SKILL.md)

---

## 🌟 Overview

**Project LabForge** is an autonomous practical lab record automation engine built to eliminate the tedious hours spent manually formatting academic and technical lab records in Microsoft Word. It ingests unformatted source `.docx` documents and raw screenshots, applies multimodal vision targeting, solves notorious Word OpenXML layout bugs at the root, and exports publication-ready, teacher-grade `.docx` and `.pdf` deliverables on the first pass.

LabForge functions both as a **standalone Python CLI tool** and as an **autonomous AI Agent skill** (for Google Antigravity, Gemini CLI, Claude Code, and Cursor).

---

## 🎓 The Story Behind LabForge

It all started during our practical lab sessions in college. While running forensic tools, carving disk images, and typing commands into terminal windows, we’d capture dozens of screenshots as proof of our work. A few days later, our teacher would hand us the official practical record template and ask us to submit the completed document.

As an avid open-source enthusiast, I do everything on Linux with LibreOffice Writer rather than proprietary software. But sitting down to manually insert, crop, and align dozens of screenshots across multiple lab exercises was pure agony. Honestly, part of me was just lazy—I didn't want to spend entire weekends wrestling with image anchor settings, paragraph margins, and list indents.

To make matters worse, every time I manually aligned the document and exported the PDF, my teacher rejected it. The layout was always broken: list numbering pushed step numbers two inches into the middle of the page with awkward tab gaps, square dialog boxes were squeezed into unreadable thumbnails, headings were pressed right against preceding images with zero whitespace, and procedure steps sat stranded at the bottom of pages while their screenshots jumped to the next.

I got tired of the repeated rejections and manual alignment headaches, so I decided to solve it the hacker way: by building an automation engine to do all the heavy lifting.

With LabForge, the workflow is dead simple. I just create folders named `lab 1`, `lab 2`, `lab 4`, drop the teacher’s `.docx` template and my raw screenshots inside, and let the engine take over. It uses multimodal AI vision to understand which screenshot belongs to which step, fixes the underlying OpenXML layout with teacher-approved precision, and uses headless LibreOffice to generate the final, beautifully aligned PDF inside a `final/` folder—all with zero manual effort.

I don't know if this will be useful to anybody else out there, but it saved my records and my sanity. This project is built entirely with open-source tools and dedicated to my friends, future students who have to survive practical submissions, and fellow open-source nerds like me! 🚀

---

## ⚡ Autonomous Setup Prompt (One-Click Copy & Paste)

Copy the master prompt below and paste it directly into your AI coding assistant (**Google Antigravity**, **Gemini CLI**, **Claude Code**, **Cursor**, or **Windsurf**). The agent will automatically clone, configure dependencies, register the `/labforge` skill, and execute the complete pipeline on your lab folders with zero manual setup:

````text
Act as an autonomous DevOps and Document Automation Engineer. Your objective is to automatically download (or scaffold), configure, register, and execute **Project LabForge: Autonomous Practical Lab Record Automation Engine** in this workspace with zero manual intervention.

---

### PHASE 1: AUTO-DOWNLOAD, SCAFFOLD & ENVIRONMENT SETUP
1. **Repository & Workspace Initialization:**
   - Check if a Git repository URL is provided or already cloned in the workspace. If a repo URL is provided (`https://github.com/cid-moosa/labforge.git`), clone or pull the latest changes.
   - If no external repository URL is provided or if core scripts are missing, scaffold the complete LabForge engine directly in this workspace.
   - Ensure the mirrored folder hierarchy exists at the project root:
     ```text
     input/
     └── lab 1/
         └── screenshots/
     output/
     ```

2. **Python & System Dependencies:**
   - Create and activate an isolated Python virtual environment (`.venv`).
   - Install required Python libraries: `python-docx`, `lxml`, `Pillow`, `pymupdf` (or `pdf2image`), and `pypdf`.
   - Verify that headless **LibreOffice** (`libreoffice --version` or `soffice --version`) and PDF rendering utilities (`pdftoppm` / `poppler-utils`) are available on the system PATH. If missing, install them automatically via the system package manager.

---

### PHASE 2: BUILD & ENFORCE THE 4-STAGE LABFORGE ARCHITECTURE
Ensure the workspace scripts (`scripts/labforge_engine.py`, `scripts/verify_pdf.py`, and `scripts/inspect_record.py` or `labforge/layout_engine.py`, `labforge/qa_audit.py`, and `labforge/runner.py`) and your agent execution loop enforce all four architectural stages:

#### Stage 1: SourceGuard (Read-Only Guardrail)
- Treat `input/` as strictly read-only. Never modify, rename, overwrite, delete, or spellcheck any source `.docx` template or screenshot inside `input/`. All formatting adapts to the source document.

#### Stage 2: VisionTarget (Multimodal AI Vision Mapping)
- Scan `input/` for any `lab <N>/` folder containing a `.docx` file and a screenshot subfolder.
- Parse all procedure steps and paragraph indices from the `.docx` template.
- Inspect every image in the lab's screenshot folder using multimodal vision: read terminal commands, window titles, active GUI dialogs, and highlight boxes.
- Discard transient loading or splash screens and map each definitive evidence screenshot to its exact target paragraph index in the `.docx`.
- **Multi-Bullet Rule:** If a step contains sub-bullets (`a, b, c, d`), map the screenshot strictly after the final sub-bullet so explanations are never split.

#### Stage 3: LayoutEngine (7 Root-Cause OpenXML / `wordprocessingML` Fixes)
Operate directly on the underlying Word OpenXML (`w:` and `a:` namespaces) to resolve all 7 layout bugs before saving to `output/lab <N>/<Original_Name> - Final.docx`:
1. **Hanging Step Numbers:** Preserve the literal step number prefix, strip native `<w:numPr>` and `<w:tabs>` elements that push numbers into the page, and apply a clean `0.3"` hanging indent.
2. **Congested Spacing:** Inject `<w:contextualSpacing w:val="0"/>` on all procedure paragraphs and enforce explicit vertical buffers (`Pt(16)` space before, `Pt(12)` space after).
3. **Off-Center Images:** Insert every screenshot in a dedicated paragraph reset to the `Normal` style with `left_indent = 0`, `right_indent = 0`, `first_line_indent = 0`, and true horizontal page centering (`WD_ALIGN_PARAGRAPH.CENTER`).
4. **Orphaned Step Text:** Strip empty spacer paragraphs between steps and their screenshots, and bind step text directly to its following image paragraph using `keep_with_next = True` and `keep_together = True`.
5. **Split Multi-Bullet Steps:** Keep all sub-bullets (`a, b, c, d`) grouped together with `keep_with_next = True` and inject the mapped screenshot strictly after the last sub-bullet.
6. **Distorted / Page-Breaking Images & 1px Borders:** Calculate the native aspect ratio of each image with `Pillow` and scale it proportionally within smart bounding boxes without clipping or distortion:
   - Widescreen terminals / full windows: max `5.80" × 2.65"`
   - Standard GUI dialogs: max `4.80" × 2.60"`
   - Compact output boxes: max `4.80" × 2.00"`
   - Inject a crisp 1px solid black OpenXML border (`<a:ln w="12700"><a:solidFill><a:srgbClr val="000000"/></a:solidFill></a:ln>`) around every inline picture (`<pic:spPr>`).
7. **Doubled Headers & Broken Footers:** Disable `odd_and_even_pages_header_footer` across all document sections, inject dynamic Word page numbering (`<w:fldSimple w:instr="PAGE">` formatted as `1 | Page` through `N | Page`), widen footer textboxes/frames if present, and replace standard hyphens in academic years with non-breaking hyphens so institution and academic-year footers stay on a single line.

#### Stage 4: LabForge Core (Headless PDF Compilation & 5-Gate QA Audit)
- Convert each generated `.docx` to a publication-ready PDF inside `output/lab <N>/final/<Original_Name> - Final.pdf` using headless LibreOffice:
  `libreoffice --headless --convert-to pdf --outdir "output/lab <N>/final" "output/lab <N>/<Original_Name> - Final.docx"`
- Render the generated PDF pages to images and perform both programmatic and visual checks against the **5-Gate PDF Quality Acceptance Checklist**:
  - **Gate 1 (Zero Trailing Blank Page):** The final page contains real lab content—no empty trailing sheet.
  - **Gate 2 (Zero Orphaned Steps):** No procedure step sits stranded at the bottom of a page while its screenshot jumps to the next page.
  - **Gate 3 (Sequential Page Headers):** Dynamic headers increment sequentially (`1 | Page` to `N | Page`) with no duplicate or missing numbers.
  - **Gate 4 (All Screenshots Accounted For):** 100% of mapped screenshots are embedded in sequence with visible 1px borders and zero edge clipping.
  - **Gate 5 (Footer Single-Line Format):** Institution name and academic year remain on a single unbroken line across all pages.
- **Self-Healing Loop:** If any QA Gate fails, automatically adjust the OpenXML bounding boxes or paragraph spacing in `layout_engine.py`, re-compile the `.docx` and PDF, and re-verify until all 5 gates pass.

---

### PHASE 3: REGISTER THE `/labforge` IDE AGENT SKILL
Create or update the workspace agent skill/rules file (`.agents/skills/labforge/SKILL.md`, `.cursorrules`, `.windsurfrules`, or `CLAUDE.md`) with the complete 4-Stage Architecture instructions above so that typing `/labforge` in any future session immediately triggers automated folder discovery, VisionTarget mapping, LayoutEngine OOXML compilation, and the 5-Gate PDF QA Audit.

---

### PHASE 4: IMMEDIATE EXECUTION
1. Run Phase 1, Phase 2, and Phase 3 now.
2. Scan `input/` for any existing lab folders containing a `.docx` file and screenshots:
   - **If unbuilt labs exist in `input/`:** Execute the full LabForge pipeline on every lab folder right now and output a structured 5-Gate QA Audit report for each generated PDF in `output/<lab_folder>/final/`.
   - **If `input/` is empty:** Confirm that the virtual environment, headless LibreOffice engine, core scripts, and `/labforge` skill are installed and ready for me to drop my lab folders into `input/`.
````

---

## 🏛️ The 4-Stage Core Architecture

```mermaid
flowchart LR
    A["Source .docx + Raw Screenshots"] --> B["1. SourceGuard<br/>(Read-Only Guardrail)"]
    B --> C["2. VisionTarget<br/>(Multimodal Vision Targeting)"]
    C --> D["3. LayoutEngine<br/>(OOXML Alignment & Formatting)"]
    D --> E["4. LabForge Core<br/>(5-Gate PDF QA Audit & Export)"]
    E --> F["Teacher-Grade .docx & .pdf"]
```

1. **🛡️ SourceGuard (Immutable Read-Only Protection):**
   - Source files in `input/` are strictly **READ-ONLY**.
   - Zero text edits: never rewrites, deletes, or spellchecks the user's sacred text. The formatting bends to the text, never the reverse.
2. **👁️ VisionTarget (Multimodal Vision Mapping & Curation):**
   - Multimodal AI vision inspects raw screenshots, CLI commands, dialog titles, and highlight boxes.
   - Intelligently filters out transient timeline/loading clutter (e.g. intermediate splash screens) and maps definitive evidence images to exact paragraph indices in `.docx`.
3. **📐 LayoutEngine (Precision OOXML Alignment Engine):**
   - Operates directly at the OpenXML (`wordprocessingML`) level.
   - Strips Word list tab gaps, removes `<w:contextualSpacing/>`, wraps images in crisp 1px borders, scales aspect ratios, and dynamically unifies headers/footers.
4. **🚀 LabForge Core (Autonomous Pipeline & QA Audit):**
   - Runs the end-to-end pipeline and enforces a strict 5-gate automated PDF quality audit.

---

## 🔄 How It Works: The Automated Folder-to-Folder Workflow

LabForge eliminates manual copy-pasting through an intuitive, mirrored folder structure. You never have to worry about where your output goes or mess with manual file renaming:

```text
input/                                              output/
├── lab 1/                                          ├── lab 1/
│   ├── IDFT Lab 1 FTK Imager.docx       ───►       │   ├── IDFT Lab 1 FTK Imager - Final.docx
│   └── screenshots/                                │   └── final/
│       ├── 1.png, 2.png, ...                       │       └── IDFT Lab 1 FTK Imager - Final.pdf
├── lab 2/                                          ├── lab 2/
│   ├── IDFT Lab 2 Autopsy.docx          ───►       │   ├── IDFT Lab 2 Autopsy - Final.docx
│   └── autopsy images/                             │   └── final/
│       ├── 1.png, 2.png, ...                       │       └── IDFT Lab 2 Autopsy - Final.pdf
└── lab 4/                                          └── lab 4/
    ├── IDFT Lab 4 Guymager.docx         ───►           ├── IDFT Lab 4 Guymager - Final.docx
    └── guymager images/                                └── final/
        ├── Screenshot_1.png, ...                           └── IDFT Lab 4 Guymager - Final.pdf
```

### 📋 The 4-Step User Experience:
1. **Create Separate Lab Folders in `input/`**:
   Simply create a folder for each practical experiment (e.g., `input/lab 1`, `input/lab 2`, `input/lab 4`).
2. **Drop Your Files Inside**:
   Place the teacher's blank practical record template (`.docx`) and all the raw screenshots you took during the lab into that folder. No need to rename the images or arrange them beforehand.
3. **Run LabForge**:
   LabForge automatically scans all folders in `input/`, inspects the procedure steps, uses AI vision to map the right screenshots to each step, and fixes low-level OpenXML layout issues.
4. **Collect Mirrored Deliverables in `output/`**:
   LabForge replicates the exact folder structure inside `output/`. The formatted Word document stays in `output/lab <N>/`, and the final, teacher-approved PDF is neatly isolated inside `output/lab <N>/final/`.

---

## ✨ Key Features & Capabilities

- 📁 **Automated Lab Folder Discovery & Mirroring:** Scans `input/` for unbuilt labs, ignores folders without screenshots until you're ready, and outputs cleanly structured folders under `output/<lab_folder>/final/`.
- 🛡️ **SourceGuard Read-Only Protection:** Source documents and screenshots in `input/` are never overwritten, modified, or deleted.
- 👁️ **Multimodal AI Vision Targeting:** Intelligently pairs screenshots with document steps by analyzing terminal commands, window headers, and GUI dialogs, discarding transient loading/splash screens.
- 📐 **Direct OpenXML Layout & Spacing Engine:** Fixes 7 notorious formatting bugs directly in the document's XML—eliminating hanging step tab gaps, unsticking paragraphs from borders, centering screenshots, and preventing split steps.
- 🖼️ **Aspect-Ratio Smart Bounding Boxes & 1px Borders:** Widescreen terminal windows and square dialog boxes are scaled proportionally and framed in crisp 1px borders so buttons and menus are never clipped.
- 📄 **Dynamic Headers & Single-Line Footers:** Injects native dynamic Word page numbers (`1 | Page` through `N | Page`), prevents odd/even page header desync, and ensures footer text never wraps across lines.
- 🖨️ **100% Open-Source PDF Compilation:** Converts documents to publication-grade PDFs via headless LibreOffice without requiring any paid or proprietary software.
- 🔍 **Automated 5-Gate PDF QA Auditor:** Verifies every generated PDF against 5 strict acceptance criteria before you submit it to your teacher.
- 📱 **Mobile & Cloud Ready (Google Colab):** Classmates without computers can run the complete pipeline directly on their Android or iPhone in a mobile web browser.
- 🤖 **Zero-Touch Agentic Integration:** Fully executable via AI agents (Antigravity, Gemini CLI, Claude Code, Cursor) using the `/labforge` slash command.

---

## 🛠️ The 7 Solved OOXML Layout Bugs

Standard Word automation tools produce broken layouts because Microsoft Word hides formatting overrides in low-level XML. LabForge resolves all 7 root causes:

| Bug | Root Cause in Word OpenXML | LabForge Engine Fix |
|---|---|---|
| **1. Hanging Step Numbers** | Native `<w:numPr>` list numbering pushes step numbers 2 inches toward the center. | Preserves literal number prefix, strips `<w:numPr>` and `<w:tabs>`, applies clean 0.3" hanging indent. |
| **2. Congested Spacing** | Word's `<w:contextualSpacing/>` silently cancels out paragraph margins. | Injects `<w:contextualSpacing w:val="0"/>` and enforces explicit vertical buffers (`Pt(16)` before / `Pt(12)` after). |
| **3. Off-Center Images** | Inserted image paragraphs inherit preceding list indentations. | Resets paragraph to `Normal` style, zeros horizontal indents, and enforces true page centering. |
| **4. Orphaned Step Text** | Empty spacer paragraphs glue step text to bottom of page. | Cleans spacer elements and binds step text to its screenshot via `keep_with_next=True` and `keep_together=True`. |
| **5. Split Multi-Bullet Steps** | Inserting images directly after step intro splits sub-bullets (`a, b, c, d`). | VisionTarget maps screenshots strictly after the final sub-bullet, keeping all explanations grouped. |
| **6. Distorted / Page-Breaking Images** | Fixed image heights or single width limits cause dialog blowouts or tiny thumbnails. | Aspect-ratio bounding boxes (5.80"×2.65" widescreen, 4.80"×2.60" dialogs, 4.80"×2.00" output) with 1px black borders. |
| **7. Doubled Headers & Broken Footers** | `odd_and_even_pages_header_footer` duplicates headers and wraps text across lines. | Unifies sections, dynamically inserts `<w:fldSimple w:instr="PAGE">`, and expands footer textboxes with non-breaking hyphens. |

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python 3.10+**
- **LibreOffice** (required for headless `.docx` → `.pdf` conversion)
  - Windows: Default path `C:\Program Files\LibreOffice\program\soffice.exe`
  - Linux: `sudo apt install libreoffice`
  - macOS: `brew install --cask libreoffice`

### 2. Installation
```bash
git clone https://github.com/cid-moosa/labforge.git
cd labforge
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### 3. Usage (CLI)

```bash
# 1. Scan and inspect unbuilt lab folders:
python scripts/inspect_record.py --scan

# 2. Inspect a specific lab document and catalog screenshots:
python scripts/inspect_record.py --dir "input/my_lab" --out "mappings/my_lab_inspection.json"

# 3. Execute LabForge engine:
python scripts/labforge_engine.py --docx "input/my_lab/record.docx" --mapping "mappings/my_lab_map.json" --out "output/my_lab/record - Final.docx"

# 4. Audit the generated PDF against all 5 quality acceptance gates:
python scripts/verify_pdf.py --pdf "output/my_lab/final/record - Final.pdf" --mapping "mappings/my_lab_map.json"
```

---

## 📱 Running on Phone / Mobile (No Computer Needed)

If your classmates or friends don't have a PC or laptop, they can run Project LabForge directly inside their smartphone web browser (Chrome, Safari, Firefox) via Google's free cloud environment:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/cid-moosa/labforge/blob/main/LabForge_Mobile.ipynb)

### 📲 Step-by-Step Mobile Instructions:
1. Tap the **Open in Colab** badge above on your smartphone.
2. Tap the **Play (▶)** button on **Step 1 & Step 2** to initialize cloud LibreOffice and Python.
3. In **Step 3**, tap **Choose Files** to upload your unformatted lab `.docx` and screenshots from your phone gallery/storage.
4. In **Step 4**, enter your free Google Gemini API key ([aistudio.google.com/apikey](https://aistudio.google.com/apikey)) so AI vision maps the images to the right procedure steps.
5. In **Step 5 & Step 6**, the engine formats the document and automatically downloads the finished `.docx` and `.pdf` directly to your phone's Downloads folder!

---

## 🤖 AI Agent Integration (/labforge)

Project LabForge includes a pre-packaged AI Agent skill in `.agents/skills/labforge/SKILL.md`.

Whenever you work with an AI assistant (Google Antigravity, Gemini CLI, Claude Code, or Cursor), simply invoke:
```text
/labforge
```
The agent reads the skill standard, inspects screenshots using vision, generates the coordinate mapping, builds the formatted `.docx`, auto-converts to `.pdf`, and outputs a verified QA audit report autonomously.

---

## 📋 The 5-Gate Automated PDF Audit

Every generated PDF is audited against 5 non-negotiable acceptance criteria:

1. **Zero Trailing Blank Page**: Verifies the final page contains genuine body/output content.
2. **Zero Orphaned Steps**: Confirms no procedure step text sits stranded at the bottom of a page without its screenshot.
3. **Sequential Page Headers**: Validates dynamic sequential page numbering (`1 | Page` through `N | Page`).
4. **All Screenshots Accounted For**: Verifies all curated screenshots are properly embedded in the PDF.
5. **Footer Single-Line Format**: Validates that institution name and academic year text remain strictly on a single line.

---

## 📂 Project Structure

```text
labforge/
├── .agents/
│   └── skills/
│       └── labforge/
│           └── SKILL.md            # AI Agent Skill Definition
├── scripts/
│   ├── labforge_engine.py         # Core OOXML Alignment & PDF Engine (LayoutEngine)
│   ├── inspect_record.py          # Document & Screenshot Inspector (VisionTarget)
│   ├── verify_pdf.py              # 5-Gate PyMuPDF Quality Auditor
│   └── inject_images.py           # Backward-compatible wrapper
├── mappings/                      # Versioned JSON image-to-paragraph mappings
├── pyproject.toml                 # Standard Python package configuration
├── requirements.txt               # Dependencies
├── CONTRIBUTING.md                # Contribution Guidelines
├── LICENSE                        # MIT License
└── README.md                      # Project Documentation
```

---

## 📄 License

Distributed under the [MIT License](LICENSE). Copyright (c) 2026 cid-moosa.
