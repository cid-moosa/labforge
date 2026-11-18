#!/usr/bin/env python3
"""
scripts/text_verifier.py
Document Text Verification & Interactive Permission-Alerting Tool for Project LabForge.

Scans .docx documents for target keyword discrepancies (e.g. Ubuntu vs. Kali Linux)
across body paragraphs, tables, headers, footers, and textboxes.
Presents interactive terminal diff alerts and requires explicit user permission
before applying any modifications. Preserves 100% of run-level formatting.
"""

import argparse
import difflib
import json
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.text.run import Run


# ANSI Color Codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


@dataclass
class VerificationRule:
    """Defines a discrepancy rule."""

    rule_id: str
    pattern: str  # Regex pattern, e.g. r"\b[Uu]buntu(?:\s+[Ll]inux)?\b"
    replacement: str  # Replacement string, e.g. "Kali Linux"
    description: str
    case_sensitive: bool = False


@dataclass
class DiscrepancyOccurrence:
    """Represents a single detected discrepancy instance."""

    occurrence_id: int
    rule_id: str
    rule_description: str
    location_type: str  # "body", "table", "header", "footer", "textbox"
    location_label: str  # e.g. "Body Paragraph #6", "Table 0 [Row 1, Col 2]"
    paragraph_index: Optional[int]
    paragraph_obj: Any  # docx Paragraph object
    full_paragraph_text: str
    matched_text: str  # Exact matched substring, e.g. "ubuntu"
    start_char: int  # Global character start offset in paragraph
    end_char: int  # Global character end offset in paragraph
    proposed_replacement: str  # e.g. "Kali Linux"
    surrounding_before: str  # Previous paragraph context
    surrounding_after: str  # Next paragraph context
    status: str = "PENDING"  # "PENDING", "APPROVED", "SKIPPED", "REJECTED"


DEFAULT_RULES = [
    VerificationRule(
        rule_id="ubuntu-to-kali",
        pattern=r"\b[Uu]buntu(?:\s+[Ll]inux)?\b",
        replacement="Kali Linux",
        description="References to Ubuntu where Kali Linux is required",
        case_sensitive=False,
    )
]


