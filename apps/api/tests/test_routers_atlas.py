import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from db.models import Installation, Repo, RepoAtlasGraph
from main import app


@pytest.mark.asyncio
async def test_atlas_graph_unauthenticated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/repos/{uuid.uuid4()}/atlas/graph")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_atlas_graph_not_found():
    from fastapi import HTTPException

    with patch(
        "routers.atlas.get_authorized_repo",
        AsyncMock(side_effect=HTTPException(status_code=404, detail="Repo not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/repos/{uuid.uuid4()}/atlas/graph",
                headers={"X-Demo-Key": "telex_demo_secret_2026"},
            )
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_atlas_graph_ready_cached():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id, default_branch="main")
    inst = Installation(id=inst_id, github_installation_id=123, account_login="owner")
    graph_row = RepoAtlasGraph(
        repo_id=repo_id,
        commit_sha="abc1234",
        status="ready",
        node_count=10,
        edge_count=12,
        graph_json={"nodes": [{"id": "src/index.ts"}], "links": []},
    )

    with patch("routers.atlas.get_authorized_repo", AsyncMock(return_value=(repo, inst))):
        with patch("routers.atlas.get_default_branch_head_sha", return_value="abc1234"):
            with patch("routers.atlas.AsyncSessionLocal") as mock_ctx:
                mock_session = MagicMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = graph_row
                mock_session.execute = AsyncMock(return_value=mock_result)
                mock_ctx.return_value = mock_session

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get(
                        f"/api/repos/{repo_id}/atlas/graph",
                        headers={"X-Demo-Key": "telex_demo_secret_2026"},
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["status"] == "ready"
                    assert data["node_count"] == 10


@pytest.mark.asyncio
async def test_atlas_graph_enqueue_on_miss():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id, default_branch="main")
    inst = Installation(id=inst_id, github_installation_id=123, account_login="owner")

    with patch("routers.atlas.get_authorized_repo", AsyncMock(return_value=(repo, inst))):
        with patch("routers.atlas.get_default_branch_head_sha", return_value="abc1234"):
            with patch("routers.atlas.AsyncSessionLocal") as mock_ctx:
                mock_session = MagicMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_nested = MagicMock()
                mock_nested.__aenter__.return_value = mock_nested
                mock_nested.__aexit__.return_value = None
                mock_session.begin_nested.return_value = mock_nested

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None  # Cache miss
                mock_result.scalars.return_value = []
                mock_session.execute = AsyncMock(return_value=mock_result)
                mock_session.commit = AsyncMock()
                mock_session.refresh = AsyncMock()
                mock_ctx.return_value = mock_session

                with patch("routers.atlas.enqueue_job", AsyncMock()) as mock_enqueue:
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        resp = await client.get(
                            f"/api/repos/{repo_id}/atlas/graph",
                            headers={"X-Demo-Key": "telex_demo_secret_2026"},
                        )
                        assert resp.status_code == 202
                        data = resp.json()
                        assert data["status"] == "computing"
                        assert data["commit_sha"] == "abc1234"
                        assert mock_enqueue.called


@pytest.mark.asyncio
async def test_atlas_file_binary_rejection():
    repo_id = uuid.uuid4()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/repos/{repo_id}/atlas/file?path=logo.png&ref=abc1234",
            headers={"X-Demo-Key": "telex_demo_secret_2026"},
        )
        assert resp.status_code == 415


@pytest.mark.asyncio
async def test_atlas_file_success():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id)
    inst = Installation(id=inst_id, github_installation_id=123)

    with patch("routers.atlas.get_authorized_repo", AsyncMock(return_value=(repo, inst))):
        with patch("routers.atlas.fetch_file_content", return_value="const x = 1;"):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/repos/{repo_id}/atlas/file?path=src/index.ts&ref=abc1234",
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["content"] == "const x = 1;"
                assert data["path"] == "src/index.ts"


@pytest.mark.asyncio
async def test_atlas_last_edited():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id)
    inst = Installation(id=inst_id, github_installation_id=123)

    info = {
        "author": "Alice",
        "committed_at": datetime.now(timezone.utc).isoformat(),
        "commit_sha": "abc1234",
        "commit_message": "fix: update",
    }
    with patch("routers.atlas.get_authorized_repo", AsyncMock(return_value=(repo, inst))):
        with patch("routers.atlas.get_file_last_commit_info", return_value=info):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/repos/{repo_id}/atlas/last-edited?path=src/index.ts&ref=abc1234",
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["last_edited"]["author"] == "Alice"


