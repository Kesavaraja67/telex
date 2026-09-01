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
from typing import Optional, Any, Dict, List
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

    Recovery path splits by failure type:
    - timeout / db_unavailable (locally-simulated infrastructure failures):
        → call recover_simulated_infrastructure() — deterministic recovery,
          no Razorpay call made (matches the simulated failure boundary).
    - card_declined (real Razorpay Test Mode failure):
        → call simulate_payment() to retry, then independently verify order
          state via verify_order_payment_status() before marking recovered.
    - all others:
        → attempt simulate_payment() + verify order state.

    Stop rules:
    - If retry_count >= 3 and failure_type == "card_declined", stop retrying.
    """
    from db.session import AsyncSessionLocal
    from db.models import RecoveryEvent, PaymentAttempt
    from services import payment_service
    from sqlalchemy import select, func

    _SIMULATED_INFRA_FAILURES = {"timeout", "db_unavailable"}

    # Check prior retry count for this order with matching classification/failure
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
                RecoveryEvent.failure_type == event.failure_type,
                RecoveryEvent.classification == "transient",
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
                f"Stopped retrying after {current_retry_count} attempts — repeated card decline is unlikely to resolve "
                "automatically. Recommend alternate payment method."
            )
            event.resolved_at = datetime.now(timezone.utc)
            await session.commit()
            return

        await session.commit()

    logger.info(
        "recover_runtime: transient — retrying for order %s (attempt #%d, failure_type=%s)",
        order_id, current_retry_count, failure_type,
    )

    # ── Recovery action: split by failure type ────────────────────────────────
    success = False
    action_detail = ""

    if failure_type in _SIMULATED_INFRA_FAILURES:
        # Locally-simulated infrastructure failure: no real Razorpay payment exists to retry.
        # Recovery is deterministic — the infrastructure condition has resolved.
        try:
            result = await asyncio.to_thread(
                payment_service.recover_simulated_infrastructure, order_id, failure_type
            )
            success = result.get("success", False)
            action_detail = (
                f"Simulated infrastructure recovery: {failure_type} resolved. "
                f"Recovery ref: {result.get('synthetic_payment_id', 'n/a')}"
            )
            logger.info(
                "recover_runtime: simulated infrastructure recovery for %s → success=%s",
                order_id, success,
            )
        except Exception as exc:
            logger.exception("recover_runtime: recover_simulated_infrastructure raised: %s", exc)
            success = False
            action_detail = f"Infrastructure recovery failed unexpectedly: {exc}"

    else:
        # Real Razorpay failure (card_declined or other).
        # Step 1: Check if the order is already paid (the original attempt may have
        # succeeded despite the failure signal).
        try:
            verify_result = await asyncio.to_thread(
                payment_service.verify_order_payment_status, order_id
            )
            success = verify_result.get("success", False)
            verified_payment_id = verify_result.get("payment_id")
            order_status = verify_result.get("order_status", "unknown")
        except Exception as exc:
            logger.warning("recover_runtime: order verification failed for %s: %s", order_id, exc)
            success = False
            verified_payment_id = None
            order_status = "error"

        if success:
            # Order already has a captured payment — it recovered without intervention
            action_detail = (
                f"Order already captured — no retry needed. "
                f"Order status: {order_status}. Captured payment: {verified_payment_id}."
            )
            logger.info(
                "recover_runtime: order %s already paid (status=%s) — marking recovered",
                order_id, order_status,
            )
        else:
            # Order not yet paid: generate a Checkout retry URL per Razorpay's Standard
            # Checkout model. Customers can retry the same order through the browser flow.
            # We do not call client.payment.create() — that is not a payment-collection API.
            from config import settings as _settings
            web_url = _settings.web_app_url or "https://telex-pi.vercel.app"
            try:
                retry_info = await asyncio.to_thread(
                    payment_service.generate_checkout_retry_url, order_id, web_url
                )
                action_detail = (
                    f"Checkout retry URL generated for customer: {retry_info.get('checkout_retry_url')}. "
                    f"Customer must re-attempt payment via Standard Checkout on the same order."
                )
            except Exception as exc:
                action_detail = f"Checkout retry URL generation failed: {exc}"
            success = False  # not recovered until customer completes Checkout
            logger.info(
                "recover_runtime: checkout retry URL generated for order %s — awaiting customer action",
                order_id,
            )

    # ── Persist outcome ───────────────────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        event = await session.get(RecoveryEvent, recovery_event_id)
        if event is None:
            return
        event.outcome = "recovered" if success else "unresolved"
        event.resolved_at = datetime.now(timezone.utc)
        if action_detail:
            event.action_taken = action_detail
        if success:
            attempt = await session.get(PaymentAttempt, event.payment_attempt_id)
            if attempt:
                attempt.status = "success"
        await session.commit()

    logger.info(
        "recover_runtime: retry for %s → outcome=%s",
        recovery_event_id, "recovered" if success else "unresolved",
    )


# Real defect location mapping for known code defects across monitored repositories
FAILURE_LOCATION_MAP: dict[str, dict[str, Any]] = {
    "order_total_mismatch": {
        "file_path": "app/api/order-summary/route.ts",
        "alt_file_paths": ["src/app/api/order-summary/route.ts"],
        "line_start": 1,
        "line_end": 40,
        "symbol_old": "calculateOrderSummary",
        "symbol_new": "",
        "description": (
            "Fee calculation produces a value 1 paise lower than expected. "
            "The observed regression (e.g. expected 247, actual 246) is consistent with "
            "a truncation operation (Math.trunc) being used instead of rounding (Math.round) "
            "when computing the platform fee. No other behavior should be changed."
        ),
        "fallback_snippet": (
            "// Platform fee calculation — suspect truncation\n"
            "const platformFee = Math.trunc(subtotal * feeRate);\n"
            "const total = subtotal + platformFee;"
        ),
    },
    "webhook_signature_mismatch": {
        "file_path": "apps/api/routers/payments.py",
        "line_start": 145,
        "line_end": 165,
        "symbol_old": "verify_webhook_signature",
        "symbol_new": "verify_webhook_signature_v2",
        "description": "Cryptographic webhook HMAC signature mismatch detected in payment router.",
        "fallback_snippet": 'if not payment_service.verify_webhook_signature(request_body, x_razorpay_signature or ""):\n    raise HTTPException(status_code=401, detail="Invalid webhook signature")',
    },
    "webhook_schema_mismatch": {
        "file_path": "apps/api/routers/payments.py",
        "line_start": 175,
        "line_end": 215,
        "symbol_old": "parse_webhook_event",
        "symbol_new": "parse_webhook_event_v2",
        "description": "Schema structure mismatch in payload parsing for webhook events.",
        "fallback_snippet": 'payment = event.get("payload", {}).get("payment", {}).get("entity", {})\norder_id = payment.get("order_id")\nrazorpay_payment_id = payment.get("id")',
    },
}

KNOWN_DEFECT_LOCATIONS = FAILURE_LOCATION_MAP


async def _handle_code_defect(recovery_event_id: uuid.UUID) -> None:
    """
    Escalate to Engine A pipeline using real defect source locations:
    seeds a DetectedChange + CodeUsage (fetching live snippet from GitHub) and enqueues generate_patch.
    For unmapped defect failure types, marks unresolved for manual review.
    """
    from db.session import AsyncSessionLocal
    from db.models import RecoveryEvent, DetectedChange, CodeUsage, Repo, Installation
    from jobs.queue import enqueue_job
    from sqlalchemy import select
    from config import settings
    from services.github_service import fetch_file_content

    logger.info("recover_runtime: code_defect — escalating to Engine A pipeline")

    async with AsyncSessionLocal() as session:
        event = await session.get(RecoveryEvent, recovery_event_id)
        if event is None:
            return

        defect_info = FAILURE_LOCATION_MAP.get(event.failure_type)
        if not defect_info:
            logger.info("recover_runtime: unmapped code defect '%s' — flagging for manual review", event.failure_type)
            event.outcome = "unresolved"
            event.resolved_at = datetime.now(timezone.utc)
            event.action_taken = "Code defect suspected but source location unknown — flagged for manual review"
            await session.commit()
            return

        # 1. Resolve target repo: prefer explicit setting, then exact mapped name, then matching active repo
        target_name = settings.payment_recovery_repo_name or defect_info.get("repo_full_name")
        repo = None
        if target_name:
            named_result = await session.execute(
                select(Repo).where(
                    Repo.full_name == target_name,
                    Repo.is_active == True,  # noqa: E712
                ).limit(1)
            )
            repo = named_result.scalar_one_or_none()
            if repo:
                logger.info("recover_runtime: targeting repo %s", repo.full_name)

        if repo is None:
            # Fallback: if order_total_mismatch, look for any active connected storefront repo
            if event.failure_type == "order_total_mismatch":
                store_result = await session.execute(
                    select(Repo).where(
                        Repo.is_active == True,  # noqa: E712
                        Repo.full_name.notilike("%telex%"),
                    ).order_by(Repo.created_at.asc()).limit(1)
                )
                repo = store_result.scalar_one_or_none()

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

        # 2. Extract strongly-typed defect metadata
        primary_file_path: str = str(defect_info["file_path"])
        alt_paths: list[str] = [str(p) for p in defect_info.get("alt_file_paths", [])]
        candidate_paths: list[str] = [primary_file_path] + alt_paths
        line_start: int = int(defect_info["line_start"])
        line_end: int = int(defect_info["line_end"])
        symbol_old: str = str(defect_info["symbol_old"])
        symbol_new: str = str(defect_info.get("symbol_new") or "")
        description: str = str(defect_info.get("description") or "")
        fallback_snippet: str = str(defect_info.get("fallback_snippet") or defect_info.get("snippet") or "")

        resolved_file_path: str = primary_file_path
        live_snippet: Optional[str] = None

        # Fetch live current snippet from GitHub API (trying primary and candidate paths)
        if repo and repo.installation_id:
            inst = await session.get(Installation, repo.installation_id)
            if inst:
                for candidate in candidate_paths:
                    full_text = await asyncio.to_thread(
                        fetch_file_content,
                        repo.full_name,
                        inst.github_installation_id,
                        candidate,
                        repo.default_branch or "main",
                    )
                    if full_text:
                        resolved_file_path = candidate
                        lines = full_text.splitlines()
                        s_idx = max(0, line_start - 1)
                        e_idx = min(len(lines), line_end)
                        live_snippet = "\n".join(lines[s_idx:e_idx])
                        logger.info("recover_runtime: live snippet fetched from %s:%s", repo.full_name, candidate)
                        break

        snippet_to_use = live_snippet or fallback_snippet

        # Seed a DetectedChange with real defect metadata
        dc = DetectedChange(
            package_version_id=None,
            source="internal_runtime",
            change_type="behavior_change",
            symbol_old=symbol_old,
            symbol_new=symbol_new,
            description=description,
            confidence=0.90,
        )
        session.add(dc)
        await session.flush()
        dc_id = dc.id

        # Seed a CodeUsage representing the real defect file and lines
        cu = CodeUsage(
            repo_id=repo_id,
            detected_change_id=dc_id,
            file_path=resolved_file_path,
            line_start=line_start,
            line_end=line_end,
            snippet=snippet_to_use,
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

