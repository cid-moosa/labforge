"""
tests/test_text_verifier.py
Comprehensive unit test suite for scripts/text_verifier.py (Requirement R2).
Tests scanning, format preservation, interactive prompting, and permission gating.
Executes strictly in isolated temporary directories using synthetic test documents.
"""

import io
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import docx

from scripts.text_verifier import (
    DEFAULT_RULES,
    VerificationRule,
    apply_replacements_to_paragraph,
    format_context_diff,
    load_rules,
    main as text_verifier_main,
    parse_args,
    scan_document,
    verify_and_correct_document,
)
from tests.helpers.integrity import (
    BASELINE_ENGINE_SHA256,
    LOCKED_ENGINE_FILE,
    assert_safe_test_path,
    hash_file,
)
from tests.helpers.sample_factory import create_synthetic_docx


class TestTextVerifier(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_txt_verifier_")
        assert_safe_test_path(self.temp_dir)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scan_detects_paragraphs_and_tables(self):
        doc_path = os.path.join(self.temp_dir, "standard.docx")
        create_synthetic_docx(doc_path, scenario="standard")

        doc, occurrences = scan_document(doc_path)

        # Standard document contains occurrences in paragraphs and table
        self.assertGreaterEqual(len(occurrences), 3)

        # Verify occurrence attributes
        body_matches = [o for o in occurrences if o.location_type == "body"]
        table_matches = [o for o in occurrences if o.location_type == "table"]

        self.assertGreaterEqual(len(body_matches), 2)
        self.assertGreaterEqual(len(table_matches), 1)

        first = occurrences[0]
        self.assertIn("Ubuntu", first.matched_text)
        self.assertEqual(first.proposed_replacement, "Kali Linux")
        self.assertIsNotNone(first.paragraph_obj)
        self.assertGreaterEqual(first.start_char, 0)
        self.assertGreater(first.end_char, first.start_char)

    def test_scan_clean_document_zero_discrepancies(self):
        clean_path = os.path.join(self.temp_dir, "clean.docx")
        create_synthetic_docx(clean_path, scenario="clean")

        doc, occurrences = scan_document(clean_path)
        self.assertEqual(len(occurrences), 0)

        # Test verify_and_correct_document on clean document
        summary = verify_and_correct_document(clean_path)
        self.assertEqual(summary["total_found"], 0)
        self.assertEqual(summary["approved"], 0)
        self.assertEqual(summary["saved"], False)

    def test_merged_table_cells_deduplication(self):
        merged_path = os.path.join(self.temp_dir, "merged.docx")
        create_synthetic_docx(merged_path, scenario="table_merged")

        doc, occurrences = scan_document(merged_path)
        # Should detect occurrences in unique cells only, not multiple times for merged spans
        table_matches = [o for o in occurrences if o.location_type == "table"]
        labels = [o.location_label for o in table_matches]
        self.assertEqual(len(labels), len(set(labels)), "Duplicate alerts emitted for merged cells!")

    def test_header_footer_detection(self):
        hf_path = os.path.join(self.temp_dir, "header_footer.docx")
        create_synthetic_docx(hf_path, scenario="header_footer")

        doc, occurrences = scan_document(hf_path)
        header_matches = [o for o in occurrences if o.location_type == "header"]
        footer_matches = [o for o in occurrences if o.location_type == "footer"]

        self.assertEqual(len(header_matches), 1)
        self.assertEqual(len(footer_matches), 1)
        self.assertIn("Ubuntu", header_matches[0].matched_text)
        self.assertIn("Ubuntu", footer_matches[0].matched_text)

    def test_format_preserving_single_run(self):
        doc = docx.Document()
        p = doc.add_paragraph()
        r0 = p.add_run("Start on ")
        r1 = p.add_run("Ubuntu")
        r1.bold = True
        r1.italic = True
        r1.font.name = "Arial"
        r2 = p.add_run(" system now.")

        # Match for 'Ubuntu' is at char 9 to 15
        text_before = p.text
        self.assertEqual(text_before, "Start on Ubuntu system now.")
        s_idx = text_before.index("Ubuntu")
        e_idx = s_idx + len("Ubuntu")

        count = apply_replacements_to_paragraph(p, [(s_idx, e_idx, "Kali Linux")])
        self.assertEqual(count, 1)
        self.assertEqual(p.text, "Start on Kali Linux system now.")

        # Verify formatting on run 1 was preserved
        runs = p.runs
        self.assertTrue(runs[1].bold)
        self.assertTrue(runs[1].italic)
        self.assertEqual(runs[1].font.name, "Arial")
        self.assertEqual(runs[1].text, "Kali Linux")

    def test_format_preserving_split_runs(self):
        doc = docx.Document()
        p = doc.add_paragraph()
        r0 = p.add_run("Launch ")
        r1 = p.add_run("Ub")
        r2 = p.add_run("untu")
        r2.bold = True
        r3 = p.add_run(" today.")

        text_before = p.text
        self.assertEqual(text_before, "Launch Ubuntu today.")
        s_idx = text_before.index("Ubuntu")
        e_idx = s_idx + len("Ubuntu")

        count = apply_replacements_to_paragraph(p, [(s_idx, e_idx, "Kali Linux")])
        self.assertEqual(count, 1)
        self.assertEqual(p.text, "Launch Kali Linux today.")

        # End run trailing text retained its styling
        self.assertEqual(p.runs[0].text, "Launch ")
        self.assertEqual(p.runs[1].text, "Kali Linux")
        self.assertEqual(p.runs[2].text, "")
        self.assertEqual(p.runs[3].text, " today.")

    def test_format_preserving_multiple_in_one_paragraph(self):
        doc = docx.Document()
        p = doc.add_paragraph("Use Ubuntu first and then configure Ubuntu later.")
        s1 = 4
        e1 = 10
        s2 = 36
        e2 = 42

        # Apply both replacements
        count = apply_replacements_to_paragraph(p, [(s1, e1, "Kali Linux"), (s2, e2, "Kali Linux")])
        self.assertEqual(count, 2)
        self.assertEqual(p.text, "Use Kali Linux first and then configure Kali Linux later.")

    def test_user_rejection_leaves_file_untouched(self):
        doc_path = os.path.join(self.temp_dir, "test_reject.docx")
        create_synthetic_docx(doc_path, scenario="standard")
        initial_hash = hash_file(doc_path)

        # Mock user entering 'n' (Reject/Skip)
        mock_input = lambda prompt: "n"

        summary = verify_and_correct_document(
            docx_path=doc_path,
            in_place=True,
            input_func=mock_input,
        )

        self.assertEqual(summary["approved"], 0)
        self.assertGreater(summary["skipped"], 0)
        self.assertFalse(summary["saved"])

        # File hash must be 100% identical!
        post_hash = hash_file(doc_path)
        self.assertEqual(initial_hash, post_hash, "File was modified despite user rejection!")

    def test_user_default_enter_leaves_file_untouched(self):
        doc_path = os.path.join(self.temp_dir, "test_default.docx")
        create_synthetic_docx(doc_path, scenario="standard")
        initial_hash = hash_file(doc_path)

        # User presses Enter without typing anything (empty string) -> default is 'n'
        mock_input = lambda prompt: ""

        summary = verify_and_correct_document(
            docx_path=doc_path,
            in_place=True,
            input_func=mock_input,
        )

        self.assertEqual(summary["approved"], 0)
        self.assertFalse(summary["saved"])
        self.assertEqual(initial_hash, hash_file(doc_path))

    def test_user_approval_updates_file(self):
        doc_path = os.path.join(self.temp_dir, "test_approve.docx")
        out_path = os.path.join(self.temp_dir, "corrected.docx")
        create_synthetic_docx(doc_path, scenario="standard")

        # Mock user entering 'y' (Approve)
        mock_input = lambda prompt: "y"

        summary = verify_and_correct_document(
            docx_path=doc_path,
            out_path=out_path,
            input_func=mock_input,
        )

        self.assertGreater(summary["approved"], 0)
        self.assertEqual(summary["skipped"], 0)
        self.assertTrue(summary["saved"])
        self.assertTrue(os.path.isfile(out_path))

        # Verify output document text contains Kali Linux instead of Ubuntu
        updated_doc = docx.Document(out_path)
        all_text = " ".join(p.text for p in updated_doc.paragraphs)
        self.assertIn("Kali Linux", all_text)
        self.assertNotIn("Ubuntu", all_text)

    def test_selective_approval_mixed(self):
        doc_path = os.path.join(self.temp_dir, "test_selective.docx")
        out_path = os.path.join(self.temp_dir, "selective_out.docx")
        create_synthetic_docx(doc_path, scenario="multiple")  # 4 occurrences

        # Approve 1 and 3, skip 2 and 4
        responses = ["y", "n", "y", "n"]
        resp_iter = iter(responses)
        mock_input = lambda prompt: next(resp_iter)

        summary = verify_and_correct_document(
            docx_path=doc_path,
            out_path=out_path,
            input_func=mock_input,
        )

        self.assertEqual(summary["total_found"], 4)
        self.assertEqual(summary["approved"], 2)
        self.assertEqual(summary["skipped"], 2)
        self.assertTrue(summary["saved"])

        # Check content in saved doc
        updated_doc = docx.Document(out_path)
        p_texts = [p.text for p in updated_doc.paragraphs if p.text.startswith("Occurrence")]
        self.assertIn("Kali Linux", p_texts[0])
        self.assertIn("Ubuntu", p_texts[1])
        self.assertIn("Kali Linux", p_texts[2])
        self.assertIn("Ubuntu", p_texts[3])

    def test_user_approval_all_flag(self):
        doc_path = os.path.join(self.temp_dir, "test_all.docx")
        out_path = os.path.join(self.temp_dir, "all_out.docx")
        create_synthetic_docx(doc_path, scenario="multiple")  # 4 occurrences

        # Enter 'a' on first prompt -> auto-approves all remaining
        prompts_called = 0

        def mock_input(prompt):
            nonlocal prompts_called
            prompts_called += 1
            return "a"

        summary = verify_and_correct_document(
            docx_path=doc_path,
            out_path=out_path,
            input_func=mock_input,
        )

        self.assertEqual(summary["total_found"], 4)
        self.assertEqual(summary["approved"], 4)
        self.assertEqual(summary["skipped"], 0)
        self.assertEqual(prompts_called, 1, "Prompt should only be called once when 'a' is chosen!")

    def test_user_quit_aborts_early(self):
        doc_path = os.path.join(self.temp_dir, "test_quit.docx")
        out_path = os.path.join(self.temp_dir, "quit_out.docx")
        create_synthetic_docx(doc_path, scenario="multiple")  # 4 occurrences

        # Enter 'y' on first, then 'q' on second
        responses = ["y", "q"]
        resp_iter = iter(responses)
        mock_input = lambda prompt: next(resp_iter)

        summary = verify_and_correct_document(
            docx_path=doc_path,
            out_path=out_path,
            input_func=mock_input,
        )

        self.assertEqual(summary["approved"], 1)
        self.assertEqual(summary["skipped"], 3)
        self.assertTrue(summary["saved"])

    def test_check_only_dry_run_mode(self):
        doc_path = os.path.join(self.temp_dir, "test_dry_run.docx")
        create_synthetic_docx(doc_path, scenario="standard")
        initial_hash = hash_file(doc_path)

        # Check-only must not prompt or write
        with patch("builtins.input", side_effect=Exception("input() called in check-only mode!")):
            summary = verify_and_correct_document(
                docx_path=doc_path,
                check_only=True,
            )

        self.assertGreater(summary["total_found"], 0)
        self.assertEqual(summary["approved"], 0)
        self.assertFalse(summary["saved"])
        self.assertEqual(initial_hash, hash_file(doc_path))

    def test_auto_approve_yes_mode(self):
        doc_path = os.path.join(self.temp_dir, "test_yes.docx")
        out_path = os.path.join(self.temp_dir, "yes_out.docx")
        create_synthetic_docx(doc_path, scenario="standard")

        # auto_approve=True must not prompt
        with patch("builtins.input", side_effect=Exception("input() called in auto-approve mode!")):
            summary = verify_and_correct_document(
                docx_path=doc_path,
                out_path=out_path,
                auto_approve=True,
            )

        self.assertGreater(summary["approved"], 0)
        self.assertTrue(summary["saved"])
        self.assertTrue(os.path.isfile(out_path))

    def test_in_place_with_backup(self):
        doc_path = os.path.join(self.temp_dir, "test_inplace.docx")
        create_synthetic_docx(doc_path, scenario="standard")
        initial_hash = hash_file(doc_path)

        summary = verify_and_correct_document(
            docx_path=doc_path,
            in_place=True,
            backup=True,
            auto_approve=True,
        )

        self.assertTrue(summary["saved"])
        bak_path = doc_path + ".bak"
        self.assertTrue(os.path.isfile(bak_path))
        self.assertEqual(hash_file(bak_path), initial_hash)
        self.assertNotEqual(hash_file(doc_path), initial_hash)

    def test_in_place_no_backup(self):
        doc_path = os.path.join(self.temp_dir, "test_nobak.docx")
        create_synthetic_docx(doc_path, scenario="standard")

        summary = verify_and_correct_document(
            docx_path=doc_path,
            in_place=True,
            backup=False,
            auto_approve=True,
        )

        self.assertTrue(summary["saved"])
        self.assertFalse(os.path.isfile(doc_path + ".bak"))

    def test_custom_regex_rule(self):
        doc = docx.Document()
        doc.add_paragraph("Replace foo with bar in this sentence.")
        custom_path = os.path.join(self.temp_dir, "custom.docx")
        out_path = os.path.join(self.temp_dir, "custom_out.docx")
        doc.save(custom_path)

        rules = load_rules(custom_find=r"\bfoo\b", custom_replace="bar")
        self.assertEqual(len(rules), 1)

        summary = verify_and_correct_document(
            docx_path=custom_path,
            out_path=out_path,
            rules=rules,
            auto_approve=True,
        )

        self.assertEqual(summary["total_found"], 1)
        self.assertEqual(summary["approved"], 1)

        updated_doc = docx.Document(out_path)
        self.assertIn("Replace bar with bar", updated_doc.paragraphs[0].text)

    def test_format_context_diff_output(self):
        doc_path = os.path.join(self.temp_dir, "diff_test.docx")
        create_synthetic_docx(doc_path, scenario="standard")
        _, occurrences = scan_document(doc_path)

        first = occurrences[0]
        diff_str = format_context_diff(first, use_color=False, context_lines=1)

        self.assertIn(first.location_label, diff_str)
        self.assertIn(first.matched_text, diff_str)
        self.assertIn(first.proposed_replacement, diff_str)
        self.assertIn(f"- {first.full_paragraph_text}", diff_str)
        self.assertIn("+ ", diff_str)

    def test_cli_parsing(self):
        args = parse_args([
            "--docx", "test.docx",
            "--out", "out.docx",
            "--yes",
            "--no-color",
            "--context-lines", "2",
        ])
        self.assertEqual(args.docx, "test.docx")
        self.assertEqual(args.out, "out.docx")
        self.assertTrue(args.yes)
        self.assertTrue(args.no_color)
        self.assertEqual(args.context_lines, 2)


if __name__ == "__main__":
    unittest.main()
