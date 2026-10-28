from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from app.config import get_settings
from app.db.models import User


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject, user: User | None = None) -> bool:
        if user is not None:
            return user.tg_id in get_settings().admin_ids
        from_user = getattr(event, "from_user", None)
        return from_user is not None and from_user.id in get_settings().admin_ids
