"""
build_atlas_graph — computes and caches the full import graph for one
repo at one commit SHA. Triggered on cache-miss from routers/atlas.py.
"""

import asyncio
import logging
import shutil
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select

from db.models import (
    AtlasEdge as DBAtlasEdge,
)
from db.models import (
    AtlasNode as DBAtlasNode,
)
from db.models import (
    AtlasState as DBAtlasState,
)
from db.models import (
    Installation,
    Repo,
    RepoAtlasGraph,
)
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
            "build_mode": "full",
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

            # Guard full-scan replacement against stale builds
            state_row = await save_session.get(DBAtlasState, repo_uuid)
            is_stale = False
            if (
                state_row
                and state_row.head_sha
                and state_row.head_sha != commit_sha
                and state_row.status != "updating"
            ):
                logger.warning(
                    "build_atlas_graph: Stale build for %s @ %s (tracked head is %s). Skipping normalized table update.",
                    repo_full_name,
                    commit_sha[:8],
                    state_row.head_sha[:8],
                )
                is_stale = True

            now_ts = datetime.now(timezone.utc)

            if not is_stale:
                # Dual-write into normalized incremental tables (Phase 3)
                await save_session.execute(
                    delete(DBAtlasEdge).where(DBAtlasEdge.repo_id == repo_uuid)
                )
                await save_session.execute(
                    delete(DBAtlasNode).where(DBAtlasNode.repo_id == repo_uuid)
                )

                for n in graph.nodes:
                    node_row = DBAtlasNode(
                        repo_id=repo_uuid,
                        path=n.id,
                        name=n.name,
                        dir=n.dir,
                        depth=n.depth,
                        ext=n.ext,
                        language=n.language or "plaintext",
                        is_binary=n.is_binary,
                        size_bytes=n.size_bytes,
                        unresolved_specifiers=n.unresolved_specifiers or [],
                        updated_sha=commit_sha,
                    )
                    save_session.add(node_row)

                if hasattr(save_session, "flush"):
                    flush_res = save_session.flush()
                    if asyncio.iscoroutine(flush_res) or hasattr(flush_res, "__await__"):
                        await flush_res

                known_node_ids = {n.id for n in graph.nodes}
                for e in graph.edges:
                    if e.source in known_node_ids and e.target in known_node_ids:
                        edge_row = DBAtlasEdge(
                            repo_id=repo_uuid,
                            source_path=e.source,
                            target_path=e.target,
                            kind=e.kind or "static",
                            updated_sha=commit_sha,
                        )
                        save_session.add(edge_row)

                if not state_row:
                    state_row = DBAtlasState(
                        repo_id=repo_uuid,
                        head_sha=commit_sha,
                        status="idle",
                        last_full_scan_sha=commit_sha,
                        last_full_scan_at=now_ts,
                    )
                    save_session.add(state_row)
                else:
                    state_row.head_sha = commit_sha
                    state_row.status = "idle"
                    state_row.error_message = None
                    state_row.last_full_scan_sha = commit_sha
                    state_row.last_full_scan_at = now_ts

            await save_session.commit()
            logger.info(
                "build_atlas_graph: repo=%s sha=%s nodes=%d edges=%d truncated=%s (normalized tables synced)",
                repo_full_name,
                commit_sha[:8],
                node_count,
                edge_count,
                truncated,
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
