"""API schemas for JOB_CATEGORY.

Source: app/models/job_category.py, docs/database-design.md Section 1.4.
"""

import uuid

from pydantic import Field

from app.schemas.base import ORMModel, RequestModel


class JobCategoryCreate(RequestModel):
    name: str = Field(min_length=1, max_length=100)


class JobCategoryUpdate(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)


class JobCategoryResponse(ORMModel):
    category_id: uuid.UUID
    name: str
