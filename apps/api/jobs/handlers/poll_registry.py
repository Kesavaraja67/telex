"""
poll_registry handler — checks npm or PyPI for new versions of tracked packages.

Payload shape:
    { "package_id": "<uuid>", "package_name": "openai", "ecosystem": "npm" }
"""

import logging
import uuid

logger = logging.getLogger(__name__)


async def run(payload: dict) -> None:
    from sqlalchemy import select

    from db.models import PackageVersion
    from db.session import AsyncSessionLocal
    from jobs.queue import enqueue_job
    from services.registry_watcher import fetch_latest_version

    package_id = uuid.UUID(payload["package_id"])
    package_name = payload["package_name"]
    ecosystem = payload.get("ecosystem", "npm").strip().lower()

    logger.info("poll_registry: checking %s (%s)", package_name, ecosystem)

    latest = await fetch_latest_version(package_name, ecosystem=ecosystem)
    if not latest or not latest.get("version"):
        logger.warning("poll_registry: no version info for %s (%s)", package_name, ecosystem)
        return

    new_version = latest["version"]
    raw_changelog = latest.get("changelog_raw") or latest.get("changelog_url") or ""

    async with AsyncSessionLocal() as session:
        # Idempotent: only create a new PackageVersion row if this version is new
        existing = await session.execute(
            select(PackageVersion).where(
                PackageVersion.package_id == package_id,
                PackageVersion.version == new_version,
            )
        )
        if existing.scalar_one_or_none():
            logger.info("poll_registry: %s@%s already known", package_name, new_version)
            return

        # Change 03: Find previous known package version for explicit context
        prev_res = await session.execute(
            select(PackageVersion)
            .where(PackageVersion.package_id == package_id)
            .order_by(
                PackageVersion.published_at.desc().nullslast(),
                PackageVersion.id.desc(),
            )
            .limit(1)
        )
        prev_pv = prev_res.scalar_one_or_none()
        old_version = prev_pv.version if prev_pv else None

        # Change 02: Persist changelog_raw metadata
        pv = PackageVersion(
            package_id=package_id,
            version=new_version,
            published_at=latest.get("published_at"),
            changelog_raw=raw_changelog,
        )
        session.add(pv)
        await session.commit()
        await session.refresh(pv)

        # Enqueue change extraction with explicit old/new version and changelog
        await enqueue_job(
            session,
            "extract_changes",
            {
                "package_version_id": str(pv.id),
                "package_name": package_name,
                "ecosystem": ecosystem,
                "old_version": old_version or "unknown",
                "new_version": new_version,
                "changelog": raw_changelog,
            },
        )

    logger.info(
        "poll_registry: found new version %s@%s (previous: %s)",
        package_name,
        new_version,
        old_version or "none",
    )

