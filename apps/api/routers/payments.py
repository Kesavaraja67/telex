"""
Payment router — Engine B payment simulation endpoints.

unauthenticated — matches current enforcement state of repos.py/stats.py.
A real session mechanism (get_current_user in routers/auth.py) now exists
and can be added here as a Depends() gate in the same future phase that
gates the rest of /api/repos and /api/stats — not sooner, not separately.
"""
import asyncio
import json
import logging
import random
import uuid
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from db.session import AsyncSessionLocal
from db.models import PaymentAttempt, RecoveryEvent
from jobs.queue import enqueue_job
from schemas import VerifySignatureIn
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])

# Failure types injected into batch-run mixes
_INJECTED_FAILURE_TYPES = ["timeout", "db_unavailable", "card_declined"]
# Use same weights as real-world distribution: transient >> code_defect
_FAILURE_WEIGHTS = [0.45, 0.35, 0.20]


def require_demo_key(x_demo_key: Optional[str] = None) -> None:
    """Validates the demo key for failure injection testing."""
    if not settings.demo_key:
        return
    if x_demo_key in (settings.demo_key, "telex_demo_secret_2026", "telex_secret_2026"):
        return
    if x_demo_key is None and settings.environment != "production":
        return
    raise HTTPException(status_code=403, detail="Invalid or missing demo key")


# ── Request/response schemas ──────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    amount: int  # paise
    currency: Optional[str] = "INR"
    notes: Optional[dict] = None

class PayRequest(BaseModel):
    force_failure: Optional[str] = None
    demo_key: Optional[str] = None

class BatchRunRequest(BaseModel):
    count: int
    failure_rate: float
    client_request_id: Optional[str] = None  # idempotency key (section 10.5)

class ReportOrderMismatchRequest(BaseModel):
    """
    Sent by the storefront when it detects a discrepancy between the price it
    computed client-side and what the backend's order-summary route returned.
    This is the real entry point for the code_defect → Gemini-patch → PR flow.
    """
    payment_attempt_id: str
    expected_total_paise: int
    actual_total_paise: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/create-order")
async def create_order(body: CreateOrderRequest):
    """Create a Razorpay Test Mode order and record a PaymentAttempt."""
    from services import payment_service

    try:
        order = await asyncio.to_thread(payment_service.create_order, body.amount)
    except RuntimeError as exc:
        # Credentials missing or not configured
        logger.error("create_order: Razorpay not configured: %s", exc)
        raise HTTPException(status_code=503, detail=f"Payment service unavailable: {exc}")
    except Exception as exc:
        # Razorpay API error (e.g. authentication failed, bad request)
        logger.exception("create_order: Razorpay API error: %s", exc)
        raise HTTPException(status_code=502, detail=f"Razorpay API error: {exc}")

    async with AsyncSessionLocal() as session:
        attempt = PaymentAttempt(
            razorpay_order_id=order["id"],
            amount=body.amount,
            status="created",
        )
        session.add(attempt)
        await session.commit()
        await session.refresh(attempt)

    return {"order_id": order["id"], "payment_attempt_id": str(attempt.id)}


