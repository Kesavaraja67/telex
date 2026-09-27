"""Unit tests for telex_core.cli."""

import json
import sys
from pathlib import Path

from telex_core.cli import build_parser, cmd_analyze, cmd_patch, cmd_scan, cmd_verify


def test_cli_parser_scan():
    parser = build_parser()
    args = parser.parse_args(
        ["scan", "./src", "--package", "lodash", "--symbol", "get", "--json"]
    )
    assert args.command == "scan"
    assert args.path == "./src"
    assert args.package == "lodash"
    assert args.symbol == "get"
    assert args.json is True


def test_cli_cmd_scan(tmp_path: Path, capsys):
    f = tmp_path / "index.ts"
    f.write_text("import { get } from 'lodash'; get(user, 'name');\n", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(
        ["scan", str(tmp_path), "--package", "lodash", "--symbol", "get", "--json"]
    )
    exit_code = cmd_scan(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["count"] == 1
    assert data["usages"][0]["file_path"] == str(f)


def test_cli_cmd_analyze(tmp_path: Path, capsys):
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text(
        "### Breaking Changes\n- Renamed `oldApi` to `newApi`\n", encoding="utf-8"
    )

    parser = build_parser()
    args = parser.parse_args(
        [
            "analyze",
            "my-lib",
            "--from",
            "1.0.0",
            "--to",
            "2.0.0",
            "--changelog",
            str(cl),
            "--json",
        ]
    )
    exit_code = cmd_analyze(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["count"] == 1
    assert data["changes"][0]["symbol"] == "oldApi"
    assert data["changes"][0]["symbol_new"] == "newApi"


def test_cli_cmd_patch(tmp_path: Path, capsys):
    src = tmp_path / "app.js"
    src.write_text("const x = 1;\n", encoding="utf-8")

    diff = tmp_path / "fix.diff"
    diff.write_text(
        "--- a/app.js\n+++ b/app.js\n@@ -1,1 +1,1 @@\n-const x = 1;\n+const x = 2;\n",
        encoding="utf-8",
    )

    parser = build_parser()
    args = parser.parse_args(["patch", str(src), "--diff", str(diff), "--json"])
    exit_code = cmd_patch(args)
    assert exit_code == 0
    assert src.read_text(encoding="utf-8") == "const x = 2;\n"


def test_cli_cmd_verify(tmp_path: Path, capsys):
    src = tmp_path / "main.py"
    src.write_text("a = 10\n", encoding="utf-8")

    py_exe = f'"{sys.executable}"'
    parser = build_parser()
    args = parser.parse_args(
        ["verify", str(tmp_path), "--test-cmd", f'{py_exe} -c "pass"', "--json"]
    )
    exit_code = cmd_verify(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["all_passed"] is True
