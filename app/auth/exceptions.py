"""Authentication exceptions.

Extend `app.core.exceptions.AppException` (Task 2) directly, rather than
introducing a parallel HTTP-aware hierarchy - the app-wide exception
handler registered in `app/core/exceptions.py` already knows how to turn
an `AppException` into a JSON response, so nothing new needs registering.

Every `detail` message here is a static, generic string - never the raw
Firebase SDK exception text - so internal Firebase error details are never
exposed to the client (Step 7/9 of this task).
"""

from fastapi import status

from app.core.exceptions import AppException


class AuthenticationError(AppException):
    """Base class for all authentication failures - HTTP 401."""

    def __init__(self, detail: str = "Authentication required.") -> None:
        super().__init__(detail, status_code=status.HTTP_401_UNAUTHORIZED)


class MissingAuthorizationHeaderError(AuthenticationError):
    def __init__(self) -> None:
        super().__init__("Missing Authorization header.")


class MalformedAuthorizationHeaderError(AuthenticationError):
    def __init__(self) -> None:
        super().__init__("Authorization header must be in the form 'Bearer <token>'.")


class InvalidTokenError(AuthenticationError):
    def __init__(self, detail: str = "Invalid authentication token.") -> None:
        super().__init__(detail)


class ExpiredTokenError(AuthenticationError):
    def __init__(self) -> None:
        super().__init__("Authentication token has expired.")


class RevokedTokenError(AuthenticationError):
    def __init__(self) -> None:
        super().__init__("Authentication token has been revoked.")


class FirebaseUserNotFoundError(AuthenticationError):
    def __init__(self) -> None:
        super().__init__("Firebase user account no longer exists.")


class EgoUserNotFoundError(AuthenticationError):
    def __init__(self) -> None:
        super().__init__("No EGO account is linked to this identity.")


class UserMappingNotConfiguredError(AppException):
    """The server cannot map a verified Firebase identity to an EGO User.

    Not the client's fault (not 401/403) - the server itself isn't able to
    complete this operation yet, pending a schema decision. See
    'AUTHENTICATION SCHEMA DECISION REQUIRED' in docs/authentication.md.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail, status_code=status.HTTP_501_NOT_IMPLEMENTED)


class AuthorizationError(AppException):
    """Base class for all AUTHORIZATION failures - HTTP 403.

    Distinct from `AuthenticationError` (401, "who are you?" - Task 8/9):
    this means "you are authenticated, but not permitted to do this" - see
    docs/user-role-architecture.md Part 2. Never conflate the two status
    codes - a Worker without a Business profile hitting a business-only
    action is a 403, not a 401.
    """

    def __init__(self, detail: str = "You do not have permission to perform this action.") -> None:
        super().__init__(detail, status_code=status.HTTP_403_FORBIDDEN)


class WorkerProfileRequiredError(AuthorizationError):
    def __init__(self) -> None:
        super().__init__("This action requires a Worker profile.")


class BusinessProfileRequiredError(AuthorizationError):
    def __init__(self) -> None:
        super().__init__("This action requires a Business profile.")
