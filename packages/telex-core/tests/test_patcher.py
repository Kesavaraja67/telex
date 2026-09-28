"""Unit tests for telex_core.patcher."""

from pathlib import Path

from telex_core.patcher import apply_diff_to_content, patch_file


def test_apply_diff_clean():
    original = "function test() {\n    return 42;\n}\n"
    diff = """--- a/test.ts
+++ b/test.ts
@@ -1,3 +1,3 @@
 function test() {
-    return 42;
+    return 100;
 }
"""
    apply_ok, new_content, _log = apply_diff_to_content("test.ts", original, diff)
    assert apply_ok is True
    assert "return 100;" in new_content
    assert "return 42;" not in new_content


def test_apply_diff_fail_closed_on_corrupt_hunk():
    original = "const a = 1;\nconst b = 2;\n"
    diff = """--- a/test.ts
+++ b/test.ts
@@ -1,2 +1,2 @@
-const NON_EXISTENT = 999;
+const REPLACED = 1000;
"""
    apply_ok, new_content, log = apply_diff_to_content("test.ts", original, diff)
    assert apply_ok is False
    assert new_content == original
    assert "Hunk #1 failed" in log


def test_patch_file_dry_run_and_apply(tmp_path: Path):
    target = tmp_path / "code.js"
    target.write_text("console.log('old');\n", encoding="utf-8")

    diff = """--- a/code.js
+++ b/code.js
@@ -1,1 +1,1 @@
-console.log('old');
+console.log('new');
"""
    # Dry run
    res_dry = patch_file(str(target), diff, dry_run=True)
    assert res_dry["success"] is True
    assert target.read_text(encoding="utf-8") == "console.log('old');\n"

    # Real application
    res_real = patch_file(str(target), diff, dry_run=False)
    assert res_real["success"] is True
    assert target.read_text(encoding="utf-8") == "console.log('new');\n"


def test_apply_diff_zero_count_hunk_with_accumulated_offset():
    """Hunks with old_count=0 (pure insertions) respect offset from earlier hunks."""
    original = "line 1\nline 2\nline 3\n"
    diff = """--- a/test.txt
+++ b/test.txt
@@ -1,1 +1,2 @@
-line 1
+line 1a
+line 1b
@@ -2,0 +3,1 @@
+line 2.5
"""
    apply_ok, new_content, log = apply_diff_to_content("test.txt", original, diff)
    assert apply_ok is True
    assert new_content == "line 1a\nline 1b\nline 2\nline 2.5\nline 3\n"

