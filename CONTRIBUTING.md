# Contributing to Project LabForge

Thank you for your interest in contributing to **Project LabForge**! 

Project LabForge is an autonomous lab record automation engine designed to produce teacher-grade academic records on the first pass without manual formatting adjustments.

---

## Code of Conduct & Architectural Guardrails

When contributing code, mappings, or features, you must uphold the core architectural contracts:

1. **SourceGuard (Zero Text Edits):**
   - Source documents in `input/` are strictly **READ-ONLY**.
   - Never edit, rewrite, delete, or spellcheck the source text. Formatting must adapt to the text, never the reverse.

2. **The 7 Mandatory OOXML Rules:**
   - Every layout fix must operate at the OpenXML (`wordprocessingML`) level.
   - Do not rely on high-level UI assumptions; test against raw OpenXML structures (`w:pPr`, `w:numPr`, `w:contextualSpacing`, `w:fldSimple`).

3. **Truthful Verification:**
   - Never submit code that produces failing gates in `scripts/verify_pdf.py`. All PRs must pass the 5 automated QA gates.

---

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/cid-moosa/labforge.git
   cd labforge
   ```

2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e .
   ```

3. **Install LibreOffice:**
   - PDF generation requires LibreOffice installed and accessible on PATH (or at `C:\Program Files\LibreOffice\program\soffice.exe` on Windows).

---

## Testing Your Changes

Run the full end-to-end alignment and PDF verification pipeline:

```bash
# 1. Run LabForge engine on a lab document:
python scripts/labforge_engine.py --docx "input/lab 1/ftk/IDFT Lab 1 FTK Imager.docx" --mapping "mappings/lab1_map.json" --out "output/lab 1/IDFT Lab 1 FTK Imager - Final.docx"

# 2. Audit generated PDF against the 5 acceptance gates:
python scripts/verify_pdf.py --pdf "output/lab 1/final/IDFT Lab 1 FTK Imager - Final.pdf" --mapping "mappings/lab1_map.json"
```

Verify that all 5 gates pass:
- Zero trailing blank page
- Zero orphaned steps
- Sequential page headers
- All screenshots accounted for
- Footer single-line format

---

## Submitting Pull Requests

1. Fork the repo and create a feature branch (`git checkout -b feature/new-lab-mapping`).
2. Commit changes with clear imperative messages (`git commit -m "Add automated mapping for Lab 3"`).
3. Ensure `.gitignore` and local workspace memories are never committed.
4. Push to your fork and submit a Pull Request!
