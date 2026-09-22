"""
Incidents router — SSE live stream, graph snapshot, and event history.

Three endpoints:
  GET /api/repos/{repo_id}/incidents/stream
      Server-Sent Events stream for live incident events for this repo.
      Auth: require_auth (cookie or Bearer — EventSource sends the httpOnly
      cookie automatically with withCredentials: true, and our CORSMiddleware
      already has allow_credentials=True).

  GET /api/repos/{repo_id}/incidents/{detected_change_id}/graph
      Full current-state snapshot of one incident. Used on mount (before
      subscribing to the stream) and for mid-incident catch-up after a
      dropped-frame.

  GET /api/repos/{repo_id}/incidents/{detected_change_id}/events
      Historical incident_event rows, ordered by created_at, with optional
      ?since=<ISO timestamp> for incremental fetch. Used by the replay feature.
"""

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, or_, select

from db.models import (
    CodeUsage,
    DetectedChange,
    IncidentEvent,
    Package,
    PackageVersion,
    Patch,
    PullRequest,
    ValidationRun,
)
from db.session import AsyncSessionLocal
from routers.auth import get_authorized_repo, require_auth
from schemas import IncidentEventOut, IncidentGraphOut, IncidentNodeOut
from services.event_bus import event_bus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repos/{repo_id}/incidents", tags=["incidents"])


@router.get("/active")
async def get_active_incidents(
    repo_id: str,
    auth_data: dict = Depends(require_auth),
):
    """Return all currently-open incidents for the repo.

    Returns [{detected_change_id, package, symbol_old, symbol_new}] for every
    DetectedChange with at least one non-'patched' CodeUsage.
    """
    async with AsyncSessionLocal() as session:
        db_repo, _ = await get_authorized_repo(session, repo_id, auth_data)

        stmt = (
            select(DetectedChange, Package.name.label("package_name"))
            .outerjoin(
                PackageVersion,
                DetectedChange.package_version_id == PackageVersion.id,
            )
            .outerjoin(Package, PackageVersion.package_id == Package.id)
            .join(CodeUsage, CodeUsage.detected_change_id == DetectedChange.id)
            .where(
                CodeUsage.repo_id == db_repo.id,
                CodeUsage.status != "patched",
            )
            .distinct()
        )
        result = await session.execute(stmt)
        rows = result.all()

        return [
            {
                "detected_change_id": str(dc.id),
                "package": pkg_name or "unknown",
                "symbol_old": dc.symbol_old or "",
                "symbol_new": dc.symbol_new or "",
                "change_type": dc.change_type or "signature_change",
            }
            for dc, pkg_name in rows
        ]


# ── SSE live stream ───────────────────────────────────────────────────────────


@router.get("/stream")
async def stream_incidents(
    repo_id: str,
    request: Request,
    auth_data: dict = Depends(require_auth),
):
    """Server-Sent Events stream of incident_events for this repo, live."""
    async with AsyncSessionLocal() as session:
        db_repo, _ = await get_authorized_repo(session, repo_id, auth_data)

    queue = event_bus.subscribe(repo_id=str(db_repo.id))

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # SSE keepalive comment — proxies see traffic, connection stays open
                    yield ": heartbeat\n\n"
        finally:
            event_bus.unsubscribe(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx/proxy response buffering
            "Connection": "keep-alive",
        },
    )


# ── Snapshot endpoint ─────────────────────────────────────────────────────────


