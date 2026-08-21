"""
diagnose_runtime_failure handler — Engine B two-tier classifier.

Payload shape:
    { "recovery_event_id": "<uuid>" }

DESIGN: Two-tier classifier — not LLM-for-everything.

Tier 1 — Deterministic lookup (no LLM call, no cost, no latency).
  Most failures have an unambiguous known cause. For these, we classify
  instantly from a rule table. llm_provider is set to "none" to make this
  visible in the dashboard.

  WHY THIS MATTERS: Using an LLM to classify a plain timeout is AI-for-AI-s-sake
  — a lookup table already solves it deterministically, cheaply, and with zero
  hallucination risk. Reserving the LLM for cases the rule table cannot resolve
  is the actual demonstration of "the right tool in the right place."

Tier 2 — LLM call, reserved for genuinely ambiguous cases only.
  If failure_type is not in the deterministic table, we call the active
  LLM provider via the same get_patch_provider() abstraction Engine A uses.
  The prompt explicitly tells the model this case was not resolvable by the
  rule table, making the LLM reasoning sharper.
"""
import logging
import uuid

logger = logging.getLogger(__name__)

# ── Tier 1: deterministic rule table ─────────────────────────────────────────
# Failure types with known, unambiguous causes — no LLM needed.
# The dashboard's RULE vs LLM label is derived from action_taken prefixes.
DETERMINISTIC_CLASSIFICATIONS: dict[str, str] = {
    "timeout":                    "transient",
    "rate_limit":                 "transient",
    "db_unavailable":             "transient",
    "network_error":              "transient",
    "payment_failed":             "transient",
    "card_declined":              "transient",
    "webhook_signature_mismatch": "code_defect",
    "webhook_schema_mismatch":    "code_defect",
}

_RULE_ACTION_PREFIX = "Classified via deterministic rule (no LLM call — failure type has a known, unambiguous cause)"
_LLM_ACTION_PREFIX = "Classified via LLM: "


async def run(payload: dict) -> None:
    from db.session import AsyncSessionLocal
    from db.models import RecoveryEvent
    from jobs.queue import enqueue_job
    from services.patch_providers import get_patch_provider
    from config import settings

    recovery_event_id = uuid.UUID(payload["recovery_event_id"])

    # ── Phase 1: read failure_type ────────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        event = await session.get(RecoveryEvent, recovery_event_id)
        if event is None:
            logger.error("diagnose_runtime_failure: RecoveryEvent %s not found", recovery_event_id)
            return

        failure_type = event.failure_type

    # ── Phase 2: classify (outside session — LLM call may be slow) ───────────
    if failure_type in DETERMINISTIC_CLASSIFICATIONS:
        # ── Tier 1: deterministic ─────────────────────────────────────────────
        classification = DETERMINISTIC_CLASSIFICATIONS[failure_type]
        action_taken = f"{_RULE_ACTION_PREFIX}: {failure_type} → {classification}"
        llm_provider = "none"
        llm_model = "none"
        logger.info(
            "diagnose_runtime_failure: Tier 1 — %s classified as %s (no LLM)",
            failure_type, classification,
        )
    else:
        # ── Tier 2: LLM for genuinely ambiguous cases ─────────────────────────
        provider = get_patch_provider()
        error_context = (
            f"A payment transaction failed with failure_type='{failure_type}'. "
            f"This type was not in the deterministic rule table, so LLM judgment is required."
        )
        result = await provider.classify_failure(
            failure_type=failure_type,
            error_context=error_context,
        )
        classification = result["classification"]
        reasoning = result.get("reasoning", "")
        action_taken = f"{_LLM_ACTION_PREFIX}{reasoning}"
        llm_provider = settings.llm_provider_default
        llm_model = provider.model_name
        logger.info(
            "diagnose_runtime_failure: Tier 2 — %s classified as %s via LLM (%s)",
            failure_type, classification, llm_model,
        )

    # ── Phase 3: write classification result and enqueue recovery ─────────────
    async with AsyncSessionLocal() as session:
        event = await session.get(RecoveryEvent, recovery_event_id)
        if event is None:
            logger.error(
                "diagnose_runtime_failure: RecoveryEvent %s disappeared before write",
                recovery_event_id,
            )
            return
        event.classification = classification
        event.action_taken = action_taken
        event.llm_provider = llm_provider
        event.llm_model = llm_model

        await enqueue_job(
            session,
            job_type="recover_runtime",
            payload={
                "recovery_event_id": str(recovery_event_id),
                "classification": classification,
            },
        )
        await session.commit()

    logger.info(
        "diagnose_runtime_failure: classified %s → %s (tier=%s)",
        failure_type, classification,
        "deterministic" if llm_provider == "none" else "llm",
    )

