"""
generate_patch handler — calls the active LLM provider to generate a unified
diff for a single code_usage, verifies it in an isolated shallow clone, and
stores the result with a real validation_run.

Payload shape:
    { "code_usage_id": "<uuid>" }
"""

import asyncio
import logging
import os
import stat
import uuid

logger = logging.getLogger(__name__)


def _remove_readonly(func, path, _):
    """Clear readonly bit on Windows when removing temp git repo."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def validate_patch(diff: str, snippet: str) -> tuple[bool, bool, bool]:
    """
    Validate the generated diff structurally:
    1. applies_cleanly: checks if diff format has valid hunk headers and non-empty content.
    2. scope_ok: checks that lines being removed (-) match lines in the original snippet.
    3. parses: checks that diff contains valid hunk structure and changes.
    """
    if not diff or len(diff) < 10 or diff == "UNABLE_TO_PATCH":
        return False, False, False

    lines = diff.splitlines()
    has_hunk = any(line.startswith("@@") for line in lines) or (
        any(line.startswith("---") for line in lines)
        and any(line.startswith("+++") for line in lines)
    )
    if not has_hunk:
        return False, False, False

    removed_lines = [
        line[1:].strip() for line in lines if line.startswith("-") and not line.startswith("---")
    ]
    added_lines = [
        line[1:].strip() for line in lines if line.startswith("+") and not line.startswith("+++")
    ]

    if not added_lines and not removed_lines:
        return False, False, False

    # Scope check: removed lines should match the original code snippet
    scope_ok = True
    if removed_lines:
        snippet_lines = [s_line.strip() for s_line in snippet.splitlines() if s_line.strip()]
        if snippet_lines:
            scope_ok = any(
                any(rl in sl or sl in rl for sl in snippet_lines) for rl in removed_lines if rl
            )

    applies_cleanly = has_hunk
    parses = applies_cleanly and scope_ok

    return applies_cleanly, parses, scope_ok


async def verify_patch_via_github(
    repo_full_name: str,
    default_branch: str,
    installation_github_id: int | None,
    diff: str,
    code_snippet: str,
    file_path: str = "src/index.ts",
    requires_tests: bool = False,
    requires_typecheck: bool = False,
    allow_install_scripts: bool = False,
) -> dict:
    """
    Execute the Verification Gate using Dynamic GitHub Actions (Zero-Memory on Render):
    1. Structural check (applies_cleanly, parses, scope_ok).
    2. Micro git apply check on single file (< 2 MB RAM, ~10ms).
    3. Detect repository ecosystem and generate dynamic verification workflow.
    4. Create temporary verification branch telex/verify/<id> on GitHub.
    5. Commit candidate patch AND dynamic .github/workflows/telex-verify-<id>.yml atomically.
    6. GitHub Actions triggers native npm ci / tsc / npm test on GitHub's 7GB runners.
    7. Poll and verify ONLY the Telex verification gate check runs.
    8. Return strictly verified result and logs.
    """
    from services.github_service import (
        apply_diff_to_content,
        commit_verification_bundle,
        create_or_update_branch,
        delete_branch,
        detect_repo_environment,
        fetch_file_content,
        generate_telex_verification_workflow,
        wait_for_telex_verification,
    )

    # 1. Structural checks
    applies_cleanly, parses, scope_ok = validate_patch(diff, code_snippet)
    if not (applies_cleanly and parses and scope_ok):
        return {
            "applies_cleanly": applies_cleanly,
            "parses": parses,
            "scope_ok": scope_ok,
            "typechecks": None,
            "tests_pass": None,
            "verification_mode": "structural_only",
            "is_verified": False,
            "log": "Structural check failed: diff does not parse or is out of scope.",
        }

    # If no installation token is configured, cannot perform full verification
    if not installation_github_id or not repo_full_name:
        return {
            "applies_cleanly": applies_cleanly,
            "parses": parses,
            "scope_ok": scope_ok,
            "typechecks": None,
            "tests_pass": None,
            "verification_mode": "structural_only",
            "is_verified": False,
            "log": "No GitHub App installation token available — cannot perform full verification.",
        }

    try:
        # 2. Fetch original file and apply diff locally in micro temp dir (~2 MB RAM)
        original_content = await asyncio.to_thread(
            fetch_file_content, repo_full_name, installation_github_id, file_path, default_branch
        )
        if not original_content:
            original_content = code_snippet

        apply_ok, new_content, apply_log = apply_diff_to_content(file_path, original_content, diff)
        if not apply_ok:
            logger.warning("verify_patch_via_github: micro git apply failed: %s", apply_log)
            return {
                "applies_cleanly": False,
                "parses": parses,
                "scope_ok": scope_ok,
                "typechecks": None,
                "tests_pass": None,
                "verification_mode": "git_apply_failed",
                "is_verified": False,
                "log": f"git apply failed: {apply_log}",
            }

        # 3. Detect repository ecosystem and generate dynamic verification workflow
        env_info = await asyncio.to_thread(
            detect_repo_environment,
            repo_full_name,
            installation_github_id,
            default_branch,
            allow_install_scripts,
        )
        workflow_id = uuid.uuid4().hex[:8]
        verify_branch = f"telex/verify/{workflow_id}"
        workflow_name = f"Telex Verification {workflow_id}"
        workflow_file_path = f".github/workflows/telex-verify-{workflow_id}.yml"

        workflow_yaml = generate_telex_verification_workflow(
            env_info=env_info,
            branch_name=verify_branch,
            workflow_name=workflow_name,
        )

        # 4. Create isolated verification branch on GitHub
        logger.info(
            "verify_patch_via_github: creating verification branch %s on %s",
            verify_branch,
            repo_full_name,
        )
        base_sha = await asyncio.to_thread(
            create_or_update_branch,
            repo_full_name,
            installation_github_id,
            verify_branch,
            default_branch,
        )

        if not base_sha:
            return {
                "applies_cleanly": True,
                "parses": True,
                "scope_ok": scope_ok,
                "typechecks": False,
                "tests_pass": False,
                "verification_mode": "error",
                "is_verified": False,
                "log": "Verification branch creation on GitHub failed.",
            }

        # 5. Commit BOTH the patched file and dynamic workflow atomically to verification branch
        commit_sha = await asyncio.to_thread(
            commit_verification_bundle,
            repo_full_name=repo_full_name,
            installation_id=installation_github_id,
            branch_name=verify_branch,
            patched_file_path=file_path,
            patched_content=new_content,
            workflow_file_path=workflow_file_path,
            workflow_content=workflow_yaml,
        )

        if not commit_sha:
            return {
                "applies_cleanly": True,
                "parses": True,
                "scope_ok": scope_ok,
                "typechecks": False,
                "tests_pass": False,
                "verification_mode": "error",
                "is_verified": False,
                "log": "Failed to commit candidate patch and dynamic verification workflow to GitHub.",
            }

        # 6. Poll GitHub Actions verification gate
        ci_result = await wait_for_telex_verification(
            repo_full_name=repo_full_name,
            installation_id=installation_github_id,
            commit_sha=commit_sha,
            expected_workflow_name=workflow_name,
            timeout_seconds=180.0,
        )

        # Clean up temporary verification branch on GitHub asynchronously
        asyncio.create_task(
            asyncio.to_thread(delete_branch, repo_full_name, installation_github_id, verify_branch)
        )

        # 7. Interpret results strictly
        if ci_result["workflow_found"] and ci_result["completed"]:
            verification_mode = "github_actions"
            typechecks = ci_result["typechecks"]
            tests_pass = ci_result["tests_pass"]
            all_passed = ci_result["conclusion"] == "success"

            tests_ok = (
                (tests_pass is True)
                if (requires_tests or env_info.get("has_test"))
                else (tests_pass in (True, None))
            )
            typecheck_ok = (
                (typechecks is True)
                if (requires_typecheck or env_info.get("has_typecheck"))
                else (typechecks in (True, None))
            )

            is_verified = (
                all_passed and applies_cleanly and parses and scope_ok and tests_ok and typecheck_ok
            )
            return {
                "applies_cleanly": True,
                "parses": parses,
                "scope_ok": scope_ok,
                "typechecks": typechecks,
                "tests_pass": tests_pass,
                "verification_mode": verification_mode,
                "is_verified": is_verified,
                "log": f"Dynamic GitHub Actions Verification: {ci_result['conclusion']}\n{ci_result['log']}",
            }
        else:
            return {
                "applies_cleanly": True,
                "parses": parses,
                "scope_ok": scope_ok,
                "typechecks": False,
                "tests_pass": False,
                "verification_mode": "github_actions_unresponsive",
                "is_verified": False,
                "log": f"Verification failed: GitHub Actions workflow did not complete successfully ({ci_result.get('log', 'unresponsive')}).",
            }
    except Exception as exc:
        logger.exception("verify_patch_via_github error: %s", exc)
        return {
            "applies_cleanly": False,
            "parses": parses,
            "scope_ok": scope_ok,
            "typechecks": False,
            "tests_pass": False,
            "verification_mode": "error",
            "is_verified": False,
            "log": f"Verification error: {exc}",
        }


# Backwards-compatible alias
verify_patch_in_clone = verify_patch_via_github


async def run(payload: dict) -> None:

    from config import settings
    from db.models import (
        CodeUsage,
        DetectedChange,
        PackageVersion,
        Patch,
    )
    from db.session import AsyncSessionLocal
    from services.patch_providers import get_patch_provider, get_patch_provider_for_user

    code_usage_id = uuid.UUID(payload["code_usage_id"])
    # user_id is optional — present when the job was triggered by an authenticated user
    # (i.e. a BYOK-aware workflow). Falls back to platform-hosted provider when absent.
    job_user_id: str | None = payload.get("user_id")
    # preferred_provider from payload overrides settings default (allows per-user provider choice)
    preferred_provider: str | None = payload.get("preferred_provider")

    # ── Phase 1: read required scalars and repo details ────────────────────────
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

        # Skip PackageVersion check if dc.package_version_id is None (Engine B internal runtime changes)
        if dc.package_version_id is not None:
            pv = await session.get(PackageVersion, dc.package_version_id)
            if pv is None:
                logger.error("generate_patch: PackageVersion %s not found", dc.package_version_id)
                return

        old_api = dc.symbol_old or ""
        new_api = dc.symbol_new or ""
        defect_description = dc.description or ""
        code_snippet = cu.snippet or ""
        file_path = cu.file_path
        context = f"File: {cu.file_path}\nLines {cu.line_start}–{cu.line_end}"
        observed_evidence = ""

    # ── Phase 2: call provider for Best-of-N candidate diffs (Section 5.2) ────
    # Phase 7: use BYOK-aware factory when a user_id is present in the payload.
    # get_patch_provider_for_user() decrypts the stored key and updates last_used_at.
    # Falls back to platform-hosted Gemini for users without a stored key.
    if job_user_id:
        provider = await get_patch_provider_for_user(
            user_id=job_user_id,
            preferred_provider=preferred_provider,
        )
    else:
        provider = get_patch_provider(preferred_provider)
    provider_name = getattr(
        provider, "model_name", preferred_provider or settings.llm_provider_default
    )
    model_name = provider.model_name

    # Request candidate diffs
    candidates = []
    if hasattr(provider, "generate_patch_candidates"):
        try:
            cand_res = await provider.generate_patch_candidates(
                old_api=old_api,
                new_api=new_api,
                code_snippet=code_snippet,
                context=context,
                defect_description=defect_description,
                observed_evidence=observed_evidence,
                n=3,
            )
            if isinstance(cand_res, list) and cand_res:
                candidates = cand_res
        except (NotImplementedError, TypeError) as exc:
            logger.debug("Provider generate_patch_candidates not usable: %s", exc)

    if not candidates:
        single_diff = await provider.generate_patch(
            old_api=old_api,
            new_api=new_api,
            code_snippet=code_snippet,
            context=context,
            defect_description=defect_description,
            observed_evidence=observed_evidence,
        )
        candidates = [single_diff]

    # Cheap checks filter + real micro-apply verification
    # Picks the "best" surviving candidate:
    # 1. Must pass structural checks (valid hunk format, parseable, scope_ok)
    # 2. Must apply cleanly to the actual code content via micro git apply
    # 3. Heuristic: Smallest diff (fewest modified lines)
    from services.github_service import apply_diff_to_content

    valid_candidates = []
    for cand in candidates:
        if cand and cand != "UNABLE_TO_PATCH":
            applies_struct, parses, scope_ok = validate_patch(cand, code_snippet)
            if applies_struct and parses and scope_ok:
                apply_ok, _, apply_log = apply_diff_to_content(file_path, code_snippet, cand)
                if apply_ok:
                    diff_lines = [
                        line
                        for line in cand.splitlines()
                        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
                    ]
                    score = len(diff_lines)
                    valid_candidates.append((score, cand))
                else:
                    logger.debug("Candidate rejected by real git apply: %s", apply_log)

    if valid_candidates:
        valid_candidates.sort(key=lambda x: x[0])
        diff = valid_candidates[0][1]
        logger.info(
            "generate_patch: Best-of-N selected candidate with %d modified lines out of %d passing candidates",
            valid_candidates[0][0],
            len(valid_candidates),
        )
    else:
        diff = "UNABLE_TO_PATCH"
        logger.warning(
            "generate_patch: all %d candidate diffs failed cheap checks", len(candidates)
        )

    # ── Phase 3: write results in transaction and hand off to validate_patch ──
    async with AsyncSessionLocal() as session:
        cu = await session.get(CodeUsage, code_usage_id)
        if cu is None:
            return

        if diff == "UNABLE_TO_PATCH":
            cu.status = "failed"
            # Record patch_failed before commit so it rides the same transaction
            from services.incident_events import record_event
            await record_event(
                session,
                event_type="patch_failed",
                code_usage_id=code_usage_id,
                payload={
                    "reason": "all_candidates_rejected",
                    "candidates_tried": len(candidates),
                },
            )
            await session.commit()
            # Publish after commit — non-fatal if bus is unavailable
            try:
                from services.event_bus import event_bus
                await event_bus.publish({
                    "event_type": "patch_failed",
                    "code_usage_id": str(code_usage_id),
                    "reason": "all_candidates_rejected",
                    "candidates_tried": len(candidates),
                })
            except Exception as exc:
                logger.warning("event_bus publish patch_failed failed (non-fatal): %s", exc)
            logger.warning(
                "generate_patch: provider returned UNABLE_TO_PATCH for usage %s", code_usage_id
            )
            return

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

        from jobs.queue import enqueue_job

        # Propagate user_id and installation_id through the job chain so downstream
        # handlers (validate_patch, open_pr) can apply fairness caps and BYOK.
        validate_payload: dict = {"patch_id": str(patch.id)}
        if job_user_id:
            validate_payload["user_id"] = job_user_id
        if payload.get("installation_id"):
            validate_payload["installation_id"] = payload["installation_id"]

        # Record patch_generated before the commit so it rides the same transaction
        from services.incident_events import record_event
        await record_event(
            session,
            event_type="patch_generated",
            code_usage_id=code_usage_id,
            job_id=None,
            payload={
                "llm_provider": provider_name,
                "llm_model": model_name,
                "verified": False,
            },
        )

        await enqueue_job(
            session,
            job_type="validate_patch",
            payload=validate_payload,
        )
        await session.commit()

        # Publish patch_generated after commit — non-fatal
        try:
            from services.event_bus import event_bus
            await event_bus.publish({
                "event_type": "patch_generated",
                "code_usage_id": str(code_usage_id),
                "llm_provider": provider_name,
                "llm_model": model_name,
                "verified": False,
            })
        except Exception as exc:
            logger.warning("event_bus publish patch_generated failed (non-fatal): %s", exc)

    logger.info(
        "generate_patch: created candidate patch %s via %s, enqueued validate_patch",
        patch.id,
        provider_name,
    )
