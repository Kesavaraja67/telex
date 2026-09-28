"""
End-to-End integration fixture test for semantic vs mechanical risk classification (ISSUE-2).
Proves the core feedback gap is closed:
1. Ingestion of release notes with both a mechanical rename and an unadvertised behavior shift.
2. Derivation of is_semantic_risk=True.
3. PR title is prefixed with [semantic-risk].
4. PR body contains the warning banner and risk classification table.
5. requires_human_review evaluates to True, preventing silent automated merges.
6. Purely mechanical changes with high confidence are correctly marked as mechanical.
"""

import pytest
from services.change_extractor import classify_risk
from services.code_scanner import find_usages, is_test_file
from services.github_service import requires_human_review
from jobs.handlers.open_pr import build_pr_metadata

FIXTURE_V1_CODE = b"""
import { fetchConfig, parseUser } from 'core-auth-lib';

export async function login(id: string) {
    const config = fetchConfig();
    return parseUser(id, config);
}
"""

FIXTURE_TEST_CODE = b"""
import { login } from './login';

test('login executes without error', async () => {
    const user = await login('usr_123');
    expect(user).toBeDefined();
});
"""


def test_semantic_risk_pipeline_e2e_behavior_change():
    """
    Scenario: core-auth-lib upgrades v1 -> v2.
    Contains:
      1. Mechanical rename: parseUser -> parseUserProfile (confidence: 0.95)
      2. Semantic behavior change: fetchConfig now throws if SSL cert is invalid (confidence: 0.85, behavior_change)
    """
    # 1. Detected changes from changelog extraction
    changes = [
        {
            "change_type": "renamed",
            "symbol_old": "parseUser",
            "symbol_new": "parseUserProfile",
            "confidence": 0.95,
            "description": "Renamed parseUser to parseUserProfile for API consistency.",
        },
        {
            "change_type": "behavior_change",
            "symbol_old": "fetchConfig",
            "symbol_new": "fetchConfig",
            "confidence": 0.85,
            "description": "Strict SSL certificate verification now enforced by default.",
        },
    ]

    # 2. Risk classification
    risk_results = [
        classify_risk(str(c["change_type"]), float(c["confidence"]))  # type: ignore[arg-type]
        for c in changes
    ]
    assert risk_results[0] is False  # Purely mechanical rename
    assert risk_results[1] is True  # Stricter behavior shift

    # Aggregate risk for the release
    is_semantic_risk = any(risk_results)
    assert is_semantic_risk is True

    # 3. AST call-site discovery
    usages_rename = find_usages(
        "src/login.ts", FIXTURE_V1_CODE, "parseUser", package_name="core-auth-lib"
    )
    assert len(usages_rename) == 1
    assert usages_rename[0]["line_start"] == 6

    usages_behavior = find_usages(
        "src/login.ts", FIXTURE_V1_CODE, "fetchConfig", package_name="core-auth-lib"
    )
    assert len(usages_behavior) == 1
    assert usages_behavior[0]["line_start"] == 5

    # 4. Check test coverage signal (tests do not call fetchConfig directly)
    from services.code_scanner import detect_symbol_in_tests

    test_has_coverage = detect_symbol_in_tests(
        {"tests/login.test.ts": FIXTURE_TEST_CODE.decode("utf-8")},
        "fetchConfig",
        package_name="core-auth-lib",
    )
    assert test_has_coverage is False

    # 5. Human review decision gate
    needs_review = requires_human_review(
        tests_passed=True,  # Tests passed in sandbox
        typecheck_passed=True,  # Types passed in sandbox
        is_semantic_risk=is_semantic_risk,
        has_test_coverage_on_changed_symbol=test_has_coverage,
    )
    # Even though tests and types are green, human review is MANDATORY because of behavior change
    assert needs_review is True

    # 6. PR title & Markdown Metadata Table generation
    base_title = "chore(deps): auto-patch for core-auth-lib@2.0.0"
    pr_title, table = build_pr_metadata(
        change_type="behavior_change, renamed",
        confidence=0.85,
        base_title=base_title,
        allow_install_scripts=False,
        needs_review=needs_review,
        is_semantic_risk=is_semantic_risk,
    )

    assert pr_title == "[semantic-risk] chore(deps): auto-patch for core-auth-lib@2.0.0"
    assert "## Change classification" in table
    assert "[Warning] Possible semantic/behavior change" in table
    assert "> [Review Required] Human review required before merge" in table
    assert "| Install scripts | blocked (default) |" in table


def test_purely_mechanical_change_e2e_contrast():
    """
    Scenario: util-lib upgrades v1 -> v2 with purely mechanical rename.
    Asserts no [semantic-risk] prefix and [Safe] Mechanical change flag.
    """
    change_type = "renamed"
    confidence = 0.98
    is_semantic_risk = classify_risk(change_type, confidence)
    assert is_semantic_risk is False

    base_title = "chore(deps): auto-patch for util-lib@2.0.0"
    pr_title, table = build_pr_metadata(
        change_type=change_type,
        confidence=confidence,
        base_title=base_title,
        allow_install_scripts=False,
        needs_review=False,
        is_semantic_risk=is_semantic_risk,
    )

    assert not pr_title.startswith("[semantic-risk]")
    assert pr_title == "chore(deps): auto-patch for util-lib@2.0.0"
    assert "[Safe] Mechanical change" in table
    assert "[Warning] Possible semantic/behavior change" not in table
    assert "Human review required" not in table
