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
from db.session import AsyncSessionLocal
from services.import_graph import build_import_graph
from services.repo_ingest import fetch_repo_snapshot

logger = logging.getLogger(__name__)


async def run(payload_or_session, maybe_job=None) -> None:
    if maybe_job is not None:
        payload = maybe_job.payload or {}
    elif isinstance(payload_or_session, dict):
        payload = payload_or_session
    elif hasattr(payload_or_session, "payload"):
        payload = payload_or_session.payload or {}
    else:
        payload = {}

    repo_id_str = payload["repo_id"]
    commit_sha = payload["commit_sha"]
    repo_uuid = uuid.UUID(repo_id_str) if isinstance(repo_id_str, str) else repo_id_str

    # 1. Quick initial setup & metadata read with dedicated session
    async with AsyncSessionLocal() as init_session:
        result = await init_session.execute(
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
            init_session.add(row)
        else:
            row.status = "computing"
            row.error_message = None
        await init_session.commit()

        repo = await init_session.get(Repo, repo_uuid)
        if repo is None:
            row.status = "failed"
            row.error_message = "repo not found"
            await init_session.commit()
            return

        installation = await init_session.get(Installation, repo.installation_id)
        if installation is None:
            row.status = "failed"
            row.error_message = "installation not found"
            await init_session.commit()
            return

        repo_full_name = repo.full_name
        github_inst_id = installation.github_installation_id

    # 2. Heavy I/O & AST parsing with no active database transaction open
    tmp_root = None
    try:
        tmp_root = await fetch_repo_snapshot(repo_full_name, github_inst_id, commit_sha)
        graph = build_import_graph(tmp_root)

        graph_payload = {
            "nodes": [n.__dict__ for n in graph.nodes],
            "edges": [e.__dict__ for e in graph.edges],
            "folders": [f.__dict__ for f in graph.folders],
            "truncated": graph.truncated,
        }
        node_count = len(graph.nodes)
        edge_count = len(graph.edges)
        truncated = graph.truncated

        # 3. Persist ready state in a fresh transaction
        async with AsyncSessionLocal() as save_session:
            result = await save_session.execute(
                select(RepoAtlasGraph).where(
                    RepoAtlasGraph.repo_id == repo_uuid,
                    RepoAtlasGraph.commit_sha == commit_sha,
                )
            )
            row = result.scalar_one_or_none()
            if row:
                row.graph_json = graph_payload
                row.node_count = node_count
                row.edge_count = edge_count
                row.truncated = truncated
                row.status = "ready"
                row.completed_at = datetime.now(timezone.utc)
                await save_session.commit()
                logger.info(
                    "build_atlas_graph: repo=%s sha=%s nodes=%d edges=%d truncated=%s",
                    repo_full_name,
                    commit_sha[:8],
                    row.node_count,
                    row.edge_count,
                    row.truncated,
                )
    except Exception as exc:
        logger.exception("build_atlas_graph failed for repo=%s sha=%s", repo_id_str, commit_sha)
        async with AsyncSessionLocal() as err_session:
            result = await err_session.execute(
                select(RepoAtlasGraph).where(
                    RepoAtlasGraph.repo_id == repo_uuid,
                    RepoAtlasGraph.commit_sha == commit_sha,
                )
            )
            row = result.scalar_one_or_none()
            if row:
                row.status = "failed"
                row.error_message = str(exc)[:2000]
                await err_session.commit()
        raise
    finally:
        if tmp_root is not None:
            to_delete = tmp_root if tmp_root.name.startswith("telex_atlas_") else tmp_root.parent
            shutil.rmtree(to_delete, ignore_errors=True)
