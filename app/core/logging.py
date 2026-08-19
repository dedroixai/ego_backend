"""Logging configuration for the application."""

import logging
import sys

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()

    logging.basicConfig(
        level=settings.LOG_LEVEL.upper(),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
        force=True,
    )

    # Quiet noisy third-party loggers by default; can be overridden via LOG_LEVEL.
    logging.getLogger("uvicorn.access").setLevel(settings.LOG_LEVEL.upper())