@pytest.mark.asyncio
async def test_atlas_graph_failed_status():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id, default_branch="main")
    inst = Installation(id=inst_id, github_installation_id=123, account_login="owner")
    graph_row = RepoAtlasGraph(
        repo_id=repo_id,
        commit_sha="abc1234",
        status="failed",
        error_message="out of memory",
    )

    with patch("routers.atlas.get_authorized_repo", AsyncMock(return_value=(repo, inst))):
        with patch("routers.atlas.get_default_branch_head_sha", return_value="abc1234"):
            with patch("routers.atlas.AsyncSessionLocal") as mock_ctx:
                mock_session = MagicMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = graph_row
                mock_session.execute = AsyncMock(return_value=mock_result)
                mock_ctx.return_value = mock_session

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get(
                        f"/api/repos/{repo_id}/atlas/graph",
                        headers={"X-Demo-Key": "telex_demo_secret_2026"},
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["status"] == "failed"
                    assert data["error"] == "out of memory"


@pytest.mark.asyncio
async def test_atlas_file_not_found():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id)
    inst = Installation(id=inst_id, github_installation_id=123)

    with patch("routers.atlas.get_authorized_repo", AsyncMock(return_value=(repo, inst))):
        with patch("routers.atlas.fetch_file_content", return_value=None):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/repos/{repo_id}/atlas/file?path=src/missing.ts&ref=abc1234",
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert resp.status_code == 404


@pytest.mark.asyncio
async def test_atlas_graph_concurrent_race_integrity_error():
    from sqlalchemy.exc import IntegrityError

    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id, default_branch="main")
    inst = Installation(id=inst_id, github_installation_id=123, account_login="owner")

    with patch("routers.atlas.get_authorized_repo", AsyncMock(return_value=(repo, inst))):
        with patch("routers.atlas.get_default_branch_head_sha", return_value="abc1234"):
            with patch("routers.atlas.AsyncSessionLocal") as mock_ctx:
                mock_session = MagicMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_nested = MagicMock()
                mock_nested.__aenter__.side_effect = IntegrityError(
                    "duplicate key", {}, Exception("unique violation")
                )
                mock_session.begin_nested.return_value = mock_nested

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None  # Cache miss
                mock_result.scalars.return_value = []
                mock_session.execute = AsyncMock(return_value=mock_result)
                mock_ctx.return_value = mock_session

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get(
                        f"/api/repos/{repo_id}/atlas/graph",
                        headers={"X-Demo-Key": "telex_demo_secret_2026"},
                    )
                    assert resp.status_code == 202
                    data = resp.json()
                    assert data["status"] == "computing"


@pytest.mark.asyncio
async def test_atlas_graph_inflight_job_deduplication():
    from db.models import Job

    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id, default_branch="main")
    inst = Installation(id=inst_id, github_installation_id=123, account_login="owner")
    existing_job = Job(
        id=uuid.uuid4(),
        job_type="build_atlas_graph",
        status="queued",
        payload={"repo_id": str(repo_id), "commit_sha": "abc1234"},
    )

    with patch("routers.atlas.get_authorized_repo", AsyncMock(return_value=(repo, inst))):
        with patch("routers.atlas.get_default_branch_head_sha", return_value="abc1234"):
            with patch("routers.atlas.AsyncSessionLocal") as mock_ctx:
                mock_session = MagicMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_nested = MagicMock()
                mock_nested.__aenter__.return_value = mock_nested
                mock_nested.__aexit__.return_value = None
                mock_session.begin_nested.return_value = mock_nested

                call_count = 0

                def fake_execute(stmt):
                    nonlocal call_count
                    call_count += 1
                    r = MagicMock()
                    if call_count == 1:
                        r.scalar_one_or_none.return_value = None  # Cache miss
                    else:
                        r.scalars.return_value = [existing_job]
                    return r

                mock_session.execute = AsyncMock(side_effect=fake_execute)
                mock_session.commit = AsyncMock()
                mock_ctx.return_value = mock_session

                with patch("routers.atlas.enqueue_job", AsyncMock()) as mock_enqueue:
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        resp = await client.get(
                            f"/api/repos/{repo_id}/atlas/graph",
                            headers={"X-Demo-Key": "telex_demo_secret_2026"},
                        )
                        assert resp.status_code == 202
                        assert not mock_enqueue.called
