"""
Tests for incremental Atlas graph updates — Section 3C / 3G.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from db.models import AtlasEdge, AtlasNode, AtlasState, Installation, Repo, RepoAtlasGraph
from services.atlas_incremental import (
    compute_content_hash,
    parse_single_file_imports,
    update_atlas_incremental,
)


def test_compute_content_hash():
    h1 = compute_content_hash("hello world")
    h2 = compute_content_hash("hello world")
    h3 = compute_content_hash("different")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64


def test_parse_single_file_imports_typescript():
    ts_code = """
    import { foo } from "./foo";
    import bar from "../bar";
    const baz = require("./baz");
    import { missing } from "./missing";
    import type { Quux } from "external-pkg";
    """
    existing_paths = {"src/foo.ts", "bar.ts", "src/baz.ts"}
    edges, unresolved = parse_single_file_imports("src/index.ts", ts_code, existing_paths)

    targets = [e["target_path"] for e in edges]
    assert "src/foo.ts" in targets
    assert "bar.ts" in targets
    assert "src/baz.ts" in targets
    # ./missing is an internal specifier that does not exist in existing_paths, so it goes to unresolved
    assert "./missing" in unresolved


@pytest.mark.asyncio
async def test_incremental_first_load_fallback_to_full():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id, default_branch="main")
    inst = Installation(id=inst_id, github_installation_id=123)

    with patch("services.atlas_incremental.AsyncSessionLocal") as mock_ctx:
        mock_session = MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        async def fake_get(model, pk):
            if model is Repo:
                return repo
            if model is Installation:
                return inst
            if model is AtlasState:
                return None  # First load: no state
            return None

        mock_session.get = AsyncMock(side_effect=fake_get)

        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_session.execute = AsyncMock(return_value=count_result)
        mock_ctx.return_value = mock_session

        with patch("jobs.handlers.build_atlas_graph.run", AsyncMock()) as mock_full_scan:
            res = await update_atlas_incremental(
                repo_id=repo_id,
                head_sha="head1234",
                changed={"added": ["src/app.ts"], "modified": [], "removed": []},
            )

            assert res["mode"] == "full"
            assert res["status"] == "ready"
            assert mock_full_scan.called
            call_args = mock_full_scan.call_args[0][0]
            assert call_args["repo_id"] == str(repo_id)
            assert call_args["commit_sha"] == "head1234"


@pytest.mark.asyncio
async def test_incremental_exceeds_40_percent_fallback():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id, default_branch="main")
    inst = Installation(id=inst_id, github_installation_id=123)
    state = AtlasState(repo_id=repo_id, head_sha="base1234", status="idle")

    with patch("services.atlas_incremental.AsyncSessionLocal") as mock_ctx:
        mock_session = MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        async def fake_get(model, pk):
            if model is Repo:
                return repo
            if model is Installation:
                return inst
            if model is AtlasState:
                return state
            return None

        mock_session.get = AsyncMock(side_effect=fake_get)

        count_result = MagicMock()
        count_result.scalar.return_value = 10  # 10 total nodes
        mock_session.execute = AsyncMock(return_value=count_result)
        mock_ctx.return_value = mock_session

        with patch("jobs.handlers.build_atlas_graph.run", AsyncMock()) as mock_full_scan:
            # 5 files changed out of 10 = 50% > 40% threshold
            res = await update_atlas_incremental(
                repo_id=repo_id,
                head_sha="head1234",
                changed={"added": [f"file{i}.ts" for i in range(5)], "modified": [], "removed": []},
            )

            assert res["mode"] == "full"
            assert mock_full_scan.called


@pytest.mark.asyncio
async def test_incremental_periodic_7_day_fallback():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id, default_branch="main")
    inst = Installation(id=inst_id, github_installation_id=123)
    eight_days_ago = datetime.now(timezone.utc) - timedelta(days=8)
    state = AtlasState(
        repo_id=repo_id,
        head_sha="base1234",
        status="idle",
        last_full_scan_at=eight_days_ago,
    )

    with patch("services.atlas_incremental.AsyncSessionLocal") as mock_ctx:
        mock_session = MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        async def fake_get(model, pk):
            if model is Repo:
                return repo
            if model is Installation:
                return inst
            if model is AtlasState:
                return state
            return None

        mock_session.get = AsyncMock(side_effect=fake_get)

        count_result = MagicMock()
        count_result.scalar.return_value = 100
        mock_session.execute = AsyncMock(return_value=count_result)
        mock_ctx.return_value = mock_session

        with patch("jobs.handlers.build_atlas_graph.run", AsyncMock()) as mock_full_scan:
            res = await update_atlas_incremental(
                repo_id=repo_id,
                head_sha="head1234",
                changed={"added": ["one.ts"], "modified": [], "removed": []},
            )

            assert res["mode"] == "full"
            assert mock_full_scan.called


@pytest.mark.asyncio
async def test_update_atlas_graph_job_handler():
    from jobs.handlers import update_atlas_graph

    repo_id = uuid.uuid4()
    payload = {
        "repo_id": str(repo_id),
        "commit_sha": "sha999",
        "changed": {"added": ["src/new.ts"], "modified": [], "removed": []},
    }

    with patch(
        "jobs.handlers.update_atlas_graph.update_incremental_graph", AsyncMock()
    ) as mock_inc:
        mock_inc.return_value = {
            "mode": "incremental",
            "head_sha": "sha999",
            "node_count": 5,
            "edge_count": 4,
        }
        res = await update_atlas_graph.run(payload)
        assert res["mode"] == "incremental"
        assert mock_inc.called
        assert mock_inc.call_args[1]["head_sha"] == "sha999"


@pytest.mark.asyncio
async def test_incremental_update_success_execution():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id, default_branch="main")
    inst = Installation(id=inst_id, github_installation_id=123)
    existing_state = AtlasState(
        repo_id=repo_id,
        head_sha="sha000",
        status="idle",
        last_full_scan_at=datetime.now(timezone.utc),
    )
    existing_node = AtlasNode(
        repo_id=repo_id,
        path="src/existing.ts",
        name="existing.ts",
        dir="src",
        depth=1,
        ext=".ts",
        language="typescript",
        is_binary=False,
        size_bytes=20,
        content_hash="oldhash",
        unresolved_specifiers=[],
        updated_sha="sha000",
    )

    with patch("services.atlas_incremental.AsyncSessionLocal") as mock_ctx:
        mock_session = MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        async def fake_get(model, pk):
            if model is Repo:
                return repo
            if model is Installation:
                return inst
            if model is AtlasState:
                return existing_state
            return None

        mock_session.get = AsyncMock(side_effect=fake_get)

        existing_edge = AtlasEdge(
            repo_id=repo_id,
            source_path="src/existing.ts",
            target_path="src/other.ts",
            kind="import",
        )

        async def fake_execute(stmt):
            m = MagicMock()
            m.scalar.return_value = 10
            stmt_str = str(stmt)
            if "atlas_edges" in stmt_str:
                m.scalars.return_value.all.return_value = [existing_edge]
            else:
                m.scalars.return_value.all.return_value = [existing_node]
            m.scalar_one_or_none.return_value = None
            return m

        mock_session.execute = AsyncMock(side_effect=fake_execute)
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()
        mock_ctx.return_value = mock_session

        with patch("services.atlas_incremental.fetch_file_content") as mock_fetch:
            mock_fetch.return_value = "import { x } from './existing';\nexport const y = 1;"

            res = await update_atlas_incremental(
                repo_id=repo_id,
                head_sha="sha111",
                changed={"added": ["src/new.ts"], "modified": [], "removed": ["src/old.ts"]},
            )

            assert res["mode"] == "incremental"
            assert res["head_sha"] == "sha111"
            assert mock_session.commit.called


def test_specifier_matches_added():
    from services.atlas_incremental import _specifier_matches_added

    added = {"src/components/Button.tsx", "src/utils.ts", "lib/index.js"}

    # Relative matching
    assert _specifier_matches_added("./Button", "src/components/App.tsx", added)
    assert _specifier_matches_added("../utils", "src/components/App.tsx", added)
    assert not _specifier_matches_added("./Missing", "src/components/App.tsx", added)

    # Alias / non-relative matching
    assert _specifier_matches_added("@/utils", "src/index.ts", added)
    assert _specifier_matches_added("lib", "src/index.ts", added)
    assert not _specifier_matches_added("external-pkg", "src/index.ts", added)
    assert not _specifier_matches_added("", "src/index.ts", added)


@pytest.mark.asyncio
async def test_incremental_already_at_head_sha_skips():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id, default_branch="main")
    inst = Installation(id=inst_id, github_installation_id=123)
    state = AtlasState(repo_id=repo_id, head_sha="sha_target", status="ready")

    with patch("services.atlas_incremental.AsyncSessionLocal") as mock_ctx:
        mock_session = MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        async def fake_get(model, pk):
            if model is Repo:
                return repo
            if model is Installation:
                return inst
            if model is AtlasState:
                return state
            return None

        mock_session.get = AsyncMock(side_effect=fake_get)
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=10)))
        mock_ctx.return_value = mock_session

        res = await update_atlas_incremental(
            repo_id=repo_id,
            base_sha="sha_old",
            head_sha="sha_target",
            changed={"added": [], "modified": [], "removed": []},
        )
        assert res["mode"] == "incremental"
        assert res["status"] == "ready"
        assert res.get("skipped") is True


@pytest.mark.asyncio
async def test_incremental_stale_base_sha_aborts():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id, default_branch="main")
    inst = Installation(id=inst_id, github_installation_id=123)
    state = AtlasState(repo_id=repo_id, head_sha="sha_tracked", status="ready")

    with patch("services.atlas_incremental.AsyncSessionLocal") as mock_ctx:
        mock_session = MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        async def fake_get(model, pk):
            if model is Repo:
                return repo
            if model is Installation:
                return inst
            if model is AtlasState:
                return state
            return None

        mock_session.get = AsyncMock(side_effect=fake_get)
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=10)))
        mock_ctx.return_value = mock_session

        res = await update_atlas_incremental(
            repo_id=repo_id,
            base_sha="sha_different",
            head_sha="sha_incoming",
            changed={"added": [], "modified": [], "removed": []},
        )
        assert res["mode"] == "aborted"
        assert res["status"] == "stale"
        assert "base_sha mismatch" in res["reason"]


@pytest.mark.asyncio
async def test_incremental_fetch_content_none_falls_back_to_full():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id, default_branch="main")
    inst = Installation(id=inst_id, github_installation_id=123)
    state = AtlasState(
        repo_id=repo_id,
        head_sha="sha_base",
        status="idle",
        last_full_scan_at=datetime.now(timezone.utc),
    )

    with patch("services.atlas_incremental.AsyncSessionLocal") as mock_ctx:
        mock_session = MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        async def fake_get(model, pk):
            if model is Repo:
                return repo
            if model is Installation:
                return inst
            if model is AtlasState:
                return state
            return None

        mock_session.get = AsyncMock(side_effect=fake_get)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalar=MagicMock(return_value=10),
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
            )
        )
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.add = MagicMock()
        mock_ctx.return_value = mock_session

        with patch("services.atlas_incremental.fetch_file_content", return_value=None):
            with patch("jobs.handlers.build_atlas_graph.run", AsyncMock()) as mock_full_scan:
                res = await update_atlas_incremental(
                    repo_id=repo_id,
                    base_sha="sha_base",
                    head_sha="sha_head",
                    changed={"added": ["src/missing.ts"], "modified": [], "removed": []},
                )
                assert res["mode"] == "full"
                assert mock_full_scan.called
                call_args = mock_full_scan.call_args[0][0]
                assert call_args.get("from_incremental") is True
