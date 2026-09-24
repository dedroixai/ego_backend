import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.job import JobListResponse, JobResponse
from app.utils.default_job_image import ALL_SLUGS, default_job_image_slug, default_job_image_url


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Site Electrician", "electrician"),
        ("Fix leaking pipe", "plumbing"),
        ("Wedding catering staff needed", "cooking"),
        ("Delivery rider for the weekend", "delivery"),
        ("Driver for family trip", "delivery"),
        ("Helper (loading)", "construction"),
        ("Night watchman", "security"),
        ("Something unusual", "general"),
    ],
)
def test_default_image_slug_matches_the_trade(title: str, expected: str) -> None:
    assert default_job_image_slug(title) == expected


def test_description_is_used_when_the_title_is_vague() -> None:
    assert default_job_image_slug("Urgent help", "Kitchen sink is leaking badly.") == "plumbing"


def test_every_default_image_is_served() -> None:
    with TestClient(app) as client:
        for slug in ALL_SLUGS:
            response = client.get(f"/static/job-images/{slug}.jpg")
            assert response.status_code == 200, slug
            assert response.headers["content-type"] == "image/jpeg"


def test_job_responses_carry_a_default_image_but_never_fake_a_real_one() -> None:
    common = {
        "job_id": uuid.uuid4(),
        "hiring_party_id": uuid.uuid4(),
        "category_id": uuid.uuid4(),
        "title": "Site Electrician",
        "budget": Decimal("900"),
        "status": "open",
        "location": "Andheri East",
        "image_url": None,
        "created_at": datetime.now(timezone.utc),
    }
    detail = JobResponse(**common, description="Wiring work", duration="per day").model_dump()
    listing = JobListResponse(**common).model_dump()

    for body in (detail, listing):
        assert body["image_url"] is None  # real photo stays empty
        assert body["default_image_url"] == default_job_image_url("Site Electrician")
