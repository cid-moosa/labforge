"""
tests/helpers/integrity.py
Production preservation and SHA-256 fingerprinting utilities for Project LabForge.
Verifies that all 122 files across input/ and output/, as well as scripts/labforge_engine.py,
remain 100% untouched and preserved.
"""

import hashlib
import os
from typing import Dict, List, Optional, Tuple

LOCKED_ENGINE_FILE = "scripts/labforge_engine.py"
LOCKED_ENGINE_SHA256 = "b1ad499421831914efc123083e7839b024f0919f9729b906d1067d9d4be54e57"
BASELINE_ENGINE_SHA256 = LOCKED_ENGINE_SHA256

INPUT_DIR = "input"
OUTPUT_DIR = "output"
EXPECTED_INPUT_COUNT = 100
EXPECTED_OUTPUT_COUNT = 10


def hash_file(filepath: str) -> str:
    """Computes the SHA-256 hex digest of a file in 64KB chunks."""
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def snapshot_directory_hashes(directory: str) -> Dict[str, str]:
    """
    Computes SHA-256 hashes for every file in the directory.
    Returns dictionary mapping normalized relative path to sha256 hash.
    """
    hashes: Dict[str, str] = {}
    if not os.path.exists(directory):
        return hashes

    for root, _, files in os.walk(directory):
        for f in files:
            if f.endswith(".tmp") or f.startswith("~$"):
                continue
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, directory).replace("\\", "/")
            hashes[rel_path] = hash_file(full_path)

    return hashes


def verify_directory_integrity(
    directory: str,
    baseline_hashes: Dict[str, str],
) -> Tuple[bool, List[str]]:
    """
    Compares current directory contents and hashes against the baseline.
    Returns (is_intact, differences).
    """
    current_hashes = snapshot_directory_hashes(directory)
    differences: List[str] = []

    # Check for missing files
    for rel_path, base_hash in baseline_hashes.items():
        if rel_path not in current_hashes:
            differences.append(f"MISSING: {rel_path} was removed from {directory}")
        elif current_hashes[rel_path] != base_hash:
            differences.append(
                f"MODIFIED: {rel_path} changed hash (baseline: {base_hash[:8]}..., current: {current_hashes[rel_path][:8]}...)"
            )

    # Check for newly added files
    for rel_path in current_hashes:
        if rel_path not in baseline_hashes:
            differences.append(f"ADDED: Unexpected new file {rel_path} found in {directory}")

    is_intact = len(differences) == 0
    return is_intact, differences


def assert_safe_test_path(path: str) -> None:
    """
    Guarantees that a path does NOT target production assets in input/, output/,
    or scripts/labforge_engine.py. Raises PermissionError on any violation.
    """
    abs_target = os.path.abspath(path)
    cwd = os.path.abspath(os.getcwd())

    # Check engine
    engine_path = os.path.abspath(os.path.join(cwd, LOCKED_ENGINE_FILE))
    if abs_target == engine_path:
        raise PermissionError(
            f"Violation of R1/R3: scripts/labforge_engine.py is locked and cannot be targeted: {path}"
        )

    # Check input/
    input_root = os.path.abspath(os.path.join(cwd, INPUT_DIR))
    if abs_target == input_root or abs_target.startswith(input_root + os.sep):
        raise PermissionError(
            f"Violation of R3: Production directory '{INPUT_DIR}' cannot be modified or written to: {path}"
        )

    # Check output/
    output_root = os.path.abspath(os.path.join(cwd, OUTPUT_DIR))
    if abs_target == output_root or abs_target.startswith(output_root + os.sep):
        raise PermissionError(
            f"Violation of R3: Production directory '{OUTPUT_DIR}' cannot be modified or written to: {path}"
        )
