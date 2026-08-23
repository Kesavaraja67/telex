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
    """
    Retry the payment in worker thread with deliberate stop rules.
    - If retry_count >= 2 and failure_type == "card_declined", deliberately STOP.
    - Otherwise execute transient backoff retry.
    """
    from db.session import AsyncSessionLocal
    from db.models import RecoveryEvent, PaymentAttempt
    from services import payment_service
    from sqlalchemy import select, func

    # Check prior retry count for this order
    async with AsyncSessionLocal() as session:
        event = await session.get(RecoveryEvent, recovery_event_id)
        if event is None:
            return

        prior_retries_res = await session.execute(
            select(func.count(RecoveryEvent.id))
            .join(PaymentAttempt, RecoveryEvent.payment_attempt_id == PaymentAttempt.id)
            .where(
                PaymentAttempt.razorpay_order_id == order_id,
                RecoveryEvent.id != recovery_event_id,
            )
        )
        prior_retries_count = prior_retries_res.scalar_one()
        current_retry_count = prior_retries_count + 1
        event.retry_count = current_retry_count
        failure_type = event.failure_type

        # DELIBERATE STOP CHECK: repeated card declines on the same order
        if current_retry_count >= 3 and failure_type == "card_declined":
            logger.info(
                "recover_runtime: deliberate stop triggered for order %s (failure_type=card_declined, retries=%d)",
                order_id, current_retry_count,
            )
            event.outcome = "unresolved"
            event.action_taken = (
                f"Stopped retrying after {current_retry_count - 1} attempts — repeated card decline is unlikely to resolve "
                "automatically. Recommend alternate payment method."
            )
            event.resolved_at = datetime.now(timezone.utc)
            await session.commit()
            return

        await session.commit()

    logger.info("recover_runtime: transient — retrying payment for order %s (attempt #%d)", order_id, current_retry_count)

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
        if success:
            attempt = await session.get(PaymentAttempt, event.payment_attempt_id)
            if attempt:
                attempt.status = "success"
        await session.commit()

    logger.info(
        "recover_runtime: retry for %s → outcome=%s",
        recovery_event_id, "recovered" if success else "unresolved",
    )


# Honest defect location mapping for known code defects
KNOWN_DEFECT_LOCATIONS = {
    "webhook_signature_mismatch": {
        "file_path": "apps/api/routers/payments.py",
        "line_start": 125,
        "line_end": 145,
        "symbol_old": "verify_webhook_signature",
        "symbol_new": "verify_webhook_signature_v2",
        "snippet": 'if not payment_service.verify_webhook_signature(request_body, x_razorpay_signature or ""):\n    raise HTTPException(status_code=401, detail="Invalid webhook signature")',
        "description": "Cryptographic webhook HMAC signature mismatch detected in payment router.",
    },
    "webhook_schema_mismatch": {
        "file_path": "apps/api/routers/payments.py",
        "line_start": 140,
        "line_end": 165,
        "symbol_old": "parse_webhook_event",
        "symbol_new": "parse_webhook_event_v2",
        "snippet": 'payment = event.get("payload", {}).get("payment", {}).get("entity", {})\norder_id = payment.get("order_id")\nrazorpay_payment_id = payment.get("id")',
        "description": "Schema structure mismatch in payload parsing for webhook events.",
    },
    "payment_malformed_response": {
        "file_path": "apps/api/services/payment_service.py",
        "line_start": 130,
        "line_end": 165,
        "symbol_old": "create_payment_attempt",
        "symbol_new": "create_payment_attempt_v2",
        "snippet": 'result = client.payment.create(payment_data)\nis_success = result.get("status") not in ("failed",)',
        "description": "Payment response parsing schema defect in payment_service.",
    },
}


async def _handle_code_defect(recovery_event_id: uuid.UUID) -> None:
    """
    Escalate to Engine A pipeline using real defect source locations:
    seeds a DetectedChange + CodeUsage and enqueues generate_patch.
    For unmapped defect failure types, marks unresolved for manual review.
    """
    from db.session import AsyncSessionLocal
    from db.models import RecoveryEvent, DetectedChange, CodeUsage, Repo
    from jobs.queue import enqueue_job
    from sqlalchemy import select
    from config import settings

    logger.info("recover_runtime: code_defect — escalating to Engine A pipeline")

    async with AsyncSessionLocal() as session:
        event = await session.get(RecoveryEvent, recovery_event_id)
        if event is None:
            return

        defect_info = KNOWN_DEFECT_LOCATIONS.get(event.failure_type)
        if not defect_info:
            logger.info("recover_runtime: unmapped code defect '%s' — flagging for manual review", event.failure_type)
            event.outcome = "unresolved"
            event.resolved_at = datetime.now(timezone.utc)
            event.action_taken = "Code defect suspected but no known source location — flagged for manual review"
            await session.commit()
            return

        # Find the target repo:
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
            event.outcome = "unresolved"
            event.resolved_at = datetime.now(timezone.utc)
            event.action_taken = "Cannot escalate code defect — no active GitHub repository connected"
            await session.commit()
            return

        repo_id = repo.id

        # Seed a DetectedChange with real defect metadata
        dc = DetectedChange(
            package_version_id=None,
            source="internal_runtime",
            change_type="behavior_change",
            symbol_old=defect_info["symbol_old"],
            symbol_new=defect_info["symbol_new"],
            description=defect_info["description"],
            confidence=0.90,
        )
        session.add(dc)
        await session.flush()
        dc_id = dc.id

        # Seed a CodeUsage representing the real defect file and lines
        cu = CodeUsage(
            repo_id=repo_id,
            detected_change_id=dc_id,
            file_path=defect_info["file_path"],
            line_start=defect_info["line_start"],
            line_end=defect_info["line_end"],
            snippet=defect_info["snippet"],
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
        "recover_runtime: code_defect escalated — CodeUsage %s (%s:%d-%d), generate_patch enqueued",
        cu_id,
        defect_info["file_path"],
        defect_info["line_start"],
        defect_info["line_end"],
    )

