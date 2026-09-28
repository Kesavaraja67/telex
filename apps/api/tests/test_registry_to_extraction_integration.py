"""
Deterministic integration fixture: Registry Polling → PackageVersion Persisted → Extraction Context.

Proves:
1. Registry polling dispatches by ecosystem (npm, pypi).
2. PackageVersion is persisted with changelog_raw metadata.
3. Prior known version is captured and explicit old_version/new_version pair is passed.
4. extract_changes job is enqueued with complete, uncorrupted context.
5. FAILS if changelog or version context is silently dropped.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.models import Base, Package, PackageVersion
from jobs.handlers.poll_registry import run as run_poll_registry


@pytest.fixture
async def async_test_session():
    """Create an isolated in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        # Create tables needed for registry & package versions
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        with patch("db.session.AsyncSessionLocal", session_factory):
            yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_registry_polling_propagates_changelog_and_version_context_npm(
    async_test_session,
):
    """Prove that npm polling persists changelog and propagates explicit old/new version context."""
    db_session = async_test_session
    # 1. Setup tracked package and an initial known version in DB
    pkg_id = uuid.uuid4()

    pkg = Package(id=pkg_id, ecosystem="npm", name="test-npm-pkg")
    db_session.add(pkg)

    pv_old = PackageVersion(
        package_id=pkg_id,
        version="1.0.0",
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        changelog_raw="Initial release v1.0.0",
    )
    db_session.add(pv_old)
    await db_session.commit()

    # 2. Mock registry response for new version 2.0.0 with explicit changelog
    expected_changelog = "## 2.0.0 Breaking Changes\n- Removed legacy createCompletion API."
    mock_latest = {
        "version": "2.0.0",
        "published_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
        "changelog_url": "https://github.com/test/pkg/releases/tag/v2.0.0",
        "changelog_raw": expected_changelog,
    }

    enqueued_jobs = []

    async def mock_enqueue(session, job_type, payload):
        enqueued_jobs.append({"job_type": job_type, "payload": payload})

    with (
        patch(
            "services.registry_watcher.fetch_latest_version",
            AsyncMock(return_value=mock_latest),
        ),
        patch("jobs.queue.enqueue_job", side_effect=mock_enqueue),
    ):
        await run_poll_registry(
            {
                "package_id": str(pkg_id),
                "package_name": "test-npm-pkg",
                "ecosystem": "npm",
            }
        )

    # 3. Assert PackageVersion persisted with changelog_raw
    result = await db_session.execute(
        select(PackageVersion).where(
            PackageVersion.package_id == pkg_id,
            PackageVersion.version == "2.0.0",
        )
    )
    pv_new = result.scalar_one_or_none()
    assert pv_new is not None, "New PackageVersion 2.0.0 must be persisted in database"
    assert (
        pv_new.changelog_raw == expected_changelog
    ), f"changelog_raw must be persisted, got {pv_new.changelog_raw}"

    # 4. Assert extract_changes job enqueued with correct context
    assert len(enqueued_jobs) == 1, "Expected exactly 1 extract_changes job to be enqueued"
    extract_job = enqueued_jobs[0]
    assert extract_job["job_type"] == "extract_changes"

    payload = extract_job["payload"]
    assert payload["package_version_id"] == str(pv_new.id)
    assert payload["package_name"] == "test-npm-pkg"
    assert payload["ecosystem"] == "npm"
    assert (
        payload["old_version"] == "1.0.0"
    ), f"old_version must be '1.0.0' from prior DB record, got {payload['old_version']}"
    assert payload["new_version"] == "2.0.0"
    assert (
        payload["changelog"] == expected_changelog
    ), f"changelog must not be empty or dropped, got {payload['changelog']}"


@pytest.mark.asyncio
async def test_registry_polling_propagates_changelog_and_version_context_pypi(
    async_test_session,
):
    """Prove that PyPI polling correctly dispatches, saves changelog, and passes explicit version context."""
    db_session = async_test_session
    pkg_id = uuid.uuid4()
    pkg = Package(id=pkg_id, ecosystem="pypi", name="test-pypi-pkg")
    db_session.add(pkg)

    pv_old = PackageVersion(
        package_id=pkg_id,
        version="0.9.0",
        published_at=datetime(2026, 2, 15, tzinfo=timezone.utc),
        changelog_raw="Version 0.9.0 notes",
    )
    db_session.add(pv_old)
    await db_session.commit()

    expected_pypi_changelog = (
        "## 1.0.0 PyPI Release\n- Deprecated old method in favor of execute()."
    )
    mock_latest_pypi = {
        "version": "1.0.0",
        "published_at": datetime(2026, 9, 20, tzinfo=timezone.utc),
        "changelog_url": "https://pypi.org/project/test-pypi-pkg/#changelog",
        "changelog_raw": expected_pypi_changelog,
    }

    enqueued_jobs = []

    async def mock_enqueue(session, job_type, payload):
        enqueued_jobs.append({"job_type": job_type, "payload": payload})

    with (
        patch(
            "services.registry_watcher.fetch_latest_version",
            AsyncMock(return_value=mock_latest_pypi),
        ),
        patch("jobs.queue.enqueue_job", side_effect=mock_enqueue),
    ):
        await run_poll_registry(
            {
                "package_id": str(pkg_id),
                "package_name": "test-pypi-pkg",
                "ecosystem": "pypi",
            }
        )

    result = await db_session.execute(
        select(PackageVersion).where(
            PackageVersion.package_id == pkg_id,
            PackageVersion.version == "1.0.0",
        )
    )
    pv_new = result.scalar_one_or_none()
    assert pv_new is not None
    assert pv_new.changelog_raw == expected_pypi_changelog

    assert len(enqueued_jobs) == 1
    payload = enqueued_jobs[0]["payload"]
    assert payload["ecosystem"] == "pypi"
    assert payload["old_version"] == "0.9.0"
    assert payload["new_version"] == "1.0.0"
    assert payload["changelog"] == expected_pypi_changelog


@pytest.mark.asyncio
async def test_registry_polling_first_version_seen_behavior(async_test_session):
    """When a package is polled for the very first time, old_version is explicitly handled."""
    db_session = async_test_session
    pkg_id = uuid.uuid4()
    pkg = Package(id=pkg_id, ecosystem="npm", name="fresh-package")
    db_session.add(pkg)
    await db_session.commit()

    mock_latest = {
        "version": "1.0.0",
        "published_at": datetime(2026, 9, 24, tzinfo=timezone.utc),
        "changelog_url": "https://github.com/fresh/package",
        "changelog_raw": "Initial release",
    }

    enqueued_jobs = []

    async def mock_enqueue(session, job_type, payload):
        enqueued_jobs.append({"job_type": job_type, "payload": payload})

    with (
        patch(
            "services.registry_watcher.fetch_latest_version",
            AsyncMock(return_value=mock_latest),
        ),
        patch("jobs.queue.enqueue_job", side_effect=mock_enqueue),
    ):
        await run_poll_registry(
            {
                "package_id": str(pkg_id),
                "package_name": "fresh-package",
                "ecosystem": "npm",
            }
        )

    assert len(enqueued_jobs) == 1
    payload = enqueued_jobs[0]["payload"]
    assert payload["new_version"] == "1.0.0"
    assert payload["old_version"] == "none"
    assert payload["changelog"] == "Initial release"
