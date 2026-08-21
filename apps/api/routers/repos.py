"""
Repos API — list, toggle, and patch history.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from db.models import Repo, CodeUsage, Patch, DetectedChange, PackageVersion, Package, PullRequest
from schemas import RepoOut, RepoToggleIn, RepoPatchesOut, PatchOut

router = APIRouter(prefix="/api/repos", tags=["repos"])


@router.get("", response_model=list[RepoOut])
async def list_repos(session: AsyncSession = Depends(get_session)):
    """Return all active repos (all installations in V1 — auth-filter in Phase 5)."""
    result = await session.execute(select(Repo).where(Repo.is_active == True))
    return result.scalars().all()


@router.post("/{repo_id}/toggle", response_model=RepoOut)
async def toggle_repo(
    repo_id: uuid.UUID,
    body: RepoToggleIn,
    session: AsyncSession = Depends(get_session),
):
    repo = await session.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    repo.is_active = body.is_active
    await session.commit()
    await session.refresh(repo)
    return repo


@router.get("/{repo_id}/patches", response_model=RepoPatchesOut)
async def list_patches(
    repo_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    repo = await session.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")

    # Join PR → PackageVersion → Package for each PR on this repo
    prs_result = await session.execute(
        select(PullRequest)
        .where(PullRequest.repo_id == repo_id)
        .order_by(PullRequest.opened_at.desc())
    )
    prs = list(prs_result.scalars())

    patches_out: list[PatchOut] = []
    for pr in prs:
        pv = await session.get(PackageVersion, pr.package_version_id)
        pkg = await session.get(Package, pv.package_id)

        # Count patched usages
        count_result = await session.execute(
            select(func.count(CodeUsage.id)).where(
                CodeUsage.repo_id == repo_id,
                CodeUsage.status == "patched",
            )
        )
        patched_count = count_result.scalar_one()

        patches_out.append(
            PatchOut(
                id=str(pr.id),
                package=pkg.name,
                old_version="unknown",  # stored on repo_packages.current_version
                new_version=pv.version,
                status=pr.status,
                pr_url=pr.github_pr_url,
                usages_patched=patched_count,
                opened_at=pr.opened_at,
            )
        )

    return RepoPatchesOut(repo=repo.full_name, patches=patches_out)
