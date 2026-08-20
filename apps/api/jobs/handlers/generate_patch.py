"""
generate_patch handler — calls the active LLM provider to generate a unified
diff for a single code_usage, then stores the result and a validation_run.

Payload shape:
    { "code_usage_id": "<uuid>" }
"""
import logging
import uuid

logger = logging.getLogger(__name__)


async def run(payload: dict) -> None:
    from db.session import AsyncSessionLocal
    from db.models import CodeUsage, DetectedChange, PackageVersion, Patch, ValidationRun
    from services.patch_providers import get_patch_provider
    from sqlalchemy import select

    code_usage_id = uuid.UUID(payload["code_usage_id"])

    # ── Phase 1: read required scalars, then release the DB connection ────────
    async with AsyncSessionLocal() as session:
        cu = await session.get(CodeUsage, code_usage_id)
        if cu is None:
            logger.error("generate_patch: CodeUsage %s not found", code_usage_id)
            return
        if cu.status != "pending":
            logger.info("generate_patch: usage %s already %s — skipping", code_usage_id, cu.status)
            return

        dc = await session.get(DetectedChange, cu.detected_change_id)
        if dc is None:
            logger.error("generate_patch: DetectedChange %s not found", cu.detected_change_id)
            return

        pv = await session.get(PackageVersion, dc.package_version_id)
        if pv is None:
            logger.error("generate_patch: PackageVersion %s not found", dc.package_version_id)
            return

        # Copy scalars so we don't hold the connection across the LLM call
        old_api = dc.symbol_old
        new_api = dc.symbol_new or ""
        code_snippet = cu.snippet
        context = f"File: {cu.file_path}\nLines {cu.line_start}–{cu.line_end}"

    # ── Phase 2: call provider (no DB connection held) ────────────────────────
    provider = get_patch_provider()
    diff = await provider.generate_patch(
        old_api=old_api,
        new_api=new_api,
        code_snippet=code_snippet,
        context=context,
    )

    # ── Phase 3: write results in a short transaction ─────────────────────────
    async with AsyncSessionLocal() as session:
        cu = await session.get(CodeUsage, code_usage_id)
        if cu is None:
            return  # deleted between phases — nothing to update

        if diff == "UNABLE_TO_PATCH":
            cu.status = "failed"
            await session.commit()
            logger.warning("generate_patch: provider returned UNABLE_TO_PATCH for usage %s", code_usage_id)
            return

        from config import settings
        provider_name = settings.llm_provider_default
        model_name = "gemini-2.0-flash" if provider_name == "gemini" else "claude-sonnet-4-5"

        patch = Patch(
            code_usage_id=code_usage_id,
            diff=diff,
            llm_provider=provider_name,
            llm_model=model_name,
            prompt_version="v1",
            verified=False,  # remains False until Phase 2 validation (parse, scope, apply) passes
        )
        session.add(patch)
        await session.flush()

        # Record a validation run — heuristic checks only; real validation in Phase 2
        applies_heuristic = len(diff) > 10 and ("---" in diff or "@@" in diff)
        vr = ValidationRun(
            patch_id=patch.id,
            applies_cleanly=applies_heuristic,
            parses=None,      # Phase 2: real parser check
            typechecks=None,  # Phase 2
            tests_pass=None,  # Phase 2
            scope_ok=None,    # Phase 2
        )
        session.add(vr)

        # Mark usage as "patched" (pending review) even though patch is not yet verified.
        # verified=True will be set in Phase 2 when all checks pass.
        if applies_heuristic:
            cu.status = "patched"
        else:
            cu.status = "failed"

        await session.commit()

    logger.info(
        "generate_patch: %s for usage %s (heuristic_ok=%s, verified=False)",
        provider_name,
        code_usage_id,
        applies_heuristic,
    )

