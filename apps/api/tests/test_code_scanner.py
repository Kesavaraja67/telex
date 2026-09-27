import pytest
from services.code_scanner import find_usages


def test_find_usages_plain_identifier():
    """Finds direct function calls in TypeScript."""
    ts_code = b"""
import { createCompletion } from 'openai';

async function run() {
    const res = await createCompletion({ model: 'text-davinci-003' });
    console.log(res);
}
"""
    usages = find_usages("src/index.ts", ts_code, "createCompletion")
    assert len(usages) == 1
    u = usages[0]
    assert u["file_path"] == "src/index.ts"
    assert u["line_start"] == 5
    assert "createCompletion" in u["snippet"]


def test_find_usages_member_expression():
    """Finds method calls on objects in TypeScript / JavaScript."""
    ts_code = b"""
import { Configuration, OpenAIApi } from 'openai';

const openai = new OpenAIApi(new Configuration());

export async function generateText(prompt: string) {
    const response = await openai.createCompletion({
        model: "text-davinci-003",
        prompt: prompt,
    });
    return response.data;
}
"""
    usages = find_usages("src/ai.ts", ts_code, "createCompletion")
    assert len(usages) == 1
    u = usages[0]
    assert u["file_path"] == "src/ai.ts"
    assert u["line_start"] == 7
    assert "openai.createCompletion" in u["snippet"]


def test_find_usages_multiple_call_sites():
    """Discovers all occurrences across multiple lines."""
    ts_code = b"""
function test() {
    doAction(1);
    doOther();
    doAction(2);
}
"""
    usages = find_usages("src/test.ts", ts_code, "doAction")
    assert len(usages) == 2
    assert usages[0]["line_start"] == 3
    assert usages[1]["line_start"] == 5


def test_find_usages_no_match():
    """Returns empty list when symbol is not called."""
    ts_code = b"""
function example() {
    const x = 10;
    return x * 2;
}
"""
    usages = find_usages("src/math.ts", ts_code, "createCompletion")
    assert usages == []


def test_find_usages_tsx_syntax():
    """Parses React JSX/TSX syntax cleanly without syntax errors."""
    tsx_code = b"""
import React from 'react';
import { trackEvent } from 'analytics';

export function Button() {
    return (
        <button onClick={() => trackEvent('button_click')}>
            Click me
        </button>
    );
}
"""
    usages = find_usages("components/Button.tsx", tsx_code, "trackEvent")
    assert len(usages) == 1
    assert "trackEvent('button_click')" in usages[0]["snippet"]


def test_find_usages_python_syntax():
    """Finds direct and attribute calls in Python code."""
    py_code = b"""
def run():
    res = create_completion(model="gpt-4")
    other = client.create_completion(model="gpt-4o")
    return res
"""
    usages = find_usages("services/agent.py", py_code, "create_completion")
    assert len(usages) == 2
    assert usages[0]["file_path"] == "services/agent.py"
    assert usages[0]["line_start"] == 3
    assert 'create_completion(model="gpt-4")' in usages[0]["snippet"]
    assert usages[1]["line_start"] == 4
    assert 'client.create_completion(model="gpt-4o")' in usages[1]["snippet"]


def test_find_usages_python_fixture():
    """Finds usages inside the sample_service.py fixture file."""
    from pathlib import Path

    fixture_path = Path(__file__).parent / "fixtures" / "sample_service.py"
    with open(fixture_path, "rb") as f:
        py_code = f.read()

    usages = find_usages("tests/fixtures/sample_service.py", py_code, "create_completion")
    assert len(usages) == 2
    snippets = [u["snippet"] for u in usages]
    assert any('create_completion(model="gpt-4"' in s for s in snippets)
    assert any('client.create_completion(model="gpt-4o"' in s for s in snippets)


# ── Change 18: Import Binding Resolution Tests ─────────────────────────────────


def test_import_binding_resolution_file_a_named_import():
    """File A imports get from lodash: get(obj, path) -> matches lodash.get."""
    code = b"""
import { get } from 'lodash';
const result = get(user, 'address.city');
"""
    usages = find_usages("src/a.ts", code, "get", package_name="lodash")
    assert len(usages) == 1
    assert "get(user, 'address.city')" in usages[0]["snippet"]
    assert usages[0]["line_start"] == 3


