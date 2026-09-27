"""
Command line interface for telex-core.

Commands:
  telex scan     — Scan a path for breaking API call sites
  telex analyze  — Extract breaking changes between package versions
  telex patch    — Test or apply a unified diff to a source file
  telex verify   — Run local verification pipeline (parse, typecheck, tests)
"""

import argparse
import json
import sys
from pathlib import Path

# Enable direct script execution without prior pip install
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telex_core import __version__
from telex_core.analyzer import extract_breaking_changes
from telex_core.patcher import patch_file
from telex_core.scanner import scan_directory
from telex_core.verifier import verify_directory


def cmd_scan(args: argparse.Namespace) -> int:
    usages = scan_directory(
        target_path=args.path,
        symbol_name=args.symbol,
        package_name=args.package,
    )
    if args.json:
        print(json.dumps({"count": len(usages), "usages": usages}, indent=2))
    else:
        print(
            f"Scanned '{args.path}' for symbol '{args.symbol}' (package: {args.package or 'any'})"
        )
        print(f"Found {len(usages)} matching call site(s):")
        for i, u in enumerate(usages, 1):
            print(f"  {i}. {u['file_path']}:{u['line_start']}: {u['snippet'].strip()}")
    return 0 if usages else 1


def cmd_analyze(args: argparse.Namespace) -> int:
    changelog_text = None
    if args.changelog:
        cl_path = Path(args.changelog)
        if cl_path.exists():
            changelog_text = cl_path.read_text(encoding="utf-8")
        else:
            print(f"Error: changelog file not found: {args.changelog}", file=sys.stderr)
            return 2

    try:
        changes = extract_breaking_changes(
            package_name=args.package,
            old_version=args.from_version,
            new_version=args.to_version,
            ecosystem=args.ecosystem,
            changelog_text=changelog_text,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "package": args.package,
                    "from_version": args.from_version,
                    "to_version": args.to_version,
                    "ecosystem": args.ecosystem,
                    "count": len(changes),
                    "changes": changes,
                },
                indent=2,
            )
        )
    else:
        print(
            f"Breaking change analysis for {args.package} ({args.from_version} -> {args.to_version}):"
        )
        if not changes:
            print("  No breaking changes detected.")
        else:
            for i, c in enumerate(changes, 1):
                sym_to = f" -> {c['symbol_new']}" if c.get("symbol_new") else ""
                print(
                    f"  {i}. [{c['change_type'].upper()}] {c['symbol']}{sym_to} (confidence: {c['confidence']:.0%})"
                )
                print(f"     {c['description']}")
    return 0


def cmd_patch(args: argparse.Namespace) -> int:
    diff_path = Path(args.diff)
    if not diff_path.exists():
        print(f"Error: diff file not found: {args.diff}", file=sys.stderr)
        return 2

    diff_text = diff_path.read_text(encoding="utf-8")
    result = patch_file(
        file_path=args.file,
        diff_text=diff_text,
        dry_run=args.dry_run,
        output_path=args.output,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["success"]:
            action = "Tested patch (dry-run)" if args.dry_run else "Applied patch to"
            out = result.get("output_path") or args.file
            print(f"[OK] {action} {out}: {result.get('log')}")
        else:
            print(
                f"[FAIL] Patch failed on {args.file}: {result.get('error')}",
                file=sys.stderr,
            )

    return 0 if result["success"] else 1


def cmd_verify(args: argparse.Namespace) -> int:
    receipt = verify_directory(
        target_path=args.path,
        test_cmd=args.test_cmd,
        typecheck_cmd=args.typecheck_cmd,
    )

    if args.json:
        print(json.dumps(receipt, indent=2))
    else:
        print(f"Verification results for '{args.path}':")
        print(f"  Files checked: {receipt['files_checked']}")
        parse_status = "PASSED" if receipt["gates"]["parse"]["passed"] else "FAILED"
        print(f"  AST Parse: {parse_status}")
        if receipt["gates"]["parse"]["error_files"]:
            for ef in receipt["gates"]["parse"]["error_files"]:
                print(f"    - Error in: {ef}")

        tc = receipt["gates"]["typecheck"]
        if tc["executed"]:
            tc_status = "PASSED" if tc["passed"] else "FAILED"
            print(f"  Typecheck ({tc['command']}): {tc_status}")

        tst = receipt["gates"]["tests"]
        if tst["executed"]:
            tst_status = "PASSED" if tst["passed"] else "FAILED"
            print(f"  Tests ({tst['command']}): {tst_status}")

        verdict = (
            "[VERIFIED] All gates passed."
            if receipt["all_passed"]
            else "[FAILED] Verification gates failed."
        )
        print(f"\n{verdict}")

    return 0 if receipt["all_passed"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="telex",
        description="telex-core — Standalone automated dependency repair engine and AST code scanner.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = subparsers.add_parser(
        "scan", help="Scan a directory for call sites of a symbol"
    )
    p_scan.add_argument("path", help="Path to file or directory to scan")
    p_scan.add_argument(
        "--symbol",
        required=True,
        help="Symbol to search for (e.g. 'get' or 'createCompletion')",
    )
    p_scan.add_argument(
        "--package", default=None, help="Target package name (e.g. 'lodash', 'openai')"
    )
    p_scan.add_argument(
        "--json", action="store_true", help="Output results in JSON format"
    )

    # analyze
    p_analyze = subparsers.add_parser(
        "analyze", help="Extract breaking changes between two versions"
    )
    p_analyze.add_argument("package", help="Package name (e.g. 'lodash', 'requests')")
    p_analyze.add_argument(
        "--from",
        dest="from_version",
        required=True,
        help="Baseline version (e.g. '4.17.20')",
    )
    p_analyze.add_argument(
        "--to", dest="to_version", required=True, help="Target version (e.g. '4.17.21')"
    )
    p_analyze.add_argument(
        "--ecosystem", choices=["npm", "pypi"], default="npm", help="Package ecosystem"
    )
    p_analyze.add_argument(
        "--changelog", default=None, help="Local changelog markdown file to parse"
    )
    p_analyze.add_argument(
        "--json", action="store_true", help="Output results in JSON format"
    )

    # patch
    p_patch = subparsers.add_parser(
        "patch", help="Apply a unified diff patch to a source file"
    )
    p_patch.add_argument("file", help="Source file to patch")
    p_patch.add_argument("--diff", required=True, help="Path to unified diff file")
    p_patch.add_argument(
        "--dry-run",
        action="store_true",
        help="Test application without modifying file on disk",
    )
    p_patch.add_argument(
        "--output", default=None, help="Optional output path for patched content"
    )
    p_patch.add_argument(
        "--json", action="store_true", help="Output results in JSON format"
    )

    # verify
    p_verify = subparsers.add_parser("verify", help="Run local verification pipeline")
    p_verify.add_argument("path", help="Directory or file to verify")
    p_verify.add_argument(
        "--test-cmd", default=None, help="Command to run tests (e.g. 'pytest')"
    )
    p_verify.add_argument(
        "--typecheck-cmd",
        default=None,
        help="Command to run typechecks (e.g. 'mypy .')",
    )
    p_verify.add_argument(
        "--json", action="store_true", help="Output results in JSON format"
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handler_map = {
        "scan": cmd_scan,
        "analyze": cmd_analyze,
        "patch": cmd_patch,
        "verify": cmd_verify,
    }

    handler = handler_map.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
