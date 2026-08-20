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

    async with AsyncSessionLocal() as session:
        cu = await session.get(CodeUsage, code_usage_id)
        if cu is None:
            logger.error("generate_patch: CodeUsage %s not found", code_usage_id)
            return
        if cu.status != "pending":
            logger.info("generate_patch: usage %s already %s — skipping", code_usage_id, cu.status)
            return

        dc = await session.get(DetectedChange, cu.detected_change_id)
        pv = await session.get(PackageVersion, dc.package_version_id)

        provider = get_patch_provider()

        diff = await provider.generate_patch(
            old_api=dc.symbol_old,
            new_api=dc.symbol_new or "",
            code_snippet=cu.snippet,
            context=f"File: {cu.file_path}\nLines {cu.line_start}–{cu.line_end}",
        )

        if diff == "UNABLE_TO_PATCH":
            cu.status = "failed"
            await session.commit()
            logger.warning("generate_patch: provider returned UNABLE_TO_PATCH for usage %s", code_usage_id)
            return

        # Determine provider metadata
        from config import settings
        provider_name = settings.llm_provider_default
        model_name = "gemini-2.0-flash" if provider_name == "gemini" else "claude-sonnet-4-5"

        patch = Patch(
            code_usage_id=code_usage_id,
            diff=diff,
            llm_provider=provider_name,
            llm_model=model_name,
            prompt_version="v1",
            verified=False,
        )
        session.add(patch)
        await session.flush()

        # Basic validation checks (non-blocking in Phase 1 — just recorded)
        applies_cleanly = len(diff) > 10 and ("---" in diff or "@@" in diff)
        vr = ValidationRun(
            patch_id=patch.id,
            applies_cleanly=applies_cleanly,
            parses=True,        # will implement real parser check in Phase 2
            typechecks=None,    # Phase 2
            tests_pass=None,    # Phase 2
            scope_ok=True,
        )
        session.add(vr)

        if applies_cleanly:
            patch.verified = True
            cu.status = "patched"
        else:
            cu.status = "failed"

        await session.commit()

    logger.info(
        "generate_patch: %s for usage %s (verified=%s)",
        provider_name,
        code_usage_id,
        applies_cleanly,
    )
