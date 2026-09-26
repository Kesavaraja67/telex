"""Unit tests for telex_core.scanner."""

from pathlib import Path

from telex_core.scanner import find_usages, scan_directory


def test_find_usages_named_import():
    code = b"""
import { get } from 'lodash';
const val = get(user, 'profile.name');
"""
    usages = find_usages("src/index.ts", code, "get", package_name="lodash")
    assert len(usages) == 1
    assert usages[0]["line_start"] == 3
    assert "get(user, 'profile.name')" in usages[0]["snippet"]


def test_find_usages_local_definition_ignored():
    code = b"""
function get(x) {
    return x * 2;
}
const val = get(10);
"""
    usages = find_usages("src/index.ts", code, "get", package_name="lodash")
    assert len(usages) == 0


def test_find_usages_foreign_import_ignored():
    code = b"""
import { get } from 'axios';
const res = await get('https://example.com');
"""
    usages = find_usages("src/index.ts", code, "get", package_name="lodash")
    assert len(usages) == 0


def test_find_usages_renamed_import():
    code = b"""
import { get as lodashGet } from 'lodash';
const val = lodashGet(obj, 'path');
"""
    usages = find_usages("src/index.ts", code, "get", package_name="lodash")
    assert len(usages) == 1
    assert "lodashGet(obj, 'path')" in usages[0]["snippet"]


def test_find_usages_python_imports():
    code = b"""
import requests
from requests import get as req_get
def get(): pass

res1 = requests.get('https://a')
res2 = req_get('https://b')
get()
"""
    usages = find_usages("api.py", code, "get", package_name="requests")
    assert len(usages) == 2
    snippets = [u["snippet"] for u in usages]
    assert any("requests.get('https://a')" in s for s in snippets)
    assert any("req_get('https://b')" in s for s in snippets)


def test_scan_directory(tmp_path: Path):
    f1 = tmp_path / "a.ts"
    f1.write_text("import { get } from 'lodash'; get(a, 'b');\n", encoding="utf-8")
    f2 = tmp_path / "b.py"
    f2.write_text("from requests import get\nget('https://api')\n", encoding="utf-8")
    f3 = tmp_path / "c.ts"
    f3.write_text("function get() {}\nget();\n", encoding="utf-8")

    usages_ts = scan_directory(str(tmp_path), "get", package_name="lodash")
    assert len(usages_ts) == 1
    assert usages_ts[0]["file_path"] == str(f1)

    usages_py = scan_directory(str(tmp_path), "get", package_name="requests")
    assert len(usages_py) == 1
    assert usages_py[0]["file_path"] == str(f2)
