from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import User


class AppMiddleware(BaseMiddleware):
    """Open one DB session per update and keep the Telegram user in sync."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            tg_user = getattr(event, "from_user", None)
            if tg_user is not None and not tg_user.is_bot:
                user = await session.get(User, tg_user.id)
                if user is None:
                    user = User(
                        tg_id=tg_user.id,
                        username=tg_user.username,
                        first_name=tg_user.first_name,
                        last_name=tg_user.last_name,
                    )
                    session.add(user)
                else:
                    user.username = tg_user.username
                    user.first_name = tg_user.first_name
                    user.last_name = tg_user.last_name
                await session.commit()
                data["user"] = user
            return await handler(event, data)


__all__ = ["AppMiddleware", "CallbackQuery", "Message"]
