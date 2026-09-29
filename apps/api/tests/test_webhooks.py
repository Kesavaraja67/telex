"""
Tests for webhook handlers — Section 5.3 acceptance rate tracking.
"""

import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from db.models import Repo, PullRequest
from routers.webhooks import _handle_pull_request


@pytest.mark.asyncio
async def test_handle_pull_request_merged(monkeypatch):
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    mock_repo = Repo(
        id=repo_id,
        github_repo_id=12345,
        full_name="org/repo",
    )

    mock_pr = PullRequest(
        id=pr_id,
        repo_id=repo_id,
        github_pr_number=42,
        github_pr_url="https://github.com/org/repo/pull/42",
        status="open",
        merged=False,
    )

    session = AsyncMock()

    async def fake_execute(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "repos" in stmt_str:
            mock_result.scalar_one_or_none.return_value = mock_repo
        elif "pull_requests" in stmt_str:
            mock_result.scalar_one_or_none.return_value = mock_pr
        else:
            mock_result.scalar_one_or_none.return_value = None
        return mock_result

    session.execute = AsyncMock(side_effect=fake_execute)
    session.commit = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr("routers.webhooks.AsyncSessionLocal", lambda: mock_ctx)

    payload = {
        "action": "closed",
        "pull_request": {
            "number": 42,
            "merged": True,
            "merged_at": "2026-09-15T12:00:00Z",
            "closed_at": "2026-09-15T12:00:00Z",
        },
        "repository": {
            "id": 12345,
        },
    }

    await _handle_pull_request(payload)

    assert mock_pr.status == "merged"
    assert mock_pr.merged is True
    assert mock_pr.merged_at is not None
    assert mock_pr.closed_at is not None
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_pull_request_closed_unmerged(monkeypatch):
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    mock_repo = Repo(
        id=repo_id,
        github_repo_id=12345,
        full_name="org/repo",
    )

    mock_pr = PullRequest(
        id=pr_id,
        repo_id=repo_id,
        github_pr_number=43,
        github_pr_url="https://github.com/org/repo/pull/43",
        status="open",
        merged=False,
    )

    session = AsyncMock()

    async def fake_execute(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "repos" in stmt_str:
            mock_result.scalar_one_or_none.return_value = mock_repo
        elif "pull_requests" in stmt_str:
            mock_result.scalar_one_or_none.return_value = mock_pr
        else:
            mock_result.scalar_one_or_none.return_value = None
        return mock_result

    session.execute = AsyncMock(side_effect=fake_execute)
    session.commit = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr("routers.webhooks.AsyncSessionLocal", lambda: mock_ctx)

    payload = {
        "action": "closed",
        "pull_request": {
            "number": 43,
            "merged": False,
            "merged_at": None,
            "closed_at": "2026-09-15T12:05:00Z",
        },
        "repository": {
            "id": 12345,
        },
    }

    await _handle_pull_request(payload)

    assert mock_pr.status == "closed"
    assert mock_pr.merged is False
    assert mock_pr.merged_at is None
    assert mock_pr.closed_at is not None
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_pull_request_reopened(monkeypatch):
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    mock_repo = Repo(
        id=repo_id,
        github_repo_id=12345,
        full_name="org/repo",
    )

    mock_pr = PullRequest(
        id=pr_id,
        repo_id=repo_id,
        github_pr_number=44,
        github_pr_url="https://github.com/org/repo/pull/44",
        status="closed",
        merged=False,
        closed_at=datetime.now(timezone.utc),
    )

    session = AsyncMock()

    async def fake_execute(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "repos" in stmt_str:
            mock_result.scalar_one_or_none.return_value = mock_repo
        elif "pull_requests" in stmt_str:
            mock_result.scalar_one_or_none.return_value = mock_pr
        else:
            mock_result.scalar_one_or_none.return_value = None
        return mock_result

    session.execute = AsyncMock(side_effect=fake_execute)
    session.commit = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr("routers.webhooks.AsyncSessionLocal", lambda: mock_ctx)

    payload = {
        "action": "reopened",
        "pull_request": {
            "number": 44,
        },
        "repository": {
            "id": 12345,
        },
    }

    await _handle_pull_request(payload)

    assert mock_pr.status == "open"
    assert mock_pr.closed_at is None
    assert mock_pr.merged is False
    assert mock_pr.merged_at is None
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_installation_created(monkeypatch):
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    added_items = []
    session.add = MagicMock(side_effect=lambda x: added_items.append(x))

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("routers.webhooks.AsyncSessionLocal", lambda: mock_ctx)

    payload = {
        "action": "created",
        "installation": {
            "id": 9999,
            "account": {"login": "test-org", "type": "Organization"},
        },
        "repositories": [
            {"id": 111, "full_name": "test-org/repo-1"},
            {"id": 222, "full_name": "test-org/repo-2"},
        ],
    }

    from routers.webhooks import _handle_installation_created

    await _handle_installation_created(payload)
    assert len(added_items) == 3
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_installation_repositories(monkeypatch):
    session = AsyncMock()
    existing_repo = Repo(id=uuid.uuid4(), github_repo_id=111, full_name="org/r1", is_active=False)
    repo_to_remove = Repo(id=uuid.uuid4(), github_repo_id=222, full_name="org/r2", is_active=True)

    call_count = 0

    def fake_execute(stmt):
        nonlocal call_count
        call_count += 1
        mock_res = MagicMock()
        if call_count == 1:
            mock_res.scalar_one_or_none.return_value = MagicMock(id=uuid.uuid4())
        elif call_count == 2:
            mock_res.scalar_one_or_none.return_value = existing_repo
        elif call_count == 3:
            mock_res.scalar_one_or_none.return_value = repo_to_remove
        else:
            mock_res.scalar_one_or_none.return_value = None
        return mock_res

    session.execute = AsyncMock(side_effect=fake_execute)
    session.commit = AsyncMock()
    session.add = MagicMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("routers.webhooks.AsyncSessionLocal", lambda: mock_ctx)

    payload = {
        "action": "added",
        "installation": {"id": 12345, "account": {"login": "org", "type": "User"}},
        "repositories_added": [{"id": 111, "full_name": "org/r1"}],
        "repositories_removed": [{"id": 222, "full_name": "org/r2"}],
    }

    from routers.webhooks import _handle_installation_repositories

    await _handle_installation_repositories(payload)
    assert existing_repo.is_active is True
    assert repo_to_remove.is_active is False
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_installation_deleted(monkeypatch):
    session = AsyncMock()
    repo1 = Repo(id=uuid.uuid4(), is_active=True)
    repo2 = Repo(id=uuid.uuid4(), is_active=True)

    mock_inst = MagicMock(id=uuid.uuid4())

    def fake_execute(stmt):
        mock_res = MagicMock()
        stmt_str = str(stmt)
        if "installations" in stmt_str:
            mock_res.scalar_one_or_none.return_value = mock_inst
        else:
            mock_res.scalars.return_value = [repo1, repo2]
        return mock_res

    session.execute = AsyncMock(side_effect=fake_execute)
    session.commit = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("routers.webhooks.AsyncSessionLocal", lambda: mock_ctx)

    from routers.webhooks import _handle_installation_deleted

    await _handle_installation_deleted(
        {"action": "deleted", "installation": {"id": 123, "account": {"login": "org"}}}
    )
    assert repo1.is_active is False
    assert repo2.is_active is False
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_github_webhook_invalid_signature(monkeypatch):
    from fastapi import HTTPException
    from routers.webhooks import github_webhook

    mock_request = AsyncMock()
    mock_request.body = AsyncMock(return_value=b'{"action":"ping"}')

    monkeypatch.setattr("routers.webhooks.verify_webhook_signature", lambda body, sig: False)

    with pytest.raises(HTTPException) as exc_info:
        await github_webhook(mock_request, x_hub_signature_256="sha256=invalid")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_github_webhook_dispatch_events(monkeypatch):
    from routers.webhooks import github_webhook

    mock_request = AsyncMock()
    mock_request.body = AsyncMock(return_value=b"{}")
    mock_request.json = AsyncMock(return_value={"action": "created"})

    monkeypatch.setattr("routers.webhooks.verify_webhook_signature", lambda body, sig: True)

    created_called = False

    async def fake_created(payload):
        nonlocal created_called
        created_called = True

    monkeypatch.setattr("routers.webhooks._handle_installation_created", fake_created)

    res = await github_webhook(
        mock_request, x_hub_signature_256="sha256=valid", x_github_event="installation"
    )
    assert res == {"ok": True}
    assert created_called


@pytest.mark.asyncio
async def test_handle_push_enqueues_update_atlas_graph(monkeypatch):
    from routers.webhooks import _handle_push

    repo_id = uuid.uuid4()
    mock_repo = Repo(id=repo_id, github_repo_id=999, full_name="owner/repo", is_active=True)

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_repo
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("routers.webhooks.AsyncSessionLocal", lambda: mock_ctx)

    mock_enqueue = AsyncMock()
    monkeypatch.setattr("routers.webhooks.enqueue_job", mock_enqueue)

    payload = {
        "ref": "refs/heads/main",
        "repository": {
            "id": 999,
            "default_branch": "main",
            "full_name": "owner/repo",
        },
        "after": "deadbeef1234",
        "commits": [
            {
                "added": ["src/new.ts"],
                "modified": ["src/index.ts"],
                "removed": ["src/old.ts"],
            }
        ],
    }

    await _handle_push(payload)

    assert mock_enqueue.called
    args, kwargs = mock_enqueue.call_args
    job_type = args[1]
    job_payload = args[2]
    assert job_type == "update_atlas_graph"
    assert job_payload["repo_id"] == str(repo_id)
    assert job_payload["commit_sha"] == "deadbeef1234"
    assert job_payload["changed"]["added"] == ["src/new.ts"]
    assert job_payload["changed"]["modified"] == ["src/index.ts"]
    assert job_payload["changed"]["removed"] == ["src/old.ts"]


@pytest.mark.asyncio
async def test_handle_push_ignored_for_non_default_branch(monkeypatch):
    from routers.webhooks import _handle_push

    mock_enqueue = AsyncMock()
    monkeypatch.setattr("routers.webhooks.enqueue_job", mock_enqueue)

    payload = {
        "ref": "refs/heads/feature-branch",
        "repository": {
            "id": 999,
            "default_branch": "main",
            "full_name": "owner/repo",
        },
        "after": "deadbeef1234",
    }

    await _handle_push(payload)
    assert not mock_enqueue.called
