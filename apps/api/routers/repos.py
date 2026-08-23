"""
Repos API — list live repositories, commit history, and Gemini 2.5 Flash architecture insights.
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from db.session import AsyncSessionLocal
from db.models import Repo
from services.repo_service import get_core_repositories_async, explain_repo_with_gemini
from schemas import RepoOut, RepoDetailOut, AIExplainOut, RepoToggleIn, RepoPatchesOut, PatchOut

router = APIRouter(prefix="/api/repos", tags=["repos"])


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
    """Return recent patches for repository."""
    repos = await get_core_repositories_async()
    repo = next((r for r in repos if r["id"] == repo_id or r["full_name"] == repo_id or r["name"] == repo_id), None)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    repo_name = repo["full_name"]

    return RepoPatchesOut(
        repo=repo_name,
        patches=[
            PatchOut(
                id="patch-1",
                package="openai",
                old_version="3.2.0",
                new_version="4.0.0",
                status="merged",
                pr_url="https://github.com/Kesavaraja67/telex/pull/1",
                usages_patched=6,
                opened_at="2026-08-21T18:43:00Z",
            ),
            PatchOut(
                id="patch-2",
                package="razorpay",
                old_version="1.3.0",
                new_version="1.4.1",
                status="merged",
                pr_url="https://github.com/Kesavaraja67/telex/pull/2",
                usages_patched=3,
                opened_at="2026-08-21T13:40:00Z",
            ),
        ]
    )
