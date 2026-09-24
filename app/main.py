"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.exception_handlers import register_service_exception_handlers
from app.api.health import router as health_router
from app.api.v1.api import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.request_logging import RequestLoggingMiddleware
from app.utils.default_job_image import STATIC_PREFIX

settings = get_settings()
configure_logging()


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        debug=settings.DEBUG,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Added last so it's outermost - captures every request (including
    # CORS preflight) and the full request/response duration.
    app.add_middleware(RequestLoggingMiddleware)

    register_exception_handlers(app)
    register_service_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Generated default job images (app/utils/default_job_image.py) -
    # public, cacheable, no auth.
    app.mount(STATIC_PREFIX, StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    return app


app = create_application()
