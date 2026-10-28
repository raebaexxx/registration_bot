from __future__ import annotations

from app.config import get_settings
from app.db.models import User


def is_admin(user: User | None) -> bool:
    return user is not None and user.tg_id in get_settings().admin_ids
