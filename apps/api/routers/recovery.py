"""
Recovery router — Engine B stats and event listing endpoints.
"""
import logging

from fastapi import APIRouter, Query
from sqlalchemy import select, func

from db.session import AsyncSessionLocal
from db.models import RecoveryEvent, PaymentAttempt
from schemas import RecoveryEventOut, RecoveryStatsOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/recovery", tags=["recovery"])


@router.get("/stats", response_model=RecoveryStatsOut)
async def get_recovery_stats():
    """Return aggregate recovery statistics for the dashboard."""
    async with AsyncSessionLocal() as session:
        total_attempts = (
            await session.execute(select(func.count(PaymentAttempt.id)))
        ).scalar_one()

        total_events = (
            await session.execute(select(func.count(RecoveryEvent.id)))
        ).scalar_one()

        recovered = (
            await session.execute(
                select(func.count(RecoveryEvent.id)).where(RecoveryEvent.outcome == "recovered")
            )
        ).scalar_one()

        escalated = (
            await session.execute(
                select(func.count(RecoveryEvent.id)).where(RecoveryEvent.outcome == "escalated")
            )
        ).scalar_one()

        unresolved = (
            await session.execute(
                select(func.count(RecoveryEvent.id)).where(RecoveryEvent.outcome == "unresolved")
            )
        ).scalar_one()

        tier1_count = (
            await session.execute(
                select(func.count(RecoveryEvent.id)).where(
                    RecoveryEvent.llm_provider == "none",
                    RecoveryEvent.classification != "unknown",
                )
            )
        ).scalar_one()

        tier2_count = (
            await session.execute(
                select(func.count(RecoveryEvent.id)).where(
                    RecoveryEvent.llm_provider != "none"
                )
            )
        ).scalar_one()

    recovery_rate = (recovered + escalated) / total_events if total_events > 0 else 0.0

    return {
        "total_payment_attempts": total_attempts,
        "total_recovery_events": total_events,
        "recovered": recovered,
        "escalated": escalated,
        "unresolved": unresolved,
        "recovery_rate": round(recovery_rate, 4),
        "tier1_classified": tier1_count,
        "tier2_classified": tier2_count,
    }


@router.get("/events", response_model=list[RecoveryEventOut])
async def get_recovery_events(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Return recent recovery events with their classification and outcome."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(RecoveryEvent)
            .order_by(RecoveryEvent.detected_at.desc())
            .limit(limit)
            .offset(offset)
        )
        events = list(result.scalars())

    return events

