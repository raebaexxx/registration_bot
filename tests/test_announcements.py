from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import events as event_service
from app.services import registrations as service
from app.services.announcements import (
    build_announcement_keyboard,
    build_announcement_text,
    publish_announcement,
)
from tests.helpers import create_event, create_game, create_user

TZ = ZoneInfo("Europe/Moscow")


async def test_announcement_text_and_buttons(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=5)
    user = await create_user(session)
    await service.register_for_game(session, game.id, user.tg_id)

    event = await event_service.get_event(session, event.id)
    assert event is not None
    counts = await service.get_counts_for_games(session, [game.id])
    text = build_announcement_text(event, counts, TZ)
    assert "Игровая суббота" in text
    assert "Мафия" in text
    assert "свободно 4 из 5" in text

    keyboard = build_announcement_keyboard(event, "test_bot", TZ)
    assert keyboard is not None
    assert keyboard.inline_keyboard[0][0].url == (f"https://t.me/test_bot?start=game_{game.id}")


async def test_publish_announcement_creates_and_updates_post(
    session: AsyncSession,
) -> None:
    event = await create_event(session)
    await create_game(session, event, capacity=5)

    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=777))
    bot.edit_message_text = AsyncMock()

    result = await publish_announcement(bot, session, event.id, "@test_channel", "test_bot", TZ)
    assert result.ok is True
    assert result.message_id == 777
    assert result.updated is False
    bot.send_message.assert_awaited_once()

    event = await event_service.get_event(session, event.id)
    assert event is not None
    assert event.channel_post is not None
    assert event.channel_post.message_id == 777

    updated = await publish_announcement(bot, session, event.id, "@test_channel", "test_bot", TZ)
    assert updated.ok is True
    assert updated.updated is True
    bot.edit_message_text.assert_awaited_once()


async def test_publish_announcement_requires_channel(session: AsyncSession) -> None:
    event = await create_event(session)
    await create_game(session, event, capacity=5)

    bot = MagicMock()
    result = await publish_announcement(bot, session, event.id, None, "test_bot", TZ)
    assert result.ok is False
    assert result.error is not None
