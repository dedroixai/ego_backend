"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.db.dependencies import DBSession, get_db

__all__ = ["DBSession", "get_db", "SettingsDep"]

SettingsDep = Annotated[Settings, Depends(get_settings)]
