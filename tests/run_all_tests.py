#!/usr/bin/env python3
"""
tests/run_all_tests.py
Master test runner for Project LabForge with automated SHA-256 production preservation verification.
"""

import os
import sys
import time
import unittest

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.helpers.integrity import (
    BASELINE_ENGINE_SHA256,
    EXPECTED_INPUT_COUNT,
    EXPECTED_OUTPUT_COUNT,
    INPUT_DIR,
    LOCKED_ENGINE_FILE,
    OUTPUT_DIR,
    hash_file,
    snapshot_directory_hashes,
    verify_directory_integrity,
)


def run_full_suite() -> int:
    print("=" * 80)
    print(" Project LabForge: Comprehensive Test Suite & Integrity Verification")
    print("=" * 80)

    # 1. Pre-test integrity snapshots
    print("\n[Phase 1] Capturing Pre-Test Production Integrity Baselines...")
    pre_engine_hash = hash_file(LOCKED_ENGINE_FILE)
    if pre_engine_hash != BASELINE_ENGINE_SHA256:
        print(f"FATAL: {LOCKED_ENGINE_FILE} baseline hash mismatch before running tests!", file=sys.stderr)
        return 1

    pre_input_hashes = snapshot_directory_hashes(INPUT_DIR)
    pre_output_hashes = snapshot_directory_hashes(OUTPUT_DIR)

    print(f"  * {LOCKED_ENGINE_FILE}: SHA-256 verified ({pre_engine_hash[:16]}...)")
    print(f"  * {INPUT_DIR}/: {len(pre_input_hashes)} production files hashed (expected {EXPECTED_INPUT_COUNT})")
    print(f"  * {OUTPUT_DIR}/: {len(pre_output_hashes)} production files hashed (expected {EXPECTED_OUTPUT_COUNT})")

    if len(pre_input_hashes) != EXPECTED_INPUT_COUNT:
        print(f"FATAL: Expected {EXPECTED_INPUT_COUNT} files in {INPUT_DIR}, found {len(pre_input_hashes)}!", file=sys.stderr)
        return 1
    if len(pre_output_hashes) != EXPECTED_OUTPUT_COUNT:
        print(f"FATAL: Expected {EXPECTED_OUTPUT_COUNT} files in {OUTPUT_DIR}, found {len(pre_output_hashes)}!", file=sys.stderr)
        return 1

    # 2. Run Test Discovery & Execution
    print("\n[Phase 2] Discovering & Executing Isolated Unit Tests...")
    start_time = time.time()

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    test_result = runner.run(suite)

    duration = time.time() - start_time
    print(f"\nTest execution finished in {duration:.2f} seconds.")

    # 3. Post-test integrity verification
    print("\n[Phase 3] Verifying Post-Test Production Work Preservation (Requirement R3)...")

    # Verify engine
    post_engine_hash = hash_file(LOCKED_ENGINE_FILE)
    if post_engine_hash != pre_engine_hash:
        print(f"INTEGRITY VIOLATION: {LOCKED_ENGINE_FILE} was modified during tests!", file=sys.stderr)
        return 1

    # Verify input directory
    input_intact, input_diffs = verify_directory_integrity(INPUT_DIR, pre_input_hashes)
    if not input_intact:
        print(f"INTEGRITY VIOLATION in {INPUT_DIR}:", file=sys.stderr)
        for diff in input_diffs:
            print(f"  - {diff}", file=sys.stderr)
        return 1

    # Verify output directory
    output_intact, output_diffs = verify_directory_integrity(OUTPUT_DIR, pre_output_hashes)
    if not output_intact:
        print(f"INTEGRITY VIOLATION in {OUTPUT_DIR}:", file=sys.stderr)
        for diff in output_diffs:
            print(f"  - {diff}", file=sys.stderr)
        return 1

    print("  * scripts/labforge_engine.py: 100% UNTOUCHED (SHA-256 match)")
    print(f"  * input/ ({EXPECTED_INPUT_COUNT} files): 100% UNTOUCHED (SHA-256 match)")
    print(f"  * output/ ({EXPECTED_OUTPUT_COUNT} files): 100% UNTOUCHED (SHA-256 match)")

    # 4. Final summary
    print("\n" + "=" * 80)
    print(" Summary of Verification Results")
    print("=" * 80)
    print(f"  Total Tests Executed: {test_result.testsRun}")
    print(f"  Passed:               {test_result.testsRun - len(test_result.failures) - len(test_result.errors)}")
    print(f"  Failures:             {len(test_result.failures)}")
    print(f"  Errors:               {len(test_result.errors)}")
    print(f"  Production Preserved: 100% (122 files verified via SHA-256)")
    print("=" * 80)

    if test_result.wasSuccessful() and input_intact and output_intact:
        print("\nALL TESTS PASSED & INTEGRITY FULLY PRESERVED.\n")
        return 0
    else:
        print("\nTEST SUITE FAILED.\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(run_full_suite())