def load_rules(
    preset: str = "forensics",
    custom_find: Optional[str] = None,
    custom_replace: Optional[str] = None,
    rules_file: Optional[str] = None,
) -> List[VerificationRule]:
    """Loads verification rules based on presets, custom arguments, or JSON config."""
    rules: List[VerificationRule] = []

    if custom_find and custom_replace is not None:
        rules.append(
            VerificationRule(
                rule_id="custom-rule",
                pattern=custom_find,
                replacement=custom_replace,
                description=f"Custom: '{custom_find}' -> '{custom_replace}'",
            )
        )
        return rules

    if rules_file and os.path.isfile(rules_file):
        with open(rules_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                rules.append(
                    VerificationRule(
                        rule_id=item.get("rule_id", "rule"),
                        pattern=item["pattern"],
                        replacement=item["replacement"],
                        description=item.get("description", ""),
                        case_sensitive=item.get("case_sensitive", False),
                    )
                )
        return rules

    # Default preset: forensics
    rules.extend(DEFAULT_RULES)
    return rules


def set_run_text_safe(run: Run, new_text: str) -> None:
    """
    Sets text of run by updating or creating <w:t> without removing <w:drawing> or other children.
    Preserves whitespace via xml:space='preserve'.
    """
    t_tag = qn("w:t")
    t_elements = run._r.findall(t_tag)
    if t_elements:
        t_elements[0].text = new_text
        for extra in t_elements[1:]:
            run._r.remove(extra)
    else:
        t = OxmlElement("w:t")
        t.text = new_text
        run._r.append(t)

    if new_text and (new_text.startswith(" ") or new_text.endswith(" ")):
        t_elem = run._r.find(t_tag)
        if t_elem is not None:
            t_elem.set(qn("xml:space"), "preserve")


def clear_run_text_safe(run: Run) -> None:
    """Clears only <w:t> elements from a run, keeping any <w:drawing> intact."""
    t_tag = qn("w:t")
    for t_elem in run._r.findall(t_tag):
        run._r.remove(t_elem)


def apply_replacements_to_paragraph(
    paragraph: Paragraph,
    approved_matches: List[Tuple[int, int, str]],
) -> int:
    """
    Applies approved text replacements to a paragraph while preserving 100% of
    run styles, font names, bold, italic, colors, and XML drawing objects.

    Args:
        paragraph: python-docx Paragraph object.
        approved_matches: List of tuples (start_char, end_char, replacement_str).
                          Assumes character indices correspond to paragraph's original text.

    Returns:
        Number of replacements successfully applied.
    """
    if not approved_matches:
        return 0

    runs = [Run(r, paragraph) for r in paragraph._p.xpath(".//w:r")]
    if not runs:
        return 0

    # Build character-to-run coordinate map: char_idx -> (run_idx, offset_in_run)
    char_map: List[Tuple[int, int]] = []
    for r_idx, r in enumerate(runs):
        t = r.text or ""
        for c_idx in range(len(t)):
            char_map.append((r_idx, c_idx))

    if not char_map:
        return 0

    # Sort approved matches in REVERSE order by start_char
    # This guarantees earlier character coordinates remain invariant!
    sorted_matches = sorted(approved_matches, key=lambda m: m[0], reverse=True)
    applied_count = 0

    for s_idx, e_idx, repl in sorted_matches:
        if s_idx >= len(char_map) or (e_idx - 1) >= len(char_map):
            continue

        r_start, c_start = char_map[s_idx]
        r_end, c_end = char_map[e_idx - 1]

        if r_start == r_end:
            # Case A: Match is fully contained within a single run
            r = runs[r_start]
            orig_text = r.text or ""
            new_run_text = orig_text[:c_start] + repl + orig_text[c_end + 1 :]
            set_run_text_safe(r, new_run_text)
        else:
            # Case B: Match spans across multiple runs
            # 1. Update first run with prefix + full replacement
            r_first = runs[r_start]
            orig_first = r_first.text or ""
            set_run_text_safe(r_first, orig_first[:c_start] + repl)

            # 2. Clear text in intermediate runs without stripping drawings
            for mid in range(r_start + 1, r_end):
                clear_run_text_safe(runs[mid])

            # 3. Update end run with suffix
            r_last = runs[r_end]
            orig_last = r_last.text or ""
            set_run_text_safe(r_last, orig_last[c_end + 1 :])

        applied_count += 1

    return applied_count


def scan_document(
    docx_path: str,
    rules: Optional[List[VerificationRule]] = None,
) -> Tuple[docx.Document, List[DiscrepancyOccurrence]]:
    """
    Scans a .docx document across body paragraphs, tables (merged-deduped),
    headers, footers, and textboxes for rule discrepancies.
    """
    if not os.path.isfile(docx_path):
        raise FileNotFoundError(f"Document not found: {docx_path}")

    doc = docx.Document(docx_path)
    active_rules = rules or DEFAULT_RULES
    discrepancies: List[DiscrepancyOccurrence] = []
    occurrence_counter = 1

    seen_paragraphs: Set[Any] = set()

    # Helper function to scan a paragraph
    def check_paragraph(
        p: Paragraph,
        loc_type: str,
        loc_label: str,
        p_idx: Optional[int],
        prev_text: str = "",
        next_text: str = "",
    ):
        nonlocal occurrence_counter
        p_elem = p._p
        if p_elem in seen_paragraphs:
            return
        seen_paragraphs.add(p_elem)

        full_text = p.text or ""
        if not full_text.strip():
            return

        for rule in active_rules:
            flags = 0 if rule.case_sensitive else re.IGNORECASE
            for match in re.finditer(rule.pattern, full_text, flags):
                s_char, e_char = match.span()
                matched_str = match.group(0)

                occ = DiscrepancyOccurrence(
                    occurrence_id=occurrence_counter,
                    rule_id=rule.rule_id,
                    rule_description=rule.description,
                    location_type=loc_type,
                    location_label=loc_label,
                    paragraph_index=p_idx,
                    paragraph_obj=p,
                    full_paragraph_text=full_text,
                    matched_text=matched_str,
                    start_char=s_char,
                    end_char=e_char,
                    proposed_replacement=rule.replacement,
                    surrounding_before=prev_text,
                    surrounding_after=next_text,
                )
                discrepancies.append(occ)
                occurrence_counter += 1

    # 1. Body paragraphs
    body_p = doc.paragraphs
    for i, p in enumerate(body_p):
        prev_t = body_p[i - 1].text if i > 0 else ""
        next_t = body_p[i + 1].text if i + 1 < len(body_p) else ""
        check_paragraph(
            p=p,
            loc_type="body",
            loc_label=f"Body Paragraph #{i}",
            p_idx=i,
            prev_text=prev_t,
            next_text=next_t,
        )

    # 2. Tables (with merged cell deduplication)
    for t_idx, table in enumerate(doc.tables):
        seen_cells: Set[Any] = set()
        for r_idx, row in enumerate(table.rows):
            for c_idx, cell in enumerate(row.cells):
                cell_elem = cell._tc
                if cell_elem in seen_cells:
                    continue
                seen_cells.add(cell_elem)

                for cp_idx, cp in enumerate(cell.paragraphs):
                    check_paragraph(
                        p=cp,
                        loc_type="table",
                        loc_label=f"Table {t_idx} [Row {r_idx}, Col {c_idx}] P#{cp_idx}",
                        p_idx=None,
                    )

    # 3. Headers and Footers
    for s_idx, section in enumerate(doc.sections):
        # Header parts
        headers = [section.header]
        try:
            if section.different_first_page_header_footer:
                headers.append(section.first_page_header)
        except Exception:
            pass
        try:
            headers.append(section.even_page_header)
        except Exception:
            pass

        for h_part in headers:
            for hp_idx, hp in enumerate(h_part.paragraphs):
                check_paragraph(
                    p=hp,
                    loc_type="header",
                    loc_label=f"Section {s_idx} Header P#{hp_idx}",
                    p_idx=None,
                )

        # Footer parts
        footers = [section.footer]
        try:
            if section.different_first_page_header_footer:
                footers.append(section.first_page_footer)
        except Exception:
            pass
        try:
            footers.append(section.even_page_footer)
        except Exception:
            pass

        for f_part in footers:
            for fp_idx, fp in enumerate(f_part.paragraphs):
                check_paragraph(
                    p=fp,
                    loc_type="footer",
                    loc_label=f"Section {s_idx} Footer P#{fp_idx}",
                    p_idx=None,
                )

    # 4. Textboxes (w:txbxContent//w:p)
    try:
        textbox_p_elems = doc.element.body.xpath(".//w:txbxContent//w:p")
        for tb_idx, tb_elem in enumerate(textbox_p_elems):
            tb_p = Paragraph(tb_elem, doc)
            check_paragraph(
                p=tb_p,
                loc_type="textbox",
                loc_label=f"Textbox #{tb_idx}",
                p_idx=None,
            )
    except Exception:
        pass

    return doc, discrepancies


def format_context_diff(
    occ: DiscrepancyOccurrence,
    use_color: bool = True,
    context_lines: int = 1,
) -> str:
    """Formats an occurrence into a clear terminal diff with surrounding context."""
    lines: List[str] = []

    c_bold = Colors.BOLD if use_color else ""
    c_red = Colors.RED if use_color else ""
    c_green = Colors.GREEN if use_color else ""
    c_yellow = Colors.YELLOW if use_color else ""
    c_blue = Colors.BLUE if use_color else ""
    c_gray = Colors.GRAY if use_color else ""
    c_reset = Colors.RESET if use_color else ""

    # Header
    lines.append(f"{c_yellow}{c_bold}[ALERT #{occ.occurrence_id}]{c_reset} Location: {c_bold}{occ.location_label}{c_reset}")
    lines.append(f"Rule: {occ.rule_description} ({c_bold}{occ.matched_text}{c_reset} -> {c_green}{occ.proposed_replacement}{c_reset})")
    lines.append("")

    # Surrounding Context
    if context_lines > 0:
        lines.append(f"{c_gray}--- Surrounding Context ---{c_reset}")
        if occ.surrounding_before.strip():
            lines.append(f"   {c_gray}[Prev]{c_reset} {occ.surrounding_before.strip()[:100]}")

        # Highlight current paragraph text
        text_before = occ.full_paragraph_text[: occ.start_char]
        match_str = occ.matched_text
        text_after = occ.full_paragraph_text[occ.end_char :]

        hl_line = f" > {text_before}{c_red}{c_bold}[{match_str}]{c_reset}{text_after}"
        lines.append(hl_line)

        if occ.surrounding_after.strip():
            lines.append(f"   {c_gray}[Next]{c_reset} {occ.surrounding_after.strip()[:100]}")
        lines.append("")

    # Unified Diff
    lines.append(f"{c_blue}--- Proposed Modification ---{c_reset}")
    orig_line = occ.full_paragraph_text
    new_line = occ.full_paragraph_text[: occ.start_char] + occ.proposed_replacement + occ.full_paragraph_text[occ.end_char :]

    lines.append(f"{c_red}- {orig_line}{c_reset}")
    lines.append(f"{c_green}+ {new_line}{c_reset}")

    return "\n".join(lines)


def prompt_user_permission(
    occ: DiscrepancyOccurrence,
    current_idx: int,
    total_count: int,
    input_func: Optional[Callable[[str], str]] = None,
    use_color: bool = True,
    context_lines: int = 1,
) -> str:
    """
    Presents the discrepancy to the user and prompts for explicit permission.
    Returns: 'y' (approve), 'n' (skip), 'a' (approve all), 'q' (quit).
    Default is 'n' (Safe default).
    """
    ask = input_func or input

    diff_display = format_context_diff(occ, use_color=use_color, context_lines=context_lines)
    print("=" * 80)
    print(diff_display)
    print("-" * 80)

    while True:
        prompt_text = (
            f"Apply this correction ({current_idx}/{total_count})? [y/N/a/q/?] (default: N): "
        )
        try:
            choice = ask(prompt_text).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborting: User canceled prompt.")
            return "q"

        if choice in ("", "n", "no"):
            return "n"
        elif choice in ("y", "yes"):
            return "y"
        elif choice in ("a", "all"):
            return "a"
        elif choice in ("q", "quit", "exit"):
            return "q"
        elif choice == "?":
            print("\nInteractive Options:")
            print("  y / yes   : Approve and apply this modification.")
            print("  n / no    : Skip this modification; leave text completely unchanged (default).")
            print("  a / all   : Approve this and all subsequent detected discrepancies.")
            print("  q / quit  : Stop scanning immediately and discard any remaining changes.")
            print("  ?         : Show this help explanation.\n")
        else:
            print(f"Unknown choice '{choice}'. Enter 'y', 'n', 'a', 'q', or '?' for help.")


def verify_and_correct_document(
    docx_path: str,
    out_path: Optional[str] = None,
    in_place: bool = False,
    backup: bool = True,
    rules: Optional[List[VerificationRule]] = None,
    auto_approve: bool = False,
    check_only: bool = False,
    input_func: Optional[Callable[[str], str]] = None,
    use_color: bool = True,
    context_lines: int = 1,
) -> Dict[str, Any]:
    """
    Master verification workflow:
    1. Scans .docx for discrepancies.
    2. If check_only: displays findings and returns summary without prompting or editing.
    3. Prompts user interactively (or auto-approves if auto_approve=True).
    4. Applies approved replacements using reverse-order run updates.
    5. Saves to out_path or in-place with backup if changes were approved.
    """
    doc, occurrences = scan_document(docx_path, rules=rules)
    total_found = len(occurrences)

    if total_found == 0:
        return {
            "scanned_path": docx_path,
            "total_found": 0,
            "approved": 0,
            "skipped": 0,
            "saved": False,
            "output_path": None,
            "message": "Document is clean. Zero discrepancies detected.",
        }

    # Check-only / Dry-run mode
    if check_only:
        for idx, occ in enumerate(occurrences, 1):
            print("=" * 80)
            print(format_context_diff(occ, use_color=use_color, context_lines=context_lines))
        return {
            "scanned_path": docx_path,
            "total_found": total_found,
            "approved": 0,
            "skipped": total_found,
            "saved": False,
            "output_path": None,
            "message": f"Check-only audit found {total_found} discrepancies.",
        }

    # Interactive or Auto-approve loop
    approved_occurrences: List[DiscrepancyOccurrence] = []
    skipped_occurrences: List[DiscrepancyOccurrence] = []
    auto_approve_remaining = auto_approve

    for idx, occ in enumerate(occurrences, 1):
        if auto_approve_remaining:
            occ.status = "APPROVED"
            approved_occurrences.append(occ)
            continue

        action = prompt_user_permission(
            occ=occ,
            current_idx=idx,
            total_count=total_found,
            input_func=input_func,
            use_color=use_color,
            context_lines=context_lines,
        )

        if action == "y":
            occ.status = "APPROVED"
            approved_occurrences.append(occ)
        elif action == "a":
            occ.status = "APPROVED"
            approved_occurrences.append(occ)
            auto_approve_remaining = True
        elif action == "q":
            occ.status = "SKIPPED"
            skipped_occurrences.append(occ)
            for remaining in occurrences[idx:]:
                remaining.status = "SKIPPED"
                skipped_occurrences.append(remaining)
            break
        else:  # 'n'
            occ.status = "SKIPPED"
            skipped_occurrences.append(occ)

    if not approved_occurrences:
        return {
            "scanned_path": docx_path,
            "total_found": total_found,
            "approved": 0,
            "skipped": len(skipped_occurrences),
            "saved": False,
            "output_path": None,
            "message": "No modifications approved. Source document left 100% untouched.",
        }

    # Group approved occurrences by paragraph
    p_map: Dict[Any, List[Tuple[int, int, str]]] = {}
    p_obj_map: Dict[Any, Paragraph] = {}

    for occ in approved_occurrences:
        pelem = occ.paragraph_obj._p
        if pelem not in p_map:
            p_map[pelem] = []
            p_obj_map[pelem] = occ.paragraph_obj
        p_map[pelem].append((occ.start_char, occ.end_char, occ.proposed_replacement))

    # Apply replacements paragraph by paragraph
    total_applied = 0
    for pelem, matches in p_map.items():
        applied = apply_replacements_to_paragraph(p_obj_map[pelem], matches)
        total_applied += applied

    # Save logic
    final_output_path: Optional[str] = None
    if in_place:
        final_output_path = docx_path
        if backup:
            bak_path = docx_path + ".bak"
            shutil.copy2(docx_path, bak_path)
        doc.save(docx_path)
    elif out_path:
        final_output_path = out_path
        out_dir = os.path.dirname(os.path.abspath(out_path))
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        doc.save(out_path)
    else:
        # Neither out_path nor in_place: Preview mode, do not save
        return {
            "scanned_path": docx_path,
            "total_found": total_found,
            "approved": len(approved_occurrences),
            "skipped": len(skipped_occurrences),
            "saved": False,
            "output_path": None,
            "message": f"Preview completed. {len(approved_occurrences)} approved, but not saved (specify --out or --in-place).",
        }

    return {
        "scanned_path": docx_path,
        "total_found": total_found,
        "approved": len(approved_occurrences),
        "skipped": len(skipped_occurrences),
        "saved": True,
        "output_path": final_output_path,
        "message": f"Successfully applied {len(approved_occurrences)} modifications. Saved to: {final_output_path}",
    }


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive Document Text Verification & Permission-Alerting Tool."
    )
    parser.add_argument("--docx", "-d", required=True, help="Input .docx document to verify")
    parser.add_argument("--out", "-o", help="Output path for corrected document")
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Modify document in-place (creates .bak unless --no-backup)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create .bak file when running --in-place",
    )
    parser.add_argument("--find", help="Custom regex pattern to find")
    parser.add_argument("--replace", help="Custom replacement string")
    parser.add_argument("--rules", help="Path to custom JSON rules file")
    parser.add_argument(
        "--preset",
        default="forensics",
        choices=["forensics", "all"],
        help="Rule preset (default: 'forensics')",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Non-interactive dry-run audit. Exits 1 if discrepancies found, 0 if clean.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Non-interactive batch mode: auto-approves all matches",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable terminal ANSI colors",
    )
    parser.add_argument(
        "--context-lines",
        type=int,
        default=1,
        help="Number of context paragraphs to display (default: 1)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output scan results as JSON to stdout",
    )
    return parser.parse_args(args)


def main() -> int:
    args = parse_args()

    use_color = not args.no_color and sys.stdout.isatty()
    rules = load_rules(
        preset=args.preset,
        custom_find=args.find,
        custom_replace=args.replace,
        rules_file=args.rules,
    )

    try:
        summary = verify_and_correct_document(
            docx_path=args.docx,
            out_path=args.out,
            in_place=args.in_place,
            backup=not args.no_backup,
            rules=rules,
            auto_approve=args.yes,
            check_only=args.check_only,
            use_color=use_color,
            context_lines=args.context_lines,
        )

        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print("\nVerification Summary:")
            print(f"  Scanned:       {summary['scanned_path']}")
            print(f"  Found:         {summary['total_found']}")
            print(f"  Approved:      {summary['approved']}")
            print(f"  Skipped:       {summary['skipped']}")
            print(f"  Saved:         {summary['saved']}")
            if summary["output_path"]:
                print(f"  Output Path:   {summary['output_path']}")
            print(f"  Status:        {summary['message']}")

        if args.check_only:
            return 1 if summary["total_found"] > 0 else 0

        return 0
    except Exception as e:
        print(f"Error during verification: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
