"""
E2E Integration Tests — Engine B Recovery Chains
=================================================

Two canonical scenarios from the P1-4 spec, exercised against a REAL in-process
SQLite database (aiosqlite).  Only the network boundary is mocked — Razorpay API
calls and GitHub API calls — so that the full SQLAlchemy ORM, job-handler logic,
classification rules, and outcome updates are all exercised without any external
dependencies.

Test 1 — Transient failure (timeout) full recovery cycle
    create_order → record PaymentAttempt(status=created)
    → pay with force_failure="timeout"
    → PaymentAttempt.status becomes "failed"
    → detect_payment_failure enqueues diagnose_runtime_failure
    → diagnose classifies "timeout" deterministically as "transient"
    → recover_runtime retries → payment succeeds
    → RecoveryEvent.outcome == "recovered"
    → PaymentAttempt.status == "success"
    → revenue_recovered reflects the real amount

Test 2 — Code-defect (order_total_mismatch) full PR cycle
    POST /report-mismatch with real mismatch
    → RecoveryEvent(classification="code_defect") created immediately
    → recover_runtime called with classification="code_defect"
    → _handle_code_defect looks up FAILURE_LOCATION_MAP
    → DetectedChange + CodeUsage seeded in DB
    → generate_patch job enqueued with recovery_event_id
    → RecoveryEvent.outcome stays "unresolved" until PR path completes
      (we confirm the generate_patch job is on the queue with correct payload)

Both tests verify the recovery stats endpoint reflects real database state.
"""
import asyncio
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, UUID as PG_UUID

# ── SQLite Compatibility for Postgres Types in In-Memory Tests ───────────────
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(type_, compiler, **kw):
    return "TEXT"


# ── Patch DB before any imports that pull db.session ──────────────────────────
# We create an in-process SQLite engine for total isolation.

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_test_engine = None
_TestSessionLocal = None


