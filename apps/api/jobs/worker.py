"""
Async worker loop — Section 7.3.
Run with: python -m jobs.worker
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, update

from db.session import AsyncSessionLocal
from db.models import Job
from jobs.queue import dequeue_job
from jobs.handlers import (
    poll_registry,
    extract_changes,
    scan_repo,
    generate_patch,
    open_pr,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("telex.worker")

JOB_HANDLERS = {
    "poll_registry": poll_registry.run,
    "extract_changes": extract_changes.run,
    "scan_repo": scan_repo.run,
    "generate_patch": generate_patch.run,
    "open_pr": open_pr.run,
}


async def reap_stale_jobs(session, lease_seconds: int = 300) -> int:
    """Re-queue jobs stuck in 'running' state whose lock has expired."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=lease_seconds)
    stmt = (
        update(Job)
        .where(
            Job.status == "running",
            Job.locked_at < cutoff,
            Job.attempts < Job.max_attempts,
        )
        .values(
            status="queued",
            locked_by=None,
            locked_at=None,
        )
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount


async def worker_loop(worker_id: str) -> None:
    logger.info("Worker %s starting", worker_id)
    last_reap = 0.0
    async with AsyncSessionLocal() as session:
        while True:
            # Periodically reap stale orphaned jobs (every 30s)
            now_ts = asyncio.get_running_loop().time()
            if now_ts - last_reap > 30.0:
                try:
                    reaped = await reap_stale_jobs(session)
                    if reaped > 0:
                        logger.info("Reaper recovered %d stale job(s)", reaped)
                    last_reap = now_ts
                except Exception as reap_exc:
                    logger.warning("Reaper check failed: %s", reap_exc)
                    await session.rollback()

            job = await dequeue_job(session, worker_id)
            if job is None:
                await asyncio.sleep(2)
                continue

            logger.info("Worker %s picked up job %s (type=%s)", worker_id, job.id, job.job_type)
            try:
                handler = JOB_HANDLERS.get(job.job_type)
                if handler is None:
                    raise ValueError(f"Unknown job type: {job.job_type}")
                await handler(job.payload)
                job.status = "done"
                logger.info("Job %s completed", job.id)
            except Exception as exc:
                # Rollback any aborted DB state before writing job status
                await session.rollback()
                job = await session.merge(job)
                if job.attempts >= job.max_attempts:
                    job.status = "failed"
                    logger.error("Job %s permanently failed after %d attempts: %s", job.id, job.attempts, exc)
                else:
                    job.status = "queued"
                    # Exponential backoff: 30s, 60s, 90s …
                    delay = 30 * job.attempts
                    job.run_after = func.now() + timedelta(seconds=delay)  # type: ignore[assignment]
                    logger.warning("Job %s failed (attempt %d/%d), retrying in %ds: %s", job.id, job.attempts, job.max_attempts, delay, exc)
            finally:
                try:
                    await session.commit()
                except Exception:
                    logger.exception("Job %s: could not persist final state", job.id)
                    await session.rollback()


if __name__ == "__main__":
    n_workers = int(os.getenv("WORKER_COUNT", "2"))
    worker_ids = [f"worker-{uuid.uuid4().hex[:8]}" for _ in range(n_workers)]
    loop = asyncio.get_event_loop()
    tasks = [loop.create_task(worker_loop(wid)) for wid in worker_ids]
    try:
        loop.run_until_complete(asyncio.gather(*tasks))
    except KeyboardInterrupt:
        logger.info("Worker pool shutting down")
