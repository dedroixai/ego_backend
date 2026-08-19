"""Application/business-logic exceptions raised by the service layer.

Deliberately NOT HTTP-aware (no status codes, no FastAPI imports) - per
Step 8 of this task, HTTP translation belongs to a future API layer, not
here. `translate_repository_error` maps the lower (data-access) layer's
exceptions (app.repositories.exceptions) onto this vocabulary so a service
never lets a raw SQLAlchemy/repository exception escape to its caller.
"""

from app.repositories.exceptions import (
    ConstraintViolationError,
    DuplicateRecordError,
    ForeignKeyViolationError,
    RecordNotFoundError,
    RepositoryError,
)


class ServiceError(Exception):
    """Base class for all service/business-logic errors."""


class ResourceNotFoundError(ServiceError):
    def __init__(self, resource: str, identifier: object) -> None:
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} not found: {identifier}")


class UnauthorizedOperationError(ServiceError):
    def __init__(self, message: str = "You are not allowed to perform this operation.") -> None:
        super().__init__(message)


class InvalidStateTransitionError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class DuplicateOperationError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class BusinessRuleViolationError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def translate_repository_error(exc: RepositoryError) -> ServiceError:
    """Map a repository-layer exception onto the service-layer vocabulary."""
    if isinstance(exc, RecordNotFoundError):
        return ResourceNotFoundError(exc.model_name, exc.identifier)
    if isinstance(exc, DuplicateRecordError):
        return DuplicateOperationError(str(exc))
    if isinstance(exc, (ForeignKeyViolationError, ConstraintViolationError)):
        return BusinessRuleViolationError(str(exc))
    return BusinessRuleViolationError(str(exc))
