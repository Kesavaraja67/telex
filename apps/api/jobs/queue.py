"""
Job queue engine — Section 7.3.
SELECT … FOR UPDATE SKIP LOCKED pattern (OpusQueue).
"""
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Job

logger = logging.getLogger(__name__)


async def dequeue_job(session: AsyncSession, worker_id: str) -> Job | None:
    """
    Atomically claim the oldest queued job whose run_after is in the past.

    Uses SKIP LOCKED so concurrent workers never block each other.
    Returns None if there are no jobs ready to run.
    """
    stmt = (
        select(Job)
        .where(Job.status == "queued", Job.run_after <= func.now())
        .order_by(Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    if job is None:
        return None

    job.status = "running"
    job.locked_by = worker_id
    job.locked_at = func.now()
    job.attempts += 1
    await session.commit()
    return job


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
    from datetime import timedelta
    from sqlalchemy import text

    run_after_expr = func.now() + text(f"interval '{run_after_seconds} seconds'") if run_after_seconds else func.now()

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
