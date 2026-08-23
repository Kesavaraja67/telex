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

        # Real Revenue Math (paise)
        # Revenue at risk: sum amount for failed attempts
        at_risk_res = await session.execute(
            select(func.coalesce(func.sum(PaymentAttempt.amount), 0))
            .where(PaymentAttempt.status == "failed")
        )
        revenue_at_risk = int(at_risk_res.scalar_one())

        # Revenue recovered: sum amount for PaymentAttempts with at least one recovered RecoveryEvent
        recovered_res = await session.execute(
            select(func.coalesce(func.sum(PaymentAttempt.amount), 0))
            .where(
                PaymentAttempt.id.in_(
                    select(RecoveryEvent.payment_attempt_id)
                    .where(RecoveryEvent.outcome == "recovered")
                )
            )
        )
        revenue_recovered = int(recovered_res.scalar_one())

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
        "revenue_at_risk": revenue_at_risk,
        "revenue_recovered": revenue_recovered,
    }


@router.get("/events", response_model=list[RecoveryEventOut])
async def get_recovery_events(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Return recent recovery events with their classification, outcome, and amount (paise)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(RecoveryEvent, PaymentAttempt.amount)
            .join(PaymentAttempt, RecoveryEvent.payment_attempt_id == PaymentAttempt.id)
            .order_by(RecoveryEvent.detected_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = result.all()
        events = []
        for event, amount in rows:
            event_dict = {
                "id": event.id,
                "payment_attempt_id": event.payment_attempt_id,
                "failure_type": event.failure_type,
                "classification": event.classification,
                "action_taken": event.action_taken,
                "llm_provider": event.llm_provider,
                "llm_model": event.llm_model,
                "outcome": event.outcome,
                "pull_request_id": event.pull_request_id,
                "amount": amount,
                "detected_at": event.detected_at,
                "resolved_at": event.resolved_at,
            }
            events.append(RecoveryEventOut(**event_dict))

    return events


