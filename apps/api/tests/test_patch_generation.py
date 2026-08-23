import pytest
from jobs.handlers.generate_patch import validate_patch
from services.patch_providers.gemini import extract_diff


def test_validate_patch_valid_diff():
    """Valid unified diff that modifies the target snippet passes all validation steps."""
    snippet = "const res = await openai.createCompletion({ model: 'text-davinci-003' });"
    diff = """--- a/src/index.ts
+++ b/src/index.ts
@@ -1,1 +1,1 @@
-const res = await openai.createCompletion({ model: 'text-davinci-003' });
+const res = await openai.chat.completions.create({ model: 'gpt-4' });"""

    applies_cleanly, parses, scope_ok = validate_patch(diff, snippet)
    assert applies_cleanly is True
    assert parses is True
    assert scope_ok is True


def test_validate_patch_out_of_scope():
    """Diff that modifies lines unrelated to the code snippet fails scope validation."""
    snippet = "const res = await openai.createCompletion({ model: 'text-davinci-003' });"
    diff = """--- a/src/index.ts
+++ b/src/index.ts
@@ -10,1 +10,1 @@
-const databaseUrl = process.env.DATABASE_URL;
+const databaseUrl = 'postgres://localhost';"""

    applies_cleanly, parses, scope_ok = validate_patch(diff, snippet)
    assert applies_cleanly is True
    assert scope_ok is False
    assert parses is False


def test_validate_patch_unable_to_patch_sentinel():
    """UNABLE_TO_PATCH sentinel returns (False, False, False)."""
    applies_cleanly, parses, scope_ok = validate_patch("UNABLE_TO_PATCH", "some code")
    assert applies_cleanly is False
    assert parses is False
    assert scope_ok is False


def test_validate_patch_invalid_format():
    """Empty or unstructured text fails diff validation."""
    applies_cleanly, parses, scope_ok = validate_patch("Just some random text explanation", "some code")
    assert applies_cleanly is False
    assert parses is False
    assert scope_ok is False


def test_extract_diff_markdown_fences():
    """Extracts unified diff from markdown code block."""
    raw = """Here is the fix for the breaking change:
```diff
--- a/src/index.ts
+++ b/src/index.ts
@@ -1,1 +1,1 @@
-oldFunc();
+newFunc();
```
Please review and merge."""
    extracted = extract_diff(raw)
    assert extracted.startswith("--- a/src/index.ts")
    assert "+newFunc();" in extracted


def test_extract_diff_unable_to_patch_handling():
    """Extracts UNABLE_TO_PATCH when model signals inability to patch."""
    assert extract_diff("I cannot patch this: UNABLE_TO_PATCH") == "UNABLE_TO_PATCH"
    assert extract_diff("UNABLE_TO_PATCH") == "UNABLE_TO_PATCH"


@pytest.mark.asyncio
async def test_verify_patch_in_clone_no_installation_is_structural_only():
    """Without installation token, verification_mode is 'structural_only' and is_verified is False."""
    from jobs.handlers.generate_patch import verify_patch_in_clone

    snippet = "const res = await openai.createCompletion({ model: 'text-davinci-003' });"
    diff = """--- a/src/index.ts
+++ b/src/index.ts
@@ -1,1 +1,1 @@
-const res = await openai.createCompletion({ model: 'text-davinci-003' });
+const res = await openai.chat.completions.create({ model: 'gpt-4' });"""

    result = await verify_patch_in_clone(
        repo_full_name="org/test-repo",
        default_branch="main",
        installation_github_id=None,
        diff=diff,
        code_snippet=snippet,
    )
    assert result["verification_mode"] == "structural_only"
    assert result["is_verified"] is False
    assert result["applies_cleanly"] is True


@pytest.mark.asyncio
async def test_verify_patch_in_clone_broken_patch_rejected():
    """Broken or out-of-scope diff is rejected by verification gate."""
    from jobs.handlers.generate_patch import verify_patch_in_clone

    snippet = "const res = await openai.createCompletion();"
    broken_diff = "not a valid diff format"

    result = await verify_patch_in_clone(
        repo_full_name="org/test-repo",
        default_branch="main",
        installation_github_id=None,
        diff=broken_diff,
        code_snippet=snippet,
    )
    assert result["verification_mode"] == "structural_only"
    assert result["is_verified"] is False
    assert result["applies_cleanly"] is False


@pytest.mark.asyncio
async def test_verify_patch_in_clone_exception_fails_verification(monkeypatch):
    """Unexpected exception during verification sets verification_mode='error' and is_verified=False."""
    from jobs.handlers.generate_patch import verify_patch_in_clone
    import services.github_service as gh_svc

    snippet = "const res = await openai.createCompletion();"
    diff = """--- a/src/index.ts
+++ b/src/index.ts
@@ -1,1 +1,1 @@
-const res = await openai.createCompletion();
+const res = await openai.chat.completions.create();"""

    monkeypatch.setattr(gh_svc, "get_installation_token", lambda install_id: "fake-token")

    async def mock_exec(*args, **kwargs):
        raise RuntimeError("Subprocess execution failed catastrophically")

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_exec)

    result = await verify_patch_in_clone(
        repo_full_name="org/test-repo",
        default_branch="main",
        installation_github_id=12345,
        diff=diff,
        code_snippet=snippet,
    )
    assert result["verification_mode"] == "error"
    assert result["is_verified"] is False
    assert result["applies_cleanly"] is False


@pytest.mark.asyncio
async def test_verify_patch_in_clone_requires_tests_policy():
    """When requires_tests=True, absence of tests or failing tests invalidates verification."""
    from jobs.handlers.generate_patch import verify_patch_in_clone

    snippet = "const res = await openai.createCompletion();"
    diff = """--- a/src/index.ts
+++ b/src/index.ts
@@ -1,1 +1,1 @@
-const res = await openai.createCompletion();
+const res = await openai.chat.completions.create();"""

    # 1. Structural only without tests when requires_tests=True -> is_verified must be False
    res_strict = await verify_patch_in_clone(
        repo_full_name="org/sample-store",
        default_branch="main",
        installation_github_id=None,
        diff=diff,
        code_snippet=snippet,
        requires_tests=True,
        requires_typecheck=True,
    )
    assert res_strict["is_verified"] is False


