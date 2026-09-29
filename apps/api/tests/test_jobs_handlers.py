"""
Unit tests for jobs/handlers/ — testing poll_registry, extract_changes, and scan_repo.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from jobs.handlers.poll_registry import run as poll_registry_run
from jobs.handlers.extract_changes import run as extract_changes_run
from jobs.handlers.scan_repo import run as scan_repo_run


@pytest.mark.asyncio
async def test_poll_registry_no_version_found():
    with patch("services.registry_watcher.fetch_latest_version", AsyncMock(return_value=None)):
        # Should cleanly return without errors
        await poll_registry_run({"package_id": str(uuid.uuid4()), "package_name": "unknown"})


@pytest.mark.asyncio
async def test_poll_registry_already_known_version():
    latest_meta = {"version": "1.0.0", "published_at": None}
    with patch(
        "services.registry_watcher.fetch_latest_version", AsyncMock(return_value=latest_meta)
    ):
        with patch("db.session.AsyncSessionLocal") as mock_ctx:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_session.execute = AsyncMock(
                return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock()))
            )
            mock_ctx.return_value = mock_session

            await poll_registry_run({"package_id": str(uuid.uuid4()), "package_name": "known-pkg"})
            mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_extract_changes_missing_package_version():
    with patch("db.session.AsyncSessionLocal") as mock_ctx:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session.get = AsyncMock(return_value=None)
        mock_ctx.return_value = mock_session

        # Should cleanly log and return
        await extract_changes_run(
            {
                "package_version_id": str(uuid.uuid4()),
                "package_name": "pkg",
            }
        )


@pytest.mark.asyncio
async def test_extract_changes_empty_changes():
    mock_pv = MagicMock()
    mock_pv.version = "2.0.0"
    mock_pv.changelog_raw = "None"
    with patch("db.session.AsyncSessionLocal") as mock_ctx:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session.get = AsyncMock(return_value=mock_pv)
        mock_session.commit = AsyncMock()
        mock_ctx.return_value = mock_session

        with patch(
            "services.change_extractor.extract_breaking_changes", AsyncMock(return_value=[])
        ):
            await extract_changes_run(
                {
                    "package_version_id": str(uuid.uuid4()),
                    "package_name": "pkg",
                }
            )
            mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_scan_repo_missing_repo():
    with patch("db.session.AsyncSessionLocal") as mock_ctx:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session.get = AsyncMock(return_value=None)
        mock_ctx.return_value = mock_session

        await scan_repo_run(
            {
                "repo_id": str(uuid.uuid4()),
                "package_version_id": str(uuid.uuid4()),
            }
        )


@pytest.mark.asyncio
async def test_extract_changes_with_detected_changes(monkeypatch):
    from db.models import PackageVersion, RepoPackage

    pv_id = uuid.uuid4()
    pkg_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    mock_pv = PackageVersion(
        id=pv_id,
        package_id=pkg_id,
        version="2.0.0",
        changelog_raw="Breaking: renamed oldMethod to newMethod",
    )
    mock_rp = RepoPackage(repo_id=repo_id, package_id=pkg_id)

    mock_changes = [
        {
            "change_type": "renamed",
            "symbol_old": "oldMethod",
            "symbol_new": "newMethod",
            "description": "renamed function",
            "confidence": 0.95,
        }
    ]

    with patch("db.session.AsyncSessionLocal") as mock_ctx:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session.get = AsyncMock(return_value=mock_pv)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=[mock_rp]))
        )
        mock_ctx.return_value = mock_session

        enqueued = []

        async def fake_enqueue(session, job_type, payload):
            enqueued.append((job_type, payload))

        monkeypatch.setattr("jobs.queue.enqueue_job", fake_enqueue)

        with patch(
            "services.change_extractor.extract_breaking_changes",
            AsyncMock(return_value=mock_changes),
        ):
            await extract_changes_run(
                {
                    "package_version_id": str(pv_id),
                    "package_name": "pkg-a",
                    "old_version": "1.0.0",
                    "changelog": "some changelog",
                }
            )
            assert mock_session.add.called
            assert mock_session.commit.called
            assert len(enqueued) == 1
            assert enqueued[0][0] == "scan_repo"
            assert enqueued[0][1]["repo_id"] == str(repo_id)


def test_build_pr_title():
    from jobs.handlers.open_pr import build_pr_title

    assert build_pr_title("chore: update foo", False) == "chore: update foo"
    assert build_pr_title("chore: update foo", True) == "[semantic-risk] chore: update foo"
    assert (
        build_pr_title("[semantic-risk] chore: update foo", True)
        == "[semantic-risk] chore: update foo"
    )


def test_build_classification_table_and_metadata():
    from jobs.handlers.open_pr import build_classification_table, build_pr_metadata

    table = build_classification_table(
        change_type="behavior_change",
        confidence=0.85,
        is_semantic_risk=True,
        allow_install_scripts=True,
        needs_review=True,
    )
    assert "behavior_change" in table
    assert "85%" in table
    assert "allowed (opt-in)" in table
    assert "[Review Required]" in table

    # Blocked scripts and safe change
    table_safe = build_classification_table(
        change_type="renamed",
        confidence=0.95,
        is_semantic_risk=False,
        allow_install_scripts=False,
        needs_review=False,
    )
    assert "[Safe] Mechanical change" in table_safe
    assert "blocked (default)" in table_safe
    assert "[Review Required]" not in table_safe

    # Metadata helper
    title, rendered_table = build_pr_metadata(
        change_type="behavior_change",
        confidence=0.9,
        base_title="chore(deps): auto-patch",
        allow_install_scripts=False,
        needs_review=True,
    )
    assert title.startswith("[semantic-risk]")
    assert "[Review Required]" in rendered_table


@pytest.mark.asyncio
async def test_update_atlas_graph_handler_modes():
    from jobs.handlers import update_atlas_graph

    repo_id = uuid.uuid4()
    p = {
        "repo_id": str(repo_id),
        "base_sha": "base111",
        "head_sha": "head222",
        "changed": {"added": ["src/a.ts"], "modified": [], "removed": []},
    }

    with patch(
        "jobs.handlers.update_atlas_graph.update_incremental_graph",
        AsyncMock(return_value={"status": "ok"}),
    ) as mock_inc:
        # 1. Dict payload
        res1 = await update_atlas_graph.run(p)
        assert res1 == {"status": "ok"}
        assert mock_inc.call_args[1]["head_sha"] == "head222"

        # 2. maybe_job passed
        mock_job = MagicMock(payload=p)
        res2 = await update_atlas_graph.run(None, maybe_job=mock_job)
        assert res2 == {"status": "ok"}

        # 3. Object with .payload attribute
        res3 = await update_atlas_graph.run(mock_job)
        assert res3 == {"status": "ok"}

        # 4. Fallback commit_sha in payload
        p_commit = {"repo_id": str(repo_id), "commit_sha": "commit333"}
        res4 = await update_atlas_graph.run(p_commit)
        assert res4 == {"status": "ok"}
        assert mock_inc.call_args[1]["head_sha"] == "commit333"
