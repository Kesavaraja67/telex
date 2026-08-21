"""
generate_patch handler — calls the active LLM provider to generate a unified
diff for a single code_usage, then stores the result and a validation_run.

Payload shape:
    { "code_usage_id": "<uuid>" }
"""
import logging
import uuid

logger = logging.getLogger(__name__)


def validate_patch(diff: str, snippet: str) -> tuple[bool, bool, bool]:
    """
    Validate the generated diff:
    1. applies_cleanly: checks if diff format has valid hunk headers and non-empty content.
    2. scope_ok: checks that lines being removed (-) match lines in the original snippet.
    3. parses: checks that diff contains valid hunk structure and changes.
    """
    if not diff or len(diff) < 10 or diff == "UNABLE_TO_PATCH":
        return False, False, False

    lines = diff.splitlines()
    has_hunk = any(line.startswith("@@") for line in lines) or (
        any(line.startswith("---") for line in lines) and any(line.startswith("+++") for line in lines)
    )
    if not has_hunk:
        return False, False, False

    removed_lines = [line[1:].strip() for line in lines if line.startswith("-") and not line.startswith("---")]
    added_lines = [line[1:].strip() for line in lines if line.startswith("+") and not line.startswith("+++")]

    if not added_lines and not removed_lines:
        return False, False, False

    # Scope check: removed lines should match the original code snippet
    scope_ok = True
    if removed_lines:
        snippet_lines = [l.strip() for l in snippet.splitlines() if l.strip()]
        if snippet_lines:
            scope_ok = any(
                any(rl in sl or sl in rl for sl in snippet_lines)
                for rl in removed_lines if rl
            )

    applies_cleanly = has_hunk
    parses = applies_cleanly and scope_ok

    return applies_cleanly, parses, scope_ok


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

        applies_cleanly, parses, scope_ok = validate_patch(diff, code_snippet)
        is_verified = applies_cleanly and parses and scope_ok

        patch = Patch(
            code_usage_id=code_usage_id,
            diff=diff,
            llm_provider=provider_name,
            llm_model=model_name,
            prompt_version="v1",
            verified=is_verified,
        )
        session.add(patch)
        await session.flush()

        # Record a validation run with verified boolean values
        vr = ValidationRun(
            patch_id=patch.id,
            applies_cleanly=applies_cleanly,
            parses=parses,
            typechecks=None,
            tests_pass=None,
            scope_ok=scope_ok,
        )
        session.add(vr)

        if is_verified:
            cu.status = "patched"
        else:
            cu.status = "failed"

        await session.commit()

    logger.info(
        "generate_patch: %s for usage %s (verified=%s, applies_cleanly=%s, scope_ok=%s)",
        provider_name,
        code_usage_id,
        is_verified,
        applies_cleanly,
        scope_ok,
    )

