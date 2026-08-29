"""
Telex FastAPI application entry point.
"""
import asyncio
import os
import uuid
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import auth, repos, packages, webhooks, stats, payments, recovery

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("telex.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Telex API starting up — LLM provider: %s", settings.llm_provider_default)
    # Start embedded worker loop for free single-service hosting
    worker_task = None
    scheduler = None
    if os.getenv("EMBEDDED_WORKER", "true").lower() in ("true", "1", "yes"):
        try:
            from jobs.worker import worker_loop, start_scheduler
            scheduler = start_scheduler()
            worker_task = asyncio.create_task(worker_loop(f"worker-embedded-{uuid.uuid4().hex[:6]}"))
            logger.info("Embedded autonomous job worker started in background.")
        except Exception as e:
            logger.warning("Could not start embedded background worker: %s", e)

    yield

    if worker_task:
        worker_task.cancel()
    if scheduler:
        try:
            scheduler.shutdown()
        except Exception:
            pass
    logger.info("Telex API shutting down")


app = FastAPI(
    title="Telex API",
    description="Self-healing API dependency bot",
    version="0.1.0",
    lifespan=lifespan,
)

_is_prod = bool(os.getenv("RENDER") or os.getenv("ENVIRONMENT", "").lower() == "production")

# CORS — allow local dev, explicitly configured origins, and all vercel deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers
app.include_router(auth.router)
app.include_router(auth.router, prefix="/api")
app.include_router(repos.router)
app.include_router(packages.router)
app.include_router(webhooks.router)
app.include_router(stats.router)
app.include_router(payments.router)
app.include_router(recovery.router)


@app.get("/health")
async def health():
    return {"status": "ok", "provider": settings.llm_provider_default}
