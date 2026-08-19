"""Integration tests for the Job Category API (GET /api/v1/job-categories).

Added for Task 18 - see app/api/v1/endpoints/job_categories.py's module
docstring for why this endpoint exists now. Mirrors the strategy
established in tests/test_jobs_api.py.
"""

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.main import app
from app.repositories.job_category_repository import JobCategoryRepository


def _use_test_db(db_session: AsyncSession) -> None:
    async def override_get_db() -> AsyncSession:
        return db_session

    app.dependency_overrides[get_db] = override_get_db


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _teardown() -> None:
    app.dependency_overrides.clear()


async def test_list_job_categories_without_authentication_succeeds(db_session: AsyncSession) -> None:
    await JobCategoryRepository(db_session).create(name="Plumbing")
    await JobCategoryRepository(db_session).create(name="Electrical")
    await db_session.commit()

    _use_test_db(db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/job-categories")
    finally:
        await _teardown()

    assert response.status_code == 200
    names = {category["name"] for category in response.json()}
    assert {"Plumbing", "Electrical"}.issubset(names)


async def test_list_job_categories_returns_real_ids_not_placeholders(db_session: AsyncSession) -> None:
    category = await JobCategoryRepository(db_session).create(name="Carpentry")
    await db_session.commit()

    _use_test_db(db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/job-categories")
    finally:
        await _teardown()

    assert response.status_code == 200
    matching = [c for c in response.json() if c["name"] == "Carpentry"]
    assert len(matching) == 1
    assert matching[0]["category_id"] == str(category.category_id)
