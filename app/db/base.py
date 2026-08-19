"""Declarative base for ORM models.

Application entities live under `app/models/` and are imported via
`app/models/__init__.py`, which populates `Base.metadata` so Alembic's
env.py can discover every model for autogeneration.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Consistent constraint naming so Alembic autogenerate produces stable,
# readable migration names instead of database-assigned defaults.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
