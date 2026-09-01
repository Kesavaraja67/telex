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
import shutil
import stat
import subprocess
import tempfile
import uuid
from typing import Optional

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


async def verify_patch_via_github(
    repo_full_name: str,
    default_branch: str,
    installation_github_id: Optional[int],
    diff: str,
    code_snippet: str,
    file_path: str = "src/index.ts",
    requires_tests: bool = False,
    requires_typecheck: bool = False,
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
        fetch_file_content,
        apply_diff_to_content,
        create_or_update_branch,
        detect_repo_environment,
        generate_telex_verification_workflow,
        commit_verification_bundle,
        delete_branch,
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
            detect_repo_environment, repo_full_name, installation_github_id, default_branch
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
        logger.info("verify_patch_via_github: creating verification branch %s on %s", verify_branch, repo_full_name)
        base_sha = await asyncio.to_thread(
            create_or_update_branch, repo_full_name, installation_github_id, verify_branch, default_branch
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
        asyncio.create_task(asyncio.to_thread(delete_branch, repo_full_name, installation_github_id, verify_branch))

        # 7. Interpret results strictly
        if ci_result["workflow_found"] and ci_result["completed"]:
            verification_mode = "github_actions"
            typechecks = ci_result["typechecks"]
            tests_pass = ci_result["tests_pass"]
            all_passed = (ci_result["conclusion"] == "success")

            tests_ok = (tests_pass is True) if (requires_tests or env_info.get("has_test")) else (tests_pass in (True, None))
            typecheck_ok = (typechecks is True) if (requires_typecheck or env_info.get("has_typecheck")) else (typechecks in (True, None))

            is_verified = (
                all_passed
                and applies_cleanly
                and parses
                and scope_ok
                and tests_ok
                and typecheck_ok
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
    from db.session import AsyncSessionLocal
    from db.models import CodeUsage, DetectedChange, PackageVersion, Patch, ValidationRun, Repo, Installation, RecoveryEvent
    from services.patch_providers import get_patch_provider
    from datetime import datetime, timezone
    from config import settings

    code_usage_id = uuid.UUID(payload["code_usage_id"])
    recovery_event_id_str = payload.get("recovery_event_id")
    recovery_event_id = uuid.UUID(recovery_event_id_str) if recovery_event_id_str else None

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

        repo = await session.get(Repo, cu.repo_id)
        repo_full_name = repo.full_name if repo else ""
        repo_default_branch = repo.default_branch if repo else "main"
        repo_requires_tests = repo.requires_tests if repo else False
        repo_requires_typecheck = repo.requires_typecheck if repo else False

        installation_github_id: Optional[int] = None
        if repo and repo.installation_id:
            inst = await session.get(Installation, repo.installation_id)
            if inst:
                installation_github_id = inst.github_installation_id

        old_api = dc.symbol_old or ""
        new_api = dc.symbol_new or ""
        defect_description = dc.description or ""
        code_snippet = cu.snippet or ""
        file_path = cu.file_path
        context = f"File: {cu.file_path}\nLines {cu.line_start}–{cu.line_end}"

        # Extract observed behavioral evidence from the originating RecoveryEvent (if any)
        observed_evidence = ""
        if recovery_event_id:
            recovery_event = await session.get(RecoveryEvent, recovery_event_id)
            if recovery_event and recovery_event.action_taken:
                observed_evidence = recovery_event.action_taken

    # ── Phase 2: call provider and verify with 1-retry fallback ────────────────
    provider = get_patch_provider()
    provider_name = settings.llm_provider_default
    model_name = provider.model_name

    diff = await provider.generate_patch(
        old_api=old_api,
        new_api=new_api,
        code_snippet=code_snippet,
        context=context,
        defect_description=defect_description,
        observed_evidence=observed_evidence,
    )

    v_result = await verify_patch_via_github(
        repo_full_name=repo_full_name,
        default_branch=repo_default_branch,
        installation_github_id=installation_github_id,
        diff=diff,
        code_snippet=code_snippet,
        file_path=file_path,
        requires_tests=repo_requires_tests,
        requires_typecheck=repo_requires_typecheck,
    )

    # If verification failed and diff was not an explicit refusal, retry ONCE with error context
    if not v_result["is_verified"] and diff != "UNABLE_TO_PATCH" and v_result["verification_mode"] in ("github_actions", "git_apply_failed", "git_apply_clean"):
        logger.info("generate_patch: first attempt failed verification (%s) — retrying once with error feedback", v_result["log"])
        retry_context = f"{context}\n\nIMPORTANT: Your previous patch attempt failed verification with error:\n{v_result['log']}\nPlease generate a corrected minimal unified diff."
        diff = await provider.generate_patch(
            old_api=old_api,
            new_api=new_api,
            code_snippet=code_snippet,
            context=retry_context,
            defect_description=defect_description,
            observed_evidence=observed_evidence,
        )
        v_result = await verify_patch_via_github(
            repo_full_name=repo_full_name,
            default_branch=repo_default_branch,
            installation_github_id=installation_github_id,
            diff=diff,
            code_snippet=code_snippet,
            file_path=file_path,
            requires_tests=repo_requires_tests,
            requires_typecheck=repo_requires_typecheck,
        )

    # ── Phase 3: write results in transaction ──────────────────────────────────
    async with AsyncSessionLocal() as session:
        cu = await session.get(CodeUsage, code_usage_id)
        if cu is None:
            return

        if diff == "UNABLE_TO_PATCH":
            cu.status = "failed"
            if recovery_event_id:
                re = await session.get(RecoveryEvent, recovery_event_id)
                if re:
                    re.outcome = "unresolved"
                    re.resolved_at = datetime.now(timezone.utc)
                    re.action_taken = "Provider signaled UNABLE_TO_PATCH."
            await session.commit()
            logger.warning("generate_patch: provider returned UNABLE_TO_PATCH for usage %s", code_usage_id)
            return

        is_verified = v_result["is_verified"]

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

        vr = ValidationRun(
            patch_id=patch.id,
            verification_mode=v_result["verification_mode"],
            applies_cleanly=v_result["applies_cleanly"],
            parses=v_result["parses"],
            typechecks=v_result["typechecks"],
            tests_pass=v_result["tests_pass"],
            scope_ok=v_result["scope_ok"],
            log=v_result["log"],
        )
        session.add(vr)

        if is_verified:
            cu.status = "patched"
            if payload.get("recovery_event_id") and payload.get("repo_id"):
                from jobs.queue import enqueue_job
                await enqueue_job(
                    session,
                    job_type="open_pr",
                    payload={
                        "repo_id": payload["repo_id"],
                        "code_usage_id": str(code_usage_id),
                        "recovery_event_id": payload["recovery_event_id"],
                    },
                )
        else:
            cu.status = "failed"
            if recovery_event_id:
                re = await session.get(RecoveryEvent, recovery_event_id)
                if re:
                    re.outcome = "unresolved"
                    re.resolved_at = datetime.now(timezone.utc)
                    if v_result["verification_mode"] == "structural_only":
                        re.action_taken = "Cannot verify — GitHub App not installed on target repo"
                    else:
                        re.action_taken = f"Patch verification gate failed: {v_result['log'][:300]}"

        await session.commit()

    logger.info(
        "generate_patch: %s for usage %s (verified=%s, mode=%s, applies=%s, tsc=%s, tests=%s)",
        provider_name,
        code_usage_id,
        is_verified,
        v_result["verification_mode"],
        v_result["applies_cleanly"],
        v_result["typechecks"],
        v_result["tests_pass"],
    )



