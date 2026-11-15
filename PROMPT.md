# 🤖 Project LabForge: The One-Shot AI Setup & Runner Prompt

Copy and paste the prompt below into **Google Antigravity**, **Gemini CLI**, **Claude Code**, **Cursor**, or **ChatGPT/Copilot**. 

The AI agent will automatically clone the repository, set up the virtual environment, install dependencies, verify LibreOffice, scan your `input/` folder, map screenshots using multimodal vision, and output teacher-approved `.docx` and `.pdf` files into `output/<lab_folder>/final/`!

---

### 📋 Copy & Paste This Prompt:

```text
You are an autonomous engineering agent executing Project LabForge (https://github.com/cid-moosa/labforge).

Goal: Set up the Project LabForge engine, discover all lab folders in input/, and autonomously generate teacher-grade practical lab records (.docx and verified .pdf) with zero manual formatting.

Execute these steps autonomously without asking intermediate questions:

1. ENVIRONMENT & REPOSITORY SETUP:
   - Check if the current directory is the LabForge repository. If not, clone it:
     git clone https://github.com/cid-moosa/labforge.git && cd labforge
   - Verify Python 3.10+ is installed.
   - Set up a virtual environment (.venv) and install dependencies:
     python -m venv .venv
     .venv/Scripts/pip install -r requirements.txt (or source .venv/bin/activate && pip install -r requirements.txt on Linux/macOS)
   - Verify LibreOffice is installed (required for headless PDF export). If missing on Windows, prompt to install via: winget install TheDocumentFoundation.LibreOffice. On Linux: sudo apt install -y libreoffice.

2. INPUT SCAN & DISCOVERY:
   - Check the 'input/' folder for subdirectories (e.g. 'input/lab 1', 'input/lab 2', 'input/lab 4').
   - If 'input/' is empty or has no folders, create 'input/' and inform me: "Please place your lab folders (each containing your teacher's .docx template and raw screenshots) inside 'input/', then tell me to continue."
   - Run the automated cataloger: python scripts/inspect_record.py --scan

3. MULTIMODAL VISION TARGETING (VisionTarget):
   - For every lab folder that contains screenshots, inspect the procedure steps in the .docx template and all raw images.
   - Use multimodal vision to map each screenshot to its exact target paragraph index in the .docx:
     * Filter out transient loading screens or splash screens (keep only definitive action/result captures).
     * If a procedure step has sub-bullets (a, b, c, d), always map the screenshot AFTER the final sub-bullet.
     * Map completed integrity hashes, info files, or finished status screenshots to the OUTPUT section.
   - Save the coordinate map to 'mappings/<lab_name>_map.json'.

4. PRECISION OPENXML ALIGNMENT & PDF GENERATION (LayoutEngine):
   - Execute the LabForge engine:
     python scripts/labforge_engine.py --docx "input/<lab_folder>/<record>.docx" --mapping "mappings/<lab_name>_map.json" --out "output/<lab_folder>/<record> - Final.docx"
   - This applies the 7 locked layout rules:
     * Unhangs list steps by removing <w:numPr> and applying clean 0.3" hanging indents.
     * Removes <w:contextualSpacing/> and enforces explicit vertical buffers.
     * Resets images to Normal style with 0 pt margins and page centering.
     * Glues step text to screenshots with keep_with_next=True.
     * Wraps screenshots in 1px solid black borders and scales aspect-ratio bounding boxes (5.80" widescreen, 4.80" dialogs).
     * Injects dynamic PAGE numbers (<w:fldSimple w:instr="PAGE">) and unifies single-line footers.
     * Automatically compiles the PDF via headless LibreOffice directly into 'output/<lab_folder>/final/<record> - Final.pdf'.

5. AUTOMATED 5-GATE QA AUDIT:
   - Run the PyMuPDF auditor:
     python scripts/verify_pdf.py --pdf "output/<lab_folder>/final/<record> - Final.pdf" --mapping "mappings/<lab_name>_map.json"
   - Confirm all 5 gates pass: zero trailing blank pages, zero orphaned steps, sequential headers, all screenshots present, and unbroken footers.

Present the final deliverable links (output/<lab_folder>/final/<record> - Final.pdf) and the QA audit report.
```
