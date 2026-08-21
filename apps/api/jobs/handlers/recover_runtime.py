"""
recover_runtime handler — Engine B recovery executor.

Payload shape:
    { "recovery_event_id": "<uuid>", "classification": "transient"|"code_defect" }

Recovery logic:
  transient   → execute retry via payment_service.simulate_payment in worker thread.
                Updates outcome to "recovered" or "unresolved".

  code_defect → does NOT touch payment code directly (never auto-applies fixes).
                Creates a DetectedChange + CodeUsage representing the suspect
                payment-handling code and enqueues generate_patch, passing
                recovery_event_id so open_pr can link the resulting PR.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Synthetic "repo" context for Engine B code_defect escalations.
# This is used to seed a CodeUsage row that represents our own payment handler.
_INTERNAL_REPO_FILE = "services/payment_service.py"
_INTERNAL_SNIPPET = "# Payment webhook handler — flagged by runtime failure classifier"


async def run(payload: dict) -> None:
    from db.session import AsyncSessionLocal
    from db.models import RecoveryEvent, PaymentAttempt

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
    """Retry the payment in worker thread. Outcome = recovered | unresolved."""
    from db.session import AsyncSessionLocal
    from db.models import RecoveryEvent
    from services import payment_service

    logger.info("recover_runtime: transient — retrying payment for order %s", order_id)

    try:
        result = await asyncio.to_thread(payment_service.simulate_payment, order_id, force_failure=None)
        success = result.get("success", False)
    except Exception as exc:
        logger.exception("recover_runtime: retry raised exception: %s", exc)
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
    """
    from db.session import AsyncSessionLocal
    from db.models import RecoveryEvent, DetectedChange, CodeUsage, Repo
    from jobs.queue import enqueue_job
    from sqlalchemy import select

    logger.info("recover_runtime: code_defect — escalating to Engine A pipeline")

    # Find the target repo:
    # 1. If settings.payment_recovery_repo_name is configured (e.g. "owner/repo"), match that.
    # 2. Otherwise, look for the primary active connected repo.
    from config import settings

    async with AsyncSessionLocal() as session:
        repo = None
        if settings.payment_recovery_repo_name:
            named_result = await session.execute(
                select(Repo).where(
                    Repo.full_name == settings.payment_recovery_repo_name,
                    Repo.is_active == True,  # noqa: E712
                ).limit(1)
            )
            repo = named_result.scalar_one_or_none()
            if repo:
                logger.info("recover_runtime: targeting configured repo %s", repo.full_name)

        if repo is None:
            repo_result = await session.execute(
                select(Repo).where(Repo.is_active == True).order_by(Repo.created_at.asc()).limit(1)  # noqa: E712
            )
            repo = repo_result.scalar_one_or_none()

        if repo is None:
            logger.warning(
                "recover_runtime: no active repo found — cannot escalate code_defect "
                "to generate_patch without a valid repo_id FK. "
                "Install the GitHub App on at least one repo first or set PAYMENT_RECOVERY_REPO_NAME."
            )
            event = await session.get(RecoveryEvent, recovery_event_id)
            if event:
                event.outcome = "unresolved"
                event.resolved_at = datetime.now(timezone.utc)
                await session.commit()
            return

        repo_id = repo.id

        # Seed a DetectedChange with source="internal_runtime" (no PackageVersion FK)
        dc = DetectedChange(
            package_version_id=None,
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

        # Enqueue generate_patch — same job type Engine A uses (shared output path)
        await enqueue_job(
            session,
            job_type="generate_patch",
            payload={
                "code_usage_id": str(cu_id),
                "recovery_event_id": str(recovery_event_id),
                "repo_id": str(repo_id),
            },
        )
        await session.commit()

    logger.info(
        "recover_runtime: code_defect escalated — CodeUsage %s, generate_patch job enqueued",
        cu_id,
    )

