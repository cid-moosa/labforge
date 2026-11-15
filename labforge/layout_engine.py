#!/usr/bin/env python3
"""
labforge.layout_engine
Precision OOXML Alignment and PDF Generation Engine for Project LabForge.
"""

import sys
import os

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.labforge_engine import (
    main,
    build_aligned_record,
    convert_docx_to_pdf,
    calculate_image_dimensions,
    fix_header_and_footer,
    ensure_college_headers_and_footers,
)

if __name__ == "__main__":
    main()
