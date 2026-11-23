"""
tests/test_production_preservation.py
Requirement R3 Production Work Preservation Verification Suite.
Guarantees 100% preservation of all 100 files in input/, 22 files in output/,
and the 846-line locked engine scripts/labforge_engine.py via SHA-256 fingerprinting.
"""

import os
import tempfile
import unittest

from tests.helpers.integrity import (
    BASELINE_ENGINE_SHA256,
    EXPECTED_INPUT_COUNT,
    EXPECTED_OUTPUT_COUNT,
    INPUT_DIR,
    LOCKED_ENGINE_FILE,
    OUTPUT_DIR,
    assert_safe_test_path,
    hash_file,
    snapshot_directory_hashes,
    verify_directory_integrity,
)


class TestProductionPreservation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Establish pre-test baselines for production directories
        cls.input_baseline = snapshot_directory_hashes(INPUT_DIR)
        cls.output_baseline = snapshot_directory_hashes(OUTPUT_DIR)

    def test_input_file_count_and_hashes(self):
        """Verifies that input/ has exactly 100 files and none were modified or deleted."""
        current_hashes = snapshot_directory_hashes(INPUT_DIR)
        self.assertEqual(
            len(current_hashes),
            EXPECTED_INPUT_COUNT,
            f"Expected {EXPECTED_INPUT_COUNT} files in {INPUT_DIR}, found {len(current_hashes)}",
        )

        is_intact, differences = verify_directory_integrity(INPUT_DIR, self.input_baseline)
        self.assertTrue(
            is_intact,
            f"Production preservation violated in {INPUT_DIR}:\n" + "\n".join(differences),
        )

    def test_output_file_count_and_hashes(self):
        """Verifies that output/ has exactly 22 files and none were modified or deleted."""
        current_hashes = snapshot_directory_hashes(OUTPUT_DIR)
        self.assertEqual(
            len(current_hashes),
            EXPECTED_OUTPUT_COUNT,
            f"Expected {EXPECTED_OUTPUT_COUNT} files in {OUTPUT_DIR}, found {len(current_hashes)}",
        )

        is_intact, differences = verify_directory_integrity(OUTPUT_DIR, self.output_baseline)
        self.assertTrue(
            is_intact,
            f"Production preservation violated in {OUTPUT_DIR}:\n" + "\n".join(differences),
        )

    def test_engine_script_untouched(self):
        """Verifies scripts/labforge_engine.py has not been edited or altered."""
        self.assertTrue(os.path.isfile(LOCKED_ENGINE_FILE))

        with open(LOCKED_ENGINE_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1012, f"Expected 1012 lines in {LOCKED_ENGINE_FILE}, found {len(lines)}")

        current_hash = hash_file(LOCKED_ENGINE_FILE)
        self.assertEqual(
            current_hash,
            BASELINE_ENGINE_SHA256,
            f"Hash mismatch on {LOCKED_ENGINE_FILE}. File was altered!",
        )

    def test_assert_safe_test_path_rejects_production(self):
        """Verifies safety guard rejects any attempt to target production directories."""
        # Test input directory
        with self.assertRaises(PermissionError):
            assert_safe_test_path("input")
        with self.assertRaises(PermissionError):
            assert_safe_test_path("input/lab 1/test.docx")

        # Test output directory
        with self.assertRaises(PermissionError):
            assert_safe_test_path("output")
        with self.assertRaises(PermissionError):
            assert_safe_test_path("output/test_image.png")

        # Test engine file
        with self.assertRaises(PermissionError):
            assert_safe_test_path("scripts/labforge_engine.py")

    def test_assert_safe_test_path_accepts_temp(self):
        """Verifies safety guard permits temporary and test paths."""
        with tempfile.TemporaryDirectory() as td:
            # Should not raise
            assert_safe_test_path(td)
            assert_safe_test_path(os.path.join(td, "subfile.docx"))


if __name__ == "__main__":
    unittest.main()
