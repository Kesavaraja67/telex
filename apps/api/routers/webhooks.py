"""
GitHub webhook receiver — Section 7.7.

Verifies HMAC-SHA256 signatures before processing any payload.
"""
import logging
from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
from db.session import AsyncSessionLocal
from db.models import Installation, Repo
from services.github_service import verify_webhook_signature
from sqlalchemy import select

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/github", status_code=200)
async def github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
):
    """
    Receive GitHub App webhook events.

    Always verifies HMAC-SHA256 signature — returns 401 on failure.
    Handles: installation.created, push (future).
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
        await _handle_installation_created(payload)

    elif event == "installation" and action == "deleted":
        await _handle_installation_deleted(payload)

    elif event == "push":
        # Future: trigger a re-scan on push to default branch
        pass

    return {"ok": True}


async def _handle_installation_created(payload: dict) -> None:
    """Create Installation and Repo rows when the GitHub App is installed."""
    inst_data = payload.get("installation", {})
    repos_data = payload.get("repositories", [])

    async with AsyncSessionLocal() as session:
        # Upsert installation
        existing = await session.execute(
            select(Installation).where(
                Installation.github_installation_id == inst_data["id"]
            )
        )
        inst = existing.scalar_one_or_none()
        if inst is None:
            inst = Installation(
                github_installation_id=inst_data["id"],
                account_login=inst_data["account"]["login"],
                account_type=inst_data["account"]["type"],
            )
            session.add(inst)
            await session.flush()

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


async def _handle_installation_deleted(payload: dict) -> None:
    """Mark repos inactive when the GitHub App is uninstalled."""
    inst_data = payload.get("installation", {})
    async with AsyncSessionLocal() as session:
        inst = await session.execute(
            select(Installation).where(
                Installation.github_installation_id == inst_data["id"]
            )
        )
        inst = inst.scalar_one_or_none()
        if inst:
            repos = await session.execute(
                select(Repo).where(Repo.installation_id == inst.id)
            )
            for repo in repos.scalars():
                repo.is_active = False
            await session.commit()
    logger.info("Installation deleted: %s", inst_data.get("account", {}).get("login"))
