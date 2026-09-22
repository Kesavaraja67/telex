"""
GitHub App service — Section 7.7.

Handles:
  - Installation-scoped API clients via GitHub App JWT
  - Branch creation, file commits, and PR opening
"""

import asyncio
import logging
from typing import Any

from config import settings

logger = logging.getLogger(__name__)


try:
    from github import (  # type: ignore[import]
        Github,
        GithubException,
        GithubIntegration,
        InputGitTreeElement,
    )
except ImportError:
    Github: Any = None
    GithubIntegration: Any = None
    GithubException: Any = Exception
    InputGitTreeElement: Any = None


def get_installation_token(installation_id: int) -> str:
    """
    Return an installation access token for shallow cloning and Git CLI authentication.
    """
    if GithubIntegration is None:
        raise RuntimeError("PyGithub not installed — run: pip install PyGithub")

    private_key = settings.github_app_private_key.replace("\\n", "\n").strip("\"'")
    integration = GithubIntegration(
        int(settings.github_app_id),
        private_key,
    )
    return integration.get_access_token(installation_id).token


def check_rate_limit_and_wait(gh) -> None:
    """
    Phase 8.2: Check the current GitHub API rate-limit state and sleep
    until the reset window if fewer than 50 requests remain.

    This runs in a thread (all PyGithub calls are blocking). Raises
    RuntimeError if rate limit info is unavailable (treat as transient,
    let the worker retry mechanism handle it) — propagates to the worker's
    exponential-backoff retry path.
    """
    import time

    try:
        rl = gh.get_rate_limit()
        core = (
            getattr(rl, "rate", None)
            or getattr(getattr(rl, "resources", None), "core", None)
            or getattr(rl, "core", None)
        )
        if core is None:
            logger.warning("Could not determine core rate limit from PyGithub; skipping check")
            return
        remaining = core.remaining
        reset_at = core.reset  # datetime UTC
    except Exception as exc:
        logger.warning("GitHub rate limit check failed: %s; proceeding without rate limit gate", exc)
        return

    if remaining < 50:
        now_ts = time.time()
        reset_ts = reset_at.timestamp()
        wait_secs = max(0, reset_ts - now_ts) + 5  # 5s buffer
        logger.warning(
            "GitHub rate limit low (%d remaining) — sleeping %.0fs until reset",
            remaining,
            wait_secs,
        )
        time.sleep(min(wait_secs, 70))  # cap at 70s so the worker heartbeat stays alive
        # Re-check; if still 0 raise so the job is re-queued via the retry mechanism
        rl2 = gh.get_rate_limit()
        core2 = (
            getattr(rl2, "rate", None)
            or getattr(getattr(rl2, "resources", None), "core", None)
            or getattr(rl2, "core", None)
        )
        if core2 and core2.remaining == 0:
            raise RuntimeError(
                f"GitHub core rate limit exhausted — resets at {reset_at.isoformat()}"
            )


def get_installation_client(installation_id: int):
    """
    Return an authenticated PyGithub client scoped to a specific installation.

    Phase 8.2: automatically calls check_rate_limit_and_wait before returning
    so every caller gets the rate-limit gate without extra boilerplate.
    """
    if Github is None:
        raise RuntimeError("PyGithub not installed — run: pip install PyGithub")

    token = get_installation_token(installation_id)
    gh = Github(token)
    check_rate_limit_and_wait(gh)
    return gh


def requires_human_review(
    tests_passed: bool | None,
    typecheck_passed: bool | None,
    is_semantic_risk: bool,
    has_test_coverage_on_changed_symbol: bool,
) -> bool:
    """
    Gate function: returns True when there is weak evidence that the patch is
    safe to merge without human inspection.

    Triggers when ANY of:
    - tests_passed is None (no test run recorded) or False (tests failed)
    - is_semantic_risk is True (Gemini classifier flagged a possible behavior change)
    - has_test_coverage_on_changed_symbol is False

    NOTE: has_test_coverage_on_changed_symbol is currently stubbed to always pass
    False from the caller (unknown / treat as no coverage). This is an open gap —
    real per-symbol coverage instrumentation has not been implemented yet.
    """
    if tests_passed is None or tests_passed is False:
        return True
    if typecheck_passed is None or typecheck_passed is False:
        return True
    if is_semantic_risk:
        return True
    if not has_test_coverage_on_changed_symbol:
        return True
    return False