def test_import_binding_resolution_file_b_local_definition():
    """File B defines local function get(x): get(x) -> does NOT match lodash.get."""
    code = b"""
function get(x) {
    return x * 2;
}
const val = get(10);
"""
    usages = find_usages("src/b.ts", code, "get", package_name="lodash")
    assert len(usages) == 0


def test_import_binding_resolution_file_c_foreign_import():
    """File C imports get from axios: get(url) -> does NOT match lodash.get."""
    code = b"""
import { get } from 'axios';
const res = await get('https://api.example.com/users');
"""
    usages = find_usages("src/c.ts", code, "get", package_name="lodash")
    assert len(usages) == 0


def test_import_binding_resolution_file_d_renamed_import():
    """File D uses renamed import import { get as lodashGet } from 'lodash': lodashGet(obj, path) -> matches lodash.get."""
    code = b"""
import { get as lodashGet } from 'lodash';
const city = lodashGet(user, 'profile.city');
"""
    usages = find_usages("src/d.ts", code, "get", package_name="lodash")
    assert len(usages) == 1
    assert "lodashGet(user, 'profile.city')" in usages[0]["snippet"]
    assert usages[0]["line_start"] == 3


def test_import_binding_resolution_commonjs_require():
    """CommonJS require patterns with namespace, destructuring, and renaming."""
    # Namespace require
    code_ns = b"""
const lodash = require('lodash');
const res = lodash.get(data, 'key');
"""
    assert len(find_usages("src/cjs1.js", code_ns, "get", package_name="lodash")) == 1

    # Destructured require
    code_destruct = b"""
const { get } = require('lodash');
const res = get(data, 'key');
"""
    assert len(find_usages("src/cjs2.js", code_destruct, "get", package_name="lodash")) == 1

    # Aliased destructured require
    code_alias = b"""
const { get: lodashGet } = require('lodash');
const res = lodashGet(data, 'key');
"""
    assert len(find_usages("src/cjs3.js", code_alias, "get", package_name="lodash")) == 1

    # Foreign require
    code_foreign = b"""
const axios = require('axios');
const { get } = require('axios');
const res1 = axios.get('https://api');
const res2 = get('https://api');
"""
    assert len(find_usages("src/cjs4.js", code_foreign, "get", package_name="lodash")) == 0


def test_import_binding_resolution_python_imports():
    """Python import statement and import-from binding resolution."""
    # from requests import get
    py_from = b"""
from requests import get
res = get('https://api.example.com')
"""
    assert len(find_usages("src/api.py", py_from, "get", package_name="requests")) == 1

    # from requests import get as req_get
    py_alias = b"""
from requests import get as req_get
res = req_get('https://api.example.com')
"""
    assert len(find_usages("src/api.py", py_alias, "get", package_name="requests")) == 1

    # import requests; requests.get(...)
    py_mod = b"""
import requests
res = requests.get('https://api.example.com')
"""
    assert len(find_usages("src/api.py", py_mod, "get", package_name="requests")) == 1

    # import requests as req; req.get(...)
    py_mod_alias = b"""
import requests as req
res = req.get('https://api.example.com')
"""
    assert len(find_usages("src/api.py", py_mod_alias, "get", package_name="requests")) == 1

    # Foreign import: from httpx import get
    py_foreign = b"""
from httpx import get
res = get('https://api.example.com')
"""
    assert len(find_usages("src/api.py", py_foreign, "get", package_name="requests")) == 0

    # Local definition: def get(x): ...
    py_local = b"""
def get(x):
    return x
val = get(10)
"""
    assert len(find_usages("src/api.py", py_local, "get", package_name="requests")) == 0


def test_is_test_file_detection():
    from services.code_scanner import is_test_file

    assert is_test_file("tests/test_scanner.py") is True
    assert is_test_file("src/__tests__/app.test.ts") is True
    assert is_test_file("spec/models/user_spec.rb") is True
    assert is_test_file("tests/e2e/test_auth.py") is True
    assert is_test_file("apps/api/tests/test_routers.py") is True
    assert is_test_file("apps/web/components/Button.test.tsx") is True
    assert is_test_file("src/services/scanner.py") is False
    assert is_test_file("src/main.ts") is False


