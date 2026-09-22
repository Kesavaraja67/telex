import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from db.models import CodeUsage, DetectedChange, Installation, Package, PackageVersion, Repo
from main import app


@pytest.mark.asyncio
async def test_active_incidents_unauthenticated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/repos/{uuid.uuid4()}/incidents/active")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_active_incidents_not_found():
    from fastapi import HTTPException

    with patch(
        "routers.incidents.get_authorized_repo",
        AsyncMock(side_effect=HTTPException(status_code=404, detail="Repo not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/repos/{uuid.uuid4()}/incidents/active",
                headers={"X-Demo-Key": "telex_demo_secret_2026"},
            )
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_active_incidents_success():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id)
    inst = Installation(id=inst_id, github_installation_id=123)
    dc = DetectedChange(
        id=uuid.uuid4(),
        symbol_old="oldFn",
        symbol_new="newFn",
        change_type="signature_change",
    )

    with patch("routers.incidents.get_authorized_repo", AsyncMock(return_value=(repo, inst))):
        with patch("routers.incidents.AsyncSessionLocal") as mock_session_ctx:
            mock_session = MagicMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None

            mock_res = MagicMock()
            mock_res.all.return_value = [(dc, "express")]
            mock_session.execute = AsyncMock(return_value=mock_res)
            mock_session_ctx.return_value = mock_session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/repos/{repo_id}/incidents/active",
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert len(data) == 1
                assert data[0]["package"] == "express"
                assert data[0]["symbol_old"] == "oldFn"


@pytest.mark.asyncio
async def test_incident_graph_success():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    dc_id = uuid.uuid4()
    pv_id = uuid.uuid4()
    pkg_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id)
    inst = Installation(id=inst_id, github_installation_id=123)
    dc = DetectedChange(
        id=dc_id,
        package_version_id=pv_id,
        symbol_old="oldFn",
        symbol_new="newFn",
    )
    pv = PackageVersion(id=pv_id, package_id=pkg_id, version="1.0.0")
    pkg = Package(id=pkg_id, name="my-awesome-pkg", ecosystem="npm")
    cu = CodeUsage(
        id=uuid.uuid4(),
        repo_id=repo_id,
        detected_change_id=dc_id,
        file_path="src/index.ts",
        line_start=1,
        line_end=5,
        status="pending",
    )

    with patch("routers.incidents.get_authorized_repo", AsyncMock(return_value=(repo, inst))):
        with patch("routers.incidents.AsyncSessionLocal") as mock_session_ctx:
            mock_session = MagicMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None

            async def fake_get(model, ident):
                if model is PackageVersion and ident == pv_id:
                    return pv
                if model is Package and ident == pkg_id:
                    return pkg
                return None

            mock_session.get = AsyncMock(side_effect=fake_get)

            call_count = 0

            def fake_execute(stmt):
                nonlocal call_count
                call_count += 1
                mock_r = MagicMock()
                if call_count == 1:
                    mock_r.scalar_one_or_none.return_value = dc
                elif call_count == 2:
                    mock_r.scalars.return_value = [cu]
                else:
                    mock_r.scalars.return_value = []
                return mock_r

            mock_session.execute = AsyncMock(side_effect=fake_execute)
            mock_session_ctx.return_value = mock_session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/repos/{repo_id}/incidents/{dc_id}/graph",
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["detected_change_id"] == str(dc_id)
                assert data["package"] == "my-awesome-pkg"
                assert len(data["nodes"]) == 1
                assert data["nodes"][0]["file_path"] == "src/index.ts"


@pytest.mark.asyncio
async def test_incident_events_success():
    from datetime import datetime, timezone
    from db.models import IncidentEvent

    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    dc_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id)
    inst = Installation(id=inst_id, github_installation_id=123)

    ev = IncidentEvent(
        id=uuid.uuid4(),
        event_type="change_detected",
        detected_change_id=dc_id,
        repo_id=repo_id,
        created_at=datetime.now(timezone.utc),
        payload={"symbol": "oldFn"},
    )

    with patch("routers.incidents.get_authorized_repo", AsyncMock(return_value=(repo, inst))):
        with patch("routers.incidents.AsyncSessionLocal") as mock_session_ctx:
            mock_session = MagicMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None

            mock_res = MagicMock()
            mock_res.scalars.return_value = [ev]
            mock_session.execute = AsyncMock(return_value=mock_res)
            mock_session_ctx.return_value = mock_session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/repos/{repo_id}/incidents/{dc_id}/events",
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert len(data) == 1
                assert data[0]["event_type"] == "change_detected"


@pytest.mark.asyncio
async def test_stream_incidents_success():
    import asyncio
    from routers.incidents import stream_incidents

    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id)
    inst = Installation(id=inst_id, github_installation_id=123)

    mock_request = MagicMock()
    disconnect_calls = 0

    async def fake_disconnected():
        nonlocal disconnect_calls
        disconnect_calls += 1
        return disconnect_calls > 1

    mock_request.is_disconnected = AsyncMock(side_effect=fake_disconnected)

    with patch("routers.incidents.get_authorized_repo", AsyncMock(return_value=(repo, inst))):
        with patch("routers.incidents.event_bus.subscribe") as mock_sub:
            mock_queue = asyncio.Queue()
            mock_queue.put_nowait({"event_type": "change_detected", "repo_id": str(repo_id)})
            mock_sub.return_value = mock_queue

            resp = await stream_incidents(str(repo_id), mock_request, {"user_id": "demo-operator"})
            assert resp.status_code == 200
            chunks = []
            async for chunk in resp.body_iterator:
                chunks.append(chunk)
            assert len(chunks) > 0
            assert "change_detected" in chunks[0]


@pytest.mark.asyncio
async def test_incident_graph_invalid_id_and_not_found():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id)
    inst = Installation(id=inst_id, github_installation_id=123)

    with patch("routers.incidents.get_authorized_repo", AsyncMock(return_value=(repo, inst))):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/repos/{repo_id}/incidents/not-a-uuid/graph",
                headers={"X-Demo-Key": "telex_demo_secret_2026"},
            )
            assert resp.status_code == 400

            with patch("routers.incidents.AsyncSessionLocal") as mock_session_ctx:
                mock_session = MagicMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_res = MagicMock()
                mock_res.scalar_one_or_none.return_value = None
                mock_session.execute = AsyncMock(return_value=mock_res)
                mock_session_ctx.return_value = mock_session

                resp2 = await client.get(
                    f"/api/repos/{repo_id}/incidents/{uuid.uuid4()}/graph",
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert resp2.status_code == 404
