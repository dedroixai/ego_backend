"""Firebase-based authentication AND authorization for the EGO API.

Firebase Authentication owns user identity (Flutter <-> Firebase). This
package verifies Firebase ID tokens server-side, maps the verified
identity onto EGO's own `User` record in Supabase PostgreSQL (which
remains the source of truth for application data), and separately
determines what that user is allowed to do (Worker/Business authorization)
from EGO's own database - never from a client-supplied role claim. See
docs/authentication.md and docs/user-role-architecture.md.
"""

from app.auth.dependencies import (
    get_current_business,
    get_current_firebase_user,
    get_current_user,
    get_current_worker,
)
from app.auth.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessProfileRequiredError,
    EgoUserNotFoundError,
    ExpiredTokenError,
    FirebaseUserNotFoundError,
    InvalidTokenError,
    MalformedAuthorizationHeaderError,
    MissingAuthorizationHeaderError,
    RevokedTokenError,
    UserMappingNotConfiguredError,
    WorkerProfileRequiredError,
)
from app.auth.schemas import FirebaseUser

__all__ = [
    "FirebaseUser",
    "get_current_firebase_user",
    "get_current_user",
    "get_current_worker",
    "get_current_business",
    "AuthenticationError",
    "MissingAuthorizationHeaderError",
    "MalformedAuthorizationHeaderError",
    "InvalidTokenError",
    "ExpiredTokenError",
    "RevokedTokenError",
    "FirebaseUserNotFoundError",
    "EgoUserNotFoundError",
    "UserMappingNotConfiguredError",
    "AuthorizationError",
    "WorkerProfileRequiredError",
    "BusinessProfileRequiredError",
]
