"""Default (placeholder) job images.

Jobs are allowed to have no photo (`Job.image_url` is nullable), which
left the app showing an empty dark box. The backend now ships a small set
of generated trade illustrations under `app/static/job-images/` (served at
`/static/job-images/<slug>.jpg`, see `app/main.py`) and every job response
carries a `default_image_url` picked from the job's own title/description.

This is presentation-only and derived on read: nothing is stored, and the
real `image_url` is never filled in with a default - so a job edited later
can't accidentally save a placeholder as its photo, and clients can still
tell "has a real photo" apart from "showing a default".
"""

STATIC_PREFIX = "/static"
JOB_IMAGES_PATH = f"{STATIC_PREFIX}/job-images"

# First match wins - more specific trades before broad ones.
_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("electrician", ("electric", "wiring", "wireman")),
    ("plumbing", ("plumb", "pipe", "leak", "tap ", "sanitary")),
    ("painting", ("paint", "polish")),
    ("carpentry", ("carpent", "wood", "furniture")),
    ("cooking", ("cook", "chef", "cater", "kitchen", "food", "restaurant", "waiter")),
    ("delivery", ("deliver", "driver", "drive", "rider", "courier", "logistic", "transport")),
    ("cleaning", ("clean", "housekeep", "maid", "sweep", "laundry")),
    ("security", ("security", "guard", "watchman")),
    ("gardening", ("garden", "landscap", "plant")),
    ("retail", ("shop", "store", "retail", "sales", "cashier")),
    ("construction", ("construct", "mason", "site", "labour", "labor", "helper", "loading", "welder")),
]

DEFAULT_SLUG = "general"
ALL_SLUGS = [slug for slug, _ in _KEYWORDS] + [DEFAULT_SLUG]


def default_job_image_slug(title: str, description: str | None = None) -> str:
    text = f" {title} {description or ''} ".lower()
    for slug, keywords in _KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return slug
    return DEFAULT_SLUG


def default_job_image_url(title: str, description: str | None = None) -> str:
    """Path (relative to the API's base URL) of the default image for a job."""
    return f"{JOB_IMAGES_PATH}/{default_job_image_slug(title, description)}.jpg"