@router.get("/{detected_change_id}/graph", response_model=IncidentGraphOut)
async def get_incident_graph(
    repo_id: str,
    detected_change_id: str,
    auth_data: dict = Depends(require_auth),
):
    """Full current-state snapshot of one incident's graph."""
    async with AsyncSessionLocal() as session:
        db_repo, _ = await get_authorized_repo(session, repo_id, auth_data)

        dc_uuid = _try_uuid(detected_change_id)
        if dc_uuid is None:
            raise HTTPException(status_code=400, detail="Invalid detected_change_id")

        # Resolve detected_change scoped to this repository through CodeUsage
        dc_stmt = (
            select(DetectedChange)
            .join(CodeUsage, CodeUsage.detected_change_id == DetectedChange.id)
            .where(
                DetectedChange.id == dc_uuid,
                CodeUsage.repo_id == db_repo.id,
            )
            .limit(1)
        )
        dc_res = await session.execute(dc_stmt)
        dc = dc_res.scalar_one_or_none()
        if dc is None:
            raise HTTPException(status_code=404, detail="Incident not found")

        # Resolve package/version info for root node label
        package_name = "unknown"
        if dc.package_version_id:
            pv = await session.get(PackageVersion, dc.package_version_id)
            if pv:
                pkg = await session.get(Package, pv.package_id)
                if pkg:
                    package_name = pkg.name

        # Fetch all CodeUsages for this change in this repo
        cu_stmt = select(CodeUsage).where(
            CodeUsage.detected_change_id == dc.id,
            CodeUsage.repo_id == db_repo.id,
        )
        cu_result = await session.execute(cu_stmt)
        code_usages = list(cu_result.scalars())

        if not code_usages:
            return IncidentGraphOut(
                detected_change_id=str(dc.id),
                repo_id=str(db_repo.id),
                package=package_name,
                symbol_old=dc.symbol_old or "",
                symbol_new=dc.symbol_new,
                change_type=dc.change_type or "signature_change",
                confidence=float(dc.confidence or 0.0),
                created_at=dc.created_at.isoformat() if dc.created_at else "",
                nodes=[],
            )

        cu_ids = [cu.id for cu in code_usages]

        # Batch-load all Patches for these usages
        patch_stmt = select(Patch).where(Patch.code_usage_id.in_(cu_ids))
        patch_result = await session.execute(patch_stmt)
        patches = list(patch_result.scalars())
        patch_by_cu: dict = {}
        for p in patches:
            patch_by_cu.setdefault(p.code_usage_id, []).append(p)

        # Batch-load all ValidationRuns for those patches
        patch_ids = [p.id for p in patches]
        vr_map: dict = {}
        if patch_ids:
            vr_stmt = (
                select(ValidationRun)
                .where(ValidationRun.patch_id.in_(patch_ids))
                .order_by(ValidationRun.created_at.desc())
            )
            vr_result = await session.execute(vr_stmt)
            for vr in vr_result.scalars():
                if vr.patch_id not in vr_map:
                    vr_map[vr.patch_id] = vr

        # Batch-load PullRequests for this repo
        pr_stmt = select(PullRequest).where(PullRequest.repo_id == db_repo.id)
        pr_result = await session.execute(pr_stmt)
        pr_rows = list(pr_result.scalars())
        pr_by_patch: dict = {}
        for pr in pr_rows:
            for pid in pr.patch_ids or []:
                pr_by_patch[pid] = pr

        # Assemble nodes
        nodes: list[IncidentNodeOut] = []
        for cu in code_usages:
            cu_patches = patch_by_cu.get(cu.id, [])
            best_patch = next((p for p in cu_patches if p.verified), None) or (
                cu_patches[0] if cu_patches else None
            )
            best_vr = vr_map.get(best_patch.id) if best_patch else None
            best_pr = pr_by_patch.get(best_patch.id) if best_patch else None

            nodes.append(
                IncidentNodeOut(
                    code_usage_id=str(cu.id),
                    file_path=cu.file_path,
                    line_start=cu.line_start,
                    line_end=cu.line_end,
                    status=cu.status or "pending",
                    patch_verified=best_patch.verified if best_patch else None,
                    validation=(
                        {
                            "applies_cleanly": best_vr.applies_cleanly,
                            "typechecks": best_vr.typechecks,
                            "tests_pass": best_vr.tests_pass,
                            "scope_ok": best_vr.scope_ok,
                            "verification_mode": best_vr.verification_mode,
                        }
                        if best_vr
                        else None
                    ),
                    pr_url=best_pr.github_pr_url if best_pr else None,
                    pr_merged=best_pr.merged if best_pr else None,
                )
            )

        return IncidentGraphOut(
            detected_change_id=str(dc.id),
            repo_id=str(db_repo.id),
            package=package_name,
            symbol_old=dc.symbol_old or "",
            symbol_new=dc.symbol_new,
            change_type=dc.change_type or "signature_change",
            confidence=float(dc.confidence or 0.0),
            created_at=dc.created_at.isoformat() if dc.created_at else "",
            nodes=nodes,
        )


# ── Event history endpoint (for replay and catch-up) ─────────────────────────


@router.get("/{detected_change_id}/events", response_model=list[IncidentEventOut])
async def get_incident_events(
    repo_id: str,
    detected_change_id: str,
    since: str | None = None,
    limit: int = 500,
    auth_data: dict = Depends(require_auth),
):
    """Return ordered incident_event rows for one incident."""
    dc_uuid = _try_uuid(detected_change_id)
    if dc_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid detected_change_id")

    async with AsyncSessionLocal() as session:
        db_repo, _ = await get_authorized_repo(session, repo_id, auth_data)

        stmt = (
            select(IncidentEvent)
            .outerjoin(CodeUsage, IncidentEvent.code_usage_id == CodeUsage.id)
            .where(
                or_(
                    and_(
                        IncidentEvent.detected_change_id == dc_uuid,
                        IncidentEvent.repo_id == db_repo.id,
                    ),
                    and_(
                        CodeUsage.detected_change_id == dc_uuid,
                        CodeUsage.repo_id == db_repo.id,
                    ),
                )
            )
            .order_by(IncidentEvent.created_at.asc())
            .limit(min(limit, 2000))
        )
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
                stmt = stmt.where(IncidentEvent.created_at > since_dt)
            except ValueError:
                pass

        result = await session.execute(stmt)
        events = list(result.scalars())

        return [
            IncidentEventOut(
                id=str(ev.id),
                event_type=ev.event_type,
                repo_id=str(ev.repo_id) if ev.repo_id else None,
                detected_change_id=str(ev.detected_change_id) if ev.detected_change_id else None,
                code_usage_id=str(ev.code_usage_id) if ev.code_usage_id else None,
                job_id=str(ev.job_id) if ev.job_id else None,
                payload=ev.payload or {},
                created_at=ev.created_at.isoformat() if ev.created_at else "",
            )
            for ev in events
        ]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _try_uuid(value: str | None):
    """Return a uuid.UUID if value is a valid UUID string, else None."""
    if not value:
        return None
    import uuid

    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None
