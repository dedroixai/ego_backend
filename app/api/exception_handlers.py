"""Translates service-layer exceptions into HTTP responses.

`app.services.exceptions.ServiceError` and its subclasses are deliberately
NOT HTTP-aware (docs/service-layer.md: "Translating these further into
HTTP status codes is left entirely to a future API layer"). This is that
layer - it belongs here (in `app/api/`), not in `app/core/exceptions.py`,
since `app.core` is foundational and shouldn't depend on `app.services`.

Security note: `BusinessRuleViolationError`'s message can originate from
`app.services.exceptions.translate_repository_error`, which may embed the
raw underlying Postgres/SQLAlchemy error text (safe to keep in a repository
exception, which never reaches the client directly - but NOT safe to echo
verbatim over HTTP). So, unlike the other service exceptions, its message
is logged server-side but never sent to the client - Step 4 of this task
("Do not expose SQLAlchemy exceptions... database errors").
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.services.exceptions import (
    BusinessRuleViolationError,
    DuplicateOperationError,
    InvalidStateTransitionError,
    ResourceNotFoundError,
    ServiceError,
    UnauthorizedOperationError,
)

logger = logging.getLogger(__name__)


def _status_for(exc: ServiceError) -> int:
    if isinstance(exc, ResourceNotFoundError):
        return status.HTTP_404_NOT_FOUND
    if isinstance(exc, UnauthorizedOperationError):
        return status.HTTP_403_FORBIDDEN
    if isinstance(exc, (DuplicateOperationError, InvalidStateTransitionError)):
        return status.HTTP_409_CONFLICT
    if isinstance(exc, BusinessRuleViolationError):
        return status.HTTP_422_UNPROCESSABLE_ENTITY
    return status.HTTP_400_BAD_REQUEST


def register_service_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_exception_handler(request: Request, exc: ServiceError) -> JSONResponse:
        status_code = _status_for(exc)

        if isinstance(exc, BusinessRuleViolationError):
            # May contain raw repository/DB error text - never echoed to the client.
            logger.warning("Business rule violation on %s: %s", request.url.path, exc)
            detail: object = "This operation could not be completed."
        else:
            logger.warning("Service error on %s: %s", request.url.path, exc)
            detail = str(exc)

        return JSONResponse(status_code=status_code, content={"detail": detail})
