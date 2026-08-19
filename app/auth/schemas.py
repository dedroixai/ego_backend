"""Verified Firebase identity, as extracted from a decoded ID token.

Deliberately a narrow, explicit model - not the raw decoded-token dict -
so only the claims this backend actually uses are ever passed around.
"""

from pydantic import BaseModel, ConfigDict


class FirebaseUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    uid: str
    phone_number: str | None = None
    email: str | None = None
    email_verified: bool = False
