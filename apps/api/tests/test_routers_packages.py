"""
Unit tests for routers/packages.py — package rescan endpoint with authentication and job debounce.
"""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock

from main import app
from db.session import get_session
from db.models import Job, Package


@pytest.mark.asyncio
async def test_rescan_package_unauthenticated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        pkg_id = str(uuid.uuid4())
        body = {
            "package_name": "unknown-pkg",
            "old_version": "1.0",
            "new_version": "2.0",
        }
        resp = await client.post(f"/api/packages/{pkg_id}/rescan", json=body)
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rescan_package_not_found():
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            pkg_id = str(uuid.uuid4())
            body = {
                "package_name": "unknown-pkg",
                "old_version": "1.0",
                "new_version": "2.0",
            }
            resp = await client.post(
                f"/api/packages/{pkg_id}/rescan",
                json=body,
                headers={"X-Demo-Key": "telex_demo_secret_2026"},
            )
            assert resp.status_code == 404
            assert resp.json()["detail"] == "Package not found"
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_rescan_package_success(monkeypatch):
    pkg_id = uuid.uuid4()
    mock_pkg = Package(id=pkg_id, name="express", ecosystem="npm")

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_pkg)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    call_count = 0

    def fake_execute(stmt):
        nonlocal call_count
        call_count += 1
        mock_res = MagicMock()
        if call_count == 1:
            # PackageVersion check
            mock_res.scalar_one_or_none.return_value = None
        else:
            # Active jobs check
            mock_res.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
        return mock_res

    mock_session.execute = AsyncMock(side_effect=fake_execute)

    enqueued_jobs = []

    async def fake_enqueue(session, job_type, payload):
        enqueued_jobs.append((job_type, payload))
        return "job-123"

    monkeypatch.setattr("routers.packages.enqueue_job", fake_enqueue)

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            body = {
                "package_name": "express",
                "old_version": "4.17.0",
                "new_version": "4.18.0",
                "changelog": "Bugfixes and performance improvements",
            }
            resp = await client.post(
                f"/api/packages/{pkg_id}/rescan",
                json=body,
                headers={"X-Demo-Key": "telex_demo_secret_2026"},
            )
            assert resp.status_code == 202
            data = resp.json()
            assert data["status"] == "queued"
            assert len(enqueued_jobs) == 1
            assert enqueued_jobs[0][0] == "extract_changes"
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_rescan_package_debounce_already_queued(monkeypatch):
    from db.models import PackageVersion

    pkg_id = uuid.uuid4()
    pv_id = uuid.uuid4()
    mock_pkg = Package(id=pkg_id, name="express", ecosystem="npm")
    mock_pv = PackageVersion(id=pv_id, package_id=pkg_id, version="4.18.0")
    existing_job = Job(
        id=uuid.uuid4(),
        job_type="extract_changes",
        status="queued",
        payload={"package_version_id": str(pv_id)},
    )

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_pkg)

    call_count = 0

    def fake_execute(stmt):
        nonlocal call_count
        call_count += 1
        mock_res = MagicMock()
        if call_count == 1:
            mock_res.scalar_one_or_none.return_value = mock_pv
        else:
            mock_res.scalars.return_value = MagicMock(all=MagicMock(return_value=[existing_job]))
        return mock_res

    mock_session.execute = AsyncMock(side_effect=fake_execute)

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            body = {
                "package_name": "express",
                "old_version": "4.17.0",
                "new_version": "4.18.0",
            }
            resp = await client.post(
                f"/api/packages/{pkg_id}/rescan",
                json=body,
                headers={"X-Demo-Key": "telex_demo_secret_2026"},
            )
            assert resp.status_code == 202
            data = resp.json()
            assert data["status"] == "already_queued"
            assert data["package_version_id"] == str(pv_id)
            assert data["job_id"] == str(existing_job.id)
    finally:
        app.dependency_overrides.pop(get_session, None)
