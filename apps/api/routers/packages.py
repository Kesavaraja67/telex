"""
Packages API — manual rescan trigger with authentication and job debounce.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Installation, Job, Package, PackageVersion, Repo, RepoPackage, User
from db.session import get_session
from jobs.queue import enqueue_job
from routers.auth import require_auth
from schemas import RescanIn

logger = logging.getLogger(__name__)

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

    # SQLite must acquire its write lock before the first read starts a transaction.
    # Hold serialization through version creation, debounce, and enqueue commit.
    try:
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                {"key": f"rescan_package:{package_id}:{body.new_version}"},
            )
        elif dialect_name == "sqlite":
            await session.execute(text("BEGIN IMMEDIATE"))
        else:
            raise RuntimeError("Unsupported rescan lock dialect")
    except Exception:
        logger.exception("Could not acquire rescan lock for package %s", package_id)
        await session.rollback()
        raise HTTPException(status_code=503, detail="Package rescan temporarily unavailable")

    pkg = await session.get(Package, package_id)
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")

    # Authorize access: verify user owns/manages at least one repo tracking this package
    if user_id not in ("dev-user", "demo-operator"):
        try:
            user_uuid = uuid.UUID(str(user_id))
        except (ValueError, TypeError):
            raise HTTPException(status_code=403, detail="Package access denied")

        user_res = await session.execute(select(User).where(User.id == user_uuid))
        user = user_res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=403, detail="Package access denied")

        user_login = user.github_login.lower() if user.github_login else None
        inst_conditions = [Installation.installed_by == user_uuid]
        if user_login:
            inst_conditions.append(func.lower(Installation.account_login) == user_login)

        auth_check = await session.execute(
            select(RepoPackage.id)
            .join(Repo, RepoPackage.repo_id == Repo.id)
            .join(Installation, Repo.installation_id == Installation.id)
            .where(
                RepoPackage.package_id == package_id,
                or_(*inst_conditions),
            )
            .limit(1)
        )
        if auth_check.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Package access denied")

    # Lookup or create target PackageVersion within the locked transaction
    existing = await session.execute(
        select(PackageVersion).where(
            PackageVersion.package_id == package_id,
            PackageVersion.version == body.new_version,
        )
    )
    pv = existing.scalar_one_or_none()
    if pv is None:
        pv = PackageVersion(
            id=uuid.uuid4(),
            package_id=package_id,
            version=body.new_version,
            changelog_raw=body.changelog,
        )
        session.add(pv)
        await session.flush()

    # Debounce against already queued or active extract_changes job
    active_jobs_res = await session.execute(
        select(Job).where(
            Job.job_type == "extract_changes",
            Job.status.in_(["queued", "running"]),
        )
    )
    active_jobs = active_jobs_res.scalars().all()
    for j in active_jobs:
        if isinstance(j.payload, dict) and (
            (pv.id and j.payload.get("package_version_id") == str(pv.id))
            or (
                j.payload.get("package_name") == pkg.name
                and j.payload.get("new_version") == body.new_version
            )
        ):
            return {
                "status": "already_queued",
                "package_version_id": str(pv.id),
                "job_id": str(j.id),
            }

    job = await enqueue_job(
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
    job_id = str(getattr(job, "id", job))
    return {
        "status": "queued",
        "package_version_id": str(pv.id),
        "job_id": job_id,
    }
