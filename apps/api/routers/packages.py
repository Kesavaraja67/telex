"""
Packages API — manual rescan trigger with authentication and job debounce.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Job, Package, PackageVersion
from db.session import get_session
from jobs.queue import enqueue_job
from routers.auth import require_auth
from schemas import RescanIn

router = APIRouter(prefix="/api/packages", tags=["packages"])


@router.post("/{package_id}/rescan", status_code=202)
async def rescan_package(
    package_id: uuid.UUID,
    body: RescanIn,
    auth_data: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """
    Manually trigger the full detect→scan→patch pipeline for a package version.
    Requires authentication and debounces against existing active extraction jobs.
    """
    user_id = auth_data.get("user_id") if isinstance(auth_data, dict) else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    pkg = await session.get(Package, package_id)
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")

    # Upsert the target version
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

    # Debounce against already queued or active extract_changes job
    active_jobs_res = await session.execute(
        select(Job).where(
            Job.job_type == "extract_changes",
            Job.status.in_(["queued", "running"]),
        )
    )
    active_jobs = active_jobs_res.scalars().all()
    for j in active_jobs:
        if isinstance(j.payload, dict) and j.payload.get("package_version_id") == str(pv.id):
            return {
                "status": "already_queued",
                "package_version_id": str(pv.id),
                "job_id": str(j.id),
            }

    job_id = await enqueue_job(
        session,
        "extract_changes",
        {
            "package_version_id": str(pv.id),
            "package_name": pkg.name,
            "old_version": body.old_version,
            "new_version": body.new_version,
            "changelog": body.changelog or "",
        },
    )
    return {
        "status": "queued",
        "package_version_id": str(pv.id),
        "job_id": job_id,
    }
