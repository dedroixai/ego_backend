"""Verifies the app can open a real connection to the configured PostgreSQL
database (Supabase in staging/production) using DATABASE_URL from the
environment. Requires a reachable database - see README "Test the connection".
"""

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.database import engine
from app.main import app


async def test_database_connection_returns_expected_value() -> None:
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))
        assert result.scalar() == 1


def test_health_db_endpoint_reports_connected() -> None:
    with TestClient(app) as client:
        response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
