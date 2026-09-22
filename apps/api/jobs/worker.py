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

from db.models import Job
from db.session import AsyncSessionLocal
from jobs.handlers import (
    build_atlas_graph,
    extract_changes,
    generate_patch,
    open_pr,
    poll_registry,
    scan_repo,
    validate_patch,
)
from jobs.queue import dequeue_job
from services.logging_utils import install_redacting_formatters

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

install_redacting_formatters()
logger = logging.getLogger("telex.worker")

JOB_HANDLERS = {
    # Engine A — npm/pypi dependency healing
    "poll_registry": poll_registry.run,
    "extract_changes": extract_changes.run,
    "scan_repo": scan_repo.run,
    "generate_patch": generate_patch.run,
    "validate_patch": validate_patch.run,
    "open_pr": open_pr.run,
    # Engine C — Repo Atlas
    "build_atlas_graph": build_atlas_graph.run,
}


async def reap_stale_jobs(session, lease_seconds: int = 300) -> int:
    """Re-queue expired running jobs with attempts remaining, and fail expired jobs that reached max_attempts."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=lease_seconds)

    # 1. Mark expired jobs that reached max_attempts as failed
    fail_stmt = (
        update(Job)
        .where(
            Job.status == "running",
            Job.locked_at < cutoff,
            Job.attempts >= Job.max_attempts,
        )
        .values(
            status="failed",
            locked_by=None,
            locked_at=None,
        )
    )
    fail_result = await session.execute(fail_stmt)

    # 2. Re-queue expired jobs with attempts remaining
    requeue_stmt = (
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
    requeue_result = await session.execute(requeue_stmt)
    await session.commit()
    return fail_result.rowcount + requeue_result.rowcount


async def _heartbeat_loop(job_id: uuid.UUID, worker_id: str, interval: float = 15.0) -> None:
    """Periodically update locked_at so actively executing jobs are not reclaimed by the reaper."""
    while True:
        await asyncio.sleep(interval)
        try:
            async with AsyncSessionLocal() as hb_session:
                stmt = (
                    update(Job)
                    .where(
                        Job.id == job_id,
                        Job.locked_by == worker_id,
                        Job.status == "running",
                    )
                    .values(locked_at=datetime.now(timezone.utc))
                )
                await hb_session.execute(stmt)
                await hb_session.commit()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.debug("Heartbeat update failed for job %s: %s", job_id, exc)


async def _resolve_repo_id_for_job(session, payload: dict | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    repo_id_val = payload.get("repo_id")
    if repo_id_val:
        return str(repo_id_val)
    if payload.get("code_usage_id"):
        from db.models import CodeUsage

        try:
            cu = await session.get(CodeUsage, uuid.UUID(str(payload["code_usage_id"])))
            if cu and cu.repo_id:
                return str(cu.repo_id)
        except Exception:
            pass
    elif payload.get("patch_id"):
        from db.models import CodeUsage, Patch

        try:
            p = await session.get(Patch, uuid.UUID(str(payload["patch_id"])))
            if p and p.code_usage_id:
                cu = await session.get(CodeUsage, p.code_usage_id)
                if cu and cu.repo_id:
                    return str(cu.repo_id)
        except Exception:
            pass
    return None


async def worker_loop(worker_id: str) -> None:
    logger.info("Worker %s starting", worker_id)
    last_reap = 0.0
    while True:
        try:
            async with AsyncSessionLocal() as session:
                # Periodically reap stale orphaned jobs (every 30s)
                now_ts = asyncio.get_running_loop().time()
                if now_ts - last_reap > 30.0:
                    try:
                        reaped = await reap_stale_jobs(session)
                        if reaped > 0:
                            logger.info("Reaper processed %d stale job(s)", reaped)
                        last_reap = now_ts
                    except Exception as reap_exc:
                        logger.warning("Reaper check failed: %s", reap_exc)
                        await session.rollback()

                job = await dequeue_job(session, worker_id)
                if job is None:
                    await asyncio.sleep(2)
                    continue

                logger.info("Worker %s picked up job %s (type=%s)", worker_id, job.id, job.job_type)

                # Start heartbeat while handler executes
                heartbeat_task = asyncio.create_task(_heartbeat_loop(job.id, worker_id))
                events_to_publish: list[dict] = []
                job_id_str = str(job.id)
                job_type_str = job.job_type
                try:
                    handler = JOB_HANDLERS.get(job.job_type)
                    if handler is None:
                        raise ValueError(f"Unknown job type: {job.job_type}")
                    await handler(job.payload)
                    job.status = "done"
                    logger.info("Job %s completed", job.id)

                    repo_id_str = await _resolve_repo_id_for_job(session, job.payload)
                    from services.incident_events import record_event as _record_event

                    await _record_event(
                        session,
                        event_type="job_done",
                        repo_id=repo_id_str,
                        job_id=job.id,
                        payload={"job_type": job_type_str, "attempts": job.attempts},
                    )
                    events_to_publish.append(
                        {
                            "event_type": "job_done",
                            "repo_id": repo_id_str,
                            "job_id": job_id_str,
                            "job_type": job_type_str,
                            "attempts": job.attempts,
                        }
                    )
                except Exception as exc:
                    # Rollback any aborted DB state before writing job status
                    await session.rollback()
                    job = await session.merge(job)
                    if job.attempts >= job.max_attempts:
                        job.status = "failed"
                        logger.error(
                            "Job %s permanently failed after %d attempts: %s",
                            job.id,
                            job.attempts,
                            exc,
                        )
                    else:
                        job.status = "queued"
                        # Exponential backoff: 30s, 60s, 90s …
                        delay = 30 * job.attempts
                        job.run_after = func.now() + timedelta(seconds=delay)  # type: ignore[assignment]
                        logger.warning(
                            "Job %s failed (attempt %d/%d), retrying in %ds: %s",
                            job.id,
                            job.attempts,
                            job.max_attempts,
                            delay,
                            exc,
                        )
                    final_status = job.status  # "failed" or "queued" (retry)
                    repo_id_str = await _resolve_repo_id_for_job(session, job.payload)
                    from services.incident_events import record_event as _record_event

                    await _record_event(
                        session,
                        event_type="job_failed",
                        repo_id=repo_id_str,
                        job_id=job.id,
                        payload={
                            "job_type": job_type_str,
                            "attempts": job.attempts,
                            "final_status": final_status,
                            "error": str(exc)[:200],
                        },
                    )
                    events_to_publish.append(
                        {
                            "event_type": "job_failed",
                            "repo_id": repo_id_str,
                            "job_id": job_id_str,
                            "job_type": job_type_str,
                            "attempts": job.attempts,
                            "final_status": final_status,
                            "error": str(exc)[:200],
                        }
                    )
                finally:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass
                    commit_ok = False
                    try:
                        await session.commit()
                        commit_ok = True
                    except Exception:
                        logger.exception("Job %s: could not persist final state", job_id_str)
                        await session.rollback()

                    if commit_ok and events_to_publish:
                        try:
                            from services.event_bus import event_bus

                            for ev in events_to_publish:
                                await event_bus.publish(ev)
                        except Exception as _bus_exc:
                            logger.warning("event_bus publish failed (non-fatal): %s", _bus_exc)
        except asyncio.CancelledError:
            logger.info("Worker %s received cancellation; exiting loop", worker_id)
            break
        except Exception as loop_exc:
            logger.warning("Worker %s loop error: %s", worker_id, loop_exc)
            await asyncio.sleep(2)


async def schedule_package_polling() -> None:
    """Periodically enqueue poll_registry for all packages tracked by active repos."""
    from sqlalchemy import select

    from db.models import Package, Repo, RepoPackage
    from jobs.queue import enqueue_job

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Package)
                .join(RepoPackage, RepoPackage.package_id == Package.id)
                .join(Repo, Repo.id == RepoPackage.repo_id)
                .where(Repo.is_active == True)  # noqa: E712
                .distinct()
            )
            packages = list(result.scalars())
            for pkg in packages:
                await enqueue_job(
                    session,
                    "poll_registry",
                    {
                        "package_id": str(pkg.id),
                        "package_name": pkg.name,
                        "ecosystem": pkg.ecosystem or "npm",
                    },
                )
            await session.commit()
        logger.info("Scheduled registry polling enqueued for %d tracked packages", len(packages))
    except Exception as exc:
        logger.warning("Scheduled package polling failed: %s", exc)


def start_scheduler():
    """Start APScheduler for periodic registry polling."""
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            schedule_package_polling,
            "interval",
            minutes=15,
            id="poll_tracked_packages",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("APScheduler started: polling tracked packages every 15m")
        return scheduler
    except Exception as exc:
        logger.warning("Could not start APScheduler: %s", exc)
        return None


if __name__ == "__main__":
    n_workers = int(os.getenv("WORKER_COUNT", "2"))
    worker_ids = [f"worker-{uuid.uuid4().hex[:8]}" for _ in range(n_workers)]
    scheduler = start_scheduler()
    loop = asyncio.get_event_loop()
    tasks = [loop.create_task(worker_loop(wid)) for wid in worker_ids]
    try:
        loop.run_until_complete(asyncio.gather(*tasks))
    except KeyboardInterrupt:
        if scheduler:
            scheduler.shutdown()
        logger.info("Worker pool shutting down")
