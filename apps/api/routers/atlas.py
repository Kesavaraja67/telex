"""
Repo Atlas router.

  GET  /api/repos/{repo_id}/atlas/graph
       ?commit_sha=<sha optional>&refresh=<bool optional>
       Returns the cached graph for the resolved commit SHA, or 202 +
       {"status": "computing"} while a build job runs, or 200 +
       {"status": "failed", "error": ...} if the last attempt errored.

  GET  /api/repos/{repo_id}/atlas/file
       ?path=<repo-relative path>&ref=<commit sha>
       On-demand single-file content fetch, text files only. 415 if the
       resolved file is classified binary/media.

  GET  /api/repos/{repo_id}/atlas/last-edited
       ?path=<repo-relative path>&ref=<commit sha>
       On-demand single-file commit metadata fetch for card last-edited timestamps.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from db.models import AtlasEdge, AtlasState, Job, RepoAtlasGraph
from db.session import AsyncSessionLocal
from jobs.queue import enqueue_job
from routers.auth import get_authorized_repo, require_auth
from services.github_service import (
    fetch_file_content,
    get_default_branch_head_sha,
    get_file_last_commit_info,
)
from services.import_graph import BINARY_EXTENSIONS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/repos/{repo_id}/atlas", tags=["atlas"])


@router.get("/graph")
async def get_atlas_graph(
    repo_id: str,
    commit_sha: str | None = Query(default=None),
    refresh: bool = Query(default=False),
    auth_data: dict = Depends(require_auth),
):
    async with AsyncSessionLocal() as session:
        repo, installation = await get_authorized_repo(session, repo_id, auth_data)

        resolved_sha = commit_sha
        if resolved_sha is None or refresh:
            try:
                resolved_sha = await asyncio.to_thread(
                    get_default_branch_head_sha,
                    repo.full_name,
                    installation.github_installation_id,
                )
            except ValueError as val_exc:
                raise HTTPException(status_code=400, detail=str(val_exc))
            except Exception as exc:
                raise HTTPException(
                    status_code=502, detail=f"Could not read HEAD from GitHub: {exc}"
                )

        result = await session.execute(
            select(RepoAtlasGraph).where(
                RepoAtlasGraph.repo_id == repo.id,
                RepoAtlasGraph.commit_sha == resolved_sha,
            )
        )
        row = result.scalar_one_or_none()

        if row is not None and row.status == "ready":
            state_row = None
            try:
                state_res = await session.execute(
                    select(AtlasState).where(AtlasState.repo_id == repo.id)
                )
                state_row = state_res.scalar_one_or_none()
            except Exception as exc:
                logger.error("Failed to query AtlasState for repo %s: %s", repo.id, exc)

            last_scan_iso = None
            mode = "full"
            if refresh:
                mode = "full"
            elif (
                row.graph_json
                and isinstance(row.graph_json, dict)
                and "build_mode" in row.graph_json
            ):
                mode = row.graph_json["build_mode"]
            elif state_row:
                if (
                    getattr(state_row, "last_full_scan_sha", None)
                    and state_row.last_full_scan_sha != resolved_sha
                ):
                    mode = "incremental"
                else:
                    mode = "full"

            if (
                state_row
                and getattr(state_row, "last_full_scan_at", None)
                and isinstance(state_row.last_full_scan_at, datetime)
            ):
                last_scan_iso = state_row.last_full_scan_at.isoformat()

            return {
                "status": "ready",
                "repo_full_name": repo.full_name,
                "commit_sha": resolved_sha,
                "node_count": row.node_count,
                "edge_count": row.edge_count,
                "truncated": row.truncated,
                "graph": row.graph_json,
                "last_full_scan_at": last_scan_iso,
                "mode": mode,
            }

        if row is not None and row.status == "failed":
            if not refresh:
                return {
                    "status": "failed",
                    "repo_full_name": repo.full_name,
                    "commit_sha": resolved_sha,
                    "error": row.error_message or "Graph computation failed",
                }

        # Check for stale computing rows (e.g. server restarted or crashed during build)
        is_stale_computing = False
        if row is not None and row.status == "computing" and row.created_at:
            if (datetime.now(timezone.utc) - row.created_at) > timedelta(seconds=120):
                is_stale_computing = True

        # If missing, explicitly refreshed, or orphaned/stale computing
        if row is None or refresh or is_stale_computing:
            # Deduplicate queued builds before enqueueing
            job_check = await session.execute(
                select(Job).where(
                    Job.job_type == "build_atlas_graph",
                    Job.status.in_(["queued", "running"]),
                )
            )
            has_inflight_job = False
            for j in job_check.scalars():
                p = j.payload or {}
                if str(p.get("repo_id")) == str(repo.id) and p.get("commit_sha") == resolved_sha:
                    has_inflight_job = True
                    break

            try:
                async with session.begin_nested():
                    if row is None:
                        row = RepoAtlasGraph(
                            id=uuid.uuid4(),
                            repo_id=repo.id,
                            commit_sha=resolved_sha,
                            status="computing",
                        )
                        session.add(row)
                    else:
                        row.status = "computing"
                        row.error_message = None

                    if not has_inflight_job:
                        job_payload = {
                            "repo_id": str(repo.id),
                            "commit_sha": resolved_sha,
                            "installation_id": str(installation.id),
                        }
                        await enqueue_job(session, "build_atlas_graph", job_payload)
                await session.commit()
            except IntegrityError:
                # Concurrent request already inserted the row or enqueued build
                pass

        return JSONResponse(
            status_code=202,
            content={
                "status": "computing",
                "repo_full_name": repo.full_name,
                "commit_sha": resolved_sha,
            },
        )


@router.get("/file")
async def get_atlas_file(
    repo_id: str,
    path: str = Query(...),
    ref: str = Query(...),
    auth_data: dict = Depends(require_auth),
):
    ext = PurePosixPath(path).suffix.lower()
    if ext in BINARY_EXTENSIONS:
        raise HTTPException(status_code=415, detail="File is binary/media — no preview available")

    async with AsyncSessionLocal() as session:
        repo, installation = await get_authorized_repo(session, repo_id, auth_data)

    content = await asyncio.to_thread(
        fetch_file_content,
        repo.full_name,
        installation.github_installation_id,
        path,
        ref=ref,
    )
    if content is None:
        raise HTTPException(status_code=404, detail="File not found at this ref")
    if len(content) > 1_000_000:
        content = content[:1_000_000] + "\n\n… (truncated, file exceeds 1MB preview limit)"

    return {"path": path, "ref": ref, "content": content, "language_ext": ext}


@router.get("/last-edited")
async def get_atlas_last_edited(
    repo_id: str,
    path: str = Query(...),
    ref: str = Query(...),
    auth_data: dict = Depends(require_auth),
):
    async with AsyncSessionLocal() as session:
        repo, installation = await get_authorized_repo(session, repo_id, auth_data)

    info = await asyncio.to_thread(
        get_file_last_commit_info,
        repo.full_name,
        installation.github_installation_id,
        path,
        ref,
    )
    return {"path": path, "ref": ref, "last_edited": info}


async def _get_node_neighbors(session, repo_id, path: str) -> dict:
    norm_path = path.replace("\\", "/").lstrip("/")

    # Query outgoing edges (what this file imports)
    out_res = await session.execute(
        select(AtlasEdge.target_path).where(
            AtlasEdge.repo_id == repo_id,
            AtlasEdge.source_path == norm_path,
        )
    )
    imports = list(out_res.scalars().all())

    # Query incoming edges (what imports this file)
    inc_res = await session.execute(
        select(AtlasEdge.source_path).where(
            AtlasEdge.repo_id == repo_id,
            AtlasEdge.target_path == norm_path,
        )
    )
    imported_by = list(inc_res.scalars().all())

    # Check if AtlasState exists for this repo
    has_atlas_state = False
    try:
        state_res = await session.execute(
            select(AtlasState.repo_id).where(AtlasState.repo_id == repo_id)
        )
        has_atlas_state = state_res.scalar_one_or_none() is not None
    except Exception as exc:
        logger.error("Failed to check AtlasState for repo %s: %s", repo_id, exc)

    # Fallback to latest ready RepoAtlasGraph only when no AtlasState exists and both edge lists are empty
    if not has_atlas_state and not imports and not imported_by:
        latest_graph_res = await session.execute(
            select(RepoAtlasGraph)
            .where(
                RepoAtlasGraph.repo_id == repo_id,
                RepoAtlasGraph.status == "ready",
            )
            .order_by(RepoAtlasGraph.created_at.desc())
            .limit(1)
        )
        latest_graph = latest_graph_res.scalar_one_or_none()
        if latest_graph and latest_graph.graph_json:
            for e in latest_graph.graph_json.get("edges", []):
                src = e.get("source")
                tgt = e.get("target")
                if src == norm_path and tgt:
                    imports.append(tgt)
                if tgt == norm_path and src:
                    imported_by.append(src)

    return {
        "path": norm_path,
        "imports": sorted(list(set(imports))),
        "imported_by": sorted(list(set(imported_by))),
    }


@router.get("/neighbors")
async def get_atlas_neighbors(
    repo_id: str,
    path: str = Query(...),
    auth_data: dict = Depends(require_auth),
):
    async with AsyncSessionLocal() as session:
        repo, _ = await get_authorized_repo(session, repo_id, auth_data)
        return await _get_node_neighbors(session, repo.id, path)


@router.get("/node/{path:path}/neighbors")
async def get_atlas_node_neighbors(
    repo_id: str,
    path: str,
    auth_data: dict = Depends(require_auth),
):
    async with AsyncSessionLocal() as session:
        repo, _ = await get_authorized_repo(session, repo_id, auth_data)
        return await _get_node_neighbors(session, repo.id, path)
