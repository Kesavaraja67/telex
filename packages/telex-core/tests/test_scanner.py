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


def test_polyglot_find_usages_go_and_rust():
    go_code = b"""package main
import "github.com/gin-gonic/gin"
func main() {
    r := gin.Default()
}
"""
    go_usages = find_usages("main.go", go_code, "Default", package_name="gin")
    assert len(go_usages) == 1
    assert "gin.Default()" in go_usages[0]["snippet"]

    rust_code = b"""use serde_json::to_string;
fn main() {
    let s = to_string(&data);
}
"""
    rust_usages = find_usages("lib.rs", rust_code, "to_string", package_name="serde_json")
    assert len(rust_usages) == 1
    assert "to_string(&data)" in rust_usages[0]["snippet"]


def test_polyglot_find_usages_java_ruby_csharp():
    java_code = b"""import com.google.gson.Gson;
class Main {
    void run() {
        Gson g = new Gson();
        g.toJson(data);
    }
}
"""
    assert len(find_usages("Main.java", java_code, "toJson", package_name="gson")) == 1

    ruby_code = b"""require "json"
JSON.parse(data)
"""
    assert len(find_usages("app.rb", ruby_code, "parse", package_name="json")) == 1

    cs_code = b"""using static System.Text.Json.JsonSerializer;
class Program {
    void Main() {
        JsonSerializer.Serialize(obj);
    }
}
"""
    assert len(find_usages("Program.cs", cs_code, "Serialize", package_name="System.Text.Json")) == 1



def test_csharp_capitalization_does_not_establish_target_binding():
    source = b"""using System.Text.Json;
using static System.Text.Json.JsonSerializer;
class Program {
    void Main() {
        OtherSerializer.Serialize(obj);
        JsonSerializer.Serialize(obj);
        System.Text.Json.JsonSerializer.Serialize(obj);
    }
}
"""
    usages = find_usages("Program.cs", source, "Serialize", package_name="System.Text.Json")
    assert [u["snippet"] for u in usages] == [
        "JsonSerializer.Serialize(obj)",
        "System.Text.Json.JsonSerializer.Serialize(obj)",
    ]
