"""
Local verification pipeline runner.

Validates AST parses, executes local typecheckers, and runs repository test suites.
Produces structured verification receipts with pass/fail gates.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def verify_parse(file_path: str, source: bytes) -> bool:
    """Verify that file parses cleanly using tree-sitter without root syntax errors."""
    try:
        import tree_sitter_languages as tsl
    except ImportError:
        return True

    suffix = Path(file_path).suffix.lower()
    ext_to_lang = {
        ".ts": "typescript",
        ".mts": "typescript",
        ".cts": "typescript",
        ".tsx": "tsx",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".py": "python",
    }
    lang_name = ext_to_lang.get(suffix)
    if not lang_name:
        return True

    try:
        parser = tsl.get_parser(lang_name)
        tree = parser.parse(source)
        return not tree.root_node.has_error
    except Exception:
        return False


def run_command(cmd: str, cwd: str | None = None, timeout: float = 60.0) -> tuple[bool, str]:
    """Execute a local shell command and return (success: bool, output: str)."""
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = proc.stdout + "\n" + proc.stderr
        return proc.returncode == 0, output.strip()
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout}s: {cmd}"
    except Exception as exc:
        return False, f"Failed to execute command '{cmd}': {exc}"


def verify_directory(
    target_path: str,
    test_cmd: str | None = None,
    typecheck_cmd: str | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """
    Run the full local verification pipeline on target_path:
    1. Parse verification across all source files
    2. Typecheck verification (if typecheck_cmd provided)
    3. Test verification (if test_cmd provided)
    """
    target = Path(target_path)
    if not target.exists():
        return {
            "all_passed": False,
            "error": f"Path not found: {target_path}",
            "gates": {},
        }

    cwd = str(target if target.is_dir() else target.parent)

    # 1. Parse check
    parse_errors: list[str] = []
    files_to_check = []
    if target.is_file():
        files_to_check.append(target)
    else:
        valid_exts = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py"}
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "venv", "__pycache__")]
            for f in files:
                p = Path(root) / f
                if p.suffix.lower() in valid_exts:
                    files_to_check.append(p)

    for fpath in files_to_check:
        try:
            content = fpath.read_bytes()
            if not verify_parse(str(fpath), content):
                parse_errors.append(str(fpath))
        except Exception as exc:
            parse_errors.append(f"{fpath} (read error: {exc})")

    parses_ok = len(parse_errors) == 0

    # 2. Typecheck check
    typecheck_ok = None
    typecheck_output = ""
    if typecheck_cmd:
        typecheck_ok, typecheck_output = run_command(typecheck_cmd, cwd=cwd, timeout=timeout)

    # 3. Test check
    tests_ok = None
    tests_output = ""
    if test_cmd:
        tests_ok, tests_output = run_command(test_cmd, cwd=cwd, timeout=timeout)

    # Determine overall status
    gates_ok = parses_ok and (typecheck_ok is not False) and (tests_ok is not False)

    return {
        "all_passed": gates_ok,
        "files_checked": len(files_to_check),
        "gates": {
            "parse": {
                "passed": parses_ok,
                "error_files": parse_errors,
            },
            "typecheck": {
                "executed": typecheck_cmd is not None,
                "passed": typecheck_ok,
                "command": typecheck_cmd,
                "output": typecheck_output[:2000] if typecheck_output else None,
            },
            "tests": {
                "executed": test_cmd is not None,
                "passed": tests_ok,
                "command": test_cmd,
                "output": tests_output[:2000] if tests_output else None,
            },
        },
    }
