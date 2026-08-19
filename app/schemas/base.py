"""Shared base classes for API schemas.

`ORMModel` is used by every *Response* schema so FastAPI/Pydantic can build
them directly from SQLAlchemy ORM instances (`Model.model_validate(orm_obj)`)
without exposing the ORM objects themselves.

`RequestModel` is used by every *Create*/*Update* schema. `extra="forbid"`
is a deliberate security choice (see Step 4 of this task): a client cannot
smuggle an undeclared field - e.g. `user_id`, `status`, `created_at` - into
a request body and have it silently dropped. Any unexpected field raises a
validation error instead.
"""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
