"""
Job queue engine — Section 7.3.
SELECT … FOR UPDATE SKIP LOCKED pattern (OpusQueue).

Phase 8 additions:
- dequeue_job now enforces a per-installation concurrent-job cap (option a
  from the spec: simple max-N running cap, not a full fair-share scheduler).
  The cap prevents one high-volume installation from starving all others.
"""

import logging
import os as _os
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Job

logger = logging.getLogger(__name__)

# ── Phase 8.1: per-installation cap ─────────────────────────────────────────
# Maximum number of jobs in "running" state per installation_id.
# Default: 3. Override with env var TELEX_MAX_JOBS_PER_INSTALLATION.
_MAX_RUNNING_PER_INSTALLATION: int = int(_os.getenv("TELEX_MAX_JOBS_PER_INSTALLATION", "3"))


async def _lock_installation(session: AsyncSession, installation_id: str) -> None:
    """
    Acquire a transaction-scoped advisory lock for the installation ID.
    In Postgres, this serializes concurrent workers checking and claiming jobs
    for the same installation so the running-count check is atomic.
    No-op on non-Postgres databases (e.g. in-memory SQLite for tests).
    """
    bind = session.get_bind()
    if bind and "postgres" in bind.dialect.name.lower():
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:iid))"),
            {"iid": installation_id},
        )


async def _resolve_payload_installation_id(session: AsyncSession, payload: Any) -> str | None:
    """
    Resolve the installation ID from top-level payload or referenced entities.
    Checks payload['installation_id'], 'repo_id', 'code_usage_id', and 'patch_id'.
    """
    if not isinstance(payload, dict):
        return None

    if payload.get("installation_id"):
        return str(payload["installation_id"])

    repo_id = payload.get("repo_id")
    if repo_id:
        try:
            res = await session.execute(
                text("SELECT installation_id FROM repos WHERE id = :rid"),
                {"rid": str(repo_id)},
            )
            val = res.scalar_one_or_none()
            if val:
                return str(val)
        except Exception:
            pass

    code_usage_id = payload.get("code_usage_id")
    if code_usage_id:
        try:
            res = await session.execute(
                text(
                    "SELECT r.installation_id FROM code_usages cu "
                    "JOIN repos r ON cu.repo_id = r.id WHERE cu.id = :cuid"
                ),
                {"cuid": str(code_usage_id)},
            )
            val = res.scalar_one_or_none()
            if val:
                return str(val)
        except Exception:
            pass

    patch_id = payload.get("patch_id")
    if patch_id:
        try:
            res = await session.execute(
                text(
                    "SELECT r.installation_id FROM patches p "
                    "JOIN code_usages cu ON p.code_usage_id = cu.id "
                    "JOIN repos r ON cu.repo_id = r.id WHERE p.id = :pid"
                ),
                {"pid": str(patch_id)},
            )
            val = res.scalar_one_or_none()
            if val:
                return str(val)
        except Exception:
            pass

    return None


async def _resolve_job_installation_id(session: AsyncSession, job: Job) -> str | None:
    """Resolve installation ID for a candidate job."""
    if isinstance(job.payload, dict):
        return await _resolve_payload_installation_id(session, job.payload)
    return None


async def _count_running_for_installation(session: AsyncSession, installation_id: str) -> int:
    """Count how many jobs are currently running for a given installation_id."""
    # installation_id is stored as a JSON key inside the JSONB payload column.
    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM jobs "
            "WHERE status = 'running' "
            "AND payload->>'installation_id' = :iid"
        ),
        {"iid": installation_id},
    )
    row = result.one_or_none()
    return int(row[0]) if row else 0


