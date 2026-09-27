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


