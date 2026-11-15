#!/usr/bin/env python3
"""
labforge.qa_audit
PyMuPDF 5-Gate Quality Assurance Auditor for Project LabForge.
"""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.verify_pdf import (
    main,
    audit_pdf,
)

if __name__ == "__main__":
    main()

