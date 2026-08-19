"""Shared test fixtures."""

import os

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

import app.models  # noqa: F401 - populate Base.metadata before create_all
from app.db.base import Base
from app.db.database import engine


@pytest.fixture(autouse=True)
async def _dispose_engine_pool() -> None:
    """Dispose pooled connections after each test.

    Each test may run in its own asyncio event loop (pytest-asyncio's default
    function-scoped loop, or the loop TestClient spins up internally). asyncpg
    connections are bound to the loop they were created on, so leaving one
    checked into the pool across tests raises a cross-loop RuntimeError. This
    is purely a test-isolation concern - the running app has a single event
    loop for its whole lifetime, so pooled connections are never reused
    across loops in production.
    """
    yield
    await engine.dispose()


# --- Repository test database -----------------------------------------
#
# Deliberately a SEPARATE code path from app.core.config.Settings/DATABASE_URL
# - repository tests must never be able to accidentally point at the
# production Supabase database. See docs/repository-layer.md for how to
# stand up a local disposable test database (one `docker run` command).
# If TEST_DATABASE_URL isn't set/reachable, these tests are skipped rather
# than falling back to any other database.

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
async def test_engine():  # type: ignore[no-untyped-def]
    if not TEST_DATABASE_URL:
        pytest.skip(
            "TEST_DATABASE_URL is not set - repository tests need a disposable "
            "local test database, separate from the app's Supabase DATABASE_URL. "
            "See docs/repository-layer.md for setup instructions."
        )

    test_engine: AsyncEngine = create_async_engine(TEST_DATABASE_URL)
    try:
        async with test_engine.connect():
            pass
    except Exception as exc:  # noqa: BLE001 - report and skip, don't fail the suite
        await test_engine.dispose()
        pytest.skip(f"TEST_DATABASE_URL is not reachable: {exc}")

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine):  # type: ignore[no-untyped-def]
    """One test = one outer transaction, rolled back afterward.

    The session joins that outer transaction via a SAVEPOINT
    (`join_transaction_mode="create_savepoint"`), so repository/test code can
    freely call `session.commit()`/`session.rollback()` (exactly what a
    transaction-rollback test needs to do) without ever affecting the outer
    transaction - which is unconditionally rolled back at the end, giving
    full isolation between tests without recreating tables each time.
    """
    connection = await test_engine.connect()
    outer_transaction = await connection.begin()
    session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)

    yield session

    await session.close()
    await outer_transaction.rollback()
    await connection.close()
