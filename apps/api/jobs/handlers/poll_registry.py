"""
poll_registry handler — checks npm for new versions of tracked packages.

Payload shape:
    { "package_id": "<uuid>", "package_name": "openai", "ecosystem": "npm" }
"""
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


async def run(payload: dict) -> None:
    from db.session import AsyncSessionLocal
    from db.models import Package, PackageVersion
    from services.registry_watcher import fetch_latest_version
    from jobs.queue import enqueue_job
    from sqlalchemy import select

    package_id = uuid.UUID(payload["package_id"])
    package_name = payload["package_name"]

    logger.info("poll_registry: checking %s", package_name)

    latest = await fetch_latest_version(package_name)
    if not latest or not latest["version"]:
        logger.warning("poll_registry: no version info for %s", package_name)
        return

    async with AsyncSessionLocal() as session:
        # Idempotent: only create a new PackageVersion row if this version is new
        existing = await session.execute(
            select(PackageVersion).where(
                PackageVersion.package_id == package_id,
                PackageVersion.version == latest["version"],
            )
        )
        if existing.scalar_one_or_none():
            logger.info("poll_registry: %s@%s already known", package_name, latest["version"])
            return

        pv = PackageVersion(
            package_id=package_id,
            version=latest["version"],
            published_at=latest.get("published_at"),
        )
        session.add(pv)
        await session.commit()
        await session.refresh(pv)

        # Enqueue change extraction for this new version
        await enqueue_job(
            session,
            "extract_changes",
            {
                "package_version_id": str(pv.id),
                "package_name": package_name,
            },
        )

    logger.info("poll_registry: found new version %s@%s", package_name, latest["version"])
