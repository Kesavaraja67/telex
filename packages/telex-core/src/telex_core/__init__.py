"""
telex-core — Standalone automated dependency repair engine and AST code scanner.
"""

__version__ = "0.1.0"

from telex_core.analyzer import extract_breaking_changes
from telex_core.patcher import apply_diff_to_content, patch_file
from telex_core.scanner import find_usages, scan_directory
from telex_core.verifier import verify_directory

__all__ = [
    "__version__",
    "apply_diff_to_content",
    "extract_breaking_changes",
    "find_usages",
    "patch_file",
    "scan_directory",
    "verify_directory",
]
