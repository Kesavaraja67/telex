"""
validate_patch handler — Section 4.2.

Executes isolated sandbox verification of candidate patches using dynamic GitHub Actions:
1. Validates structural syntax, unified diff format, and AST scope.
2. Checks local micro git apply in memory.
3. Detects target repository ecosystem (Node/Python, package manager, test/typecheck scripts).
4. Pushes candidate patch and ephemeral workflow bundle to an isolated branch.
5. Awaits check runs from GitHub Actions verification gate.
6. Cleans up temporary branch.
7. Enforces repository quality gates (requires_tests, requires_typecheck).
8. Records ValidationRun and enqueues open_pr if verified.

Payload shape:
    { "patch_id": "<uuid>" }
"""

import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)


async def run(payload: dict) -> None:
    from db.models import CodeUsage, Installation, Patch, Repo, ValidationRun
    from db.session import AsyncSessionLocal
    from jobs.handlers.generate_patch import validate_patch
    from jobs.queue import enqueue_job
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

    patch_id_raw = payload.get("patch_id")
    if not patch_id_raw:
        logger.error("validate_patch: missing patch_id in payload")
        return

    patch_id = uuid.UUID(patch_id_raw)

    # Import event helpers — used across all branches below
    from services.event_bus import event_bus
    from services.incident_events import record_event

    async def _publish_validation_event(event_type: str, cu_id, dc_id, repo_id_val, extra: dict):
        """Publish a validation event after commit — exception-safe."""
        try:
            await event_bus.publish({
                "event_type": event_type,
                "code_usage_id": str(cu_id) if cu_id else None,
                "detected_change_id": str(dc_id) if dc_id else None,
                "repo_id": str(repo_id_val) if repo_id_val else None,
                **extra,
            })
        except Exception as exc:
            logger.warning("event_bus publish %s failed (non-fatal): %s", event_type, exc)

    async with AsyncSessionLocal() as session:
        patch = await session.get(Patch, patch_id)
        if patch is None:
            logger.error("validate_patch: patch %s not found", patch_id)
            return

        code_usage = await session.get(CodeUsage, patch.code_usage_id)
        if code_usage is None:
            logger.error(
                "validate_patch: CodeUsage %s not found for patch %s", patch.code_usage_id, patch_id
            )
            return

        repo = await session.get(Repo, code_usage.repo_id)
        if repo is None:
            logger.error("validate_patch: repo %s not found", code_usage.repo_id)
            return

        installation = await session.get(Installation, repo.installation_id)
        if installation is None:
            logger.error("validate_patch: installation %s not found", repo.installation_id)
            return

        # Snapshot scalar values before background/thread calls
        repo_id = repo.id
        repo_full_name = repo.full_name
        repo_default_branch = repo.default_branch or "main"
        installation_github_id = installation.github_installation_id
        file_path = code_usage.file_path
        code_snippet = code_usage.snippet or ""
        repo_requires_tests = repo.requires_tests
        repo_requires_typecheck = repo.requires_typecheck
        repo_allow_install_scripts = getattr(repo, "allow_install_scripts", False)
        diff = patch.diff

        # 1. Structural check
        applies_cleanly, parses, scope_ok = validate_patch(diff, code_snippet)

        # Emit validating event on entry (before any gate checks)
        # Publish direct — no DB row needed for this in-flight signal
        try:
            await event_bus.publish({
                "event_type": "validating",
                "code_usage_id": str(code_usage.id),
                "repo_id": str(repo_id),
            })
        except Exception as exc:
            logger.warning("event_bus publish validating failed (non-fatal): %s", exc)

        if not (applies_cleanly and parses and scope_ok):
            logger.info("validate_patch: patch %s failed structural check", patch_id)
            vr = ValidationRun(
                patch_id=patch.id,
                verification_mode="structural_only",
                applies_cleanly=applies_cleanly,
                parses=parses,
                typechecks=None,
                tests_pass=None,
                scope_ok=scope_ok,
                log="Structural check failed: diff does not parse or is out of scope.",
            )
            session.add(vr)
            patch.verified = False
            code_usage.status = "failed"
            await record_event(
                session,
                event_type="validation_failed",
                code_usage_id=code_usage.id,
                repo_id=repo_id,
                payload={
                    "applies_cleanly": applies_cleanly,
                    "parses": parses,
                    "scope_ok": scope_ok,
                    "typechecks": None,
                    "tests_pass": None,
                    "verification_mode": "structural_only",
                    "reason": "structural_check_failed",
                },
            )
            await session.commit()
            await _publish_validation_event(
                "validation_failed", code_usage.id, None, repo_id,
                {"applies_cleanly": applies_cleanly, "parses": parses,
                 "scope_ok": scope_ok, "typechecks": None, "tests_pass": None,
                 "verification_mode": "structural_only"},
            )
            return

        # 2. Check GitHub App installation token
        if not installation_github_id or not repo_full_name:
            logger.info("validate_patch: no GitHub App installation token for patch %s", patch_id)
            vr = ValidationRun(
                patch_id=patch.id,
                verification_mode="structural_only",
                applies_cleanly=applies_cleanly,
                parses=parses,
                typechecks=None,
                tests_pass=None,
                scope_ok=scope_ok,
                log="No GitHub App installation token available — cannot perform full verification.",
            )
            session.add(vr)
            patch.verified = False
            code_usage.status = "failed"
            await record_event(
                session,
                event_type="validation_failed",
                code_usage_id=code_usage.id,
                repo_id=repo_id,
                payload={
                    "applies_cleanly": applies_cleanly,
                    "parses": parses,
                    "scope_ok": scope_ok,
                    "typechecks": None,
                    "tests_pass": None,
                    "verification_mode": "structural_only",
                    "reason": "no_installation_token",
                },
            )
            await session.commit()
            await _publish_validation_event(
                "validation_failed", code_usage.id, None, repo_id,
                {"applies_cleanly": applies_cleanly, "parses": parses,
                 "scope_ok": scope_ok, "typechecks": None, "tests_pass": None,
                 "verification_mode": "structural_only"},
            )
            return

        # 3. Micro git apply check on single file
        branch_name: str | None = None
        try:
            original_content = await asyncio.to_thread(
                fetch_file_content,
                repo_full_name,
                installation_github_id,
                file_path,
                repo_default_branch,
            )
            if not original_content:
                original_content = code_snippet

            apply_ok, new_content, apply_log = apply_diff_to_content(
                file_path, original_content, diff
            )
            if not apply_ok:
                logger.warning("validate_patch: micro git apply failed: %s", apply_log)
                vr = ValidationRun(
                    patch_id=patch.id,
                    verification_mode="structural_only",
                    applies_cleanly=False,
                    parses=parses,
                    typechecks=None,
                    tests_pass=None,
                    scope_ok=scope_ok,
                    log=f"git apply failed: {apply_log}",
                )
                session.add(vr)
                patch.verified = False
                code_usage.status = "failed"
                await record_event(
                    session,
                    event_type="validation_failed",
                    code_usage_id=code_usage.id,
                    repo_id=repo_id,
                    payload={
                        "applies_cleanly": False,
                        "parses": parses,
                        "scope_ok": scope_ok,
                        "typechecks": None,
                        "tests_pass": None,
                        "verification_mode": "structural_only",
                        "reason": "git_apply_failed",
                    },
                )
                await session.commit()
                await _publish_validation_event(
                    "validation_failed", code_usage.id, None, repo_id,
                    {"applies_cleanly": False, "parses": parses, "scope_ok": scope_ok,
                     "typechecks": None, "tests_pass": None, "verification_mode": "structural_only"},
                )
                return

            # 4. Detect repository ecosystem and generate dynamic verification workflow
            env_info = await asyncio.to_thread(
                detect_repo_environment,
                repo_full_name,
                installation_github_id,
                repo_default_branch,
                repo_allow_install_scripts,
            )
            workflow_id = patch_id.hex[:10]
            branch_name = f"telex/validate-{workflow_id}"
            workflow_name = f"Telex Verification {workflow_id}"
            workflow_file_path = ".github/workflows/telex-verify.yml"

            workflow_yaml = generate_telex_verification_workflow(
                env_info=env_info,
                branch_name=branch_name,
                workflow_name=workflow_name,
            )

            # 5. Create isolated verification branch on GitHub
            base_sha = await asyncio.to_thread(
                create_or_update_branch,
                repo_full_name,
                installation_github_id,
                branch_name,
                repo_default_branch,
            )
            if not base_sha:
                vr = ValidationRun(
                    patch_id=patch.id,
                    verification_mode="structural_only",
                    applies_cleanly=True,
                    parses=True,
                    typechecks=False,
                    tests_pass=False,
                    scope_ok=scope_ok,
                    log="Verification branch creation on GitHub failed.",
                )
                session.add(vr)
                patch.verified = False
                code_usage.status = "failed"
                await record_event(
                    session,
                    event_type="validation_failed",
                    code_usage_id=code_usage.id,
                    repo_id=repo_id,
                    payload={
                        "applies_cleanly": True,
                        "parses": True,
                        "scope_ok": scope_ok,
                        "typechecks": False,
                        "tests_pass": False,
                        "verification_mode": "structural_only",
                        "reason": "branch_creation_failed",
                    },
                )
                await session.commit()
                await _publish_validation_event(
                    "validation_failed", code_usage.id, None, repo_id,
                    {"applies_cleanly": True, "parses": True, "scope_ok": scope_ok,
                     "typechecks": False, "tests_pass": False, "verification_mode": "structural_only"},
                )
                return

            # 6. Commit candidate patch and verification workflow bundle atomically
            commit_sha = await asyncio.to_thread(
                commit_verification_bundle,
                repo_full_name=repo_full_name,
                installation_id=installation_github_id,
                branch_name=branch_name,
                patched_file_path=file_path,
                patched_content=new_content,
                workflow_file_path=workflow_file_path,
                workflow_content=workflow_yaml,
            )
            if not commit_sha:
                await asyncio.to_thread(
                    delete_branch, repo_full_name, installation_github_id, branch_name
                )
                vr = ValidationRun(
                    patch_id=patch.id,
                    verification_mode="structural_only",
                    applies_cleanly=False,
                    parses=True,
                    typechecks=False,
                    tests_pass=False,
                    scope_ok=scope_ok,
                    log="Failed to commit candidate patch and dynamic verification workflow to GitHub.",
                )
                session.add(vr)
                patch.verified = False
                code_usage.status = "failed"
                await record_event(
                    session,
                    event_type="validation_failed",
                    code_usage_id=code_usage.id,
                    repo_id=repo_id,
                    payload={
                        "applies_cleanly": False,
                        "parses": True,
                        "scope_ok": scope_ok,
                        "typechecks": False,
                        "tests_pass": False,
                        "verification_mode": "structural_only",
                        "reason": "commit_bundle_failed",
                    },
                )
                await session.commit()
                await _publish_validation_event(
                    "validation_failed", code_usage.id, None, repo_id,
                    {"applies_cleanly": False, "parses": True, "scope_ok": scope_ok,
                     "typechecks": False, "tests_pass": False, "verification_mode": "structural_only"},
                )
                return

            # 7. Poll GitHub Actions verification gate
            result = await wait_for_telex_verification(
                repo_full_name=repo_full_name,
                installation_id=installation_github_id,
                commit_sha=commit_sha,
                expected_workflow_name=workflow_name,
                timeout_seconds=180.0,
            )

            # 8. Clean up temporary verification branch on GitHub
            await asyncio.to_thread(
                delete_branch, repo_full_name, installation_github_id, branch_name
            )

            has_test = bool(env_info.get("has_test"))
            has_typecheck = bool(env_info.get("has_typecheck"))

            # Verification mode: "full" if repo has automated tests, otherwise "structural_only"
            verification_mode = "full" if has_test else "structural_only"

            tests_pass = result.get("tests_pass") if has_test else None
            typechecks = result.get("typechecks") if has_typecheck else None
            conclusion = result.get("conclusion")
            all_passed = conclusion == "success"

            vr = ValidationRun(
                patch_id=patch.id,
                verification_mode=verification_mode,
                applies_cleanly=True,
                parses=parses,
                typechecks=typechecks,
                tests_pass=tests_pass,
                scope_ok=scope_ok,
                log=result.get("log"),
            )
            session.add(vr)

            # 9. Gating policy per Section 4.2
            fails_test_req = repo_requires_tests and (tests_pass is not True)
            fails_typecheck_req = repo_requires_typecheck and (typechecks is not True)
            is_workflow_success = (
                bool(result.get("workflow_found"))
                and bool(result.get("completed"))
                and result.get("conclusion") == "success"
                and all_passed
            )
            run_failed = not is_workflow_success

            if fails_test_req or fails_typecheck_req or run_failed:
                patch.verified = False
                code_usage.status = "failed"
                logger.info("validate_patch: patch %s failed repo gate requirements", patch_id)
                await record_event(
                    session,
                    event_type="validation_failed",
                    code_usage_id=code_usage.id,
                    repo_id=repo_id,
                    payload={
                        "applies_cleanly": True,
                        "typechecks": typechecks,
                        "tests_pass": tests_pass,
                        "scope_ok": scope_ok,
                        "verification_mode": verification_mode,
                        "reason": "gate_requirements_failed",
                    },
                )
            else:
                patch.verified = True
                code_usage.status = "patched"
                await record_event(
                    session,
                    event_type="validation_passed",
                    code_usage_id=code_usage.id,
                    repo_id=repo_id,
                    payload={
                        "applies_cleanly": True,
                        "typechecks": typechecks,
                        "tests_pass": tests_pass,
                        "scope_ok": scope_ok,
                        "verification_mode": verification_mode,
                    },
                )
                await enqueue_job(
                    session,
                    job_type="open_pr",
                    payload={
                        "repo_id": str(repo_id),
                        "code_usage_id": str(code_usage.id),
                    },
                )
                logger.info(
                    "validate_patch: patch %s verified successfully and enqueued open_pr", patch_id
                )

            await session.commit()

            # Publish final outcome after commit
            outcome_event = "validation_failed" if (fails_test_req or fails_typecheck_req or run_failed) else "validation_passed"
            await _publish_validation_event(
                outcome_event, code_usage.id, None, repo_id,
                {"applies_cleanly": True, "typechecks": typechecks,
                 "tests_pass": tests_pass, "scope_ok": scope_ok,
                 "verification_mode": verification_mode},
            )

        except Exception as exc:
            logger.exception("validate_patch error for patch %s: %s", patch_id, exc)
            if branch_name:
                try:
                    await asyncio.to_thread(
                        delete_branch, repo_full_name, installation_github_id, branch_name
                    )
                except Exception:
                    pass
            vr = ValidationRun(
                patch_id=patch.id,
                verification_mode="structural_only",
                applies_cleanly=False,
                parses=False,
                typechecks=False,
                tests_pass=False,
                scope_ok=False,
                log=f"Verification exception: {exc}",
            )
            session.add(vr)
            patch.verified = False
            code_usage.status = "failed"
            await record_event(
                session,
                event_type="validation_failed",
                code_usage_id=code_usage.id,
                repo_id=repo_id,
                payload={
                    "applies_cleanly": False,
                    "parses": False,
                    "scope_ok": False,
                    "typechecks": False,
                    "tests_pass": False,
                    "verification_mode": "structural_only",
                    "reason": f"exception: {type(exc).__name__}",
                },
            )
            await session.commit()
            await _publish_validation_event(
                "validation_failed", code_usage.id, None, repo_id,
                {"applies_cleanly": False, "parses": False, "scope_ok": False,
                 "typechecks": False, "tests_pass": False, "verification_mode": "structural_only"},
            )
