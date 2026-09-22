"""
Telex FastAPI application entry point.
"""

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from routers import atlas as atlas_router
from routers import auth, packages, repos, stats, webhooks
from routers import settings as settings_router
from routers.incidents import router as incidents_router
from services.logging_utils import install_redacting_formatters

_API_DIR = Path(__file__).resolve().parent
load_dotenv(_API_DIR / ".env")
load_dotenv(_API_DIR.parent.parent / ".env")
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("telex.api")

# Redact API key patterns from all log output
install_redacting_formatters()
# ───────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Telex API starting up — LLM provider: %s", settings.llm_provider_default)
    # Start embedded worker loop for free single-service hosting
    worker_task = None
    scheduler = None
    if os.getenv("EMBEDDED_WORKER", "true").lower() in ("true", "1", "yes"):
        try:
            from jobs.worker import start_scheduler, worker_loop

            scheduler = start_scheduler()
            worker_task = asyncio.create_task(
                worker_loop(f"worker-embedded-{uuid.uuid4().hex[:6]}")
            )
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

# CORS — allow explicitly configured origins, local dev, and project-specific Vercel preview deploys
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://telex[a-zA-Z0-9_-]*\.vercel\.app$",
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
app.include_router(incidents_router)
app.include_router(settings_router.router)
app.include_router(atlas_router.router)


@app.get("/health")
async def health():
    return {"status": "ok", "provider": settings.llm_provider_default}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Global exception handler caught: %s on %s", exc, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )
