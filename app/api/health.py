"""Unversioned infrastructure endpoints (liveness/readiness probes)."""

import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.db.database import check_database_connection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Plain liveness check - does not touch the database."""
    return {"status": "ok"}


@router.get("/health/db")
async def database_health_check() -> JSONResponse:
    """Readiness check - confirms the app can reach Supabase PostgreSQL."""
    try:
        await check_database_connection()
    except Exception:
        logger.exception("Database connectivity check failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "database": "unreachable"},
        )
    return JSONResponse(content={"status": "ok", "database": "connected"})