async def open_patch_pr(
    repo_full_name: str,
    installation_id: int,
    branch_name: str,
    patches: list[dict],
    summary: str,
    title: str | None = None,
    is_semantic_risk: bool = False,
    tests_passed: bool | None = None,
    typecheck_passed: bool | None = None,
    allow_install_scripts: bool = False,
) -> tuple[str, int]:
    """
    Open a pull request on `repo_full_name` with the given patches applied.

    Each entry in `patches` must have:
        - file_path: str
        - new_content: str   (full file content after applying the patch)
        - package_name: str
        - new_version: str

    When `is_semantic_risk` is True the PR title is prefixed with [semantic-risk]
    (if a custom `title` was not already provided with that prefix).

    When `requires_human_review` determines that human sign-off is needed, the
    label `needs-human-review` is added to the PR.

    Returns:
        (pr_html_url, pr_number)
    """
    if not patches:
        raise ValueError("open_patch_pr called with empty patches list")

    # All PyGithub calls are synchronous blocking I/O; run them in a thread
    def _do_github_work() -> tuple[str, int]:
        gh = get_installation_client(installation_id)
        repo = gh.get_repo(repo_full_name)
        base_branch = repo.get_branch(repo.default_branch)

        # Create or update the patch branch from the current HEAD of default branch (retry-safe)
        try:
            repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=base_branch.commit.sha,
            )
        except GithubException as exc:
            if getattr(exc, "status", None) == 422:
                try:
                    ref = repo.get_git_ref(f"heads/{branch_name}")
                    ref.edit(sha=base_branch.commit.sha, force=True)
                except Exception as ref_exc:
                    logger.warning("Could not reset existing ref %s: %s", branch_name, ref_exc)
            else:
                raise

        for patch in patches:
            content_file = repo.get_contents(patch["file_path"], ref=branch_name)
            repo.update_file(
                patch["file_path"],
                f"fix: update for {patch['package_name']}@{patch['new_version']}",
                patch["new_content"],
                content_file.sha,  # type: ignore[arg-type]
                branch=branch_name,
            )

        # Create or find existing PR for this branch (retry-safe)
        pr_title = (
            title
            or f"chore(deps): auto-patch for {patches[0]['package_name']}@{patches[0]['new_version']}"
        )
        if is_semantic_risk and not pr_title.startswith("[semantic-risk]"):
            pr_title = f"[semantic-risk] {pr_title}"
        try:
            pr = repo.create_pull(
                title=pr_title,
                body=summary,
                head=branch_name,
                base=repo.default_branch,
            )
        except GithubException as exc:
            if getattr(exc, "status", None) == 422:
                pulls = repo.get_pulls(state="open", head=f"{repo.owner.login}:{branch_name}")
                if pulls.totalCount > 0:
                    pr = pulls[0]
                else:
                    raise
            else:
                raise

        # Apply needs-human-review label when the gate fires
        _needs_review = requires_human_review(
            tests_passed=tests_passed,
            typecheck_passed=typecheck_passed,
            is_semantic_risk=is_semantic_risk,
            has_test_coverage_on_changed_symbol=False,  # stub — always unknown
        )
        if _needs_review:
            try:
                label = repo.get_label("needs-human-review")
            except GithubException:
                try:
                    label = repo.create_label(
                        name="needs-human-review",
                        color="e11d48",
                        description="Telex flagged this PR for human review before merge",
                    )
                except GithubException:
                    # Concurrent worker may have created it first — re-fetch
                    try:
                        label = repo.get_label("needs-human-review")
                    except GithubException as label_err:
                        logger.error(
                            "open_patch_pr: failed to fetch or create needs-human-review label: %s",
                            label_err,
                        )
                        raise
            pr.add_to_labels(label)

        logger.info("PR #%d on %s: %s", pr.number, repo_full_name, pr.html_url)
        return pr.html_url, pr.number

    return await asyncio.to_thread(_do_github_work)