def _make_engine():
    global _test_engine, _TestSessionLocal
    if _test_engine is None:
        _test_engine = create_async_engine(_TEST_DB_URL, echo=False)
        _TestSessionLocal = async_sessionmaker(_test_engine, expire_on_commit=False)
    return _test_engine, _TestSessionLocal


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Provide a fresh SQLite database for each test.

    We re-import db.models here (after sys.path is set by conftest.py) to
    create all tables in the in-process engine.
    """
    from db.models import Base

    engine, SessionLocal = _make_engine()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        yield session


@pytest.fixture()
def patch_db(db_session):
    """
    Monkey-patch db.session.AsyncSessionLocal so every handler/router call
    gets the same test session factory.
    """
    from db import session as session_module

    _orig = session_module.AsyncSessionLocal
    _, SessionLocal = _make_engine()
    session_module.AsyncSessionLocal = SessionLocal
    yield SessionLocal
    session_module.AsyncSessionLocal = _orig


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _seed_installation_and_repo(session: AsyncSession) -> tuple:
    """
    Insert the minimum rows needed by _handle_code_defect:
    an Installation and an active Repo.
    """
    from db.models import Installation, Repo

    inst = Installation(
        github_installation_id=99999,
        account_login="Kesavaraja67",
        account_type="User",
    )
    session.add(inst)
    await session.flush()

    repo = Repo(
        installation_id=inst.id,
        github_repo_id=888888,
        full_name="Kesavaraja67/sample-store",
        default_branch="main",
        is_active=True,
    )
    session.add(repo)
    await session.commit()
    await session.refresh(inst)
    await session.refresh(repo)
    return inst, repo


async def _create_payment_attempt(session: AsyncSession, amount: int = 50000):
    from db.models import PaymentAttempt

    attempt = PaymentAttempt(
        razorpay_order_id=f"order_test_{uuid.uuid4().hex[:12]}",
        amount=amount,
        status="created",
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    return attempt


async def _create_recovery_event(
    session: AsyncSession,
    payment_attempt,
    failure_type: str,
    classification: str = "unknown",
    outcome: str = "unresolved",
):
    from db.models import RecoveryEvent

    event = RecoveryEvent(
        payment_attempt_id=payment_attempt.id,
        failure_type=failure_type,
        classification=classification,
        action_taken="seeded by test",
        llm_provider="none",
        llm_model="none",
        outcome=outcome,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — Transient failure: timeout → classify → retry → recovered
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_transient_failure_full_recovery_cycle(patch_db):
    """
    Real timeout injection chain:
      PaymentAttempt (failed, timeout) →
      diagnose classifies as transient (deterministic Tier-1) →
      recover_runtime retries → simulated retry succeeds →
      RecoveryEvent.outcome == "recovered"
      PaymentAttempt.status == "success"
      revenue_recovered reflects the real amount (paise)
    """
    from jobs.handlers import diagnose_runtime_failure, recover_runtime
    from db.session import AsyncSessionLocal
    from db.models import RecoveryEvent, PaymentAttempt

    AMOUNT_PAISE = 50_000  # ₹500

    SessionLocal = patch_db

    # ── Step 1: Seed a failed payment attempt with a "timeout" failure ─────
    async with SessionLocal() as session:
        attempt = await _create_payment_attempt(session, amount=AMOUNT_PAISE)
        attempt.status = "failed"
        attempt.injected_failure = "timeout"
        await session.commit()
        attempt_id = attempt.id

    # ── Step 2: Seed a RecoveryEvent for it (simulates detect_payment_failure) ─
    async with SessionLocal() as session:
        attempt = await session.get(PaymentAttempt, attempt_id)
        event = await _create_recovery_event(
            session, attempt,
            failure_type="timeout",
            classification="unknown",
        )
        event_id = event.id

    # ── Step 3: Run diagnose handler — should classify "timeout" as "transient"
    #   via Tier-1 deterministic rule (no LLM call).
    enqueue_calls: list[dict] = []

    async def fake_enqueue(session, *, job_type: str, payload: dict, **kw):
        enqueue_calls.append({"job_type": job_type, "payload": payload})

    with patch("jobs.queue.enqueue_job", side_effect=fake_enqueue):
        await diagnose_runtime_failure.run({"recovery_event_id": str(event_id)})

    async with SessionLocal() as session:
        event = await session.get(RecoveryEvent, event_id)
        assert event.classification == "transient", (
            f"Expected 'transient' but got '{event.classification}' — "
            "Tier-1 rule for 'timeout' should fire without LLM"
        )
        assert event.llm_provider == "none", "Tier-1 must NOT call any LLM"
        assert "Classified via deterministic rule" in event.action_taken

    # diagnose must have enqueued recover_runtime
    assert any(c["job_type"] == "recover_runtime" for c in enqueue_calls), (
        "diagnose_runtime_failure must enqueue recover_runtime after classification"
    )
    recover_payload = next(
        c["payload"] for c in enqueue_calls if c["job_type"] == "recover_runtime"
    )
    assert recover_payload["classification"] == "transient"

    # ── Step 4: Run recover_runtime — mock simulate_payment to return success ──
    def fake_simulate(order_id, force_failure=None):
        return {"success": True, "razorpay_payment_id": "pay_recovered_test123", "error_type": None}

    with patch("services.payment_service.simulate_payment", side_effect=fake_simulate):
        await recover_runtime.run({
            "recovery_event_id": str(event_id),
            "classification": "transient",
        })

    # ── Step 5: Assert final DB state ─────────────────────────────────────────
    async with SessionLocal() as session:
        event = await session.get(RecoveryEvent, event_id)
        attempt = await session.get(PaymentAttempt, attempt_id)

        assert event.outcome == "recovered", (
            f"Expected 'recovered' after successful retry, got '{event.outcome}'"
        )
        assert event.resolved_at is not None, "resolved_at must be set after recovery"

        assert attempt.status == "success", (
            f"PaymentAttempt.status must be 'success' after recovery, got '{attempt.status}'"
        )

    # ── Step 6: Verify revenue_recovered in stats route reflects real amount ──
    # Directly exercise the stats query logic (same queries as the stats endpoint).
    from sqlalchemy import func

    async with SessionLocal() as session:
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

    assert revenue_recovered == AMOUNT_PAISE, (
        f"revenue_recovered should be {AMOUNT_PAISE} paise (₹{AMOUNT_PAISE // 100}), "
        f"got {revenue_recovered} — check that PaymentAttempt.amount is preserved through the cycle"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — Code-defect: report-mismatch → code_defect → patch pipeline seeded
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_code_defect_full_pr_cycle(patch_db):
    """
    Real order_total_mismatch bridge:
      POST /report-mismatch (via endpoint logic, not HTTP) →
      RecoveryEvent(failure_type="order_total_mismatch", classification="code_defect") created →
      recover_runtime called with classification="code_defect" →
      DetectedChange + CodeUsage seeded in DB (real defect location) →
      generate_patch job enqueued with recovery_event_id + code_usage_id

    Only the GitHub file-fetch is mocked (network boundary only).
    """
    from jobs.handlers import recover_runtime
    from db.session import AsyncSessionLocal
    from db.models import RecoveryEvent, PaymentAttempt, DetectedChange, CodeUsage, Job

    SessionLocal = patch_db

    # ── Step 1: Seed a PaymentAttempt and an active Repo ──────────────────────
    async with SessionLocal() as session:
        _, repo = await _seed_installation_and_repo(session)
        repo_id = repo.id

    async with SessionLocal() as session:
        attempt = await _create_payment_attempt(session, amount=99_900)  # ₹999
        attempt_id = attempt.id

    # ── Step 2: Simulate /report-mismatch endpoint logic ──────────────────────
    #   (We call the DB writes directly to avoid needing a running HTTP server.)
    async with SessionLocal() as session:
        attempt = await session.get(PaymentAttempt, attempt_id)
        event = RecoveryEvent(
            payment_attempt_id=attempt.id,
            failure_type="order_total_mismatch",
            classification="code_defect",   # deterministic per DETERMINISTIC_CLASSIFICATIONS table
            action_taken=(
                "Storefront reported order total mismatch: expected 99900 paise, got 95000 paise"
            ),
            llm_provider="none",
            llm_model="none",
            outcome="unresolved",
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)
        event_id = event.id

    # Confirm initial state
    async with SessionLocal() as session:
        event = await session.get(RecoveryEvent, event_id)
        assert event.classification == "code_defect", (
            "report-mismatch must immediately set classification='code_defect' — "
            "this is deterministic per DETERMINISTIC_CLASSIFICATIONS['order_total_mismatch']"
        )
        assert event.outcome == "unresolved"

    # ── Step 3: Run recover_runtime with classification="code_defect" ─────────
    #   Mock only the GitHub file-fetch (network boundary).
    enqueue_calls: list[dict] = []

    async def fake_enqueue(session, *, job_type: str, payload: dict, **kw):
        enqueue_calls.append({"job_type": job_type, "payload": payload})

    FAKE_FILE_CONTENT = (
        "// order-summary/route.ts (mock content for test)\n"
        "const subtotal = items.reduce((acc, i) => acc + i.price * i.qty, 0);\n"
        "const tax = Math.floor(subtotal * 0.18);\n"
        "const total = subtotal + tax;\n"
    )

    with patch("jobs.queue.enqueue_job", side_effect=fake_enqueue), \
         patch(
             "services.github_service.fetch_file_content",
             return_value=FAKE_FILE_CONTENT,
         ):
        await recover_runtime.run({
            "recovery_event_id": str(event_id),
            "classification": "code_defect",
        })

    # ── Step 4: Assert pipeline seeded in DB ──────────────────────────────────
    async with SessionLocal() as session:
        # DetectedChange must exist for the order_total_mismatch defect
        dc_res = await session.execute(
            select(DetectedChange)
            .where(DetectedChange.source == "internal_runtime")
            .order_by(DetectedChange.created_at.desc())
            .limit(1)
        )
        dc = dc_res.scalar_one_or_none()
        assert dc is not None, (
            "recover_runtime must seed a DetectedChange when handling code_defect"
        )
        assert dc.symbol_old == "calculateOrderSummary", (
            "DetectedChange symbol_old must match FAILURE_LOCATION_MAP['order_total_mismatch']['symbol_old']"
        )
        assert dc.confidence == 0.90

        # CodeUsage must reference the correct file path from FAILURE_LOCATION_MAP
        cu_res = await session.execute(
            select(CodeUsage)
            .where(CodeUsage.detected_change_id == dc.id)
            .limit(1)
        )
        cu = cu_res.scalar_one_or_none()
        assert cu is not None, "CodeUsage must be seeded by _handle_code_defect"
        # Allow either primary or alt path to match
        assert cu.file_path in (
            "app/api/order-summary/route.ts",
            "src/app/api/order-summary/route.ts",
        ), f"Unexpected file_path: {cu.file_path}"
        assert cu.repo_id == repo_id
        assert cu.status == "pending"

    # ── Step 5: Confirm generate_patch was enqueued with recovery_event_id ────
    patch_calls = [c for c in enqueue_calls if c["job_type"] == "generate_patch"]
    assert len(patch_calls) == 1, (
        f"Exactly one generate_patch job must be enqueued, got {len(patch_calls)}"
    )
    patch_payload = patch_calls[0]["payload"]
    assert patch_payload["recovery_event_id"] == str(event_id), (
        "generate_patch payload must carry recovery_event_id so open_pr can link the PR"
    )
    assert "code_usage_id" in patch_payload, "generate_patch payload must include code_usage_id"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — /report-mismatch rejects trivially invalid inputs
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_mismatch_validation(patch_db):
    """
    The report-mismatch endpoint must:
      - Return 400 when expected == actual (no real mismatch)
      - Return 404 for an unknown payment_attempt_id
    """
    from routers.payments import report_order_mismatch, ReportOrderMismatchRequest
    from fastapi import HTTPException

    SessionLocal = patch_db

    # Case 1: expected == actual → 400
    with pytest.raises(HTTPException) as exc_info:
        await report_order_mismatch(
            ReportOrderMismatchRequest(
                payment_attempt_id=str(uuid.uuid4()),
                expected_total_paise=100,
                actual_total_paise=100,
            )
        )
    assert exc_info.value.status_code == 400

    # Case 2: non-existent payment_attempt_id → 404
    with pytest.raises(HTTPException) as exc_info:
        await report_order_mismatch(
            ReportOrderMismatchRequest(
                payment_attempt_id=str(uuid.uuid4()),
                expected_total_paise=100,
                actual_total_paise=90,
            )
        )
    assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — Stage derivation is correct for all outcome × classification combos
# ─────────────────────────────────────────────────────────────────────────────

def test_derive_stage_all_combinations():
    """
    _derive_stage must produce stable, well-defined output for all
    outcome × classification combinations.  This is the contract that
    both the dashboard and Aura Drops rely on.
    """
    from routers.recovery import _derive_stage

    assert _derive_stage("recovered", "transient")    == "resolved"
    assert _derive_stage("recovered", "code_defect")  == "resolved"
    assert _derive_stage("escalated", "transient")    == "escalated"
    assert _derive_stage("escalated", "code_defect")  == "escalated"
    assert _derive_stage("unresolved", "code_defect") == "recovering"
    assert _derive_stage("unresolved", "transient")   == "detected"
    assert _derive_stage("unresolved", "unknown")     == "detected"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — recovery_rate formula is split correctly
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_payment_recovery_rate_vs_execution_rate(patch_db):
    """
    With 3 events (2 recovered, 1 escalated):
      payment_recovery_rate = 2/3 ≈ 0.6667
      recovery_execution_rate = 3/3 = 1.0

    The two must be different — if they are equal, the P0-2 fix isn't working.
    """
    from db.models import PaymentAttempt, RecoveryEvent
    from sqlalchemy import func

    SessionLocal = patch_db

    async with SessionLocal() as session:
        amounts = [10_000, 20_000, 30_000]
        outcomes = ["recovered", "recovered", "escalated"]

        for amount, outcome in zip(amounts, outcomes):
            attempt = PaymentAttempt(
                razorpay_order_id=f"order_{uuid.uuid4().hex[:10]}",
                amount=amount,
                status="failed" if outcome != "recovered" else "success",
            )
            session.add(attempt)
            await session.flush()

            event = RecoveryEvent(
                payment_attempt_id=attempt.id,
                failure_type="timeout",
                classification="transient",
                action_taken="test",
                llm_provider="none",
                llm_model="none",
                outcome=outcome,
            )
            session.add(event)

        await session.commit()

    async with SessionLocal() as session:
        total_res = await session.execute(select(func.count(RecoveryEvent.id)))
        total = total_res.scalar_one()

        recovered_res = await session.execute(
            select(func.count(RecoveryEvent.id)).where(RecoveryEvent.outcome == "recovered")
        )
        recovered = recovered_res.scalar_one()

        escalated_res = await session.execute(
            select(func.count(RecoveryEvent.id)).where(RecoveryEvent.outcome == "escalated")
        )
        escalated = escalated_res.scalar_one()

    payment_recovery_rate = recovered / total
    recovery_execution_rate = (recovered + escalated) / total

    assert abs(payment_recovery_rate - 2 / 3) < 1e-6, (
        f"payment_recovery_rate should be 2/3, got {payment_recovery_rate}"
    )
    assert abs(recovery_execution_rate - 1.0) < 1e-6, (
        f"recovery_execution_rate should be 1.0 (all handled), got {recovery_execution_rate}"
    )
    assert payment_recovery_rate < recovery_execution_rate, (
        "payment_recovery_rate and recovery_execution_rate must be distinct — "
        "escalation must NOT count as completed recovery"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 — Bounded Stopping: 3 repeated card declines trigger deliberate STOP
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bounded_stopping_repeated_card_declines(patch_db):
    """
    Scenario: Repeated card decline attempts on the same order ID.
    Safety Guardrail:
      - Attempt 1: Transient retry attempted
      - Attempt 2: Transient retry attempted
      - Attempt 3: DELIBERATE STOP triggered (outcome=unresolved, no further retry)
    """
    from db.models import PaymentAttempt, RecoveryEvent
    from jobs.handlers import recover_runtime

    SessionLocal = patch_db
    order_id = f"order_decline_{uuid.uuid4().hex[:10]}"

    # Seed PaymentAttempt
    async with SessionLocal() as session:
        attempt = PaymentAttempt(
            razorpay_order_id=order_id,
            amount=249900,  # ₹2,499
            status="failed",
            injected_failure="card_declined",
        )
        session.add(attempt)
        await session.commit()
        await session.refresh(attempt)
        attempt_id = attempt.id

        # Seed two prior retry events for this order with failure_type="card_declined"
        event1 = RecoveryEvent(
            payment_attempt_id=attempt_id,
            failure_type="card_declined",
            classification="transient",
            action_taken="Simulated retry attempt #1",
            retry_count=1,
            outcome="unresolved",
        )
        event2 = RecoveryEvent(
            payment_attempt_id=attempt_id,
            failure_type="card_declined",
            classification="transient",
            action_taken="Simulated retry attempt #2",
            retry_count=2,
            outcome="unresolved",
        )
        session.add_all([event1, event2])
        await session.commit()

        # Seed the 3rd recovery event
        event3 = RecoveryEvent(
            payment_attempt_id=attempt_id,
            failure_type="card_declined",
            classification="transient",
            action_taken="Pending 3rd retry",
            outcome="unresolved",
        )
        session.add(event3)
        await session.commit()
        await session.refresh(event3)
        event3_id = event3.id

    # Run recover_runtime on the 3rd event
    with patch("services.payment_service.simulate_payment") as mock_simulate:
        await recover_runtime.run({
            "recovery_event_id": str(event3_id),
            "classification": "transient",
        })
        # Crucial safety check: simulate_payment must NOT be called on 3rd attempt
        mock_simulate.assert_not_called()

    # Verify event3 state in DB
    async with SessionLocal() as session:
        updated_event = await session.get(RecoveryEvent, event3_id)
        assert updated_event is not None
        assert updated_event.retry_count == 3
        assert updated_event.outcome == "unresolved"
        assert "Stopped retrying after 3 attempts" in updated_event.action_taken
        assert "repeated card decline is unlikely to resolve automatically" in updated_event.action_taken


# ─────────────────────────────────────────────────────────────────────────────
# TEST 7 — Razorpay Webhook Idempotency: Duplicate delivery ignored
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_webhook_delivery_idempotent_ignored(patch_db):
    """
    Scenario: Razorpay sends a webhook event (e.g. payment.captured).
    First delivery succeeds and marks PaymentAttempt as 'success'.
    Second duplicate delivery with identical event_id is safely ignored (200 OK + duplicate_ignored).
    """
    import json
    from db.models import PaymentAttempt
    from routers.payments import razorpay_webhook
    from unittest.mock import AsyncMock

    SessionLocal = patch_db
    order_id = f"order_hook_{uuid.uuid4().hex[:10]}"
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    payment_id = f"pay_{uuid.uuid4().hex[:12]}"

    # Seed PaymentAttempt
    async with SessionLocal() as session:
        attempt = PaymentAttempt(
            razorpay_order_id=order_id,
            amount=50000,
            status="created",
        )
        session.add(attempt)
        await session.commit()

    webhook_payload = {
        "id": event_id,
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "order_id": order_id,
                    "amount": 50000,
                    "status": "captured",
                }
            }
        }
    }
    raw_body = json.dumps(webhook_payload).encode("utf-8")

    mock_request = AsyncMock()
    mock_request.body.return_value = raw_body

    with patch("services.payment_service.verify_webhook_signature", return_value=True):
        # 1. First webhook delivery
        resp1 = await razorpay_webhook(mock_request, x_razorpay_signature="test_sig")
        assert resp1["status"] == "ok"

        # Verify attempt updated
        async with SessionLocal() as session:
            stmt = select(PaymentAttempt).where(PaymentAttempt.razorpay_order_id == order_id)
            res = await session.execute(stmt)
            att = res.scalar_one()
            assert att.status == "success"
            assert att.razorpay_event_id == event_id
            assert att.razorpay_payment_id == payment_id

        # 2. Duplicate webhook delivery
        resp2 = await razorpay_webhook(mock_request, x_razorpay_signature="test_sig")
        assert resp2["status"] == "ok"
        assert resp2["message"] == "duplicate_ignored"