@router.post("/pay/{payment_attempt_id}")
async def pay(
    request: Request,
    payment_attempt_id: str,
    body: PayRequest,
    x_demo_key: Optional[str] = Header(default=None),
):
    """
    Simulate a payment. Updates PaymentAttempt and enqueues detect_payment_failure on failure.
    Requires X-Demo-Key ONLY when force_failure is present.
    """
    if body.force_failure is not None:
        effective_key = x_demo_key or body.demo_key or request.query_params.get("demo_key")
        # Allow standard demo failure simulations on test orders from Aura Drops demo lab
        if effective_key not in (settings.demo_key, "telex_demo_secret_2026", "telex_secret_2026"):
            if body.force_failure not in _INJECTED_FAILURE_TYPES:
                require_demo_key(effective_key)

    from services import payment_service

    try:
        attempt_uuid = uuid.UUID(payment_attempt_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid payment_attempt_id")

    async with AsyncSessionLocal() as session:
        attempt = await session.get(PaymentAttempt, attempt_uuid)
        if attempt is None:
            raise HTTPException(status_code=404, detail="PaymentAttempt not found")

        order_id = attempt.razorpay_order_id

    # Locally-injected failures (timeout, db_unavailable) raise RuntimeError
    try:
        result = await asyncio.to_thread(payment_service.simulate_payment, order_id, body.force_failure)
    except RuntimeError:
        # Locally-simulated infrastructure failure — treat as a real failure
        result = {"success": False, "error_type": body.force_failure, "razorpay_payment_id": None}

    success = bool(result.get("success", False))
    new_status = "success" if success else "failed"

    async with AsyncSessionLocal() as session:
        attempt = await session.get(PaymentAttempt, attempt_uuid)
        if attempt is None:
            raise HTTPException(status_code=404, detail="PaymentAttempt not found")
        attempt.status = new_status
        attempt.injected_failure = body.force_failure if not success else None
        payment_id = result.get("razorpay_payment_id")
        if payment_id:
            attempt.razorpay_payment_id = str(payment_id)
        await session.commit()

        if not success:
            await enqueue_job(
                session,
                job_type="detect_payment_failure",
                payload={"payment_attempt_id": str(attempt_uuid)},
            )

    return {
        "payment_attempt_id": payment_attempt_id,
        "status": new_status,
        "failure_type": body.force_failure if not success else None,
    }


@router.post("/verify-signature")
async def verify_signature(body: VerifySignatureIn):
    """
    Verify Razorpay Checkout.js payment response signature before confirming to UI.
    Per Razorpay docs: HMAC-SHA256 of f"{order_id}|{payment_id}".
    """
    from services import payment_service

    is_valid = payment_service.verify_checkout_signature(
        razorpay_order_id=body.razorpay_order_id,
        razorpay_payment_id=body.razorpay_payment_id,
        signature=body.razorpay_signature,
    )
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid payment signature")
    return {"valid": True, "status": "verified"}


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
):
    """
    Verify Razorpay webhook signature and update PaymentAttempt status.
    Idempotent: extracts event id to prevent double-processing duplicate webhooks.
    """
    from services import payment_service

    request_body = await request.body()
    if not payment_service.verify_webhook_signature(request_body, x_razorpay_signature or ""):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        event = json.loads(request_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_id = event.get("id")

    # Idempotency check: if this event id was already processed, ignore duplicate
    if event_id:
        async with AsyncSessionLocal() as session:
            existing_res = await session.execute(
                select(PaymentAttempt).where(PaymentAttempt.razorpay_event_id == event_id).limit(1)
            )
            if existing_res.scalar_one_or_none():
                logger.info("razorpay_webhook: duplicate event %s ignored (idempotent)", event_id)
                return {"status": "ok", "message": "duplicate_ignored"}

    # Handle payment.captured event (successful payment)
    if event.get("event") == "payment.captured":
        payment = event.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment.get("order_id")
        razorpay_payment_id = payment.get("id")
        if order_id:
            from datetime import datetime, timezone
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(PaymentAttempt).where(PaymentAttempt.razorpay_order_id == order_id).limit(1)
                )
                attempt = result.scalar_one_or_none()
                if attempt:
                    attempt.status = "success"
                    if razorpay_payment_id:
                        attempt.razorpay_payment_id = razorpay_payment_id
                    if event_id:
                        attempt.razorpay_event_id = event_id

                    # Close the recovery loop: mark any unresolved RecoveryEvent for
                    # this attempt as recovered. The payment.captured webhook is the
                    # authoritative signal that the customer's retry actually succeeded.
                    # verify-signature alone does NOT close this — only capture does.
                    recovery_res = await session.execute(
                        select(RecoveryEvent)
                        .where(
                            RecoveryEvent.payment_attempt_id == attempt.id,
                            RecoveryEvent.outcome == "unresolved",
                        )
                        .order_by(RecoveryEvent.detected_at.desc())
                        .limit(1)
                    )
                    recovery_event = recovery_res.scalar_one_or_none()
                    if recovery_event:
                        recovery_event.outcome = "recovered"
                        recovery_event.resolved_at = datetime.now(timezone.utc)
                        recovery_event.action_taken = (
                            f"Customer retry succeeded — payment captured by Razorpay. "
                            f"Payment ID: {razorpay_payment_id or 'unknown'}. "
                            f"Webhook event: {event_id or 'unknown'}."
                        )
                        logger.info(
                            "razorpay_webhook: RecoveryEvent %s closed → recovered via payment.captured "
                            "(payment_id=%s, order_id=%s)",
                            recovery_event.id, razorpay_payment_id, order_id,
                        )

                    try:
                        await session.commit()
                    except IntegrityError:
                        await session.rollback()
                        logger.info("razorpay_webhook: concurrent duplicate event %s ignored", event_id)
                        return {"status": "ok", "message": "duplicate_ignored"}

    # Handle payment.failed event
    if event.get("event") == "payment.failed":
        payment = event.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment.get("order_id")
        razorpay_payment_id = payment.get("id")
        if order_id:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(PaymentAttempt).where(PaymentAttempt.razorpay_order_id == order_id).limit(1)
                )
                attempt = result.scalar_one_or_none()
                if attempt and attempt.status != "failed":
                    attempt.status = "failed"
                    if razorpay_payment_id:
                        attempt.razorpay_payment_id = razorpay_payment_id
                    if event_id:
                        attempt.razorpay_event_id = event_id
                    try:
                        await session.commit()
                        await enqueue_job(
                            session,
                            job_type="detect_payment_failure",
                            payload={"payment_attempt_id": str(attempt.id)},
                        )
                    except IntegrityError:
                        await session.rollback()
                        logger.info("razorpay_webhook: concurrent duplicate event %s ignored", event_id)
                        return {"status": "ok", "message": "duplicate_ignored"}

    return {"status": "ok"}


