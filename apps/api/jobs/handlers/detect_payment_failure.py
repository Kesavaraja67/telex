"""
detect_payment_failure handler — Engine B entry point.

Payload shape:
    { "payment_attempt_id": "<uuid>" }

Reads the failed PaymentAttempt, creates a RecoveryEvent recording
that a failure was detected, then enqueues diagnose_runtime_failure.
This handler does NOT classify — classification is the next handler's job.
"""
import logging
import uuid

logger = logging.getLogger(__name__)


async def run(payload: dict) -> None:
    from db.session import AsyncSessionLocal
    from db.models import PaymentAttempt, RecoveryEvent
    from jobs.queue import enqueue_job

    payment_attempt_id = uuid.UUID(payload["payment_attempt_id"])

    # ── Phase 1: read scalars ─────────────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        attempt = await session.get(PaymentAttempt, payment_attempt_id)
        if attempt is None:
            logger.error(
                "detect_payment_failure: PaymentAttempt %s not found", payment_attempt_id
            )
            return
        if attempt.status != "failed":
            logger.info(
                "detect_payment_failure: attempt %s status is %s — skipping",
                payment_attempt_id, attempt.status,
            )
            return

        # Derive failure_type from injected_failure or a generic "payment_failed" label
        failure_type = attempt.injected_failure or "payment_failed"

        # ── Phase 2: record the detection event ───────────────────────────────
        event = RecoveryEvent(
            payment_attempt_id=payment_attempt_id,
            failure_type=failure_type,
            classification="unknown",
            action_taken="Failure detected — awaiting diagnosis",
            llm_provider="none",
            llm_model="none",
            outcome="unresolved",
        )
        session.add(event)
        await session.flush()
        event_id = event.id
        await session.commit()

    # ── Phase 3: enqueue diagnosis (outside session) ──────────────────────────
    async with AsyncSessionLocal() as session:
        await enqueue_job(
            session,
            job_type="diagnose_runtime_failure",
            payload={"recovery_event_id": str(event_id)},
        )

    logger.info(
        "detect_payment_failure: created RecoveryEvent %s for attempt %s (failure_type=%s)",
        event_id, payment_attempt_id, failure_type,
    )
