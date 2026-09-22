import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from db.models import Installation, Repo, RepoAtlasGraph
from jobs.handlers import build_atlas_graph
from services.import_graph import AtlasGraph


@pytest.mark.asyncio
async def test_build_atlas_graph_success():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id)
    inst = Installation(id=inst_id, github_installation_id=123)
    graph_row = RepoAtlasGraph(
        id=uuid.uuid4(),
        repo_id=repo_id,
        commit_sha="sha123",
        status="computing",
    )

    fake_graph = AtlasGraph(nodes=[], edges=[], folders=[], truncated=False)

    with patch("jobs.handlers.build_atlas_graph.AsyncSessionLocal") as mock_session_ctx:
        mock_session = MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        def fake_get(model, pk):
            if model == Repo:
                return repo
            if model == Installation:
                return inst
            return None

        mock_session.get = AsyncMock(side_effect=fake_get)
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = graph_row
        mock_session.execute = AsyncMock(return_value=mock_res)
        mock_session.commit = AsyncMock()
        mock_session_ctx.return_value = mock_session

        with patch(
            "jobs.handlers.build_atlas_graph.fetch_repo_snapshot",
            AsyncMock(return_value=Path("/tmp/fake/sub")),
        ):
            with patch(
                "jobs.handlers.build_atlas_graph.build_import_graph", return_value=fake_graph
            ):
                with patch("shutil.rmtree"):
                    await build_atlas_graph.run(
                        {
                            "repo_id": str(repo_id),
                            "commit_sha": "sha123",
                        }
                    )

                    assert graph_row.status == "ready"
                    assert graph_row.node_count == 0


@pytest.mark.asyncio
async def test_build_atlas_graph_repo_not_found():
    repo_id = uuid.uuid4()
    graph_row = RepoAtlasGraph(
        id=uuid.uuid4(),
        repo_id=repo_id,
        commit_sha="sha123",
        status="computing",
    )

    with patch("jobs.handlers.build_atlas_graph.AsyncSessionLocal") as mock_session_ctx:
        mock_session = MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session.get = AsyncMock(return_value=None)
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = graph_row
        mock_session.execute = AsyncMock(return_value=mock_res)
        mock_session.commit = AsyncMock()
        mock_session_ctx.return_value = mock_session

        await build_atlas_graph.run(
            {
                "repo_id": str(repo_id),
                "commit_sha": "sha123",
            }
        )

        assert graph_row.status == "failed"
        assert graph_row.error_message == "repo not found"


@pytest.mark.asyncio
async def test_build_atlas_graph_installation_not_found():
    repo_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=uuid.uuid4())
    graph_row = RepoAtlasGraph(
        id=uuid.uuid4(),
        repo_id=repo_id,
        commit_sha="sha123",
        status="computing",
    )

    with patch("jobs.handlers.build_atlas_graph.AsyncSessionLocal") as mock_session_ctx:
        mock_session = MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        def fake_get(model, pk):
            if model == Repo:
                return repo
            return None

        mock_session.get = AsyncMock(side_effect=fake_get)
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = graph_row
        mock_session.execute = AsyncMock(return_value=mock_res)
        mock_session.commit = AsyncMock()
        mock_session_ctx.return_value = mock_session

        await build_atlas_graph.run(
            {
                "repo_id": str(repo_id),
                "commit_sha": "sha123",
            }
        )

        assert graph_row.status == "failed"
        assert graph_row.error_message == "installation not found"


@pytest.mark.asyncio
async def test_build_atlas_graph_exception():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id)
    inst = Installation(id=inst_id, github_installation_id=123)
    graph_row = RepoAtlasGraph(
        id=uuid.uuid4(),
        repo_id=repo_id,
        commit_sha="sha123",
        status="computing",
    )

    with patch("jobs.handlers.build_atlas_graph.AsyncSessionLocal") as mock_session_ctx:
        mock_session = MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        def fake_get(model, pk):
            if model == Repo:
                return repo
            if model == Installation:
                return inst
            return None

        mock_session.get = AsyncMock(side_effect=fake_get)
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = graph_row
        mock_session.execute = AsyncMock(return_value=mock_res)
        mock_session.commit = AsyncMock()
        mock_session_ctx.return_value = mock_session

        with patch(
            "jobs.handlers.build_atlas_graph.fetch_repo_snapshot",
            AsyncMock(side_effect=RuntimeError("download error")),
        ):
            with pytest.raises(RuntimeError):
                await build_atlas_graph.run(
                    {
                        "repo_id": str(repo_id),
                        "commit_sha": "sha123",
                    }
                )

            assert graph_row.status == "failed"
            assert graph_row.error_message is not None
            assert "download error" in graph_row.error_message
