"""
Unit tests for services/github_service.py

Covers:
  - requires_human_review: all branch logic
  - detect_repo_environment: --ignore-scripts flag for npm / pnpm / yarn
  - detect_repo_environment: allow_install_scripts=True removes the flag
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.github_service import detect_repo_environment, requires_human_review

# ── requires_human_review ────────────────────────────────────────────────────


def test_requires_human_review_no_tests_recorded():
    """tests_passed=None means no test run was recorded — always requires review."""
    assert (
        requires_human_review(
            tests_passed=None,
            typecheck_passed=None,
            is_semantic_risk=False,
            has_test_coverage_on_changed_symbol=True,
        )
        is True
    )


def test_requires_human_review_tests_failed():
    """tests_passed=False means tests failed — requires review."""
    assert (
        requires_human_review(
            tests_passed=False,
            typecheck_passed=True,
            is_semantic_risk=False,
            has_test_coverage_on_changed_symbol=True,
        )
        is True
    )


def test_requires_human_review_typecheck_failed():
    """typecheck_passed=False means typecheck failed — requires review."""
    assert (
        requires_human_review(
            tests_passed=True,
            typecheck_passed=False,
            is_semantic_risk=False,
            has_test_coverage_on_changed_symbol=True,
        )
        is True
    )


def test_requires_human_review_typecheck_none():
    """typecheck_passed=None means no typecheck recorded — requires review."""
    assert (
        requires_human_review(
            tests_passed=True,
            typecheck_passed=None,
            is_semantic_risk=False,
            has_test_coverage_on_changed_symbol=True,
        )
        is True
    )


def test_requires_human_review_semantic_risk():
    """is_semantic_risk=True triggers review even when tests passed."""
    assert (
        requires_human_review(
            tests_passed=True,
            typecheck_passed=True,
            is_semantic_risk=True,
            has_test_coverage_on_changed_symbol=True,
        )
        is True
    )


def test_requires_human_review_no_coverage():
    """has_test_coverage_on_changed_symbol=False triggers review (unknown coverage)."""
    assert (
        requires_human_review(
            tests_passed=True,
            typecheck_passed=True,
            is_semantic_risk=False,
            has_test_coverage_on_changed_symbol=False,
        )
        is True
    )


def test_requires_human_review_all_clear():
    """All conditions satisfied — no review required."""
    assert (
        requires_human_review(
            tests_passed=True,
            typecheck_passed=True,
            is_semantic_risk=False,
            has_test_coverage_on_changed_symbol=True,
        )
        is False
    )


# ── detect_repo_environment — --ignore-scripts ───────────────────────────────


def _make_mock_github(lockfile: str, scripts: dict | None = None):
    """
    Build a minimal mock GitHub client that makes detect_repo_environment
    think it found a package.json with the given lockfile in the repo root.
    """
    scripts = scripts or {"test": "jest", "typecheck": "tsc"}
    pkg_json = json.dumps({"scripts": scripts}).encode("utf-8")

    mock_pkg_file = MagicMock()
    mock_pkg_file.decoded_content = pkg_json

    root_items = ["package.json", lockfile]
    root_file_mocks = [MagicMock(name=n) for n in root_items]
    for fm, n in zip(root_file_mocks, root_items):
        fm.name = n

    mock_repo = MagicMock()
    mock_repo.get_contents.side_effect = lambda path, ref="main": (
        root_file_mocks if path == "" else mock_pkg_file
    )

    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_repo
    return mock_gh


def _call_detect(lockfile: str, allow_install_scripts: bool = False) -> dict:
    mock_gh = _make_mock_github(lockfile)
    with patch("services.github_service.get_installation_client", return_value=mock_gh):
        return detect_repo_environment(
            repo_full_name="owner/repo",
            installation_id=12345,
            ref="main",
            allow_install_scripts=allow_install_scripts,
        )


def test_detect_npm_blocks_scripts_by_default():
    """npm ci becomes npm ci --ignore-scripts when allow_install_scripts=False."""
    env = _call_detect("package-lock.json", allow_install_scripts=False)
    assert env["install_cmd"] == "npm ci --ignore-scripts"


def test_detect_pnpm_blocks_scripts_by_default():
    """pnpm install --frozen-lockfile becomes ...--ignore-scripts by default."""
    env = _call_detect("pnpm-lock.yaml", allow_install_scripts=False)
    assert env["install_cmd"] == "pnpm install --frozen-lockfile --ignore-scripts"


def test_detect_yarn_blocks_scripts_by_default():
    """yarn install --frozen-lockfile becomes ...--ignore-scripts by default."""
    env = _call_detect("yarn.lock", allow_install_scripts=False)
    assert env["install_cmd"] == "yarn install --frozen-lockfile --ignore-scripts"


def test_detect_npm_allows_scripts_when_opted_in():
    """When allow_install_scripts=True, --ignore-scripts is NOT appended."""
    env = _call_detect("package-lock.json", allow_install_scripts=True)
    assert "--ignore-scripts" not in env["install_cmd"]
    assert env["install_cmd"] == "npm ci"


def test_detect_pnpm_allows_scripts_when_opted_in():
    env = _call_detect("pnpm-lock.yaml", allow_install_scripts=True)
    assert "--ignore-scripts" not in env["install_cmd"]
    assert env["install_cmd"] == "pnpm install --frozen-lockfile"


def test_detect_yarn_allows_scripts_when_opted_in():
    env = _call_detect("yarn.lock", allow_install_scripts=True)
    assert "--ignore-scripts" not in env["install_cmd"]
    assert env["install_cmd"] == "yarn install --frozen-lockfile"


def test_detect_default_fallback_blocks_scripts():
    """
    When GitHub API fails entirely the fallback env_info must also block scripts.
    """
    with patch(
        "services.github_service.get_installation_client",
        side_effect=RuntimeError("rate limit"),
    ):
        env = detect_repo_environment(
            repo_full_name="owner/repo",
            installation_id=12345,
            allow_install_scripts=False,
        )
    assert "--ignore-scripts" in env["install_cmd"]


def test_detect_default_fallback_allows_scripts_when_opted_in():
    """Fallback env_info omits --ignore-scripts when opt-in flag is True."""
    with patch(
        "services.github_service.get_installation_client",
        side_effect=RuntimeError("rate limit"),
    ):
        env = detect_repo_environment(
            repo_full_name="owner/repo",
            installation_id=12345,
            allow_install_scripts=True,
        )
    assert "--ignore-scripts" not in env["install_cmd"]


# ── generate_telex_verification_workflow ─────────────────────────────────────


def test_generate_telex_verification_workflow_uses_ignore_scripts():
    """CI YAML contains the flag-adjusted install command."""
    from services.github_service import generate_telex_verification_workflow

    env_info = {
        "ecosystem": "node",
        "package_manager": "npm",
        "install_cmd": "npm ci --ignore-scripts",
        "test_cmd": "npm test",
        "typecheck_cmd": "npx tsc --noEmit",
    }
    workflow = generate_telex_verification_workflow(env_info, branch_name="telex/verify/123")
    assert "npm ci --ignore-scripts" in workflow


# ── open_patch_pr ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_open_patch_pr_applies_needs_human_review_label():
    """open_patch_pr attaches needs-human-review label when gate triggers."""
    from github import GithubException
    from services.github_service import open_patch_pr

    mock_gh = MagicMock()
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    mock_branch = MagicMock()
    mock_branch.commit.sha = "head-sha"
    mock_repo.get_branch.return_value = mock_branch

    mock_content_file = MagicMock()
    mock_content_file.sha = "file-sha"
    mock_repo.get_contents.return_value = mock_content_file

    mock_pr = MagicMock()
    mock_pr.number = 42
    mock_pr.html_url = "https://github.com/owner/repo/pull/42"
    mock_repo.create_pull.return_value = mock_pr

    mock_label = MagicMock()
    mock_repo.get_label.return_value = mock_label

    patches = [
        {
            "file_path": "src/index.ts",
            "new_content": "console.log('patched');",
            "package_name": "my-pkg",
            "new_version": "2.0.0",
        }
    ]

    with patch("services.github_service.get_installation_client", return_value=mock_gh):
        url, num = await open_patch_pr(
            repo_full_name="owner/repo",
            installation_id=123,
            branch_name="telex/patch-1",
            patches=patches,
            summary="Test patch summary",
            is_semantic_risk=True,
        )

    assert url == "https://github.com/owner/repo/pull/42"
    assert num == 42
    mock_pr.add_to_labels.assert_called_once_with(mock_label)
    # PR title should have received [semantic-risk] prefix
    create_pull_args = mock_repo.create_pull.call_args[1]
    assert create_pull_args["title"].startswith("[semantic-risk]")


@pytest.mark.asyncio
async def test_open_patch_pr_creates_label_if_missing():
    """If the label does not exist on the repo, create_label is called."""
    from github import GithubException
    from services.github_service import open_patch_pr

    mock_gh = MagicMock()
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    mock_branch = MagicMock()
    mock_branch.commit.sha = "head-sha"
    mock_repo.get_branch.return_value = mock_branch

    mock_content_file = MagicMock()
    mock_content_file.sha = "file-sha"
    mock_repo.get_contents.return_value = mock_content_file

    mock_pr = MagicMock()
    mock_pr.number = 43
    mock_pr.html_url = "https://github.com/owner/repo/pull/43"
    mock_repo.create_pull.return_value = mock_pr

    created_label = MagicMock()
    # First get_label raises GithubException (404), then create_label succeeds
    mock_repo.get_label.side_effect = GithubException(404, "Not Found")
    mock_repo.create_label.return_value = created_label

    patches = [
        {
            "file_path": "src/index.ts",
            "new_content": "console.log('patched');",
            "package_name": "my-pkg",
            "new_version": "2.0.0",
        }
    ]

    with patch("services.github_service.get_installation_client", return_value=mock_gh):
        await open_patch_pr(
            repo_full_name="owner/repo",
            installation_id=123,
            branch_name="telex/patch-2",
            patches=patches,
            summary="Test patch summary",
            is_semantic_risk=False,
        )

    mock_repo.create_label.assert_called_once()
    mock_pr.add_to_labels.assert_called_once_with(created_label)


@pytest.mark.asyncio
async def test_open_patch_pr_raises_when_label_fails():
    """If get_label and create_label both fail, open_patch_pr raises GithubException."""
    from github import GithubException
    from services.github_service import open_patch_pr

    mock_gh = MagicMock()
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    mock_branch = MagicMock()
    mock_branch.commit.sha = "head-sha"
    mock_repo.get_branch.return_value = mock_branch

    mock_content_file = MagicMock()
    mock_content_file.sha = "file-sha"
    mock_repo.get_contents.return_value = mock_content_file

    mock_pr = MagicMock()
    mock_pr.number = 44
    mock_pr.html_url = "https://github.com/owner/repo/pull/44"
    mock_repo.create_pull.return_value = mock_pr

    mock_repo.get_label.side_effect = GithubException(500, "Internal Server Error")
    mock_repo.create_label.side_effect = GithubException(500, "Internal Server Error")

    patches = [
        {
            "file_path": "src/index.ts",
            "new_content": "console.log('patched');",
            "package_name": "my-pkg",
            "new_version": "2.0.0",
        }
    ]

    with patch("services.github_service.get_installation_client", return_value=mock_gh):
        with pytest.raises(GithubException):
            await open_patch_pr(
                repo_full_name="owner/repo",
                installation_id=123,
                branch_name="telex/patch-fail",
                patches=patches,
                summary="Test patch summary",
                is_semantic_risk=True,
            )


def test_detect_python_blocks_scripts_by_default():
    """Python repo skips pip install when allow_install_scripts=False."""
    root_items = ["requirements.txt"]
    root_file_mocks = [MagicMock(name=n) for n in root_items]
    for fm, n in zip(root_file_mocks, root_items):
        fm.name = n

    mock_repo = MagicMock()
    mock_repo.get_contents.return_value = root_file_mocks
    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    with patch("services.github_service.get_installation_client", return_value=mock_gh):
        env = detect_repo_environment(
            repo_full_name="owner/repo",
            installation_id=12345,
            ref="main",
            allow_install_scripts=False,
        )
    assert env["ecosystem"] == "python"
    assert "Dependency installation skipped" in env["install_cmd"]


def test_detect_python_allows_scripts_when_opted_in():
    """Python repo runs pip install when allow_install_scripts=True."""
    root_items = ["requirements.txt"]
    root_file_mocks = [MagicMock(name=n) for n in root_items]
    for fm, n in zip(root_file_mocks, root_items):
        fm.name = n

    mock_repo = MagicMock()
    mock_repo.get_contents.return_value = root_file_mocks
    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    with patch("services.github_service.get_installation_client", return_value=mock_gh):
        env = detect_repo_environment(
            repo_full_name="owner/repo",
            installation_id=12345,
            ref="main",
            allow_install_scripts=True,
        )
    assert env["ecosystem"] == "python"
    assert env["install_cmd"] == "pip install -r requirements.txt"


@pytest.mark.asyncio
async def test_wait_for_telex_verification_success():
    """Telex verification passes when Telex check run completes with success."""
    from services.github_service import wait_for_telex_verification

    mock_check = MagicMock()
    mock_check.name = "Telex Validation"
    mock_check.status = "completed"
    mock_check.conclusion = "success"
    mock_check.output = MagicMock(title="Passed", summary="All gates passed", text=None)

    mock_commit = MagicMock()
    mock_commit.get_check_runs.return_value = [mock_check]

    mock_repo = MagicMock()
    mock_repo.get_commit.return_value = mock_commit
    mock_repo.get_workflow_runs.return_value = []

    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    with patch("services.github_service.get_installation_client", return_value=mock_gh):
        result = await wait_for_telex_verification(
            repo_full_name="owner/repo",
            installation_id=12345,
            commit_sha="abcd123",
            expected_workflow_name="Telex Validation",
            timeout_seconds=5.0,
            poll_interval=0.1,
        )

    assert result["is_verified"] is True
    assert result["conclusion"] == "success"
    assert result["workflow_found"] is True


@pytest.mark.asyncio
async def test_wait_for_telex_verification_fails_on_neutral_or_skipped():
    """Neutral or skipped conclusions must fail closed (not count as success)."""
    from services.github_service import wait_for_telex_verification

    for concl in ["neutral", "skipped", "failure"]:
        mock_check = MagicMock()
        mock_check.name = "telex-ci"
        mock_check.status = "completed"
        mock_check.conclusion = concl
        mock_check.output = MagicMock(title=concl, summary=f"Finished with {concl}", text="log")

        mock_commit = MagicMock()
        mock_commit.get_check_runs.return_value = [mock_check]

        mock_repo = MagicMock()
        mock_repo.get_commit.return_value = mock_commit
        mock_repo.get_workflow_runs.return_value = []

        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo

        with patch("services.github_service.get_installation_client", return_value=mock_gh):
            result = await wait_for_telex_verification(
                repo_full_name="owner/repo",
                installation_id=12345,
                commit_sha="abcd123",
                expected_workflow_name="telex-ci",
                timeout_seconds=5.0,
                poll_interval=0.1,
            )

        assert result["is_verified"] is False
        assert result["conclusion"] == "failure"


@pytest.mark.asyncio
async def test_wait_for_telex_verification_ignores_unrelated_checks():
    """Unrelated check runs (e.g. unrelated CI) must NOT be counted as Telex verification."""
    from services.github_service import wait_for_telex_verification

    # A check run that succeeded, but has nothing to do with telex or expected workflow
    mock_check = MagicMock()
    mock_check.name = "unrelated-build-step"
    mock_check.status = "completed"
    mock_check.conclusion = "success"
    mock_check.output = MagicMock(title="Success", summary="Done", text=None)

    mock_commit = MagicMock()
    mock_commit.get_check_runs.return_value = [mock_check]

    mock_repo = MagicMock()
    mock_repo.get_commit.return_value = mock_commit
    mock_repo.get_workflow_runs.return_value = []

    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    with patch("services.github_service.get_installation_client", return_value=mock_gh):
        result = await wait_for_telex_verification(
            repo_full_name="owner/repo",
            installation_id=12345,
            commit_sha="abcd123",
            expected_workflow_name="telex-verification",
            timeout_seconds=0.2,
            poll_interval=0.1,
        )

    # Must time out and NOT verify based on unrelated checks
    assert result["is_verified"] is False
    assert result["workflow_found"] is False
    assert result["conclusion"] == "timed_out"
