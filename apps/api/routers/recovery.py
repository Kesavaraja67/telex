"""
Recovery router — Engine B stats and event listing endpoints.
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from sqlalchemy import select, func

from db.session import AsyncSessionLocal
from db.models import RecoveryEvent, PaymentAttempt
from schemas import RecoveryEventOut, RecoveryStatsOut
from routers.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/recovery", tags=["recovery"])


def _derive_stage(outcome: str, classification: str) -> str:
    """
    Compute a UX-friendly stage label from stored outcome + classification.

    Mapping (computed at read time, no extra DB column needed):
      recovered                         -> "resolved"
      escalated                         -> "escalated"
      code_defect + unresolved          -> "recovering"  (Gemini patch in flight)
      unresolved (other classification) -> "detected"
    """
    if outcome == "recovered":
        return "resolved"
    if outcome == "escalated":
        return "escalated"
    if classification == "code_defect" and outcome == "unresolved":
        return "recovering"
    return "detected"


@router.get("/stats", response_model=RecoveryStatsOut, dependencies=[Depends(require_auth)])
async def get_recovery_stats():
    """Return aggregate recovery statistics for the dashboard (requires authentication)."""
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

    # P0-2: Two separate, honestly-named metrics.
    # payment_recovery_rate = payments actually recovered (escalations do NOT count).
    # recovery_execution_rate = events that were actioned in any way (recovered OR escalated).
    payment_recovery_rate = recovered / total_events if total_events > 0 else 0.0
    recovery_execution_rate = (recovered + escalated) / total_events if total_events > 0 else 0.0

    return {
        "total_payment_attempts": total_attempts,
        "total_recovery_events": total_events,
        "recovered": recovered,
        "escalated": escalated,
        "unresolved": unresolved,
        "payment_recovery_rate": round(payment_recovery_rate, 4),
        "recovery_execution_rate": round(recovery_execution_rate, 4),
        "tier1_classified": tier1_count,
        "tier2_classified": tier2_count,
        "revenue_at_risk": revenue_at_risk,
        "revenue_recovered": revenue_recovered,
    }


@router.get("/events", response_model=list[RecoveryEventOut])
async def get_recovery_events(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    payment_attempt_id: Optional[str] = Query(
        None,
        description="Filter events to a specific PaymentAttempt UUID (P0-3)",
    ),
):
    """Return recent recovery events with classification, outcome, amount (paise), and stage."""
    # P1-2: Global feed requires auth; specific payment attempt lookups remain open for customer storefront
    if payment_attempt_id is None:
        await require_auth(request)

    # P0-3: Validate and parse optional filter before hitting the DB
    attempt_uuid_filter: Optional[uuid.UUID] = None
    if payment_attempt_id is not None:
        try:
            attempt_uuid_filter = uuid.UUID(payment_attempt_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid payment_attempt_id UUID")

    async with AsyncSessionLocal() as session:
        query = (
            select(RecoveryEvent, PaymentAttempt.amount)
            .join(PaymentAttempt, RecoveryEvent.payment_attempt_id == PaymentAttempt.id)
        )
        if attempt_uuid_filter is not None:
            query = query.where(RecoveryEvent.payment_attempt_id == attempt_uuid_filter)
        query = query.order_by(RecoveryEvent.detected_at.desc()).limit(limit).offset(offset)

        result = await session.execute(query)
        rows = result.all()
        events = []
        for event, amount in rows:
            # P0-4: Derive stage and action at read time — no new DB columns needed
            stage = _derive_stage(event.outcome, event.classification)
            event_dict = {
                "id": event.id,
                "payment_attempt_id": event.payment_attempt_id,
                "failure_type": event.failure_type,
                "classification": event.classification,
                "action_taken": event.action_taken,
                "action": event.action_taken,  # alias for frontend .action reads
                "stage": stage,
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


