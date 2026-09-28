"""
Unit tests for routers/repos.py — repository listing, syncing, details, and policy toggles.
Validates authentication, authorization (get_authorized_repo), and rate limiting.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from db.models import Installation, Repo
from main import app
from routers.repos import _AI_EXPLAIN_COOLDOWN


@pytest.fixture(autouse=True)
def clear_cooldown():
    _AI_EXPLAIN_COOLDOWN.clear()
    yield
    _AI_EXPLAIN_COOLDOWN.clear()


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
async def test_get_repo_details():
    now = datetime.now(timezone.utc)
    repo_uuid = uuid.uuid4()
    mock_db_repo = Repo(
        id=repo_uuid, full_name="owner/detail-repo", default_branch="main", is_active=True
    )
    mock_inst = Installation(id=uuid.uuid4(), github_installation_id=123)

    mock_repos = [
        {
            "id": str(repo_uuid),
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

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unauthenticated -> 401
        r_unauth = await client.get(f"/api/repos/{repo_uuid}")
        assert r_unauth.status_code == 401

        # 2. Unauthorized -> 403
        with patch(
            "routers.repos.get_authorized_repo",
            AsyncMock(
                side_effect=HTTPException(status_code=403, detail="Repository access denied")
            ),
        ):
            r_forbidden = await client.get(
                f"/api/repos/{repo_uuid}", headers={"X-Demo-Key": "telex_demo_secret_2026"}
            )
            assert r_forbidden.status_code == 403

        # 3. Not found -> 404
        with patch(
            "routers.repos.get_authorized_repo",
            AsyncMock(side_effect=HTTPException(status_code=404, detail="Repo not found")),
        ):
            r_notfound = await client.get(
                f"/api/repos/{repo_uuid}", headers={"X-Demo-Key": "telex_demo_secret_2026"}
            )
            assert r_notfound.status_code == 404

        # 4. Authorized -> 200
        with patch(
            "routers.repos.get_authorized_repo", AsyncMock(return_value=(mock_db_repo, mock_inst))
        ):
            with patch(
                "routers.repos.get_core_repositories_async", AsyncMock(return_value=mock_repos)
            ):
                resp = await client.get(
                    f"/api/repos/{repo_uuid}", headers={"X-Demo-Key": "telex_demo_secret_2026"}
                )
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
    repo_uuid = uuid.uuid4()
    mock_db_repo = Repo(id=repo_uuid, full_name="owner/repo-1", default_branch="main")
    mock_inst = Installation(id=uuid.uuid4(), github_installation_id=123)
    mock_explain = {
        "summary": "FastAPI backend",
        "commit_insights": [],
        "architecture_verdict": "Production-ready",
        "risk_score": 10,
        "recommended_actions": [],
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Unauthenticated -> 401
        r_unauth = await client.post(f"/api/repos/{repo_uuid}/ai-explain")
        assert r_unauth.status_code == 401

        # Authorized -> 200
        with patch(
            "routers.repos.get_authorized_repo", AsyncMock(return_value=(mock_db_repo, mock_inst))
        ):
            with patch(
                "routers.repos.explain_repo_with_gemini", AsyncMock(return_value=mock_explain)
            ):
                resp = await client.post(
                    f"/api/repos/{repo_uuid}/ai-explain",
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert resp.status_code == 200
                assert resp.json()["architecture_verdict"] == "Production-ready"

                # Rapid duplicate request -> 429 rate limit cooldown
                r_ratelimit = await client.post(
                    f"/api/repos/{repo_uuid}/ai-explain",
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert r_ratelimit.status_code == 429


@pytest.mark.asyncio
async def test_ai_explain_not_found():
    repo_uuid = uuid.uuid4()
    mock_db_repo = Repo(id=repo_uuid, full_name="owner/repo-1", default_branch="main")
    mock_inst = Installation(id=uuid.uuid4(), github_installation_id=123)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch(
            "routers.repos.get_authorized_repo", AsyncMock(return_value=(mock_db_repo, mock_inst))
        ):
            with patch(
                "routers.repos.explain_repo_with_gemini",
                AsyncMock(side_effect=KeyError("not found")),
            ):
                resp = await client.post(
                    f"/api/repos/{repo_uuid}/ai-explain",
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert resp.status_code == 404


@pytest.mark.asyncio
async def test_toggle_repo():
    repo_uuid = uuid.uuid4()
    mock_db_repo = Repo(id=repo_uuid, full_name="org/repo-99", is_active=True)
    mock_inst = Installation(id=uuid.uuid4(), github_installation_id=123)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Unauthenticated -> 401
        r_unauth = await client.post(f"/api/repos/{repo_uuid}/toggle", json={"is_active": False})
        assert r_unauth.status_code == 401

        # Authorized -> 200
        with patch(
            "routers.repos.get_authorized_repo", AsyncMock(return_value=(mock_db_repo, mock_inst))
        ):
            with patch("routers.repos.AsyncSessionLocal") as mock_session_ctx:
                mock_session = AsyncMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_session.commit = AsyncMock()
                mock_session_ctx.return_value = mock_session

                resp = await client.post(
                    f"/api/repos/{repo_uuid}/toggle",
                    json={"is_active": False},
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert resp.status_code == 200
                assert resp.json() == {"id": str(repo_uuid), "is_active": False}


@pytest.mark.asyncio
async def test_update_repo_settings():
    repo_uuid = uuid.uuid4()
    mock_db_repo = Repo(
        id=repo_uuid,
        full_name="org/test-repo",
        requires_tests=False,
        requires_typecheck=False,
        is_active=True,
    )
    mock_inst = Installation(id=uuid.uuid4(), github_installation_id=123)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Unauthenticated -> 401
        r_unauth = await client.patch(f"/api/repos/{repo_uuid}", json={"requires_tests": True})
        assert r_unauth.status_code == 401

        # Authorized -> 200
        with patch(
            "routers.repos.get_authorized_repo", AsyncMock(return_value=(mock_db_repo, mock_inst))
        ):
            with patch("routers.repos.AsyncSessionLocal") as mock_session_ctx:
                mock_session = AsyncMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_session.commit = AsyncMock()
                mock_session_ctx.return_value = mock_session

                resp = await client.patch(
                    f"/api/repos/{repo_uuid}",
                    json={
                        "requires_tests": True,
                        "requires_typecheck": True,
                        "is_active": False,
                        "allow_install_scripts": True,
                    },
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["requires_tests"] is True
                assert data["requires_typecheck"] is True
                assert data["is_active"] is False
                assert data["allow_install_scripts"] is True


@pytest.mark.asyncio
async def test_list_patches_endpoint():
    repo_uuid = uuid.uuid4()
    mock_db_repo = Repo(id=repo_uuid, full_name="org/repo-1", is_active=True)
    mock_inst = Installation(id=uuid.uuid4(), github_installation_id=123)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Unauthenticated -> 401
        r_unauth = await client.get(f"/api/repos/{repo_uuid}/patches")
        assert r_unauth.status_code == 401

        # Authorized -> 200
        with patch(
            "routers.repos.get_authorized_repo", AsyncMock(return_value=(mock_db_repo, mock_inst))
        ):
            with patch("routers.repos.AsyncSessionLocal") as mock_session_ctx:
                mock_session = AsyncMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_session.execute = AsyncMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                )
                mock_session_ctx.return_value = mock_session

                resp = await client.get(
                    f"/api/repos/{repo_uuid}/patches",
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert "patches" in data
                assert data["patches"] == []


@pytest.mark.asyncio
async def test_repo_endpoints_404_cases():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch(
            "routers.repos.get_authorized_repo",
            AsyncMock(side_effect=HTTPException(status_code=404, detail="Repo not found")),
        ):
            r1 = await client.get(
                "/api/repos/missing-repo", headers={"X-Demo-Key": "telex_demo_secret_2026"}
            )
            assert r1.status_code == 404

            r2 = await client.post(
                "/api/repos/missing-repo/toggle",
                json={"is_active": True},
                headers={"X-Demo-Key": "telex_demo_secret_2026"},
            )
            assert r2.status_code == 404

            r3 = await client.patch(
                "/api/repos/missing-repo",
                json={"requires_tests": True},
                headers={"X-Demo-Key": "telex_demo_secret_2026"},
            )
            assert r3.status_code == 404

            r4 = await client.get(
                "/api/repos/missing-repo/patches", headers={"X-Demo-Key": "telex_demo_secret_2026"}
            )
            assert r4.status_code == 404


@pytest.mark.asyncio
async def test_list_patches_populated():
    repo_id = uuid.uuid4()
    patch_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    from db.models import CodeUsage, Patch, PullRequest, ValidationRun

    mock_db_repo = Repo(id=repo_id, full_name="org/repo")
    mock_inst = Installation(id=uuid.uuid4(), github_installation_id=123)

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

    with patch(
        "routers.repos.get_authorized_repo", AsyncMock(return_value=(mock_db_repo, mock_inst))
    ):
        with patch("routers.repos.AsyncSessionLocal") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None

            call_idx = 0

            def fake_execute(stmt):
                nonlocal call_idx
                call_idx += 1
                mock_res = MagicMock()
                if call_idx == 1:
                    mock_res.all.return_value = [(mock_patch, mock_cu)]
                elif call_idx == 2:
                    mock_res.scalars.return_value = MagicMock(all=MagicMock(return_value=[mock_pr]))
                elif call_idx == 3:
                    mock_res.scalars.return_value = MagicMock(all=MagicMock(return_value=[mock_vr]))
                else:
                    mock_res.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
                return mock_res

            mock_session.execute = AsyncMock(side_effect=fake_execute)
            mock_session_ctx.return_value = mock_session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/repos/{repo_id}/patches",
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert len(data["patches"]) == 1
                p = data["patches"][0]
                assert p["status"] == "verified"
                assert p["verification_mode"] == "docker_sandbox"
                assert p["tests_passed"] is True
                assert p["typecheck_passed"] is True


@pytest.mark.asyncio
async def test_human_review_digest():
    """Verify /api/repos/digest/human-review returns open PR summaries."""
    from db.models import PullRequest, Repo

    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    mock_db_repo = Repo(id=repo_id, full_name="org/review-repo", is_active=True)
    mock_pr = PullRequest(
        id=pr_id,
        repo_id=repo_id,
        github_pr_number=99,
        github_pr_url="https://github.com/org/review-repo/pull/99",
        status="open",
        opened_at=datetime.now(timezone.utc),
    )

    with patch("routers.stats._accessible_repo_ids", AsyncMock(return_value=[repo_id])):
        with patch("routers.repos.AsyncSessionLocal") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None

            mock_res = MagicMock()
            mock_res.all.return_value = [(mock_pr, mock_db_repo)]
            mock_session.execute = AsyncMock(return_value=mock_res)
            mock_session_ctx.return_value = mock_session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/repos/digest/human-review",
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert len(data["open_review_prs"]) == 1
                pr_item = data["open_review_prs"][0]
                assert pr_item["github_pr_number"] == 99
                assert pr_item["repo_name"] == "org/review-repo"
