"""Async SQLAlchemy engine and session factory for Supabase PostgreSQL.

Connection pooling is configured differently depending on which Supabase
connection mode `DATABASE_URL` points at - see `Settings.DB_POOL_MODE`:

- "session" (default): direct connection or Supavisor *session* pooler.
  SQLAlchemy owns pooling via its normal QueuePool.
- "transaction": Supavisor *transaction* pooler. The pooler already
  multiplexes connections and does not support server-side prepared
  statements, so SQLAlchemy is configured with NullPool and asyncpg's
  statement cache is disabled.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

_connect_args: dict[str, Any] = {}
if settings.DB_SSL_REQUIRE:
    _connect_args["ssl"] = "require"

_engine_kwargs: dict[str, Any] = {
    "echo": settings.DB_ECHO,
    "pool_pre_ping": True,
    "connect_args": _connect_args,
}

if settings.DB_POOL_MODE == "transaction":
    # PgBouncer/Supavisor transaction mode can't reuse prepared statements
    # across pooled connections - disable asyncpg's statement cache and let
    # the pooler (not SQLAlchemy) own connection pooling.
    _connect_args["statement_cache_size"] = 0
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
    )

engine: AsyncEngine = create_async_engine(settings.sqlalchemy_database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for the duration of a request."""
    async with AsyncSessionLocal() as session:
        yield session


async def check_database_connection() -> bool:
    """Run a trivial round-trip query to confirm Supabase PostgreSQL is reachable."""
    from sqlalchemy import text

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return True
