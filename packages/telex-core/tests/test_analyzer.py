"""Unit tests for telex_core.analyzer."""

from telex_core.analyzer import extract_breaking_changes, parse_changelog_changes


def test_parse_changelog_renames():
    changelog = """
# Release 2.0.0
### Breaking Changes
- Renamed `createCompletion` to `createChatCompletion`
- `oldFunc` -> `newFunc`
"""
    changes = parse_changelog_changes(changelog)
    assert len(changes) == 2
    assert changes[0]["change_type"] == "renamed"
    assert changes[0]["symbol"] == "createCompletion"
    assert changes[0]["symbol_new"] == "createChatCompletion"
    assert changes[1]["change_type"] == "renamed"
    assert changes[1]["symbol"] == "oldFunc"
    assert changes[1]["symbol_new"] == "newFunc"


def test_parse_changelog_removals():
    changelog = """
# Release 3.0.0
- Removed deprecated `fetchUser` method
- Dropped support for `legacyAuth`
"""
    changes = parse_changelog_changes(changelog)
    symbols = {c["symbol"] for c in changes}
    assert "fetchUser" in symbols
    assert "legacyAuth" in symbols
    assert all(c["change_type"] == "removed" for c in changes)


def test_parse_changelog_deprecations():
    changelog = """
# Release 1.5.0
- Deprecated `calculateTax` in favor of new billing API
"""
    changes = parse_changelog_changes(changelog)
    assert len(changes) == 1
    assert changes[0]["change_type"] == "deprecated"
    assert changes[0]["symbol"] == "calculateTax"


def test_extract_breaking_changes_with_changelog_text():
    changelog = """
## 2.0.0
### Breaking
- Parameter order changed for `formatDate`
"""
    changes = extract_breaking_changes(
        package_name="date-utils",
        old_version="1.9.0",
        new_version="2.0.0",
        changelog_text=changelog,
    )
    assert len(changes) == 1
    assert changes[0]["symbol"] == "formatDate"
