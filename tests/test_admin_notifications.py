from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.services import registrations as service
from app.services.notifications import (
    admin_game_keyboard,
    build_admin_cancellation_text,
    build_admin_registration_text,
)
from app.services.notifier import (
    send_admin_cancellation,
    send_admin_new_registration,
)
from tests.helpers import create_event, create_game, create_user

TZ = ZoneInfo("Europe/Moscow")


async def test_admin_registration_texts(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=1)
    user1 = await create_user(session, 1)
    user2 = await create_user(session, 2)

    first = await service.register_for_game(session, game.id, user1.tg_id)
    text = build_admin_registration_text(user1, first, TZ)
    assert "Новая запись" in text
    assert "Тест" in text
    assert "Мафия" in text
    assert "Занято 1 из 1" in text

    second = await service.register_for_game(session, game.id, user2.tg_id)
    waitlist_text = build_admin_registration_text(user2, second, TZ)
    assert "Новая запись в лист ожидания" in waitlist_text
    assert "позиция 1" in waitlist_text

    keyboard = admin_game_keyboard(game.id)
    assert keyboard.inline_keyboard[0][0].callback_data == f"admin:game:{game.id}"


async def test_admin_cancellation_texts(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=1)
    user1 = await create_user(session, 1)
    user2 = await create_user(session, 2)

    await service.register_for_game(session, game.id, user1.tg_id)
    await service.register_for_game(session, game.id, user2.tg_id)

    outcome = await service.cancel_registration(session, game.id, user1.tg_id)
    assert outcome.previous_status == "confirmed"
    text = build_admin_cancellation_text(user1, outcome, TZ)
    assert "Запись отменена" in text
    assert "Было: ✅ Подтверждена" in text
    assert "Предложение отправлено следующему" in text

    declined = await service.cancel_registration(session, game.id, user2.tg_id)
    assert declined.previous_status == "offered"
    declined_text = build_admin_cancellation_text(user2, declined, TZ)
    assert "Было: 🎟 Предложено место" in declined_text
    assert "отказался от предложенного места" in declined_text


async def test_admin_notifications_are_sent_to_all_admins(
    session: AsyncSession,
) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=5)
    user = await create_user(session)
    outcome = await service.register_for_game(session, game.id, user.tg_id)

    settings = Settings(
        admin_ids=[1, 2],
        admin_notifications=True,
        _env_file=None,
    )
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=True)

    sent = await send_admin_new_registration(bot, settings, user, outcome)
    assert sent == 2
    chat_ids = [call.kwargs["chat_id"] for call in bot.send_message.await_args_list]
    assert chat_ids == [1, 2]

    disabled = Settings(
        admin_ids=[1, 2],
        admin_notifications=False,
        _env_file=None,
    )
    bot.send_message.reset_mock()
    assert await send_admin_new_registration(bot, disabled, user, outcome) == 0
    bot.send_message.assert_not_awaited()


async def test_admin_cancellation_notification_is_sent(
    session: AsyncSession,
) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=5)
    user = await create_user(session)
    await service.register_for_game(session, game.id, user.tg_id)
    outcome = await service.cancel_registration(session, game.id, user.tg_id)

    settings = Settings(admin_ids=[1], _env_file=None)
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=True)

    sent = await send_admin_cancellation(bot, settings, user, outcome)
    assert sent == 1
    bot.send_message.assert_awaited_once()
