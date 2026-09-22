"""
Unit tests for routers/repos.py — repository listing, syncing, details, and policy toggles.
"""

from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from main import app
from schemas import RepoOut


@pytest.mark.asyncio
async def test_list_repos_endpoint():
    now = datetime.now(timezone.utc)
    mock_repos = [
        {
            "id": "repo-123",
            "full_name": "owner/repo-1",
            "name": "repo-1",
            "owner": "owner",
            "description": "Monitored repo",
            "default_branch": "main",
            "is_active": True,
            "requires_tests": False,
            "requires_typecheck": False,
            "created_at": now,
            "github_url": "https://github.com/owner/repo-1",
            "languages": ["TypeScript"],
            "patch_count": 0,
            "status": "healthy",
            "category": "personal",
            "commits": [],
            "last_commit": None,
            "dependencies": ["typescript"],
        }
    ]

    with patch("routers.repos.get_core_repositories_async", AsyncMock(return_value=mock_repos)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            unauth_resp = await client.get("/api/repos")
            assert unauth_resp.status_code == 401

            resp = await client.get("/api/repos", headers={"X-Demo-Key": "telex_demo_secret_2026"})
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["full_name"] == "owner/repo-1"


@pytest.mark.asyncio
async def test_get_repo_details_found():
    now = datetime.now(timezone.utc)
    mock_repos = [
        {
            "id": "repo-456",
            "full_name": "owner/detail-repo",
            "name": "detail-repo",
            "owner": "owner",
            "description": "Detailed repo",
            "default_branch": "main",
            "is_active": True,
            "requires_tests": False,
            "requires_typecheck": False,
            "created_at": now,
            "github_url": "https://github.com/owner/detail-repo",
            "languages": ["Python"],
            "patch_count": 2,
            "status": "healthy",
            "commits": [],
            "dependencies": ["fastapi"],
        }
    ]

    with patch("routers.repos.get_core_repositories_async", AsyncMock(return_value=mock_repos)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/repos/repo-456")
            assert resp.status_code == 200
            data = resp.json()
            assert data["full_name"] == "owner/detail-repo"


@pytest.mark.asyncio
async def test_sync_repos_endpoint():
    with patch("routers.repos.sync_github_app_repositories_async", AsyncMock()):
        with patch("routers.repos.get_core_repositories_async", AsyncMock(return_value=[])):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Unauthenticated request should be rejected with 401
                unauth_resp = await client.post("/api/repos/sync")
                assert unauth_resp.status_code == 401

                # Authenticated request with demo key succeeds
                resp = await client.post(
                    "/api/repos/sync", headers={"X-Demo-Key": "telex_demo_secret_2026"}
                )
                assert resp.status_code == 200
                assert resp.json() == []


@pytest.mark.asyncio
async def test_ai_explain_repo():
    mock_explain = {
        "summary": "FastAPI backend",
        "commit_insights": [],
        "architecture_verdict": "Production-ready",
        "risk_score": 10,
        "recommended_actions": [],
    }
    with patch("routers.repos.explain_repo_with_gemini", AsyncMock(return_value=mock_explain)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/repos/repo-1/ai-explain")
            assert resp.status_code == 200
            assert resp.json()["architecture_verdict"] == "Production-ready"


@pytest.mark.asyncio
async def test_ai_explain_not_found():
    with patch(
        "routers.repos.explain_repo_with_gemini", AsyncMock(side_effect=KeyError("not found"))
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/repos/non-existent/ai-explain")
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_toggle_repo():
    from routers.auth import require_auth

    async def override_require_auth():
        return {"user_id": "test-user"}

    app.dependency_overrides[require_auth] = override_require_auth
    try:
        mock_repos = [{"id": "repo-99", "full_name": "org/repo-99", "name": "repo-99"}]
        with patch("routers.repos.get_core_repositories_async", AsyncMock(return_value=mock_repos)):
            with patch("routers.repos.AsyncSessionLocal") as mock_session_ctx:
                mock_session = AsyncMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_session.execute = AsyncMock(
                    return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock()))
                )
                mock_session_ctx.return_value = mock_session

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post("/api/repos/repo-99/toggle", json={"is_active": False})
                    assert resp.status_code == 200
                    assert resp.json() == {"id": "repo-99", "is_active": False}
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.mark.asyncio
async def test_update_repo_settings():
    from routers.auth import require_auth
    from db.models import Repo
    import uuid

    async def override_require_auth():
        return {"user_id": "test-user"}

    app.dependency_overrides[require_auth] = override_require_auth
    try:
        repo_uuid = uuid.uuid4()
        mock_repo = Repo(
            id=repo_uuid,
            full_name="org/test-repo",
            requires_tests=False,
            requires_typecheck=False,
            is_active=True,
        )

        with patch("routers.repos.AsyncSessionLocal") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_session.execute = AsyncMock(
                return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_repo))
            )
            mock_session.commit = AsyncMock()
            mock_session_ctx.return_value = mock_session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.patch(
                    f"/api/repos/{repo_uuid}",
                    json={
                        "requires_tests": True,
                        "requires_typecheck": True,
                        "is_active": False,
                        "allow_install_scripts": True,
                    },
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["requires_tests"] is True
                assert data["requires_typecheck"] is True
                assert data["is_active"] is False
                assert data["allow_install_scripts"] is True
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.mark.asyncio
async def test_list_patches_endpoint():
    mock_repos = [{"id": "repo-1", "full_name": "org/repo-1", "name": "repo-1"}]
    with patch("routers.repos.get_core_repositories_async", AsyncMock(return_value=mock_repos)):
        with patch("routers.repos.AsyncSessionLocal") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_session.execute = AsyncMock(
                return_value=MagicMock(
                    scalar_one_or_none=MagicMock(return_value=MagicMock(id="repo-1")),
                    scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
                )
            )
            mock_session_ctx.return_value = mock_session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/repos/repo-1/patches")
                assert resp.status_code == 200
                data = resp.json()
                assert "patches" in data
                assert data["patches"] == []


@pytest.mark.asyncio
async def test_repo_endpoints_404_cases():
    from routers.auth import require_auth

    async def override_require_auth():
        return {"user_id": "test-user"}

    app.dependency_overrides[require_auth] = override_require_auth
    try:
        with patch("routers.repos.get_core_repositories_async", AsyncMock(return_value=[])):
            with patch("routers.repos.AsyncSessionLocal") as mock_session_ctx:
                mock_session = AsyncMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_session.execute = AsyncMock(
                    return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
                )
                mock_session_ctx.return_value = mock_session

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # 1. get_repo_details 404
                    r1 = await client.get("/api/repos/missing-repo")
                    assert r1.status_code == 404

                    # 2. toggle_repo 404
                    r2 = await client.post(
                        "/api/repos/missing-repo/toggle", json={"is_active": True}
                    )
                    assert r2.status_code == 404

                    # 3. update_repo_settings 404
                    r3 = await client.patch(
                        "/api/repos/missing-repo", json={"requires_tests": True}
                    )
                    assert r3.status_code == 404

                    # 4. list_patches 404
                    r4 = await client.get("/api/repos/missing-repo/patches")
                    assert r4.status_code == 404
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.mark.asyncio
async def test_list_patches_populated():
    import uuid
    from db.models import Patch, CodeUsage, Repo, PullRequest, ValidationRun

    repo_id = uuid.uuid4()
    patch_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_repos = [{"id": str(repo_id), "full_name": "org/repo", "name": "repo"}]
    mock_db_repo = Repo(id=repo_id, full_name="org/repo")

    mock_patch = Patch(
        id=patch_id,
        code_usage_id=uuid.uuid4(),
        llm_provider="openai",
        verified=True,
        diff="--- a/index.ts\n+++ b/index.ts\n@@ -1 +1 @@\n-old()\n+new()",
        created_at=now,
    )
    mock_cu = CodeUsage(
        id=mock_patch.code_usage_id,
        repo_id=repo_id,
        file_path="src/index.ts",
        detected_change_id=uuid.uuid4(),
    )
    mock_pr = PullRequest(
        id=uuid.uuid4(),
        repo_id=repo_id,
        github_pr_url="https://github.com/org/repo/pull/1",
        patch_ids=[patch_id],
    )
    mock_vr = ValidationRun(
        patch_id=patch_id,
        verification_mode="docker_sandbox",
        tests_pass=True,
        typechecks=True,
    )

    with patch("routers.repos.get_core_repositories_async", AsyncMock(return_value=mock_repos)):
        with patch("routers.repos.AsyncSessionLocal") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None

            # Execute calls:
            # 1. repo_res (select Repo)
            # 2. pairs (select Patch, CodeUsage)
            # 3. pr_res (select PullRequest)
            # 4. vr_res (select ValidationRun)
            # 5. dc_res (select DetectedChange)
            call_idx = 0

            def fake_execute(stmt):
                nonlocal call_idx
                call_idx += 1
                mock_res = MagicMock()
                if call_idx == 1:
                    mock_res.scalar_one_or_none.return_value = mock_db_repo
                elif call_idx == 2:
                    mock_res.all.return_value = [(mock_patch, mock_cu)]
                elif call_idx == 3:
                    mock_res.scalars.return_value = MagicMock(all=MagicMock(return_value=[mock_pr]))
                elif call_idx == 4:
                    mock_res.scalars.return_value = MagicMock(all=MagicMock(return_value=[mock_vr]))
                else:
                    mock_res.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
                return mock_res

            mock_session.execute = AsyncMock(side_effect=fake_execute)
            mock_session_ctx.return_value = mock_session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(f"/api/repos/{repo_id}/patches")
                assert resp.status_code == 200
                data = resp.json()
                assert len(data["patches"]) == 1
                p = data["patches"][0]
                assert p["status"] == "verified"
                assert p["verification_mode"] == "docker_sandbox"
                assert p["tests_passed"] is True
                assert p["typecheck_passed"] is True
