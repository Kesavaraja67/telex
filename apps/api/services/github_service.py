"""
GitHub App service — Section 7.7.

Handles:
  - Installation-scoped API clients via GitHub App JWT
  - Branch creation, file commits, and PR opening
"""
import asyncio
import logging
from typing import Optional, Any

from config import settings

logger = logging.getLogger(__name__)


try:
    from github import Github, GithubIntegration, GithubException, InputGitTreeElement  # type: ignore[import]
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

    private_key = settings.github_app_private_key.replace("\\n", "\n").strip('"\'')
    integration = GithubIntegration(
        int(settings.github_app_id),
        private_key,
    )
    return integration.get_access_token(installation_id).token


def get_installation_client(installation_id: int):
    """
    Return an authenticated PyGithub client scoped to a specific installation.
    """
    if Github is None:
        raise RuntimeError("PyGithub not installed — run: pip install PyGithub")

    token = get_installation_token(installation_id)
    return Github(token)


async def open_patch_pr(
    repo_full_name: str,
    installation_id: int,
    branch_name: str,
    patches: list[dict],
    summary: str,
) -> tuple[str, int]:
    """
    Open a pull request on `repo_full_name` with the given patches applied.

    Each entry in `patches` must have:
        - file_path: str
        - new_content: str   (full file content after applying the patch)
        - package_name: str
        - new_version: str

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
        try:
            pr = repo.create_pull(
                title=f"chore(deps): auto-patch for {patches[0]['package_name']}@{patches[0]['new_version']}",
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

        logger.info("PR #%d on %s: %s", pr.number, repo_full_name, pr.html_url)
        return pr.html_url, pr.number

    return await asyncio.to_thread(_do_github_work)


def apply_diff_to_content(file_path: str, original_content: str, diff: str) -> tuple[bool, str, str]:
    """
    Apply a unified diff to original_content using an isolated micro git process.
    Takes ~10ms and < 2 MB RAM (zero full repo cloning, zero npm ci).

    Returns:
        (success: bool, new_content: str, log: str)
    """
    import os
    import stat
    import subprocess
    import tempfile
    import shutil

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

        with open(full_target, "r", encoding="utf-8") as f:
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
) -> Optional[str]:
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
        logger.warning("create_or_update_branch failed for %s:%s — %s", repo_full_name, branch_name, exc)
        return None


def push_file_to_branch(
    repo_full_name: str,
    installation_id: int,
    branch_name: str,
    file_path: str,
    content: str,
    commit_message: str,
) -> Optional[str]:
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
        logger.warning("push_file_to_branch failed for %s:%s on %s — %s", repo_full_name, file_path, branch_name, exc)
        return None


def detect_repo_environment(
    repo_full_name: str,
    installation_id: int,
    ref: str = "main",
) -> dict:
    """
    Inspect target repository via GitHub API to detect ecosystem, package manager, and test scripts.
    """
    import json
    env_info = {
        "ecosystem": "node",
        "package_manager": "npm",
        "install_cmd": "npm ci",
        "test_cmd": "npm test",
        "typecheck_cmd": "npx tsc --noEmit",
        "has_test": True,
        "has_typecheck": True,
    }

    try:
        gh = get_installation_client(installation_id)
        repo = gh.get_repo(repo_full_name)
        root_contents = repo.get_contents("", ref=ref)
        file_names = {item.name for item in root_contents} if isinstance(root_contents, list) else set()

        if "package.json" in file_names:
            pkg_file = repo.get_contents("package.json", ref=ref)
            if hasattr(pkg_file, "decoded_content"):
                try:
                    pkg_json = json.loads(pkg_file.decoded_content.decode("utf-8"))
                    scripts = pkg_json.get("scripts", {})

                    if "pnpm-lock.yaml" in file_names:
                        pm = "pnpm"
                        install_cmd = "pnpm install --frozen-lockfile"
                        test_cmd = "pnpm test" if "test" in scripts else ""
                        typecheck_cmd = "pnpm run typecheck" if "typecheck" in scripts else "pnpm exec tsc --noEmit"
                    elif "yarn.lock" in file_names:
                        pm = "yarn"
                        install_cmd = "yarn install --frozen-lockfile"
                        test_cmd = "yarn test" if "test" in scripts else ""
                        typecheck_cmd = "yarn typecheck" if "typecheck" in scripts else "yarn tsc --noEmit"
                    else:
                        pm = "npm"
                        install_cmd = "npm ci"
                        test_cmd = "npm test" if "test" in scripts else ""
                        typecheck_cmd = "npm run typecheck" if "typecheck" in scripts else "npx tsc --noEmit"

                    has_tsconfig = "tsconfig.json" in file_names or "tsconfig.base.json" in file_names
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
            install_cmd = "pip install -r requirements.txt" if "requirements.txt" in file_names else "pip install -e ."
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
        logger.warning("detect_repo_environment failed for %s: %s (using default node/npm)", repo_full_name, exc)
        return env_info


def generate_telex_verification_workflow(
    env_info: dict,
    branch_name: str,
    workflow_name: str = "Telex Verification",
) -> str:
    """Generate a self-contained GitHub Actions YAML workflow for verification on branch_name."""
    ecosystem = env_info.get("ecosystem", "node")
    install_cmd = env_info.get("install_cmd", "npm ci")
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
) -> Optional[str]:
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
        logger.info("commit_verification_bundle: committed %s and %s on %s (SHA: %s)", patched_file_path, workflow_file_path, branch_name, new_commit.sha)
        return new_commit.sha
    except Exception as exc:
        logger.error("commit_verification_bundle failed on %s:%s — %s", repo_full_name, branch_name, exc)
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
            cr for cr in check_runs
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
                all_success = all(c["conclusion"] in ("success", "neutral", "skipped") for c in observed_checks.values())

                logs = []
                for c in observed_checks.values():
                    status_str = "passed" if c["conclusion"] in ("success", "skipped") else f"failed ({c['conclusion']})"
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
                    "log": "\n".join(logs) or f"Verification Gate: {'passed' if all_success else 'failed'}",
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
) -> Optional[str]:
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


def verify_webhook_signature(payload: bytes, signature_header: Optional[str]) -> bool:
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