def test_detect_symbol_in_tests():
    from services.code_scanner import detect_symbol_in_tests

    repo_files_with_coverage = {
        "src/client.ts": "import { fetchUser } from 'user-sdk'; fetchUser('123');",
        "tests/client.test.ts": "import { fetchUser } from 'user-sdk'; test('fetch', () => { fetchUser('456'); });",
    }
    assert detect_symbol_in_tests(repo_files_with_coverage, "fetchUser", "user-sdk") is True

    repo_files_without_coverage = {
        "src/client.ts": "import { fetchUser } from 'user-sdk'; fetchUser('123');",
        "tests/other.test.ts": "test('math', () => { expect(1+1).toBe(2); });",
    }
    assert detect_symbol_in_tests(repo_files_without_coverage, "fetchUser", "user-sdk") is False


def test_find_usages_go_selector_and_package_boundary():
    """Go selector expressions, direct calls, and foreign import exclusion."""
    go_code = b"""package main
import (
    "github.com/gin-gonic/gin"
    mylog "github.com/sirupsen/logrus"
)
func main() {
    r := gin.Default()
    mylog.Default()
}
"""
    # Should find gin.Default() but NOT mylog.Default()
    usages = find_usages("main.go", go_code, "Default", package_name="gin")
    assert len(usages) == 1
    assert "gin.Default()" in usages[0]["snippet"]
    assert usages[0]["line_start"] == 7


def test_find_usages_rust_scoped_and_direct_bindings():
    """Rust scoped identifier, direct imports, and field expressions."""
    rust_code = b"""use serde_json::to_string;
use serde_json as sj;
use other_crate::to_string as other_to_string;

fn main() {
    let s = to_string(&foo);
    let v = sj::from_str(&s);
    let o = other_to_string(&bar);
}
"""
    # Direct import usage
    usages_to_string = find_usages("lib.rs", rust_code, "to_string", package_name="serde_json")
    assert len(usages_to_string) == 1
    assert "to_string(&foo)" in usages_to_string[0]["snippet"]

    # Scoped usage
    usages_from_str = find_usages("lib.rs", rust_code, "from_str", package_name="serde_json")
    assert len(usages_from_str) == 1
    assert "sj::from_str(&s)" in usages_from_str[0]["snippet"]


def test_find_usages_java_method_invocation():
    """Java method invocation with import binding."""
    java_code = b"""import com.google.gson.Gson;
class Main {
    void run() {
        Gson g = new Gson();
        g.toJson(data);
    }
}
"""
    usages = find_usages("Main.java", java_code, "toJson", package_name="gson")
    assert len(usages) == 1
    assert "g.toJson(data)" in usages[0]["snippet"]


def test_find_usages_ruby_require_and_call():
    """Ruby require statement and method call."""
    rb_code = b"""require "json"
def process(data)
    JSON.parse(data)
end
"""
    usages = find_usages("app.rb", rb_code, "parse", package_name="json")
    assert len(usages) == 1
    assert "JSON.parse(data)" in usages[0]["snippet"]


def test_find_usages_csharp_member_access():
    """C# using directive and member access expression."""
    cs_code = b"""using System.Text.Json;
class Program {
    void Main() {
        JsonSerializer.Serialize(obj);
    }
}
"""
    usages = find_usages("Program.cs", cs_code, "Serialize", package_name="System.Text.Json")
    assert len(usages) == 1
    assert "JsonSerializer.Serialize(obj)" in usages[0]["snippet"]


def test_polyglot_is_test_file():
    """Polyglot test file pattern detection across Go, Rust, Java, Ruby, C#."""
    from services.code_scanner import is_test_file

    assert is_test_file("pkg/server/server_test.go") is True
    assert is_test_file("src/tests/test_model.rs") is True
    assert is_test_file("src/test/java/UserTest.java") is True
    assert is_test_file("spec/models/order_spec.rb") is True
    assert is_test_file("Tests/ApiTests.cs") is True
    assert is_test_file("pkg/server/server.go") is False
    assert is_test_file("src/main.rs") is False
    assert is_test_file("src/User.java") is False



