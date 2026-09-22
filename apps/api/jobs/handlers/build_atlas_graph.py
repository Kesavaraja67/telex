"""
build_atlas_graph — computes and caches the full import graph for one
repo at one commit SHA. Triggered on cache-miss from routers/atlas.py.
"""

import logging
import shutil
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from db.models import Installation, Repo, RepoAtlasGraph
from services.import_graph import build_import_graph
from services.repo_ingest import fetch_repo_snapshot

logger = logging.getLogger(__name__)


async def run(session, job) -> None:
    payload = job.payload or {}
    repo_id_str = payload["repo_id"]
    commit_sha = payload["commit_sha"]
    repo_uuid = uuid.UUID(repo_id_str) if isinstance(repo_id_str, str) else repo_id_str

    result = await session.execute(
        select(RepoAtlasGraph).where(
            RepoAtlasGraph.repo_id == repo_uuid,
            RepoAtlasGraph.commit_sha == commit_sha,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = RepoAtlasGraph(
            id=uuid.uuid4(),
            repo_id=repo_uuid,
            commit_sha=commit_sha,
            status="computing",
        )
        session.add(row)
        await session.commit()
    else:
        row.status = "computing"
        row.error_message = None
        await session.commit()

    repo = await session.get(Repo, repo_uuid)
    if repo is None:
        row.status = "failed"
        row.error_message = "repo not found"
        await session.commit()
        return

    installation = await session.get(Installation, repo.installation_id)
    if installation is None:
        row.status = "failed"
        row.error_message = "installation not found"
        await session.commit()
        return

    tmp_root = None
    try:
        tmp_root = await fetch_repo_snapshot(
            repo.full_name, installation.github_installation_id, commit_sha
        )
        graph = build_import_graph(tmp_root)

        row.graph_json = {
            "nodes": [n.__dict__ for n in graph.nodes],
            "edges": [e.__dict__ for e in graph.edges],
            "folders": [f.__dict__ for f in graph.folders],
            "truncated": graph.truncated,
        }
        row.node_count = len(graph.nodes)
        row.edge_count = len(graph.edges)
        row.truncated = graph.truncated
        row.status = "ready"
        row.completed_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info(
            "build_atlas_graph: repo=%s sha=%s nodes=%d edges=%d truncated=%s",
            repo.full_name,
            commit_sha[:8],
            row.node_count,
            row.edge_count,
            row.truncated,
        )
    except Exception as exc:
        logger.exception(
            "build_atlas_graph failed for repo=%s sha=%s", repo_id_str, commit_sha
        )
        row.status = "failed"
        row.error_message = str(exc)[:2000]
        await session.commit()
        raise
    finally:
        if tmp_root is not None:
            shutil.rmtree(tmp_root.parent, ignore_errors=True)
