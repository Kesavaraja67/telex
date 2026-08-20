"""
GitHub App service — Section 7.7.

Handles:
  - Installation-scoped API clients via GitHub App JWT
  - Branch creation, file commits, and PR opening
"""
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


def get_installation_client(installation_id: int):
    """
    Return an authenticated PyGithub client scoped to a specific installation.
    """
    try:
        from github import Github, GithubIntegration
    except ImportError:
        raise RuntimeError("PyGithub not installed — run: pip install PyGithub")

    private_key = settings.github_app_private_key.replace("\\n", "\n").strip('"\'')
    integration = GithubIntegration(
        int(settings.github_app_id),
        private_key,
    )
    token = integration.get_access_token(installation_id).token
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
    gh = get_installation_client(installation_id)
    repo = gh.get_repo(repo_full_name)
    base_branch = repo.get_branch(repo.default_branch)

    # Create the patch branch from the current HEAD of default branch
    repo.create_git_ref(
        ref=f"refs/heads/{branch_name}",
        sha=base_branch.commit.sha,
    )

    for patch in patches:
        content_file = repo.get_contents(patch["file_path"], ref=branch_name)
        repo.update_file(
            patch["file_path"],
            f"fix: update for {patch['package_name']}@{patch['new_version']}",
            patch["new_content"],
            content_file.sha,  # type: ignore[arg-type]
            branch=branch_name,
        )

    if not patches:
        raise ValueError("open_patch_pr called with empty patches list")

    pr = repo.create_pull(
        title=f"chore(deps): auto-patch for {patches[0]['package_name']}@{patches[0]['new_version']}",
        body=summary,
        head=branch_name,
        base=repo.default_branch,
    )
    logger.info("Opened PR #%d on %s: %s", pr.number, repo_full_name, pr.html_url)
    return pr.html_url, pr.number


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
