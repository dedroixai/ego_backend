"""API schemas for USER.

Source: app/models/user.py, docs/database-design.md Section 1.1.

`role` and `kyc_status` have no defined set of allowed values anywhere in
the diagrams (docs/database-design.md Section 7.3) - validated as plain
non-empty strings, not restricted to a Literal/enum, matching the deliberate
choice already made at the DB layer (docs/model-implementation.md).
`kyc_status` is server-controlled (defaults to 'pending', advanced by KYC
verification) and is never client-writable.
"""

import re
import uuid
from datetime import date, datetime

from pydantic import Field, field_validator

from app.schemas.base import ORMModel, RequestModel

_PHONE_PATTERN = re.compile(r"^[+0-9\s\-()]+$")


class UserCreate(RequestModel):
    phone: str = Field(min_length=7, max_length=20)
    language: str = Field(min_length=2, max_length=10)
    role: str = Field(min_length=1, max_length=20)
    dob: date | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone_format(cls, value: str) -> str:
        if not _PHONE_PATTERN.match(value):
            raise ValueError("phone must contain only digits, spaces, and + - ( )")
        return value

    @field_validator("dob")
    @classmethod
    def validate_dob_not_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("dob cannot be in the future")
        return value


class UserUpdate(RequestModel):
    """Profile fields a user can self-update. Identity (`phone`, `role`) and
    system-controlled (`kyc_status`) fields are intentionally excluded."""

    language: str | None = Field(default=None, min_length=2, max_length=10)
    dob: date | None = None

    @field_validator("dob")
    @classmethod
    def validate_dob_not_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("dob cannot be in the future")
        return value


class UserResponse(ORMModel):
    user_id: uuid.UUID
    phone: str
    language: str
    role: str
    kyc_status: str
    created_at: datetime
    dob: date | None
