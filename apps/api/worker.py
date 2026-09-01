"""
Telex Standalone Worker — used by the separate Render background worker service.

This is the entrypoint for `telex-worker` in render.yaml.
It runs the autonomous job queue (generate_patch, recover_runtime, open_pr, etc.)
in complete isolation from the API web process, preventing npm ci / tsc / npm test
from consuming memory inside the 512 MB API container.

Usage:
    python worker.py
"""
import asyncio
import logging
import uuid

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("telex.worker")


async def main() -> None:
    from jobs.worker import worker_loop, start_scheduler

    worker_id = f"worker-standalone-{uuid.uuid4().hex[:8]}"
    logger.info("Telex standalone worker starting — id: %s", worker_id)

    scheduler = start_scheduler()
    try:
        await worker_loop(worker_id)
    finally:
        if scheduler is not None:
            try:
                scheduler.shutdown()
            except Exception:
                pass
        logger.info("Telex standalone worker shutting down — id: %s", worker_id)


if __name__ == "__main__":
    asyncio.run(main())
