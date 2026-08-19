"""Data access for HIRING_PARTY.

Source: app/models/business.py, docs/database-design.md Section 1.3.

No extra lookups beyond the inherited `get_by_id` (shared key with USER).
"""

from app.models.business import HiringParty
from app.repositories.base import BaseRepository


class HiringPartyRepository(BaseRepository[HiringParty]):
    model = HiringParty
