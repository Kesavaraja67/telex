import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Alembic Config object
config = context.config

# Set up Python logging from .ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import models so autogenerate can see all tables
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.models import Base  # noqa: E402

target_metadata = Base.metadata

from config import settings

# Read DATABASE_URL from environment or settings
database_url = os.environ.get("DATABASE_URL") or settings.database_url
if database_url.startswith("postgresql+asyncpg://"):
    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
else:
    sync_url = database_url

if sync_url:
    config.set_main_option("sqlalchemy.url", sync_url)


def run_migrations_offline() -> None:
    """Run migrations without a live database connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations with an async engine (used when DATABASE_URL is asyncpg)."""
    # Build a temporary async URL for the engine
    async_url = os.environ.get("DATABASE_URL") or settings.database_url
    if not async_url:
        raise RuntimeError("DATABASE_URL not set")

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = async_url
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online (connected) migration mode."""
    # If we have an async URL, run the async path
    db_url = os.environ.get("DATABASE_URL") or settings.database_url
    if "asyncpg" in db_url:
        asyncio.run(run_async_migrations())
    else:
        from sqlalchemy import engine_from_config

        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        with connectable.connect() as connection:
            do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