async def dequeue_job(session: AsyncSession, worker_id: str) -> Job | None:
    """
    Atomically claim the oldest queued job whose run_after is in the past,
    subject to the per-installation concurrent-job cap (Phase 8.1).

    Algorithm:
      1. Scan queued candidate batches in order (oldest first).
      2. For each candidate, resolve installation_id and serialize the count-and-claim
         via an installation-scoped advisory lock.
      3. If an installation is at capacity, skip and continue scanning beyond the
         initial batch so uncapped installations are never starved.
      4. Claim the first uncapped job.

    Uses SKIP LOCKED so concurrent workers never block each other.
    Returns None if there are no jobs ready to run.
    """
    batch_size = 20
    offset = 0
    claimed_job: Job | None = None

    while True:
        stmt = (
            select(Job)
            .where(Job.status == "queued", Job.run_after <= func.now())
            .order_by(Job.created_at)
            .offset(offset)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        candidates = list(result.scalars())

        if not candidates:
            break

        for job in candidates:
            iid = await _resolve_job_installation_id(session, job)
            if iid:
                # Serialize check-and-claim atomically for this installation
                await _lock_installation(session, iid)
                running = await _count_running_for_installation(session, iid)
                if running >= _MAX_RUNNING_PER_INSTALLATION:
                    logger.debug(
                        "dequeue_job: installation %s is at cap (%d running) — skipping job %s",
                        iid,
                        running,
                        job.id,
                    )
                    continue

                # Ensure installation_id is recorded in payload for tracking
                if isinstance(job.payload, dict) and "installation_id" not in job.payload:
                    job.payload = dict(job.payload, installation_id=iid)

            claimed_job = job
            break

        if claimed_job is not None:
            break

        # Entire batch was capped; scan next batch
        offset += batch_size

    if claimed_job is None:
        await session.rollback()
        return None

    claimed_job.status = "running"
    claimed_job.locked_by = worker_id
    claimed_job.locked_at = func.now()
    claimed_job.attempts += 1

    # Resolve repo_id from payload so the event can be scoped correctly
    repo_id_str: str | None = None
    if isinstance(claimed_job.payload, dict):
        repo_id_val = claimed_job.payload.get("repo_id")
        if repo_id_val:
            repo_id_str = str(repo_id_val)

    # Record job_running event (rides the running-status commit)
    from services.incident_events import record_event as _record_event
    from db.models import IncidentEvent as _  # noqa: ensure model is loaded
    await _record_event(
        session,
        event_type="job_running",
        repo_id=repo_id_str,
        job_id=claimed_job.id,
        payload={"job_type": claimed_job.job_type},
    )

    await session.commit()

    # Publish to bus after commit — non-fatal, never blocks the queue engine
    try:
        from services.event_bus import event_bus as _event_bus
        await _event_bus.publish({
            "event_type": "job_running",
            "repo_id": repo_id_str,
            "job_id": str(claimed_job.id),
            "job_type": claimed_job.job_type,
        })
    except Exception as _exc:
        logger.warning("event_bus publish job_running failed (non-fatal): %s", _exc)

    return claimed_job



async def enqueue_job(
    session: AsyncSession,
    job_type: str,
    payload: dict,
    run_after_seconds: int = 0,
) -> Job:
    """
    Insert a new job into the queue.

    Args:
        job_type: one of the values in the jobs.job_type CHECK constraint.
        payload: arbitrary dict passed to the handler.
        run_after_seconds: delay before the job becomes eligible to run.
    """
    from datetime import datetime, timedelta, timezone

    # Automatically enrich payload with installation_id if resolvable
    if isinstance(payload, dict) and not payload.get("installation_id"):
        resolved_iid = await _resolve_payload_installation_id(session, payload)
        if resolved_iid:
            payload["installation_id"] = resolved_iid

    if run_after_seconds:
        run_after_expr = datetime.now(timezone.utc) + timedelta(seconds=run_after_seconds)
    else:
        run_after_expr = func.now()

    job = Job(
        job_type=job_type,
        payload=payload,
        status="queued",
        run_after=run_after_expr,  # type: ignore[arg-type]
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    logger.info("Enqueued job %s (type=%s)", job.id, job_type)
    return job
