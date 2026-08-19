"""Aggregator for all v1 API endpoint routers.

Application-specific routers (payments, ...) are registered here as they
are implemented in later tasks.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    applications,
    businesses,
    device_tokens,
    job_categories,
    jobs,
    messages,
    notifications,
    users,
    workers,
)

api_router = APIRouter()
api_router.include_router(users.router)
api_router.include_router(workers.router)
api_router.include_router(businesses.router)
api_router.include_router(jobs.router)
api_router.include_router(applications.router)
api_router.include_router(job_categories.router)
api_router.include_router(device_tokens.router)
api_router.include_router(notifications.router)
api_router.include_router(messages.router)
