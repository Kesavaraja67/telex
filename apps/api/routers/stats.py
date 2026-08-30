"""
Stats API — dashboard summary counts.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from db.models import Repo, PullRequest, Patch
from schemas import StatsOut
from routers.auth import require_auth

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", response_model=StatsOut)
async def get_stats(session: AsyncSession = Depends(get_session)):
    """Return aggregate counts for the dashboard overview."""

    repos_count = (
        await session.execute(select(func.count(Repo.id)).where(Repo.is_active == True))
    ).scalar_one()

    prs_total = (
        await session.execute(select(func.count(PullRequest.id)))
    ).scalar_one()

    prs_merged = (
        await session.execute(
            select(func.count(PullRequest.id)).where(PullRequest.status == "merged")
        )
    ).scalar_one()

    patches_count = (
        await session.execute(select(func.count(Patch.id)).where(Patch.verified == True))
    ).scalar_one()

    merge_rate = (prs_merged / prs_total) if prs_total > 0 else 0.0

    return StatsOut(
        repos_watched=repos_count,
        prs_opened=prs_total,
        patches_generated=patches_count,
        merge_rate=round(merge_rate, 3),
    )
