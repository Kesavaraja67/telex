"""
GitHub webhook receiver — Section 7.7.

Verifies HMAC-SHA256 signatures before processing any payload.
"""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from sqlalchemy import select

from db.models import Installation, Job, PullRequest, Repo, User
from db.session import AsyncSessionLocal
from jobs.queue import enqueue_job
from services.github_service import (
    ensure_repo_labels,
    get_installation_client,
    verify_webhook_signature,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


async def _bootstrap_repo_labels(installation_id: int, repo_full_names: list[str]) -> None:
    """Ensure semantic-risk and needs-human-review labels exist on each repo.

    Runs each repo synchronously in a thread. A failure on one repo never
    prevents the others from being processed, and never raises to the caller.
    """
    if not repo_full_names:
        return

    def _sync_bootstrap() -> None:
        try:
            gh = get_installation_client(installation_id)
        except Exception as exc:
            logger.warning(
                "_bootstrap_repo_labels: could not get client for installation %s: %s",
                installation_id,
                exc,
            )
            return
        for name in repo_full_names:
            try:
                ensure_repo_labels(gh.get_repo(name))
            except Exception as exc:
                logger.warning("_bootstrap_repo_labels: failed for %s: %s", name, exc)

    await asyncio.to_thread(_sync_bootstrap)


@router.post("/github", status_code=200)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
):
    """
    Receive GitHub App webhook events.

    Always verifies HMAC-SHA256 signature — returns 401 on failure.
    Handles: installation.created, installation.deleted, installation_repositories, pull_request, push.
    """
    raw_body = await request.body()

    if not verify_webhook_signature(raw_body, x_hub_signature_256):
        logger.warning("Webhook signature verification failed")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    action = payload.get("action")
    event = x_github_event

    logger.info("GitHub webhook: event=%s action=%s", event, action)

    if event == "installation" and action == "created":
        await _handle_installation_created(payload, background_tasks)

    elif event == "installation" and action == "deleted":
        await _handle_installation_deleted(payload)

    elif event == "installation_repositories":
        await _handle_installation_repositories(payload, background_tasks)

    elif event == "pull_request":
        await _handle_pull_request(payload)

    elif event == "push":
        await _handle_push(payload)

    return {"ok": True}


async def _handle_installation_created(payload: dict, background_tasks: BackgroundTasks) -> None:
    """Create Installation and Repo rows when the GitHub App is installed."""
    inst_data = payload.get("installation", {})
    repos_data = payload.get("repositories", [])

    async with AsyncSessionLocal() as session:
        # Upsert installation
        existing = await session.execute(
            select(Installation).where(Installation.github_installation_id == inst_data["id"])
        )
        inst = existing.scalar_one_or_none()
        if inst is None:
            inst = Installation(
                github_installation_id=inst_data["id"],
                account_login=inst_data["account"]["login"],
                account_type=inst_data["account"]["type"],
            )
            sender_id = payload.get("sender", {}).get("id")
            if sender_id:
                user_res = await session.execute(select(User).where(User.github_id == sender_id))
                user = user_res.scalar_one_or_none()
                if user:
                    inst.installed_by = user.id
            session.add(inst)
            await session.flush()
        elif inst.installed_by is None:
            sender_id = payload.get("sender", {}).get("id")
            if sender_id:
                user_res = await session.execute(select(User).where(User.github_id == sender_id))
                user = user_res.scalar_one_or_none()
                if user:
                    inst.installed_by = user.id

        # Upsert repos
        for repo_data in repos_data:
            existing_repo = await session.execute(
                select(Repo).where(Repo.github_repo_id == repo_data["id"])
            )
            if existing_repo.scalar_one_or_none() is None:
                repo = Repo(
                    installation_id=inst.id,
                    github_repo_id=repo_data["id"],
                    full_name=repo_data["full_name"],
                )
                session.add(repo)

        await session.commit()
    logger.info("Installation created: %s", inst_data.get("account", {}).get("login"))
    background_tasks.add_task(
        _bootstrap_repo_labels,
        inst_data["id"],
        [r["full_name"] for r in repos_data],
    )


