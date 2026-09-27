"""
Unit tests for jobs/handlers/open_pr.py

Covers Phase 3 verification pipeline invariants:
1. Idempotency: skip when an open PR already exists for (repo_id, package_version_id).
2. Base commit drift: fail closed and abort PR creation when default branch HEAD != base_sha.
3. Patch application integrity: fail closed and abort PR creation when apply_diff_to_content fails.
4. Happy path: PR opened cleanly when all pre-flight invariants are satisfied.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from db.models import (
    CodeUsage,
    DetectedChange,
    Installation,
    Package,
    PackageVersion,
    Patch,
    PullRequest,
    Repo,
    ValidationRun,
)
from jobs.handlers import open_pr


@pytest.fixture
def open_pr_setup():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    pkg_id = uuid.uuid4()
    pv_id = uuid.uuid4()
    dc_id = uuid.uuid4()
    cu_id = uuid.uuid4()
    patch_id = uuid.uuid4()

    repo = Repo(
        id=repo_id,
        installation_id=inst_id,
        full_name="acme/service",
        default_branch="main",
        requires_tests=False,
        requires_typecheck=False,
    )
    installation = Installation(
        id=inst_id,
        github_installation_id=777888,
        account_login="acme",
        account_type="Organization",
    )
    pkg = Package(
        id=pkg_id,
        ecosystem="npm",
        name="lodash",
    )
    pv = PackageVersion(
        id=pv_id,
        package_id=pkg_id,
        version="4.17.21",
    )
    dc = DetectedChange(
        id=dc_id,
        package_version_id=pv_id,
        change_type="signature_change",
        symbol_old="cloneDeep",
        symbol_new="cloneDeep",
        description="cloneDeep signature changed",
        confidence=0.9,
    )
    cu = CodeUsage(
        id=cu_id,
        repo_id=repo_id,
        detected_change_id=dc_id,
        file_path="src/index.js",
        line_start=1,
        line_end=1,
        snippet="lodash.cloneDeep(x)",
        status="verified",
    )
    valid_patch = Patch(
        id=patch_id,
        code_usage_id=cu_id,
        diff="--- a/src/index.js\n+++ b/src/index.js\n@@ -1,1 +1,1 @@\n-lodash.cloneDeep(x)\n+structuredClone(x)",
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        prompt_version="v1",
        verified=True,
    )
    vr = ValidationRun(
        id=uuid.uuid4(),
        patch_id=patch_id,
        verification_mode="full",
        applies_cleanly=True,
        parses=True,
        typechecks=True,
        tests_pass=True,
        scope_ok=True,
        log="[base_sha:sha-base-123] [commit_sha:sha-commit-456]\nTests passed",
    )

    return {
        "repo": repo,
        "installation": installation,
        "package": pkg,
        "package_version": pv,
        "detected_change": dc,
        "code_usage": cu,
        "patch": valid_patch,
        "validation_run": vr,
    }


def create_mock_session(entities, existing_prs=None):
    session = AsyncMock()
    added_items = []

    def fake_add(item):
        added_items.append(item)

    async def fake_get(model_cls, entity_id):
        for e in entities.values():
            if isinstance(e, model_cls) and getattr(e, "id", None) == entity_id:
                return e
        return None

    async def fake_execute(stmt):
        mock_result = MagicMock()
        # Handle select(PullRequest)
        stmt_str = str(stmt).lower()
        if "from pull_requests" in stmt_str:
            if existing_prs:
                mock_result.scalars.return_value = existing_prs
                mock_result.scalar_one_or_none.return_value = (
                    existing_prs[0] if existing_prs else None
                )
            else:
                mock_result.scalars.return_value = []
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        # Handle select(Patch)
        if "from patches" in stmt_str:
            mock_result.scalars.return_value = [entities["patch"]]
            return mock_result

        # Handle select(ValidationRun)
        if "from validation_runs" in stmt_str:
            mock_result.scalar_one_or_none.return_value = entities.get("validation_run")
            return mock_result

        mock_result.scalars.return_value = []
        mock_result.scalar_one_or_none.return_value = None
        return mock_result

    session.get = AsyncMock(side_effect=fake_get)
    session.add = MagicMock(side_effect=fake_add)
    session.commit = AsyncMock()
    session.execute = AsyncMock(side_effect=fake_execute)
    session.added_items = added_items
    return session


@pytest.mark.asyncio
async def test_open_pr_idempotency_skips_when_open_pr_exists(
    open_pr_setup, monkeypatch
):
    """When an open PR already exists for (repo_id, package_version_id), open_pr must skip."""
    entities = open_pr_setup
    repo = entities["repo"]
    pv = entities["package_version"]

    existing_pr = PullRequest(
        id=uuid.uuid4(),
        repo_id=repo.id,
        package_version_id=pv.id,
        github_pr_number=42,
        github_pr_url="https://github.com/acme/service/pull/42",
        status="open",
        patch_ids=[entities["patch"].id],
    )

    mock_session = create_mock_session(entities, existing_prs=[existing_pr])
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("db.session.AsyncSessionLocal", lambda: mock_session_ctx)

    mock_open_patch_pr = AsyncMock()
    monkeypatch.setattr("services.github_service.open_patch_pr", mock_open_patch_pr)

    payload = {
        "repo_id": str(repo.id),
        "package_version_id": str(pv.id),
    }

    await open_pr.run(payload)

    # Must NOT call open_patch_pr because open PR already exists
    mock_open_patch_pr.assert_not_called()


@pytest.mark.asyncio
async def test_open_pr_fails_closed_when_base_branch_drifted(
    open_pr_setup, monkeypatch
):
    """When target branch HEAD does not match base_sha, fail closed and emit patch_failed event."""
    entities = open_pr_setup
    repo = entities["repo"]
    pv = entities["package_version"]

    mock_session = create_mock_session(entities, existing_prs=[])
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("db.session.AsyncSessionLocal", lambda: mock_session_ctx)

    # Mock PyGithub client
    mock_branch = MagicMock()
    mock_branch.commit.sha = "new-drifted-sha-999"  # Drifted from sha-base-123

    mock_gh_repo = MagicMock()
    mock_gh_repo.get_branch.return_value = mock_branch

    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_gh_repo
    monkeypatch.setattr(
        "services.github_service.get_installation_client", lambda *args: mock_gh
    )

    mock_open_patch_pr = AsyncMock()
    monkeypatch.setattr("services.github_service.open_patch_pr", mock_open_patch_pr)

    mock_record_event = AsyncMock()
    monkeypatch.setattr("services.incident_events.record_event", mock_record_event)

    payload = {
        "repo_id": str(repo.id),
        "package_version_id": str(pv.id),
        "base_sha": "sha-base-123",
    }

    await open_pr.run(payload)

    # Must NOT open PR on drifted branch
    mock_open_patch_pr.assert_not_called()
    # Must record patch_failed event
    mock_record_event.assert_called_once()
    assert mock_record_event.call_args[1]["event_type"] == "patch_failed"
    assert mock_record_event.call_args[1]["payload"]["reason"] == "base_branch_drifted"


@pytest.mark.asyncio
async def test_open_pr_fails_closed_when_diff_application_fails(
    open_pr_setup, monkeypatch
):
    """When apply_diff_to_content fails, fail closed (never fall back to original file)."""
    entities = open_pr_setup
    repo = entities["repo"]
    pv = entities["package_version"]

    mock_session = create_mock_session(entities, existing_prs=[])
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("db.session.AsyncSessionLocal", lambda: mock_session_ctx)

    # Mock PyGithub client
    mock_branch = MagicMock()
    mock_branch.commit.sha = "sha-base-123"

    mock_content_file = MagicMock()
    mock_content_file.decoded_content = b"lodash.cloneDeep(x)"

    mock_gh_repo = MagicMock()
    mock_gh_repo.get_branch.return_value = mock_branch
    mock_gh_repo.get_contents.return_value = mock_content_file

    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_gh_repo
    monkeypatch.setattr(
        "services.github_service.get_installation_client", lambda *args: mock_gh
    )

    # Simulate diff application failure
    monkeypatch.setattr(
        "services.github_service.apply_diff_to_content",
        lambda fpath, orig, diff: (False, "", "Hunk #1 failed at offset 10"),
    )

    mock_open_patch_pr = AsyncMock()
    monkeypatch.setattr("services.github_service.open_patch_pr", mock_open_patch_pr)

    mock_record_event = AsyncMock()
    monkeypatch.setattr("services.incident_events.record_event", mock_record_event)

    payload = {
        "repo_id": str(repo.id),
        "package_version_id": str(pv.id),
        "base_sha": "sha-base-123",
    }

    await open_pr.run(payload)

    # Must NOT call open_patch_pr with unmodified file
    mock_open_patch_pr.assert_not_called()
    # Must record patch_failed event
    mock_record_event.assert_called_once()
    assert mock_record_event.call_args[1]["event_type"] == "patch_failed"
    assert (
        mock_record_event.call_args[1]["payload"]["reason"]
        == "apply_diff_to_content_failed"
    )


@pytest.mark.asyncio
async def test_open_pr_happy_path(open_pr_setup, monkeypatch):
    """When validation passes, branch matches base_sha, and diff applies cleanly, open PR."""
    entities = open_pr_setup
    repo = entities["repo"]
    pv = entities["package_version"]

    mock_session = create_mock_session(entities, existing_prs=[])
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("db.session.AsyncSessionLocal", lambda: mock_session_ctx)

    # Mock PyGithub client
    mock_branch = MagicMock()
    mock_branch.commit.sha = "sha-base-123"

    mock_content_file = MagicMock()
    mock_content_file.decoded_content = b"lodash.cloneDeep(x)"

    mock_gh_repo = MagicMock()
    mock_gh_repo.get_branch.return_value = mock_branch
    mock_gh_repo.get_contents.return_value = mock_content_file

    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_gh_repo
    monkeypatch.setattr(
        "services.github_service.get_installation_client", lambda *args: mock_gh
    )

    monkeypatch.setattr(
        "services.github_service.apply_diff_to_content",
        lambda fpath, orig, diff: (True, "structuredClone(x)", "Applied cleanly"),
    )

    mock_open_patch_pr = AsyncMock(
        return_value=("https://github.com/acme/service/pull/99", 99)
    )
    monkeypatch.setattr("services.github_service.open_patch_pr", mock_open_patch_pr)

    mock_create_check_run = AsyncMock()
    monkeypatch.setattr(
        "services.github_service.create_check_run", mock_create_check_run
    )

    mock_record_event = AsyncMock()
    monkeypatch.setattr("services.incident_events.record_event", mock_record_event)

    payload = {
        "repo_id": str(repo.id),
        "package_version_id": str(pv.id),
        "base_sha": "sha-base-123",
    }

    await open_pr.run(payload)

    # Must open PR on GitHub
    mock_open_patch_pr.assert_called_once()
    # Must record pr_opened event
    mock_record_event.assert_called_once()
    assert mock_record_event.call_args[1]["event_type"] == "pr_opened"
    assert mock_record_event.call_args[1]["payload"]["github_pr_number"] == 99
