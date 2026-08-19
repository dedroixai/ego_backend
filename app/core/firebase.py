"""Firebase Admin SDK initialization.

Used ONLY for server-side verification of Firebase ID tokens
(`firebase_admin.auth.verify_id_token`) - see app/auth/dependencies.py.
No application data is stored in Firebase; Supabase PostgreSQL remains the
source of truth (see docs/authentication.md).

Credentials are never hardcoded - loaded from `FIREBASE_CREDENTIALS_JSON`
or `FIREBASE_CREDENTIALS_FILE` (see app/core/config.py), neither of which
is committed to git.
"""

import json
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials

from app.core.config import get_settings


@lru_cache
def get_firebase_app() -> firebase_admin.App:
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass  # no default app initialized yet

    settings = get_settings()

    if settings.FIREBASE_CREDENTIALS_JSON:
        cert = credentials.Certificate(json.loads(settings.FIREBASE_CREDENTIALS_JSON))
    elif settings.FIREBASE_CREDENTIALS_FILE:
        cert = credentials.Certificate(settings.FIREBASE_CREDENTIALS_FILE)
    else:
        raise RuntimeError(
            "Firebase Admin SDK is not configured - set FIREBASE_CREDENTIALS_JSON "
            "or FIREBASE_CREDENTIALS_FILE in the environment. See .env.example "
            "and docs/authentication.md."
        )

    return firebase_admin.initialize_app(cert)
