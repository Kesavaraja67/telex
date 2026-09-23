"""
Unit tests for routers/stats.py — dashboard summary and activity feed endpoints.
Verifies authentication requirement, tenant scoping, and cross-user isolation.
"""

import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from main import app
from db.session import get_session
from db.models import Repo, PullRequest, Patch, DetectedChange, User, Installation
from routers.auth import create_session_token


@pytest.mark.asyncio
async def test_stats_and_activity_unauthenticated_returns_401():
    """Verify anonymous access is strictly blocked with 401 on both endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        stats_resp = await client.get("/api/stats")
        assert stats_resp.status_code == 401
        assert stats_resp.json()["detail"] == "Authentication required"

        activity_resp = await client.get("/api/activity")
        assert activity_resp.status_code == 401
        assert activity_resp.json()["detail"] == "Authentication required"


@pytest.mark.asyncio
async def test_get_stats_empty():
    mock_session = AsyncMock()
    repo_id = uuid.uuid4()
    # 1. _accessible_repo_ids (demo-operator) -> all() returning [(repo_id,)]
    # 2. repos_count
    # 3. prs_total
    # 4. prs_merged
    # 5. patches_count
    # 6. dc_res
    mock_session.execute = AsyncMock()
    mock_session.execute.side_effect = [
        MagicMock(all=MagicMock(return_value=[(repo_id,)])),  # _accessible_repo_ids
        MagicMock(scalar_one=MagicMock(return_value=2)),  # repos_count
        MagicMock(scalar_one=MagicMock(return_value=5)),  # prs_total
        MagicMock(scalar_one=MagicMock(return_value=4)),  # prs_merged
        MagicMock(scalar_one=MagicMock(return_value=3)),  # patches_count
        MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ),  # dc_res
    ]

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/stats",
                headers={"X-Demo-Key": "telex_demo_secret_2026"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["repos_watched"] == 2
            assert data["prs_opened"] == 5
            assert data["patches_generated"] == 3
            assert data["merge_rate"] == 0.8
            assert data["recent_changes"] == []
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_get_activity_empty():
    mock_session = AsyncMock()
    repo_id = uuid.uuid4()
    mock_session.execute = AsyncMock()
    mock_session.execute.side_effect = [
        MagicMock(all=MagicMock(return_value=[(repo_id,)])),  # _accessible_repo_ids
        MagicMock(all=MagicMock(return_value=[])),  # pr_res
        MagicMock(all=MagicMock(return_value=[])),  # patch_res
        MagicMock(all=MagicMock(return_value=[])),  # dc_res
    ]

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/activity",
                headers={"X-Demo-Key": "telex_demo_secret_2026"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "activities" in data
            assert data["activities"] == []
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_get_stats_zero_prs():
    mock_session = AsyncMock()
    repo_id = uuid.uuid4()
    mock_session.execute = AsyncMock()
    mock_session.execute.side_effect = [
        MagicMock(all=MagicMock(return_value=[(repo_id,)])),  # _accessible_repo_ids
        MagicMock(scalar_one=MagicMock(return_value=0)),  # repos_count
        MagicMock(scalar_one=MagicMock(return_value=0)),  # prs_total
        MagicMock(scalar_one=MagicMock(return_value=0)),  # prs_merged
        MagicMock(scalar_one=MagicMock(return_value=0)),  # patches_count
        MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ),  # dc_res
    ]

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/stats",
                headers={"X-Demo-Key": "telex_demo_secret_2026"},
            )
            assert resp.status_code == 200
            assert resp.json()["merge_rate"] == 0.0
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_get_activity_populated():
    mock_session = AsyncMock()
    repo_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    pr = MagicMock(
        id=uuid.uuid4(),
        status="merged",
        github_pr_number=101,
        github_pr_url="https://github.com/org/repo/pull/1",
        created_at=now,
        opened_at=now,
    )
    repo = MagicMock(full_name="org/repo")

    patch_obj = MagicMock(
        id=uuid.uuid4(),
        llm_provider="openai",
        verified=True,
        created_at=now,
    )
    cu = MagicMock(file_path="src/index.ts", status="patched")

    dc = MagicMock(
        id=uuid.uuid4(),
        symbol_old="legacyFunc",
        change_type="removed",
        description="Removed legacy function",
        created_at=now,
    )

    mock_session.execute = AsyncMock()
    mock_session.execute.side_effect = [
        MagicMock(all=MagicMock(return_value=[(repo_id,)])),  # _accessible_repo_ids
        MagicMock(all=MagicMock(return_value=[(pr, repo)])),  # pr_res
        MagicMock(all=MagicMock(return_value=[(patch_obj, cu, repo)])),  # patch_res
        MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ),  # vr_res
        MagicMock(all=MagicMock(return_value=[(dc, cu, repo)])),  # dc_res
    ]

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/activity",
                headers={"X-Demo-Key": "telex_demo_secret_2026"},
            )
            assert resp.status_code == 200
            activities = resp.json()["activities"]
            assert len(activities) == 3
            types = [a["type"] for a in activities]
            assert "pull_request" in types
            assert "patch" in types
            assert "detected_change" in types
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_cross_user_isolation():
    """Verify User A and User B receive disjoint, tenant-isolated activities."""
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    token_a = create_session_token(str(user_a_id))
    token_b = create_session_token(str(user_b_id))

    repo_a_id = uuid.uuid4()
    repo_b_id = uuid.uuid4()

    user_a = User(id=user_a_id, github_login="alice")
    user_b = User(id=user_b_id, github_login="bob")

    now = datetime.now(timezone.utc)
    pr_a = MagicMock(
        id=uuid.uuid4(),
        status="opened",
        github_pr_number=1,
        github_pr_url="https://github.com/alice/repo-a/pull/1",
        created_at=now,
        opened_at=now,
    )
    repo_a = MagicMock(id=repo_a_id, full_name="alice/repo-a")

    pr_b = MagicMock(
        id=uuid.uuid4(),
        status="merged",
        github_pr_number=2,
        github_pr_url="https://github.com/bob/repo-b/pull/2",
        created_at=now,
        opened_at=now,
    )
    repo_b = MagicMock(id=repo_b_id, full_name="bob/repo-b")

    # Call for User A
    mock_session_a = AsyncMock()
    mock_session_a.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=user_a)),  # user lookup
        MagicMock(all=MagicMock(return_value=[(repo_a_id,)])),  # accessible repos
        MagicMock(all=MagicMock(return_value=[(pr_a, repo_a)])),  # pr_res for A
        MagicMock(all=MagicMock(return_value=[])),  # patch_res
        MagicMock(all=MagicMock(return_value=[])),  # dc_res
    ]

    async def override_get_session_a():
        yield mock_session_a

    app.dependency_overrides[get_session] = override_get_session_a
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp_a = await client.get(
                "/api/activity",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert resp_a.status_code == 200
            acts_a = resp_a.json()["activities"]
            assert len(acts_a) == 1
            assert acts_a[0]["repo_name"] == "alice/repo-a"
    finally:
        app.dependency_overrides.pop(get_session, None)

    # Call for User B
    mock_session_b = AsyncMock()
    mock_session_b.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=user_b)),  # user lookup
        MagicMock(all=MagicMock(return_value=[(repo_b_id,)])),  # accessible repos
        MagicMock(all=MagicMock(return_value=[(pr_b, repo_b)])),  # pr_res for B
        MagicMock(all=MagicMock(return_value=[])),  # patch_res
        MagicMock(all=MagicMock(return_value=[])),  # dc_res
    ]

    async def override_get_session_b():
        yield mock_session_b

    app.dependency_overrides[get_session] = override_get_session_b
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp_b = await client.get(
                "/api/activity",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert resp_b.status_code == 200
            acts_b = resp_b.json()["activities"]
            assert len(acts_b) == 1
            assert acts_b[0]["repo_name"] == "bob/repo-b"
    finally:
        app.dependency_overrides.pop(get_session, None)
