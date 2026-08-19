"""Generic base repository.

Implemented because nearly every entity needs the same handful of
operations (get by primary key, create, update, delete, list) - a thin
generic base removes that repetition without hiding anything unusual.
Entity-specific repositories subclass this and add only the queries their
entity actually needs (unique-field lookups, relationship-based listing).

Transaction discipline (see docs/repository-layer.md): methods here call
`session.flush()`, never `session.commit()` or `session.rollback()`. This
lets a caller (a future service layer, or a test) batch multiple repository
calls into one transaction and decide when to commit or roll back - exactly
what Step 4 of this task asks for. `IntegrityError` raised during flush is
caught here, translated to the domain exceptions in
`app.repositories.exceptions` (both instance methods and inspected
Postgres SQLSTATE codes), and re-raised - the caller is still responsible
for rolling back the session afterward before reusing it.
"""

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.repositories.exceptions import (
    ConstraintViolationError,
    DuplicateRecordError,
    ForeignKeyViolationError,
    RecordNotFoundError,
    RepositoryError,
)

ModelT = TypeVar("ModelT", bound=Base)

_UNIQUE_VIOLATION = "23505"
_FOREIGN_KEY_VIOLATION = "23503"


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _translate_integrity_error(self, exc: IntegrityError) -> RepositoryError:
        sqlstate = getattr(exc.orig, "sqlstate", None)
        detail = str(exc.orig) if exc.orig is not None else str(exc)
        model_name = self.model.__name__
        if sqlstate == _UNIQUE_VIOLATION:
            return DuplicateRecordError(model_name, detail)
        if sqlstate == _FOREIGN_KEY_VIOLATION:
            return ForeignKeyViolationError(model_name, detail)
        return ConstraintViolationError(model_name, detail)

    async def get_by_id(self, id_value: Any) -> ModelT | None:
        return await self.session.get(self.model, id_value)

    async def get_by_id_or_raise(self, id_value: Any) -> ModelT:
        instance = await self.get_by_id(id_value)
        if instance is None:
            raise RecordNotFoundError(self.model.__name__, id_value)
        return instance

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        result = await self.session.execute(select(self.model).limit(limit).offset(offset))
        return result.scalars().all()

    async def create(self, **fields: Any) -> ModelT:
        instance = self.model(**fields)
        self.session.add(instance)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise self._translate_integrity_error(exc) from exc
        return instance

    async def update(self, instance: ModelT, **changes: Any) -> ModelT:
        for field, value in changes.items():
            setattr(instance, field, value)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise self._translate_integrity_error(exc) from exc
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self.session.delete(instance)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise self._translate_integrity_error(exc) from exc
