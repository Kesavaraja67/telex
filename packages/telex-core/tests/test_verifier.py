import sys
from pathlib import Path

from telex_core.verifier import run_command, verify_directory, verify_parse

PY = f'"{sys.executable}"'


def test_verify_parse_valid():
    valid_ts = b"const x: number = 42;\nexport function add(a: number, b: number) { return a + b; }\n"
    assert verify_parse("index.ts", valid_ts) is True

    valid_py = b"def greet(name: str) -> str:\n    return f'Hello {name}'\n"
    assert verify_parse("greet.py", valid_py) is True


def test_verify_parse_invalid():
    invalid_py = b"def broken(\n   return"
    assert verify_parse("broken.py", invalid_py) is False


def test_run_command_execution():
    ok, out = run_command(f"{PY} -c \"print('hello telex')\"")
    assert ok is True
    assert "hello telex" in out

    fail_ok, _fail_out = run_command(f'{PY} -c "import sys; sys.exit(42)"')
    assert fail_ok is False


def test_verify_directory_pipeline(tmp_path: Path):
    valid_file = tmp_path / "valid.py"
    valid_file.write_text("x = 1\n", encoding="utf-8")

    receipt = verify_directory(
        target_path=str(tmp_path),
        test_cmd=f"{PY} -c \"print('tests passed')\"",
    )
    assert receipt["all_passed"] is True
    assert receipt["files_checked"] == 1
    assert receipt["gates"]["parse"]["passed"] is True
    assert receipt["gates"]["tests"]["passed"] is True
