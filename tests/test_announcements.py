from __future__ import annotations

from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import registrations as service
from app.services.announcements import (
    build_announcement_keyboard,
    build_announcement_text,
)
from tests.helpers import create_event, create_game, create_user

TZ = ZoneInfo("Europe/Moscow")


async def test_announcement_text_and_buttons(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=5)
    user = await create_user(session)
    await service.register_for_game(session, game.id, user.tg_id)

    from app.services import events as event_service

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
