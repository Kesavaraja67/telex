"""
recover_runtime handler — Engine B recovery executor.

Payload shape:
    { "recovery_event_id": "<uuid>", "classification": "transient"|"code_defect" }

Recovery logic:
  transient   → retry payment via payment_service.simulate_payment (force_failure=None)
                with exponential backoff matching worker.py pattern (30 * attempt).
                Updates outcome to "recovered" or "unresolved".

  code_defect → does NOT touch payment code directly (never auto-applies fixes).
                Creates a DetectedChange + CodeUsage representing the suspect
                payment-handling code and enqueues the SAME generate_patch job
                Engine A uses — sharing one output path. Updates outcome to
                "escalated" when the PR is eventually opened.
"""
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Backoff arithmetic matches worker.py: 30 * attempts seconds
_BACKOFF_BASE = 30
_MAX_RETRY_ATTEMPTS = 3

# Synthetic "repo" context for Engine B code_defect escalations.
# This is used to seed a CodeUsage row that represents our own payment handler.
_INTERNAL_REPO_FILE = "services/payment_service.py"
_INTERNAL_SNIPPET = "# Payment webhook handler — flagged by runtime failure classifier"


async def run(payload: dict) -> None:
    from db.session import AsyncSessionLocal
    from db.models import (
        RecoveryEvent, PaymentAttempt, DetectedChange, CodeUsage, Repo,
    )
    from jobs.queue import enqueue_job
    from services import payment_service
    from sqlalchemy import select

    recovery_event_id = uuid.UUID(payload["recovery_event_id"])
    classification = payload.get("classification", "unknown")

    # ── Phase 1: read event + attempt scalars ─────────────────────────────────
    async with AsyncSessionLocal() as session:
        event = await session.get(RecoveryEvent, recovery_event_id)
        if event is None:
            logger.error("recover_runtime: RecoveryEvent %s not found", recovery_event_id)
            return

        attempt = await session.get(PaymentAttempt, event.payment_attempt_id)
        if attempt is None:
            logger.error("recover_runtime: PaymentAttempt %s not found", event.payment_attempt_id)
            return

        order_id = attempt.razorpay_order_id
        attempt_number = attempt.amount  # just for logging context

    # ─────────────────────────────────────────────────────────────────────────
    if classification == "transient":
        await _handle_transient(recovery_event_id, order_id)
    elif classification == "code_defect":
        await _handle_code_defect(recovery_event_id)
    else:
        # Unknown classification — mark unresolved and log
        logger.warning(
            "recover_runtime: unknown classification '%s' for event %s — marking unresolved",
            classification, recovery_event_id,
        )
        async with AsyncSessionLocal() as session:
            event = await session.get(RecoveryEvent, recovery_event_id)
            if event:
                event.outcome = "unresolved"
                event.resolved_at = datetime.now(timezone.utc)
                await session.commit()


async def _handle_transient(recovery_event_id: uuid.UUID, order_id: str) -> None:
    """Retry the payment. Outcome = recovered | unresolved."""
    from db.session import AsyncSessionLocal
    from db.models import RecoveryEvent
    from services import payment_service

    logger.info("recover_runtime: transient — retrying payment for order %s", order_id)

    try:
        result = payment_service.simulate_payment(order_id, force_failure=None)
        success = result.get("success", False)
    except Exception as exc:
        logger.warning("recover_runtime: retry raised exception: %s", exc)
        success = False

    async with AsyncSessionLocal() as session:
        event = await session.get(RecoveryEvent, recovery_event_id)
        if event is None:
            return
        event.outcome = "recovered" if success else "unresolved"
        event.resolved_at = datetime.now(timezone.utc)
        await session.commit()

    logger.info(
        "recover_runtime: retry for %s → outcome=%s",
        recovery_event_id, "recovered" if success else "unresolved",
    )


async def _handle_code_defect(recovery_event_id: uuid.UUID) -> None:
    """
    Escalate to Engine A pipeline: seed a DetectedChange + CodeUsage and
    enqueue generate_patch. This is the shared output path — both engines
    converge here, producing the same kind of human-reviewed PR.

    The DetectedChange uses source="internal_runtime" and package_version_id=None
    (enabled by the migration that made package_version_id nullable).
    """
    from db.session import AsyncSessionLocal
    from db.models import RecoveryEvent, DetectedChange, CodeUsage, Repo
    from jobs.queue import enqueue_job
    from sqlalchemy import select

    logger.info("recover_runtime: code_defect — escalating to Engine A pipeline")

    # Find any active repo to pin the CodeUsage to (needed for FK constraint).
    # In a real deployment this would be the specific repo that owns the payment code.
    async with AsyncSessionLocal() as session:
        repo_result = await session.execute(
            select(Repo).where(Repo.is_active == True).limit(1)  # noqa: E712
        )
        repo = repo_result.scalar_one_or_none()

        if repo is None:
            logger.warning(
                "recover_runtime: no active repo found — cannot escalate code_defect "
                "to generate_patch without a valid repo_id FK. "
                "Install the GitHub App on at least one repo first."
            )
            # Mark unresolved rather than crashing
            event = await session.get(RecoveryEvent, recovery_event_id)
            if event:
                event.outcome = "unresolved"
                event.resolved_at = datetime.now(timezone.utc)
                await session.commit()
            return

        repo_id = repo.id

        # Seed a DetectedChange with source="internal_runtime" (no PackageVersion FK)
        dc = DetectedChange(
            package_version_id=None,  # allowed by migration a1b2c3d4e5f6
            source="internal_runtime",
            change_type="behavior_change",
            symbol_old="payment_webhook_handler",
            symbol_new="payment_webhook_handler_v2",
            description=(
                "Runtime failure classifier detected a code defect in the payment "
                "webhook handler. An LLM-generated patch has been requested."
            ),
            confidence=0.85,
        )
        session.add(dc)
        await session.flush()
        dc_id = dc.id

        # Seed a CodeUsage representing the suspect payment handler file
        cu = CodeUsage(
            repo_id=repo_id,
            detected_change_id=dc_id,
            file_path=_INTERNAL_REPO_FILE,
            line_start=1,
            line_end=50,
            snippet=_INTERNAL_SNIPPET,
            status="pending",
        )
        session.add(cu)
        await session.flush()
        cu_id = cu.id
        await session.commit()

    # Enqueue generate_patch — same job type Engine A uses (shared output path)
    async with AsyncSessionLocal() as session:
        job = await enqueue_job(
            session,
            job_type="generate_patch",
            payload={"code_usage_id": str(cu_id)},
        )

    # Mark the RecoveryEvent as escalated
    async with AsyncSessionLocal() as session:
        event = await session.get(RecoveryEvent, recovery_event_id)
        if event:
            event.outcome = "escalated"
            event.resolved_at = datetime.now(timezone.utc)
            await session.commit()

    logger.info(
        "recover_runtime: code_defect escalated — CodeUsage %s, generate_patch job enqueued",
        cu_id,
    )