async def _handle_installation_repositories(
    payload: dict, background_tasks: BackgroundTasks
) -> None:
    """Handle repositories added or removed from an existing installation."""
    inst_data = payload.get("installation", {})
    repos_added = payload.get("repositories_added", [])
    repos_removed = payload.get("repositories_removed", [])

    async with AsyncSessionLocal() as session:
        existing = await session.execute(
            select(Installation).where(Installation.github_installation_id == inst_data["id"])
        )
        inst = existing.scalar_one_or_none()
        if inst is None:
            inst = Installation(
                github_installation_id=inst_data["id"],
                account_login=inst_data.get("account", {}).get("login", "unknown"),
                account_type=inst_data.get("account", {}).get("type", "User"),
            )
            session.add(inst)
            await session.flush()

        for repo_data in repos_added:
            existing_repo = await session.execute(
                select(Repo).where(Repo.github_repo_id == repo_data["id"])
            )
            r = existing_repo.scalar_one_or_none()
            if r is None:
                repo = Repo(
                    installation_id=inst.id,
                    github_repo_id=repo_data["id"],
                    full_name=repo_data["full_name"],
                    is_active=True,
                )
                session.add(repo)
            else:
                r.is_active = True

        for repo_data in repos_removed:
            existing_repo = await session.execute(
                select(Repo).where(Repo.github_repo_id == repo_data["id"])
            )
            r = existing_repo.scalar_one_or_none()
            if r:
                r.is_active = False

        await session.commit()
    logger.info("Installation repositories updated for installation %s", inst_data.get("id"))
    background_tasks.add_task(
        _bootstrap_repo_labels,
        inst_data["id"],
        [r["full_name"] for r in repos_added],
    )


async def _handle_installation_deleted(payload: dict) -> None:
    """Mark repos inactive when the GitHub App is uninstalled."""
    inst_data = payload.get("installation", {})
    async with AsyncSessionLocal() as session:
        inst = await session.execute(
            select(Installation).where(Installation.github_installation_id == inst_data["id"])
        )
        inst = inst.scalar_one_or_none()
        if inst:
            repos = await session.execute(select(Repo).where(Repo.installation_id == inst.id))
            for repo in repos.scalars():
                repo.is_active = False
            await session.commit()
    logger.info("Installation deleted: %s", inst_data.get("account", {}).get("login"))


async def _handle_pull_request(payload: dict) -> None:
    """Track pull request merge and closure status for acceptance rate tracking."""
    action = payload.get("action")
    pr_data = payload.get("pull_request", {})
    repo_data = payload.get("repository", {})

    pr_number = pr_data.get("number")
    github_repo_id = repo_data.get("id")

    if not pr_number or not github_repo_id:
        return

    async with AsyncSessionLocal() as session:
        repo_res = await session.execute(select(Repo).where(Repo.github_repo_id == github_repo_id))
        repo = repo_res.scalar_one_or_none()
        if not repo:
            return

        pr_res = await session.execute(
            select(PullRequest).where(
                PullRequest.repo_id == repo.id,
                PullRequest.github_pr_number == pr_number,
            )
        )
        pr = pr_res.scalar_one_or_none()
        if not pr:
            return

        if action == "reopened":
            pr.status = "open"
            pr.closed_at = None
            pr.merged = False
            pr.merged_at = None
            await session.commit()
            logger.info("PullRequest %s (#%s) reopened: status=open", pr.id, pr_number)
            return

        if action == "closed":
            is_merged = bool(pr_data.get("merged", False))
            pr.status = "merged" if is_merged else "closed"
            pr.merged = is_merged

            merged_at_str = pr_data.get("merged_at")
            if merged_at_str and is_merged:
                try:
                    pr.merged_at = datetime.fromisoformat(merged_at_str.replace("Z", "+00:00"))
                except Exception:
                    pr.merged_at = datetime.now(timezone.utc)
            elif is_merged:
                pr.merged_at = datetime.now(timezone.utc)

            closed_at_str = pr_data.get("closed_at")
            if closed_at_str:
                try:
                    pr.closed_at = datetime.fromisoformat(closed_at_str.replace("Z", "+00:00"))
                except Exception:
                    pr.closed_at = datetime.now(timezone.utc)
            else:
                pr.closed_at = datetime.now(timezone.utc)

            await session.commit()
            logger.info(
                "PullRequest %s (#%s) updated: status=%s, merged=%s",
                pr.id,
                pr_number,
                pr.status,
                pr.merged,
            )


