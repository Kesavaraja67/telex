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
    from github import Github, GithubIntegration, GithubException  # type: ignore[import]
except ImportError:
    Github: Any = None
    GithubIntegration: Any = None
    GithubException: Any = Exception


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
