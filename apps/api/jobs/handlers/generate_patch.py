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


async def _run_subprocess_with_timeout(
    *cmd: str,
    cwd: Optional[str] = None,
    timeout: float = 60.0,
) -> tuple[int, bytes, bytes]:
    """Runs a subprocess with strict timeout, killing the process tree if timed out."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, stdout or b"", stderr or b""
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        raise


async def verify_patch_in_clone(
    repo_full_name: str,
    default_branch: str,
    installation_github_id: Optional[int],
    diff: str,
    code_snippet: str,
) -> dict:
    """
    Execute the real Verification Gate:
    1. Check structural validity (applies_cleanly, parses, scope_ok).
    2. If installation token is available, shallow-clone the repo into an isolated tempdir.
    3. Run `git apply` in clone.
    4. Run repo's typechecker (`npx tsc --noEmit` or `mypy`).
    5. Run repo's test suite (`npm test` or `pytest`).
    6. Return verification_mode ("full" vs "structural_only"), 3-state booleans, and logs.
       NOTE: is_verified is ONLY True when verification_mode == "full".
    """
    from services.github_service import get_installation_token

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

    # If no installation token is configured or available, we cannot do a full verification
    if not installation_github_id:
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

    token = None
    try:
        token = await asyncio.to_thread(get_installation_token, installation_github_id)
    except Exception as exc:
        logger.warning("verify_patch_in_clone: could not retrieve installation token: %s", exc)

    if not token:
        return {
            "applies_cleanly": applies_cleanly,
            "parses": parses,
            "scope_ok": scope_ok,
            "typechecks": None,
            "tests_pass": None,
            "verification_mode": "structural_only",
            "is_verified": False,
            "log": "Token retrieval unavailable — cannot perform full verification.",
        }

    tmpdir = tempfile.mkdtemp(prefix="telex_verify_")
    typechecks: Optional[bool] = None
    tests_pass: Optional[bool] = None
    verification_mode = "full"
    log_messages: list[str] = []

    try:
        # Clone isolated shallow copy
        clone_url = f"https://x-access-token:{token}@github.com/{repo_full_name}.git"
        logger.info("verify_patch_in_clone: shallow cloning %s into %s", repo_full_name, tmpdir)

        clone_rc, _, clone_err = await _run_subprocess_with_timeout(
            "git", "clone", "--depth", "1", "--branch", default_branch, clone_url, tmpdir,
            timeout=60.0,
        )
        if clone_rc != 0:
            logger.warning("verify_patch_in_clone: git clone failed: %s", clone_err.decode(errors="replace"))
            return {
                "applies_cleanly": applies_cleanly,
                "parses": parses,
                "scope_ok": scope_ok,
                "typechecks": None,
                "tests_pass": None,
                "verification_mode": "structural_only",
                "is_verified": False,
                "log": f"Clone failed: {clone_err.decode(errors='replace')[:200]}",
            }

        # Strip credential-bearing clone URL from .git/config immediately after clone
        try:
            await _run_subprocess_with_timeout(
                "git", "remote", "set-url", "origin", f"https://github.com/{repo_full_name}.git",
                cwd=tmpdir,
                timeout=10.0,
            )
        except Exception as e:
            logger.warning("verify_patch_in_clone: failed to reset remote origin URL: %s", e)

        # Apply diff via git apply
        patch_file = os.path.join(tmpdir, "_telex_candidate.patch")
        with open(patch_file, "w", encoding="utf-8") as f:
            f.write(diff if diff.endswith("\n") else diff + "\n")

        apply_rc, _, apply_err = await _run_subprocess_with_timeout(
            "git", "apply", "--ignore-whitespace", "_telex_candidate.patch",
            cwd=tmpdir,
            timeout=30.0,
        )
        if apply_rc != 0:
            applies_cleanly = False
            err_msg = apply_err.decode(errors="replace")
            logger.warning("verify_patch_in_clone: git apply failed: %s", err_msg)
            log_messages.append(f"git apply failed: {err_msg}")
            return {
                "applies_cleanly": False,
                "parses": parses,
                "scope_ok": scope_ok,
                "typechecks": None,
                "tests_pass": None,
                "verification_mode": "full",
                "is_verified": False,
                "log": f"git apply failed: {err_msg}",
            }

        log_messages.append("git apply succeeded cleanly.")

        # Typecheck detection (3 states: True=passed, False=failed or errored, None=not configured)
        tsconfig_path = os.path.join(tmpdir, "tsconfig.json")
        mypy_path = os.path.join(tmpdir, "mypy.ini")
        pyproject_path = os.path.join(tmpdir, "pyproject.toml")

        if os.path.exists(tsconfig_path):
            try:
                tc_rc, _, tc_err = await _run_subprocess_with_timeout(
                    "npx", "--yes", "tsc", "--noEmit",
                    cwd=tmpdir,
                    timeout=120.0,
                )
                typechecks = (tc_rc == 0)
                log_messages.append(f"Typecheck (npx tsc): {'passed' if typechecks else 'failed'}")
                if not typechecks:
                    log_messages.append(f"Typecheck error: {tc_err.decode(errors='replace')[:400]}")
            except Exception as e:
                logger.warning("Typecheck command failed to execute: %s", e)
                typechecks = False  # Configured check errored during run
                log_messages.append(f"Typecheck crashed: {e}")
        elif os.path.exists(mypy_path) or (os.path.exists(pyproject_path) and "tool.mypy" in open(pyproject_path, encoding="utf-8", errors="ignore").read()):
            try:
                tc_rc, _, tc_err = await _run_subprocess_with_timeout(
                    "mypy", ".",
                    cwd=tmpdir,
                    timeout=120.0,
                )
                typechecks = (tc_rc == 0)
                log_messages.append(f"Typecheck (mypy): {'passed' if typechecks else 'failed'}")
                if not typechecks:
                    log_messages.append(f"Typecheck error: {tc_err.decode(errors='replace')[:400]}")
            except Exception as e:
                logger.warning("mypy command failed to execute: %s", e)
                typechecks = False  # Configured check errored during run
                log_messages.append(f"Typecheck crashed: {e}")
        else:
            typechecks = None  # Genuinely not configured
            log_messages.append("Typecheck: no tsconfig.json or mypy configuration found.")

        # Test suite detection (3 states: True=passed, False=failed or errored, None=not configured)
        pkg_json_path = os.path.join(tmpdir, "package.json")
        tests_dir_path = os.path.join(tmpdir, "tests")

        if os.path.exists(pkg_json_path):
            try:
                pkg_data = open(pkg_json_path, encoding="utf-8", errors="ignore").read()
                if '"test"' in pkg_data and "no test specified" not in pkg_data:
                    test_rc, _, t_err = await _run_subprocess_with_timeout(
                        "npm", "test",
                        cwd=tmpdir,
                        timeout=180.0,
                    )
                    tests_pass = (test_rc == 0)
                    log_messages.append(f"Tests (npm test): {'passed' if tests_pass else 'failed'}")
                    if not tests_pass:
                        log_messages.append(f"Test failure output: {t_err.decode(errors='replace')[:400]}")
                else:
                    tests_pass = None  # Genuinely no test script
                    log_messages.append("Tests: package.json has no test script.")
            except Exception as e:
                logger.warning("npm test command failed to execute: %s", e)
                tests_pass = False  # Configured check errored during run
                log_messages.append(f"npm test crashed: {e}")
        elif os.path.exists(tests_dir_path):
            try:
                test_rc, _, t_err = await _run_subprocess_with_timeout(
                    "pytest",
                    cwd=tmpdir,
                    timeout=180.0,
                )
                tests_pass = (test_rc == 0)
                log_messages.append(f"Tests (pytest): {'passed' if tests_pass else 'failed'}")
                if not tests_pass:
                    log_messages.append(f"Test failure output: {t_err.decode(errors='replace')[:400]}")
            except Exception as e:
                logger.warning("pytest command failed to execute: %s", e)
                tests_pass = False  # Configured check errored during run
                log_messages.append(f"pytest crashed: {e}")
        else:
            tests_pass = None  # Genuinely not configured
            log_messages.append("Tests: no test suite configuration found.")

    except Exception as exc:
        logger.exception("verify_patch_in_clone: unexpected error during verification: %s", exc)
        verification_mode = "error"
        applies_cleanly = False
        typechecks = False
        tests_pass = False
        log_messages.append(f"Verification error: {exc}")
    finally:
        shutil.rmtree(tmpdir, onerror=_remove_readonly)

    # Tightened verified formula: MUST be full mode, clean diff, and non-failing type/test checks
    is_verified = (
        verification_mode == "full"
        and applies_cleanly
        and parses
        and scope_ok
        and typechecks in (True, None)
        and tests_pass in (True, None)
    )

    return {
        "applies_cleanly": applies_cleanly,
        "parses": parses,
        "scope_ok": scope_ok,
        "typechecks": typechecks,
        "tests_pass": tests_pass,
        "verification_mode": verification_mode,
        "is_verified": is_verified,
        "log": "\n".join(log_messages),
    }


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

        installation_github_id: Optional[int] = None
        if repo and repo.installation_id:
            inst = await session.get(Installation, repo.installation_id)
            if inst:
                installation_github_id = inst.github_installation_id

        old_api = dc.symbol_old
        new_api = dc.symbol_new or ""
        code_snippet = cu.snippet
        context = f"File: {cu.file_path}\nLines {cu.line_start}–{cu.line_end}"

    # ── Phase 2: call provider and verify with 1-retry fallback ────────────────
    provider = get_patch_provider()
    provider_name = settings.llm_provider_default
    model_name = provider.model_name

    diff = await provider.generate_patch(
        old_api=old_api,
        new_api=new_api,
        code_snippet=code_snippet,
        context=context,
    )

    v_result = await verify_patch_in_clone(
        repo_full_name=repo_full_name,
        default_branch=repo_default_branch,
        installation_github_id=installation_github_id,
        diff=diff,
        code_snippet=code_snippet,
    )

    # If verification failed and diff was not an explicit refusal, retry ONCE with error context
    if not v_result["is_verified"] and diff != "UNABLE_TO_PATCH" and v_result["verification_mode"] == "full":
        logger.info("generate_patch: first attempt failed verification (%s) — retrying once with error feedback", v_result["log"])
        retry_context = f"{context}\n\nIMPORTANT: Your previous patch attempt failed verification with error:\n{v_result['log']}\nPlease generate a corrected minimal unified diff."
        diff = await provider.generate_patch(
            old_api=old_api,
            new_api=new_api,
            code_snippet=code_snippet,
            context=retry_context,
        )
        v_result = await verify_patch_in_clone(
            repo_full_name=repo_full_name,
            default_branch=repo_default_branch,
            installation_github_id=installation_github_id,
            diff=diff,
            code_snippet=code_snippet,
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