async def _handle_push(payload: dict) -> None:
    """Handle push to repository default branch and trigger incremental atlas update."""
    repo_data = payload.get("repository", {})
    github_repo_id = repo_data.get("id")
    if not github_repo_id:
        return

    ref = payload.get("ref", "")
    default_branch = repo_data.get("default_branch", "main")
    # Only process pushes to the default branch
    if ref != f"refs/heads/{default_branch}":
        logger.debug("Push ignored for non-default branch: %s", ref)
        return

    head_sha = payload.get("after") or payload.get("head_commit", {}).get("id")
    if not head_sha or head_sha == "0000000000000000000000000000000000000000":
        return

    commits = payload.get("commits", [])
    truncated = payload.get("truncated", False) or len(commits) >= 20
    base_sha = payload.get("before")
    if base_sha == "0000000000000000000000000000000000000000":
        base_sha = None

    # Extract added, modified, removed files across commits
    added: set[str] = set()
    modified: set[str] = set()
    removed: set[str] = set()
    for commit in commits:
        added.update(commit.get("added", []))
        modified.update(commit.get("modified", []))
        removed.update(commit.get("removed", []))

    async with AsyncSessionLocal() as session:
        repo_res = await session.execute(select(Repo).where(Repo.github_repo_id == github_repo_id))
        repo = repo_res.scalar_one_or_none()
        if not repo or not repo.is_active:
            return

        # Deduplicate active atlas jobs for this repo & commit_sha
        existing_jobs_res = await session.execute(
            select(Job).where(
                Job.job_type.in_(["update_atlas_graph", "build_atlas_graph"]),
                Job.status.in_(["queued", "running"]),
            )
        )
        for j in existing_jobs_res.scalars().all():
            if (
                isinstance(j.payload, dict)
                and str(j.payload.get("repo_id")) == str(repo.id)
                and j.payload.get("commit_sha") == head_sha
            ):
                logger.info(
                    "Skipping duplicate atlas job for %s @ %s", repo.full_name, head_sha[:8]
                )
                return

        if truncated:
            await enqueue_job(
                session,
                "build_atlas_graph",
                {
                    "repo_id": str(repo.id),
                    "commit_sha": head_sha,
                    "expected_head_sha": base_sha,
                    "base_sha": base_sha,
                },
            )
            await session.commit()
            logger.info(
                "Enqueued full build_atlas_graph for %s @ %s (truncated/large push: %d commits)",
                repo.full_name,
                head_sha[:8],
                len(commits),
            )
            return

        # Enqueue update_atlas_graph job
        job_payload = {
            "repo_id": str(repo.id),
            "commit_sha": head_sha,
            "base_sha": base_sha,
            "expected_head_sha": base_sha,
            "changed": {
                "added": sorted(added),
                "modified": sorted(modified),
                "removed": sorted(removed),
            },
        }
        await enqueue_job(session, "update_atlas_graph", job_payload)
        await session.commit()
        logger.info(
            "Enqueued update_atlas_graph for %s @ %s (base %s, +%d ~%d -%d)",
            repo.full_name,
            head_sha[:8],
            base_sha[:8] if base_sha else "none",
            len(added),
            len(modified),
            len(removed),
        )
