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


def _publish_change_detected(repo_id_str, dc_id_str, payload_dict):
    """Fire-and-forget coroutine helper called after commit."""
    import asyncio
    from services.event_bus import event_bus

    async def _do():
        try:
            await event_bus.publish({
                "event_type": "change_detected",
                "repo_id": repo_id_str,
                "detected_change_id": dc_id_str,
                **payload_dict,
            })
        except Exception as exc:
            logger.warning("event_bus publish change_detected failed (non-fatal): %s", exc)

    loop = asyncio.get_event_loop()
    loop.create_task(_do())


async def run(payload: dict) -> None:
    from sqlalchemy import select

    from db.models import DetectedChange, PackageVersion, RepoPackage
    from db.session import AsyncSessionLocal
    from jobs.queue import enqueue_job
    from services.change_extractor import extract_breaking_changes

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
            logger.info(
                "extract_changes: no breaking changes found in %s@%s", package_name, pv.version
            )
            pv.scanned_at = __import__("datetime").datetime.utcnow()
            await session.commit()
            return

        from services.incident_events import record_event

        dc_rows = []
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
            dc_rows.append((dc, change))

        # Capture scalar values before commit to avoid DetachedInstanceError
        pv_package_id = pv.package_id
        pv_version = pv.version

        from datetime import datetime, timezone

        pv.scanned_at = datetime.now(timezone.utc)

        # Record incident events for each detected change (rides same transaction)
        # repo_id is not directly available here — resolved from RepoPackage below
        for dc, change in dc_rows:
            await record_event(
                session,
                event_type="change_detected",
                detected_change_id=dc.id,
                payload={
                    "symbol_old": change.get("symbol_old", ""),
                    "symbol_new": change.get("symbol_new"),
                    "change_type": change.get("change_type", "signature_change"),
                    "confidence": float(change.get("confidence", 0.8)),
                    "package": package_name,
                    "version": pv_version,
                },
            )

        await session.commit()

        # Publish to live bus after commit (bus never sees uncommitted rows)
        # Collect dc ids/payloads before they become detached
        dc_publish_list = [
            (str(dc.id), {
                "symbol_old": ch.get("symbol_old", ""),
                "symbol_new": ch.get("symbol_new"),
                "change_type": ch.get("change_type", "signature_change"),
                "confidence": float(ch.get("confidence", 0.8)),
                "package": package_name,
                "version": pv_version,
            })
            for dc, ch in dc_rows
        ]
        for dc_id_str, ev_payload in dc_publish_list:
            _publish_change_detected(None, dc_id_str, ev_payload)

        # Enqueue scan_repo for every repo that tracks this package
        repo_pkgs = await session.execute(
            select(RepoPackage).where(RepoPackage.package_id == pv_package_id)
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

    logger.info(
        "extract_changes: stored %d changes for %s@%s", len(changes), package_name, pv_version
    )
