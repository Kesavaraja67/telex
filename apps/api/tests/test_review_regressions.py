"""Regression coverage for distribution bindings, rescan serialization, and demo safety."""

import importlib.util
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.models import Base, Job, Package, PackageVersion
from routers.packages import rescan_package
from schemas import RescanIn
from services.code_scanner import find_usages
from services.python_imports import resolve_import_names


@pytest.mark.parametrize(
    "distribution,import_name",
    [("PyYAML", "yaml"), ("Pillow", "PIL"), ("scikit-learn", "sklearn")],
)
@pytest.mark.parametrize("qualified", [False, True])
def test_distribution_aliases(distribution, import_name, monkeypatch, qualified):
    monkeypatch.setattr("services.python_imports.packages_distributions", lambda: {})
    source = f"""import {import_name} as target
from {import_name}.submodule import load as direct
from unrelated import load as foreign
import unrelated as other
target.load(data)
direct(data)
foreign(data)
other.load(data)
"""
    usages = find_usages(
        "app.py",
        source,
        f"{import_name}.load" if qualified else "load",
        package_name=distribution,
        import_names=resolve_import_names(distribution),
    )
    assert [u["snippet"] for u in usages] == ["target.load(data)", "direct(data)"]


def test_metadata_import_names_and_normalization(monkeypatch):
    monkeypatch.setattr(
        "services.python_imports.packages_distributions",
        lambda: {"ActualImport": ["custom.package"], "foreign": ["other"]},
    )
    assert resolve_import_names("CUSTOM-Package") == ("ActualImport", "custom_package")
    source = "import ActualImport.submodule as target\ntarget.load(data)"
    assert (
        len(
            find_usages(
                "app.py",
                source,
                "load",
                package_name="CUSTOM-Package",
                import_names=resolve_import_names("CUSTOM-Package"),
            )
        )
        == 1
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("dialect", ["sqlite", "postgresql"])
async def test_rescan_lock_failure_stops_before_reads(dialect, caplog):
    session = AsyncMock()
    session.get_bind = MagicMock()
    session.get_bind.return_value.dialect.name = dialect
    session.execute.side_effect = RuntimeError("lock unavailable")
    with pytest.raises(HTTPException) as exc:
        await rescan_package(
            uuid.uuid4(),
            RescanIn(package_name="example", old_version="1", new_version="2"),
            auth_data={"user_id": "demo-operator"},
            session=session,
        )
    assert exc.value.status_code == 503
    session.get.assert_not_called()
    session.rollback.assert_awaited_once()
    assert session.execute.await_count == 1
    assert "Could not acquire rescan lock" in caplog.text


@pytest.mark.asyncio
async def test_sqlite_rescan_serializes_and_debounces(tmp_path):
    import asyncio

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'rescan.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        package_id = uuid.uuid4()
        async with sessions() as session:
            session.add(Package(id=package_id, name="example", ecosystem="pypi"))
            await session.commit()

        async def rescan():
            async with sessions() as session:
                return await rescan_package(
                    package_id,
                    RescanIn(package_name="example", old_version="1", new_version="2"),
                    auth_data={"user_id": "demo-operator"},
                    session=session,
                )

        results = await asyncio.gather(rescan(), rescan())
        assert sorted(result["status"] for result in results) == [
            "already_queued",
            "queued",
        ]
        async with sessions() as session:
            assert await session.scalar(select(func.count(PackageVersion.id))) == 1
            assert await session.scalar(select(func.count(Job.id))) == 1
    finally:
        await engine.dispose()


@pytest.fixture
def seed_module():
    path = Path(__file__).resolve().parents[3] / "scripts" / "seed_demo.py"
    spec = importlib.util.spec_from_file_location("seed_demo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
@pytest.mark.parametrize("clean", [False, True])
@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://demo:demo@demo-host/production",
        "postgresql+asyncpg://user@localhost/production?application_name=demo",
        "postgresql+asyncpg://user@localhost/telex_demo_backup",
        "sqlite+aiosqlite:///production.db",
        "sqlite+aiosqlite:///production.db?demo=true",
    ],
)
async def test_seed_rejects_non_demo_before_database_operations(seed_module, url, clean):
    engine = MagicMock(url=url)
    with pytest.raises(RuntimeError, match="Refusing to seed or wipe"):
        await seed_module.seed_demo_data(engine, clean=clean, db_url=url)
    engine.begin.assert_not_called()


@pytest.mark.asyncio
async def test_seed_rejects_mismatched_engine(seed_module):
    engine = MagicMock(url="postgresql+asyncpg://user@localhost/production")
    with pytest.raises(RuntimeError, match="does not match"):
        await seed_module.seed_demo_data(
            engine, clean=True, db_url="postgresql+asyncpg://user@localhost/telex_demo"
        )
    engine.begin.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["postgresql", "sqlite"])
async def test_seed_accepts_explicit_demo_targets(seed_module, backend):
    url = (
        "postgresql+asyncpg://user@localhost/telex_demo"
        if backend == "postgresql"
        else f"sqlite+aiosqlite:///{seed_module.API_DIR / 'telex_demo.db'}"
    )
    engine = MagicMock(url=url)
    engine.begin.side_effect = RuntimeError("reached database operation")
    with pytest.raises(RuntimeError, match="reached database operation"):
        await seed_module.seed_demo_data(engine, clean=True, db_url=url)
    engine.begin.assert_called_once()


@pytest.mark.asyncio
async def test_stats_generated_query_errors_are_not_hidden(monkeypatch):
    from routers import stats

    repo_id = uuid.uuid4()
    monkeypatch.setattr(stats, "require_auth", AsyncMock(return_value={"user_id": "demo-operator"}))
    monkeypatch.setattr(stats, "_accessible_repo_ids", AsyncMock(return_value=[repo_id]))
    session = AsyncMock()
    session.execute.side_effect = [
        *[MagicMock(scalar_one=MagicMock(return_value=value)) for value in (2, 5, 4, 3)],
        RuntimeError("generated count failed"),
    ]
    with pytest.raises(RuntimeError, match="generated count failed"):
        await stats.get_stats(MagicMock(), session=session)
    assert session.execute.await_count == 5
