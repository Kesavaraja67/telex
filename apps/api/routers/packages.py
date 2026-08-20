"""
Packages API — manual rescan trigger.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from db.models import Package, PackageVersion
from jobs.queue import enqueue_job
from schemas import RescanIn

router = APIRouter(prefix="/api/packages", tags=["packages"])


@router.post("/{package_id}/rescan", status_code=202)
async def rescan_package(
    package_id: uuid.UUID,
    body: RescanIn,
    session: AsyncSession = Depends(get_session),
):
    """
    Manually trigger the full detect→scan→patch pipeline for a package version.
    Useful for demos and testing.
    """
    pkg = await session.get(Package, package_id)
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")

    # Upsert the target version
    from sqlalchemy import select
    existing = await session.execute(
        select(PackageVersion).where(
            PackageVersion.package_id == package_id,
            PackageVersion.version == body.new_version,
        )
    )
    pv = existing.scalar_one_or_none()
    if pv is None:
        pv = PackageVersion(
            package_id=package_id,
            version=body.new_version,
            changelog_raw=body.changelog,
        )
        session.add(pv)
        await session.commit()
        await session.refresh(pv)

    await enqueue_job(
        session,
        "extract_changes",
        {
            "package_version_id": str(pv.id),
            "package_name": pkg.name,
            "old_version": body.old_version,
            "changelog": body.changelog or "",
        },
    )
    return {"status": "queued", "package_version_id": str(pv.id)}
