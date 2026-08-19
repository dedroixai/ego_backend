"""Data-access exceptions raised by the repository layer.

These are deliberately NOT HTTP-aware (no status codes, no FastAPI
imports) - the repository layer only identifies *what* went wrong at the
database level. Translating that into an HTTP response is the service/API
layer's job (see docs/repository-layer.md).
"""

from typing import Any


class RepositoryError(Exception):
    """Base class for all repository/data-access errors."""


class RecordNotFoundError(RepositoryError):
    def __init__(self, model_name: str, identifier: Any) -> None:
        self.model_name = model_name
        self.identifier = identifier
        super().__init__(f"{model_name} not found: {identifier!r}")


class DuplicateRecordError(RepositoryError):
    """A unique constraint was violated (Postgres SQLSTATE 23505)."""

    def __init__(self, model_name: str, detail: str | None = None) -> None:
        self.model_name = model_name
        self.detail = detail
        super().__init__(f"Duplicate {model_name}: {detail or 'unique constraint violated'}")


class ForeignKeyViolationError(RepositoryError):
    """A foreign key constraint was violated (Postgres SQLSTATE 23503)."""

    def __init__(self, model_name: str, detail: str | None = None) -> None:
        self.model_name = model_name
        self.detail = detail
        super().__init__(f"Invalid reference on {model_name}: {detail or 'foreign key constraint violated'}")


class ConstraintViolationError(RepositoryError):
    """Any other DB constraint violation (CHECK, NOT NULL, ...) that made it
    past Pydantic validation - a defense-in-depth catch-all."""

    def __init__(self, model_name: str, detail: str | None = None) -> None:
        self.model_name = model_name
        self.detail = detail
        super().__init__(f"Constraint violation on {model_name}: {detail or 'unknown'}")
