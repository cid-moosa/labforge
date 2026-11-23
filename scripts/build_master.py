#!/usr/bin/env python3
"""
scripts/build_master.py
Project LabForge: Master Record Builder entry point and alias to build_master_records.py.
"""

import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.build_master_records import assemble_master_record, build_all_master_records, STUDENTS


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target == "all":
        build_all_master_records()
    elif target in STUDENTS:
        assemble_master_record(target)
    else:
        print(f"Unknown target: {target}. Choices: {list(STUDENTS.keys())} or 'all'")
        sys.exit(1)


if __name__ == "__main__":
    main()