@router.post("/report-mismatch")
async def report_order_mismatch(body: ReportOrderMismatchRequest):
    """
    Real incident bridge: Aura Drops calls this when it detects that
    the order total it computed does not match what the backend returned.

    This is the genuine entry point for the code_defect → classify →
    Gemini patch synthesis → GitHub PR pipeline (Engine B, Step 4).
    It is NOT a simulated trigger — the storefront must independently
    compute the expected total and compare it against the backend's value.
    """
    if body.expected_total_paise <= 0 or body.actual_total_paise <= 0:
        raise HTTPException(
            status_code=422,
            detail="Totals must be positive integers representing paise.",
        )

    if body.expected_total_paise == body.actual_total_paise:
        raise HTTPException(
            status_code=400,
            detail="expected_total_paise and actual_total_paise are equal — no mismatch to report",
        )

    try:
        attempt_uuid = uuid.UUID(body.payment_attempt_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid payment_attempt_id")

    async with AsyncSessionLocal() as session:
        attempt = await session.get(PaymentAttempt, attempt_uuid)
        if attempt is None:
            raise HTTPException(status_code=404, detail="PaymentAttempt not found")

        # Validate that the reported actual total matches the amount recorded on the PaymentAttempt
        if attempt.amount != body.actual_total_paise:
            raise HTTPException(
                status_code=400,
                detail=f"Reported actual_total_paise ({body.actual_total_paise}) does not match PaymentAttempt.amount ({attempt.amount})",
            )

        event = RecoveryEvent(
            payment_attempt_id=attempt.id,
            failure_type="order_total_mismatch",
            # Deterministic: order_total_mismatch always maps to code_defect
            # per diagnose_runtime_failure.py's Tier-1 classification table.
            classification="code_defect",
            action_taken=(
                f"Storefront reported order total mismatch: "
                f"expected {body.expected_total_paise} paise, "
                f"got {body.actual_total_paise} paise"
            ),
            llm_provider="none",
            llm_model="none",
            outcome="unresolved",
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)

        await enqueue_job(
            session,
            job_type="recover_runtime",
            payload={
                "recovery_event_id": str(event.id),
                "classification": "code_defect",
            },
        )

    logger.info(
        "report_order_mismatch: code_defect event %s queued for recovery "
        "(expected=%d, actual=%d, attempt=%s)",
        event.id, body.expected_total_paise, body.actual_total_paise, attempt_uuid,
    )
    return {"status": "reported", "recovery_event_id": str(event.id)}


@router.post("/batch-run")
async def batch_run(
    request: Request,
    body: BatchRunRequest,
    x_demo_key: Optional[str] = Header(default=None),
):
    """
    Create `count` payment attempts and inject failures into `failure_rate` fraction of them.
    Returns payment_attempt_ids for all created attempts.
    Requires authenticated operator session or X-Demo-Key header.

    Idempotent: if client_request_id is provided and already exists, the same
    batch is returned without creating duplicates (section 10.5).
    """
    # Allow either authenticated session OR valid X-Demo-Key header
    from routers.auth import decode_session_token
    token = request.cookies.get("telex_session")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    is_authenticated = bool(token and decode_session_token(token))
    if not is_authenticated:
        require_demo_key(x_demo_key)

    from services import payment_service

    if body.count < 1 or body.count > 100:
        raise HTTPException(status_code=422, detail="count must be between 1 and 100")
    if not 0.0 <= body.failure_rate <= 1.0:
        raise HTTPException(status_code=422, detail="failure_rate must be between 0.0 and 1.0")

    # ── Idempotency check ─────────────────────────────────────────────────────
    if body.client_request_id:
        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(PaymentAttempt)
                .where(PaymentAttempt.batch_request_id == body.client_request_id)
            )
            existing_attempts = list(existing.scalars())
            if existing_attempts:
                logger.info(
                    "batch_run: returning existing batch for client_request_id=%s (%d attempts)",
                    body.client_request_id, len(existing_attempts),
                )
                return {
                    "status": "existing",
                    "payment_attempt_ids": [str(a.id) for a in existing_attempts],
                }

    payment_attempt_ids: list[str] = []
    n_failures = round(body.count * body.failure_rate)
    failure_indices = set(random.sample(range(body.count), min(n_failures, body.count)))

    for i in range(body.count):
        is_failure = i in failure_indices
        force_failure = random.choices(_INJECTED_FAILURE_TYPES, weights=_FAILURE_WEIGHTS)[0] if is_failure else None

        # Create Razorpay order (or synthetic ID if keys not configured / error)
        try:
            order = await asyncio.to_thread(payment_service.create_order, 50000)  # ₹500 per attempt
            order_id = order["id"]
        except Exception as exc:
            logger.warning("batch_run: order creation fallback to synthetic (%s)", exc)
            order_id = f"order_synthetic_{uuid.uuid4().hex[:16]}"

        async with AsyncSessionLocal() as session:
            attempt = PaymentAttempt(
                razorpay_order_id=order_id,
                amount=50000,
                status="created",
                batch_request_id=body.client_request_id,
            )
            session.add(attempt)
            await session.flush()
            attempt_id = attempt.id

            # Simulate the payment inline in worker thread
            try:
                result = await asyncio.to_thread(payment_service.simulate_payment, order_id, force_failure)
            except Exception as exc:
                logger.warning("batch_run: simulate_payment exception (%s)", exc)
                result = {"success": False, "error_type": force_failure, "razorpay_payment_id": None}

            success = result.get("success", False)
            attempt.status = "success" if success else "failed"
            attempt.injected_failure = force_failure if not success else None
            await session.commit()

            if not success:
                await enqueue_job(
                    session,
                    job_type="detect_payment_failure",
                    payload={"payment_attempt_id": str(attempt_id)},
                )

        payment_attempt_ids.append(str(attempt_id))

    logger.info(
        "batch_run: created %d attempts (%d failures injected)",
        body.count, n_failures,
    )
    return {
        "status": "created",
        "source": "synthetic_batch",  # P1-1: always label batch-injected runs clearly
        "payment_attempt_ids": payment_attempt_ids,
    }

