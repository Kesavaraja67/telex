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
