"""
extract_changes handler — feeds changelog to Gemini, stores detected_changes rows.

Payload shape:
    {
        "package_version_id": "<uuid>",
        "package_name": "openai",
        "old_version": "3.2.0",   # optional — used for richer prompts
        "changelog": "..."        # optional — if omitted, fetched from npm
    }
"""
import logging
import uuid

logger = logging.getLogger(__name__)


async def run(payload: dict) -> None:
    from db.session import AsyncSessionLocal
    from db.models import PackageVersion, DetectedChange, RepoPackage, Package
    from services.change_extractor import extract_breaking_changes
    from jobs.queue import enqueue_job
    from sqlalchemy import select

    package_version_id = uuid.UUID(payload["package_version_id"])
    package_name = payload["package_name"]

    async with AsyncSessionLocal() as session:
        pv = await session.get(PackageVersion, package_version_id)
        if pv is None:
            logger.error("extract_changes: PackageVersion %s not found", package_version_id)
            return

        # Fetch changelog if not supplied in payload
        changelog = payload.get("changelog") or pv.changelog_raw or ""
        if not changelog:
            logger.warning("extract_changes: no changelog for %s@%s", package_name, pv.version)

        old_version = payload.get("old_version", "unknown")

        changes = await extract_breaking_changes(
            package_name=package_name,
            old_version=old_version,
            new_version=pv.version,
            changelog=changelog,
        )

        if not changes:
            logger.info("extract_changes: no breaking changes found in %s@%s", package_name, pv.version)
            pv.scanned_at = __import__("datetime").datetime.utcnow()
            await session.commit()
            return

        for change in changes:
            dc = DetectedChange(
                package_version_id=package_version_id,
                change_type=change.get("change_type", "signature_change"),
                symbol_old=change.get("symbol_old", ""),
                symbol_new=change.get("symbol_new"),
                description=change.get("description", ""),
                confidence=float(change.get("confidence", 0.8)),
            )
            session.add(dc)

        pv.scanned_at = __import__("datetime").datetime.utcnow()
        await session.commit()

        # Read scalars before session closes to avoid DetachedInstanceError
        pv_version = pv.version

        # Enqueue scan_repo for every repo that tracks this package
        pkg = await session.get(Package, pv.package_id)
        repo_pkgs = await session.execute(
            select(RepoPackage).where(RepoPackage.package_id == pv.package_id)
        )
        for rp in repo_pkgs.scalars():
            await enqueue_job(
                session,
                "scan_repo",
                {
                    "repo_id": str(rp.repo_id),
                    "package_version_id": str(package_version_id),
                },
            )

    logger.info("extract_changes: stored %d changes for %s@%s", len(changes), package_name, pv_version)
