"""
Async worker loop — Section 7.3.
Run with: python -m jobs.worker
"""
import asyncio
import logging
import os
import uuid
from datetime import timedelta
from sqlalchemy import func

from db.session import AsyncSessionLocal
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


async def worker_loop(worker_id: str) -> None:
    logger.info("Worker %s starting", worker_id)
    async with AsyncSessionLocal() as session:
        while True:
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
                await session.commit()


if __name__ == "__main__":
    n_workers = int(os.getenv("WORKER_COUNT", "2"))
    worker_ids = [f"worker-{uuid.uuid4().hex[:8]}" for _ in range(n_workers)]
    loop = asyncio.get_event_loop()
    tasks = [loop.create_task(worker_loop(wid)) for wid in worker_ids]
    try:
        loop.run_until_complete(asyncio.gather(*tasks))
    except KeyboardInterrupt:
        logger.info("Worker pool shutting down")