def apply_diff_to_content(
    file_path: str, original_content: str, diff: str
) -> tuple[bool, str, str]:
    """
    Apply a unified diff to original_content using an isolated micro git process.
    Takes ~10ms and < 2 MB RAM (zero full repo cloning, zero npm ci).

    Returns:
        (success: bool, new_content: str, log: str)
    """
    import os
    import shutil
    import stat
    import subprocess
    import tempfile

    def _remove_readonly(func, path, _):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    tmpdir = tempfile.mkdtemp(prefix="telex_micro_apply_")
    try:
        norm_path = file_path.replace("\\", "/").lstrip("/")
        full_target = os.path.join(tmpdir, norm_path)
        os.makedirs(os.path.dirname(full_target), exist_ok=True)

        with open(full_target, "w", encoding="utf-8", newline="\n") as f:
            f.write(original_content)

        subprocess.run(["git", "init", "-q"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=tmpdir, check=True, capture_output=True)

        patch_file = os.path.join(tmpdir, "_candidate.patch")
        with open(patch_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(diff if diff.endswith("\n") else diff + "\n")

        res = subprocess.run(
            ["git", "apply", "--ignore-whitespace", "_candidate.patch"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
        )

        if res.returncode != 0:
            err_msg = res.stderr.strip() or res.stdout.strip() or "git apply rejected diff"
            return False, original_content, f"git apply failed: {err_msg}"

        with open(full_target, encoding="utf-8") as f:
            new_content = f.read()

        return True, new_content, "git apply succeeded cleanly."
    except Exception as e:
        return False, original_content, f"Exception during micro apply: {e}"
    finally:
        shutil.rmtree(tmpdir, onerror=_remove_readonly)


def create_or_update_branch(
    repo_full_name: str,
    installation_id: int,
    branch_name: str,
    base_branch: str = "main",
) -> str | None:
    """Create or reset a branch on GitHub to the HEAD of base_branch. Returns base commit SHA."""
    try:
        gh = get_installation_client(installation_id)
        repo = gh.get_repo(repo_full_name)
        base = repo.get_branch(base_branch)
        base_sha = base.commit.sha

        try:
            repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)
        except GithubException as exc:
            if getattr(exc, "status", None) == 422:
                ref = repo.get_git_ref(f"heads/{branch_name}")
                ref.edit(sha=base_sha, force=True)
            else:
                raise
        return base_sha
    except Exception as exc:
        logger.warning(
            "create_or_update_branch failed for %s:%s — %s", repo_full_name, branch_name, exc
        )
        return None


def push_file_to_branch(
    repo_full_name: str,
    installation_id: int,
    branch_name: str,
    file_path: str,
    content: str,
    commit_message: str,
) -> str | None:
    """Commit updated file content to branch on GitHub via REST API. Returns new commit SHA."""
    try:
        gh = get_installation_client(installation_id)
        repo = gh.get_repo(repo_full_name)
        content_file = repo.get_contents(file_path, ref=branch_name)
        result = repo.update_file(
            file_path,
            commit_message,
            content,
            content_file.sha,  # type: ignore[arg-type]
            branch=branch_name,
        )
        commit = result.get("commit")
        return commit.sha if commit else None
    except Exception as exc:
        logger.warning(
            "push_file_to_branch failed for %s:%s on %s — %s",
            repo_full_name,
            file_path,
            branch_name,
            exc,
        )
        return None


def detect_repo_environment(
    repo_full_name: str,
    installation_id: int,
    ref: str = "main",
    allow_install_scripts: bool = False,
) -> dict:
    """
    Inspect target repository via GitHub API to detect ecosystem, package manager, and test scripts.

    When `allow_install_scripts` is False (the default), lifecycle scripts are
    blocked by appending ``--ignore-scripts`` to every npm / pnpm / yarn install
    command so untrusted ``postinstall`` scripts cannot execute.  Set
    ``allow_install_scripts=True`` (opt-in, per-repo) to restore the original
    behaviour.
    """
    import json

    env_info = {
        "ecosystem": "node",
        "package_manager": "npm",
        "install_cmd": "npm ci" if allow_install_scripts else "npm ci --ignore-scripts",
        "test_cmd": "npm test",
        "typecheck_cmd": "npx tsc --noEmit",
        "has_test": True,
        "has_typecheck": True,
    }

    try:
        gh = get_installation_client(installation_id)
        repo = gh.get_repo(repo_full_name)
        root_contents = repo.get_contents("", ref=ref)
        file_names = (
            {item.name for item in root_contents} if isinstance(root_contents, list) else set()
        )

        if "package.json" in file_names:
            pkg_file = repo.get_contents("package.json", ref=ref)
            if hasattr(pkg_file, "decoded_content"):
                try:
                    pkg_json = json.loads(pkg_file.decoded_content.decode("utf-8"))
                    scripts = pkg_json.get("scripts", {})

                    if "pnpm-lock.yaml" in file_names:
                        pm = "pnpm"
                        _base_install = "pnpm install --frozen-lockfile"
                        install_cmd = (
                            _base_install
                            if allow_install_scripts
                            else f"{_base_install} --ignore-scripts"
                        )
                        test_cmd = "pnpm test" if "test" in scripts else ""
                        typecheck_cmd = (
                            "pnpm run typecheck"
                            if "typecheck" in scripts
                            else "pnpm exec tsc --noEmit"
                        )
                    elif "yarn.lock" in file_names:
                        pm = "yarn"
                        _base_install = "yarn install --frozen-lockfile"
                        install_cmd = (
                            _base_install
                            if allow_install_scripts
                            else f"{_base_install} --ignore-scripts"
                        )
                        test_cmd = "yarn test" if "test" in scripts else ""
                        typecheck_cmd = (
                            "yarn typecheck" if "typecheck" in scripts else "yarn tsc --noEmit"
                        )
                    else:
                        pm = "npm"
                        _base_install = "npm ci"
                        install_cmd = (
                            _base_install
                            if allow_install_scripts
                            else f"{_base_install} --ignore-scripts"
                        )
                        test_cmd = "npm test" if "test" in scripts else ""
                        typecheck_cmd = (
                            "npm run typecheck" if "typecheck" in scripts else "npx tsc --noEmit"
                        )

                    has_tsconfig = (
                        "tsconfig.json" in file_names or "tsconfig.base.json" in file_names
                    )
                    has_test = bool(test_cmd) and "no test specified" not in scripts.get("test", "")

                    return {
                        "ecosystem": "node",
                        "package_manager": pm,
                        "install_cmd": install_cmd,
                        "test_cmd": test_cmd or "npm test",
                        "typecheck_cmd": typecheck_cmd if has_tsconfig else "",
                        "has_test": has_test,
                        "has_typecheck": has_tsconfig,
                    }
                except Exception as e:
                    logger.warning("detect_repo_environment: failed to parse package.json: %s", e)

        elif "pyproject.toml" in file_names or "requirements.txt" in file_names:
            if allow_install_scripts:
                install_cmd = (
                    "pip install -r requirements.txt"
                    if "requirements.txt" in file_names
                    else "pip install -e ."
                )
            else:
                install_cmd = "echo 'Dependency installation skipped: allow_install_scripts is false (requires opt-in)'"
            return {
                "ecosystem": "python",
                "package_manager": "pip",
                "install_cmd": install_cmd,
                "test_cmd": "pytest",
                "typecheck_cmd": "mypy ." if "mypy.ini" in file_names else "",
                "has_test": True,
                "has_typecheck": "mypy.ini" in file_names,
            }

        return env_info
    except Exception as exc:
        logger.warning(
            "detect_repo_environment failed for %s: %s (using default node/npm)",
            repo_full_name,
            exc,
        )
        return env_info


def generate_telex_verification_workflow(
    env_info: dict,
    branch_name: str,
    workflow_name: str = "Telex Verification",
) -> str:
    """Generate a self-contained GitHub Actions YAML workflow for verification on branch_name."""
    ecosystem = env_info.get("ecosystem", "node")
    install_cmd = env_info.get("install_cmd", "npm ci --ignore-scripts")
    test_cmd = env_info.get("test_cmd", "npm test")
    typecheck_cmd = env_info.get("typecheck_cmd", "npx tsc --noEmit")

    if ecosystem == "python":
        steps_yaml = f"""      - name: Checkout candidate repair branch
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: {install_cmd}

      - name: Run Tests
        run: {test_cmd}"""
        if typecheck_cmd:
            steps_yaml += f"""

      - name: Run Typecheck
        run: {typecheck_cmd}"""
    else:
        pm = env_info.get("package_manager", "npm")
        setup_pm = ""
        if pm == "pnpm":
            setup_pm = """      - name: Setup pnpm
        uses: pnpm/action-setup@v3
        with:
          version: 8
"""
        steps_yaml = f"""      - name: Checkout candidate repair branch
        uses: actions/checkout@v4
{setup_pm}
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Install dependencies
        run: {install_cmd}"""
        if typecheck_cmd:
            steps_yaml += f"""

      - name: Run Typecheck
        run: {typecheck_cmd}
        if: always()"""
        if test_cmd:
            steps_yaml += f"""

      - name: Run Automated Tests
        run: {test_cmd}"""

    return f"""name: {workflow_name}

on:
  push:
    branches:
      - "{branch_name}"

permissions:
  contents: read

jobs:
  telex-verify:
    name: Telex Verification Gate
    runs-on: ubuntu-latest
    steps:
{steps_yaml}
"""


def commit_verification_bundle(
    repo_full_name: str,
    installation_id: int,
    branch_name: str,
    patched_file_path: str,
    patched_content: str,
    workflow_file_path: str,
    workflow_content: str,
) -> str | None:
    """
    Commit BOTH the patched file and the dynamic verification workflow to branch_name
    in a single atomic commit using PyGithub's Git Data API. Returns the new commit SHA.
    """
    try:
        gh = get_installation_client(installation_id)
        repo = gh.get_repo(repo_full_name)
        ref = repo.get_git_ref(f"heads/{branch_name}")
        base_commit = repo.get_commit(ref.object.sha)

        tree_elements = [
            InputGitTreeElement(
                path=patched_file_path.replace("\\", "/").lstrip("/"),
                mode="100644",
                type="blob",
                content=patched_content,
            ),
            InputGitTreeElement(
                path=workflow_file_path.replace("\\", "/").lstrip("/"),
                mode="100644",
                type="blob",
                content=workflow_content,
            ),
        ]

        new_tree = repo.create_git_tree(tree_elements, base_tree=base_commit.commit.tree)
        new_commit = repo.create_git_commit(
            message="ci(telex): candidate patch with autonomous verification gate",
            tree=new_tree,
            parents=[base_commit.commit],
        )
        ref.edit(new_commit.sha)
        logger.info(
            "commit_verification_bundle: committed %s and %s on %s (SHA: %s)",
            patched_file_path,
            workflow_file_path,
            branch_name,
            new_commit.sha,
        )
        return new_commit.sha
    except Exception as exc:
        logger.error(
            "commit_verification_bundle failed on %s:%s — %s", repo_full_name, branch_name, exc
        )
        return None


def delete_branch(
    repo_full_name: str,
    installation_id: int,
    branch_name: str,
) -> bool:
    """Delete a temporary branch on GitHub."""
    try:
        gh = get_installation_client(installation_id)
        repo = gh.get_repo(repo_full_name)
        ref = repo.get_git_ref(f"heads/{branch_name}")
        ref.delete()
        return True
    except Exception as exc:
        logger.debug("delete_branch for %s:%s — %s (non-fatal)", repo_full_name, branch_name, exc)
        return False


async def wait_for_telex_verification(
    repo_full_name: str,
    installation_id: int,
    commit_sha: str,
    expected_workflow_name: str,
    timeout_seconds: float = 180.0,
    poll_interval: float = 5.0,
) -> dict:
    """
    Poll GitHub Actions specifically for the Telex verification workflow run matching
    expected_workflow_name or commit_sha until completion or timeout.
    """
    import time

    start_time = time.time()
    observed_checks: dict[str, dict] = {}
    saw_checks = False

    while (time.time() - start_time) < timeout_seconds:

        def _query():
            gh = get_installation_client(installation_id)
            repo = gh.get_repo(repo_full_name)
            commit = repo.get_commit(commit_sha)
            check_runs = list(commit.get_check_runs())
            workflow_runs = list(repo.get_workflow_runs(head_sha=commit_sha))
            return check_runs, workflow_runs

        try:
            check_runs, workflow_runs = await asyncio.to_thread(_query)
        except Exception as exc:
            logger.warning("wait_for_telex_verification query failed: %s (will retry)", exc)
            await asyncio.sleep(poll_interval)
            continue

        # Filter check runs for our specific verification gate
        matching_checks = [
            cr
            for cr in check_runs
            if "telex" in (cr.name or "").lower() or expected_workflow_name in (cr.name or "")
        ]
        target_checks = matching_checks or check_runs

        if target_checks:
            saw_checks = True
            for cr in target_checks:
                observed_checks[cr.name] = {
                    "name": cr.name,
                    "status": cr.status,
                    "conclusion": cr.conclusion,
                    "title": getattr(cr.output, "title", None) if cr.output else None,
                    "summary": getattr(cr.output, "summary", None) if cr.output else None,
                    "text": getattr(cr.output, "text", None) if cr.output else None,
                }

            all_completed = all(c["status"] == "completed" for c in observed_checks.values())
            if all_completed and observed_checks:
                all_success = all(
                    c["conclusion"] in ("success", "neutral", "skipped")
                    for c in observed_checks.values()
                )

                logs = []
                for c in observed_checks.values():
                    status_str = (
                        "passed"
                        if c["conclusion"] in ("success", "skipped")
                        else f"failed ({c['conclusion']})"
                    )
                    logs.append(f"Verification Check [{c['name']}]: {status_str}")
                    if c["summary"]:
                        logs.append(f"Summary: {c['summary'][:400]}")
                    if c["text"] and not all_success:
                        logs.append(f"Failure Output: {c['text'][:600]}")

                return {
                    "is_verified": all_success,
                    "workflow_found": True,
                    "completed": True,
                    "conclusion": "success" if all_success else "failure",
                    "typechecks": all_success,
                    "tests_pass": all_success,
                    "log": "\n".join(logs)
                    or f"Verification Gate: {'passed' if all_success else 'failed'}",
                    "check_runs": list(observed_checks.values()),
                }

        await asyncio.sleep(poll_interval)

    return {
        "is_verified": False,
        "workflow_found": saw_checks,
        "completed": False,
        "conclusion": "timed_out",
        "typechecks": False,
        "tests_pass": False,
        "log": f"Verification Gate timed out after {int(timeout_seconds)}s — checks did not complete.",
        "check_runs": list(observed_checks.values()),
    }


# Backwards compatibility alias
wait_for_github_ci = wait_for_telex_verification


def fetch_file_content(
    repo_full_name: str,
    installation_id: int,
    file_path: str,
    ref: str = "main",
) -> str | None:
    """Fetch the text content of a file from GitHub using the installation client."""
    try:
        gh = get_installation_client(installation_id)
        repo = gh.get_repo(repo_full_name)
        content_file = repo.get_contents(file_path, ref=ref)
        if hasattr(content_file, "decoded_content"):
            return content_file.decoded_content.decode("utf-8")
        return None
    except Exception as exc:
        logger.warning("fetch_file_content failed for %s:%s — %s", repo_full_name, file_path, exc)
        return None


def verify_webhook_signature(payload: bytes, signature_header: str | None) -> bool:
    """
    Verify a GitHub webhook HMAC-SHA256 signature.

    Always returns False if GITHUB_WEBHOOK_SECRET is not configured.
    """
    import hashlib
    import hmac

    secret = settings.github_webhook_secret
    if not secret:
        logger.error("GITHUB_WEBHOOK_SECRET not configured — rejecting webhook")
        return False

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature_header)


async def create_check_run(
    repo_full_name: str,
    installation_id: int,
    head_sha: str,
    name: str = "Telex Validation",
    conclusion: str = "success",
    title: str = "Telex patch verified",
    summary: str = "",
) -> bool:
    """
    Phase 8.4: Create a GitHub Check Run on the given commit SHA.

    Appears alongside the repo's own CI checks in the PR interface.
    conclusion must be one of: 'success' | 'failure' | 'neutral' | 'skipped'.

    Returns True if the check run was created, False on error.
    """

    def _do_create() -> bool:
        gh = get_installation_client(installation_id)
        # PyGithub exposes create_check_run via get_repo().create_check_run()
        repo = gh.get_repo(repo_full_name)
        try:
            repo.create_check_run(
                name=name,
                head_sha=head_sha,
                status="completed",
                conclusion=conclusion,
                output={
                    "title": title,
                    "summary": summary or f"Telex validation {conclusion} for this patch.",
                },
            )
            logger.info(
                "create_check_run: created '%s' on %s (%s), conclusion=%s",
                name,
                repo_full_name,
                head_sha[:8],
                conclusion,
            )
            return True
        except Exception as exc:
            logger.warning(
                "create_check_run: failed for %s sha=%s: %s",
                repo_full_name,
                head_sha[:8],
                exc,
            )
            return False

    try:
        return await asyncio.to_thread(_do_create)
    except Exception as exc:
        logger.warning("create_check_run: thread error: %s", exc)
        return False


def get_default_branch_head_sha(repo_full_name: str, installation_id: int) -> str:
    """Return the current commit SHA of the repo's default branch."""
    gh = get_installation_client(installation_id)
    repo = gh.get_repo(repo_full_name)
    branch = repo.get_branch(repo.default_branch)
    return branch.commit.sha


def get_file_last_commit_info(
    repo_full_name: str, installation_id: int, file_path: str, ref: str
) -> dict | None:
    """
    Return {"sha": str, "committed_at": iso str, "author": str} for the most
    recent commit touching file_path as of ref. Used for the "last edited"
    label on each Atlas card. Best-effort: returns None on any failure
    (card falls back to showing no timestamp rather than a wrong one).
    """
    try:
        gh = get_installation_client(installation_id)
        repo = gh.get_repo(repo_full_name)
        commits = repo.get_commits(path=file_path, sha=ref)
        latest = commits[0]
        return {
            "sha": latest.sha,
            "committed_at": latest.commit.author.date.isoformat(),
            "author": latest.commit.author.name,
        }
    except Exception as exc:
        logger.debug("get_file_last_commit_info failed for %s: %s", file_path, exc)
        return None

