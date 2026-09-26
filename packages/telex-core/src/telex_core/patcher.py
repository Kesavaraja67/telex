"""
Deterministic patch applier and unified diff generator.

Implements pure-Python unified diff application with strict fail-closed integrity.
Never modifies original files if any hunk fails to match or apply cleanly.
"""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def apply_diff_to_content(
    file_path: str,
    original_content: str,
    diff_text: str,
) -> tuple[bool, str, str]:
    """
    Apply a unified diff to original_content in memory.

    Returns:
        (apply_ok: bool, new_content: str, log_message: str)
    """
    if not diff_text or not diff_text.strip():
        return False, original_content, "Empty diff provided"

    orig_lines = original_content.splitlines(keepends=True)
    # Normalize CRLF in original lines to LF for uniform hunk matching
    orig_lines_normalized = [line_item.replace("\r\n", "\n") for line_item in orig_lines]

    hunk_header_re = re.compile(
        r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
    )

    lines = diff_text.splitlines()
    hunks = []
    current_hunk = None

    for line in lines:
        match = hunk_header_re.match(line)
        if match:
            if current_hunk:
                hunks.append(current_hunk)
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) is not None else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) is not None else 1
            current_hunk = {
                "old_start": old_start,
                "old_count": old_count,
                "new_start": new_start,
                "new_count": new_count,
                "lines": [],
            }
        elif current_hunk is not None:
            if line.startswith(("+", "-", " ", "\\")):
                current_hunk["lines"].append(line)

    if current_hunk:
        hunks.append(current_hunk)

    if not hunks:
        return False, original_content, "No valid unified diff hunks found in diff text"

    result_lines = list(orig_lines_normalized)
    offset = 0

    for i, hunk in enumerate(hunks, 1):
        old_start = hunk["old_start"] - 1 + offset
        expected_old_lines = []
        replacement_lines = []

        for hline in hunk["lines"]:
            if hline.startswith("-"):
                expected_old_lines.append(hline[1:] + "\n")
            elif hline.startswith("+"):
                replacement_lines.append(hline[1:] + "\n")
            elif hline.startswith(" "):
                expected_old_lines.append(hline[1:] + "\n")
                replacement_lines.append(hline[1:] + "\n")

        # Find match position
        target_pos = old_start
        found_pos = None

        # Check exact target position first
        if 0 <= target_pos <= len(result_lines):
            slice_end = target_pos + len(expected_old_lines)
            if [line_item.rstrip("\r\n") for line_item in result_lines[target_pos:slice_end]] == [
                line_item.rstrip("\r\n") for line_item in expected_old_lines
            ]:
                found_pos = target_pos

        # If not at exact position, scan with small window
        if found_pos is None:
            max_drift = 25
            best_pos = None
            min_dist = float("inf")
            for pos in range(
                max(0, target_pos - max_drift),
                min(len(result_lines) - len(expected_old_lines) + 1, target_pos + max_drift),
            ):
                slice_end = pos + len(expected_old_lines)
                if [line_item.rstrip("\r\n") for line_item in result_lines[pos:slice_end]] == [
                    line_item.rstrip("\r\n") for line_item in expected_old_lines
                ]:
                    dist = abs(pos - target_pos)
                    if dist < min_dist:
                        min_dist = dist
                        best_pos = pos
            found_pos = best_pos

        if found_pos is None:
            return (
                False,
                original_content,
                f"Hunk #{i} failed to match target content around line {hunk['old_start']} in {file_path}",
            )

        # Apply hunk replacement
        slice_end = found_pos + len(expected_old_lines)
        result_lines[found_pos:slice_end] = replacement_lines
        offset += len(replacement_lines) - len(expected_old_lines)

    new_content = "".join(result_lines)
    # Preserve original line endings if original had CRLF
    if "\r\n" in original_content and "\r\n" not in new_content:
        new_content = new_content.replace("\n", "\r\n")

    return True, new_content, "Patch applied cleanly"


def patch_file(
    file_path: str,
    diff_text: str,
    dry_run: bool = False,
    output_path: str | None = None,
) -> dict[str, Any]:
    """
    Apply diff_text to file_path.
    """
    target = Path(file_path)
    if not target.exists():
        return {
            "success": False,
            "file_path": file_path,
            "error": f"File does not exist: {file_path}",
        }

    try:
        orig = target.read_text(encoding="utf-8")
    except Exception as exc:
        return {
            "success": False,
            "file_path": file_path,
            "error": f"Could not read {file_path}: {exc}",
        }

    apply_ok, new_content, log = apply_diff_to_content(file_path, orig, diff_text)
    if not apply_ok:
        return {
            "success": False,
            "file_path": file_path,
            "error": log,
        }

    if not dry_run:
        out = Path(output_path) if output_path else target
        try:
            out.write_text(new_content, encoding="utf-8")
        except Exception as exc:
            return {
                "success": False,
                "file_path": file_path,
                "error": f"Could not write to {out}: {exc}",
            }

    return {
        "success": True,
        "file_path": file_path,
        "dry_run": dry_run,
        "output_path": output_path or file_path,
        "log": log,
    }
