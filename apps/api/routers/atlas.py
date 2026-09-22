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
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select

from db.models import Installation, Job, Repo, RepoAtlasGraph
from db.session import AsyncSessionLocal
from routers.auth import require_auth
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
    try:
        repo_uuid = uuid.UUID(repo_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid repo_id")

    async with AsyncSessionLocal() as session:
        repo = await session.get(Repo, repo_uuid)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repo not found")
        installation = await session.get(Installation, repo.installation_id)
        if installation is None:
            raise HTTPException(status_code=404, detail="Installation not found")

        resolved_sha = commit_sha
        if resolved_sha is None or refresh:
            try:
                resolved_sha = await asyncio.to_thread(
                    get_default_branch_head_sha,
                    repo.full_name,
                    installation.github_installation_id,
                )
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
            return {
                "status": "ready",
                "commit_sha": resolved_sha,
                "node_count": row.node_count,
                "edge_count": row.edge_count,
                "truncated": row.truncated,
                "graph": row.graph_json,
            }

        if row is not None and row.status == "failed":
            if not refresh:
                return {
                    "status": "failed",
                    "commit_sha": resolved_sha,
                    "error": row.error_message or "Graph computation failed",
                }

        # If missing or if re-triggering on refresh
        if row is None or refresh:
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

            from jobs.queue import enqueue_job

            await enqueue_job(
                session,
                "build_atlas_graph",
                {
                    "repo_id": str(repo.id),
                    "commit_sha": resolved_sha,
                    "installation_id": str(installation.id),
                },
            )
            await session.commit()

        return JSONResponse(
            status_code=202,
            content={"status": "computing", "commit_sha": resolved_sha},
        )


@router.get("/file")
async def get_atlas_file(
    repo_id: str,
    path: str = Query(...),
    ref: str = Query(...),
    auth_data: dict = Depends(require_auth),
):
    try:
        repo_uuid = uuid.UUID(repo_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid repo_id")

    ext = PurePosixPath(path).suffix.lower()
    if ext in BINARY_EXTENSIONS:
        raise HTTPException(
            status_code=415, detail="File is binary/media — no preview available"
        )

    async with AsyncSessionLocal() as session:
        repo = await session.get(Repo, repo_uuid)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repo not found")
        installation = await session.get(Installation, repo.installation_id)
        if installation is None:
            raise HTTPException(status_code=404, detail="Installation not found")

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
        content = (
            content[:1_000_000] + "\n\n… (truncated, file exceeds 1MB preview limit)"
        )

    return {"path": path, "ref": ref, "content": content, "language_ext": ext}


@router.get("/last-edited")
async def get_atlas_last_edited(
    repo_id: str,
    path: str = Query(...),
    ref: str = Query(...),
    auth_data: dict = Depends(require_auth),
):
    try:
        repo_uuid = uuid.UUID(repo_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid repo_id")

    async with AsyncSessionLocal() as session:
        repo = await session.get(Repo, repo_uuid)
        if repo is None:
            raise HTTPException(status_code=404, detail="Repo not found")
        installation = await session.get(Installation, repo.installation_id)
        if installation is None:
            raise HTTPException(status_code=404, detail="Installation not found")

    info = await asyncio.to_thread(
        get_file_last_commit_info,
        repo.full_name,
        installation.github_installation_id,
        path,
        ref,
    )
    return {"path": path, "ref": ref, "last_edited": info}
