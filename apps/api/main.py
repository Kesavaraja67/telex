"""
Telex FastAPI application entry point.
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import auth, repos, packages, webhooks, stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("telex.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Telex API starting up — LLM provider: %s", settings.llm_provider_default)
    yield
    logger.info("Telex API shutting down")


app = FastAPI(
    title="Telex API",
    description="Self-healing API dependency bot",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow local dev and all Vercel production preview/live domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers
app.include_router(auth.router)
app.include_router(repos.router)
app.include_router(packages.router)
app.include_router(webhooks.router)
app.include_router(stats.router)


@app.get("/health")
async def health():
    return {"status": "ok", "provider": settings.llm_provider_default}
