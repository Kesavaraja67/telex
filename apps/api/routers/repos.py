"""
Repos API — list live repositories, commit history, and Gemini 2.5 Flash architecture insights.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select, or_, cast, Text
import uuid

from db.session import AsyncSessionLocal
from db.models import Repo, Patch, CodeUsage, PullRequest
from services.repo_service import get_core_repositories_async, explain_repo_with_gemini
from schemas import RepoOut, RepoDetailOut, AIExplainOut, RepoToggleIn, RepoPatchesOut, PatchOut
from routers.auth import require_auth

# P1-2: Enforce authentication on all operational repo routes
router = APIRouter(prefix="/api/repos", tags=["repos"], dependencies=[Depends(require_auth)])


@router.get("", response_model=list[RepoOut])
async def list_repos():
    """Return all active monitored repositories with live git commit metadata."""
    repos = await get_core_repositories_async()
    return repos


@router.get("/{repo_id}", response_model=RepoDetailOut)
async def get_repo_details(repo_id: str):
    """Return full repository detail with full recent commit history."""
    repos = await get_core_repositories_async()
    repo = next((r for r in repos if r["id"] == repo_id or r["full_name"] == repo_id or r["name"] == repo_id), None)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    return repo


@router.post("/{repo_id}/ai-explain", response_model=AIExplainOut)
async def ai_explain_repo(repo_id: str):
    """Invoke Gemini 2.5 Flash to generate live architectural and commit analysis."""
    try:
        explanation = await explain_repo_with_gemini(repo_id)
        return explanation
    except KeyError:
        raise HTTPException(status_code=404, detail="Repo not found")


@router.post("/{repo_id}/toggle", response_model=dict)
async def toggle_repo(repo_id: str, body: RepoToggleIn):
    """Toggle monitoring state for a repository."""
    repos = await get_core_repositories_async()
    repo = next((r for r in repos if r["id"] == repo_id or r["full_name"] == repo_id or r["name"] == repo_id), None)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    repo["is_active"] = body.is_active

    # Persist in DB if repository record exists
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Repo).where(Repo.full_name == repo["full_name"]).limit(1)
        )
        db_repo = result.scalar_one_or_none()
        if db_repo:
            db_repo.is_active = body.is_active
            await session.commit()

    return {"id": repo_id, "is_active": body.is_active}


@router.get("/{repo_id}/patches", response_model=RepoPatchesOut)
async def list_patches(repo_id: str):
    """Return recent patches for repository from real DB records (P1-8)."""
    repos = await get_core_repositories_async()
    repo = next((r for r in repos if r["id"] == repo_id or r["full_name"] == repo_id or r["name"] == repo_id), None)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    repo_name = repo["full_name"]

    patches_out: list[PatchOut] = []
    async with AsyncSessionLocal() as session:
        # Find DB repo row by full_name or id
        repo_res = await session.execute(
            select(Repo).where(
                or_(
                    Repo.full_name == repo_name,
                    cast(Repo.id, Text) == repo_id,
                )
            ).limit(1)
        )
        db_repo = repo_res.scalar_one_or_none()

        if db_repo:
            stmt = (
                select(Patch, CodeUsage)
                .join(CodeUsage, Patch.code_usage_id == CodeUsage.id)
                .where(CodeUsage.repo_id == db_repo.id)
                .order_by(Patch.created_at.desc())
                .limit(20)
            )
            res = await session.execute(stmt)
            for patch_row, cu_row in res.all():
                # Query associated pull request if opened
                pr_res = await session.execute(
                    select(PullRequest)
                    .where(
                        PullRequest.repo_id == db_repo.id,
                        PullRequest.patch_ids.contains([patch_row.id]),
                    )
                    .limit(1)
                )
                pr_row = pr_res.scalar_one_or_none()

                patches_out.append(
                    PatchOut(
                        id=str(patch_row.id),
                        package=cu_row.file_path,
                        old_version="current",
                        new_version="patched",
                        status="verified" if patch_row.verified else "generated",
                        pr_url=pr_row.github_pr_url if pr_row else f"https://github.com/{repo_name}",
                        usages_patched=1,
                        opened_at=patch_row.created_at.isoformat() if patch_row.created_at else "2026-08-30T00:00:00Z",
                    )
                )

    return RepoPatchesOut(
        repo=repo_name,
        patches=patches_out,
    )
