from __future__ import annotations

from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import GameStatus
from app.handlers.user.common import build_game_view
from app.services import events as event_service
from app.services import registrations as service
from app.services.notifications import build_offer_text
from app.services.registrations import RegisterResult
from app.texts import admin_game_card_text, event_card_text, participants_text
from tests.helpers import create_event, create_game, create_user

TZ = ZoneInfo("Europe/Moscow")


async def test_game_view_for_new_user(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=5)
    user = await create_user(session)

    view = await build_game_view(session, game.id, user.tg_id, TZ)
    assert view is not None
    assert "Мафия" in view.text
    assert "свободно 5" in view.text
    assert view.keyboard.inline_keyboard[0][0].text == "✅ Записаться"


async def test_game_view_after_registration_and_cancel(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=5)
    user = await create_user(session)

    await service.register_for_game(session, game.id, user.tg_id)
    view = await build_game_view(session, game.id, user.tg_id, TZ)
    assert view is not None
    assert "Ты записан" in view.text
    assert view.keyboard.inline_keyboard[0][0].text == "❌ Отменить запись"

    await service.cancel_registration(session, game.id, user.tg_id)
    view = await build_game_view(session, game.id, user.tg_id, TZ)
    assert view is not None
    assert view.registration is None
    assert view.keyboard.inline_keyboard[0][0].text == "✅ Записаться"


async def test_confirmed_user_can_cancel_after_registration_closed(
    session: AsyncSession,
) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=5)
    user = await create_user(session)

    await service.register_for_game(session, game.id, user.tg_id)
    game.status = GameStatus.CLOSED.value
    await session.commit()

    view = await build_game_view(session, game.id, user.tg_id, TZ)
    assert view is not None
    assert "Ты записан" in view.text
    assert "Новые записи закрыты" in view.text
    assert view.keyboard.inline_keyboard[0][0].text == "❌ Отменить запись"


async def test_reserved_offer_can_be_accepted_after_registration_closed(
    session: AsyncSession,
) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=1)
    user1 = await create_user(session, 1)
    user2 = await create_user(session, 2)

    await service.register_for_game(session, game.id, user1.tg_id)
    await service.register_for_game(session, game.id, user2.tg_id)
    await service.cancel_registration(session, game.id, user1.tg_id)

    game.status = GameStatus.CLOSED.value
    await session.commit()

    accepted = await service.register_for_game(session, game.id, user2.tg_id)
    assert accepted.result == RegisterResult.OFFER_ACCEPTED


async def test_game_view_waitlist_and_offer(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=1)
    user1 = await create_user(session, 1)
    user2 = await create_user(session, 2)

    await service.register_for_game(session, game.id, user1.tg_id)
    await service.register_for_game(session, game.id, user2.tg_id)

    view = await build_game_view(session, game.id, user2.tg_id, TZ)
    assert view is not None
    assert "листе ожидания" in view.text
    assert view.keyboard.inline_keyboard[0][0].text == "❌ Выйти из листа ожидания"

    await service.cancel_registration(session, game.id, user1.tg_id)
    view = await build_game_view(session, game.id, user2.tg_id, TZ)
    assert view is not None
    assert "предложено место" in view.text
    assert view.keyboard.inline_keyboard[0][0].text == "✅ Занять место"


async def test_admin_texts(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=5)
    user = await create_user(session)
    await service.register_for_game(session, game.id, user.tg_id)

    event = await event_service.get_event(session, event.id)
    assert event is not None
    counts = await service.get_counts_for_games(session, [game.id])
    card = event_card_text(event, counts, TZ)
    assert "Игровая суббота" in card
    assert "Мафия" in card
    assert "1/5" in card

    admin_card = admin_game_card_text(game, await service.get_counts(session, game), TZ)
    assert "Занято 1 из 5" in admin_card

    registrations = await service.get_game_registrations(session, game.id)
    participants = participants_text(game, registrations, 0, 1, TZ)
    assert "Тест" in participants
    assert "@tester" in participants


async def test_offer_text(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=1)
    user1 = await create_user(session, 1)
    user2 = await create_user(session, 2)

    await service.register_for_game(session, game.id, user1.tg_id)
    await service.register_for_game(session, game.id, user2.tg_id)
    outcome = await service.cancel_registration(session, game.id, user1.tg_id)
    assert outcome.offer is not None

    text = build_offer_text(outcome.offer, TZ, 120)
    assert "Место освободилось" in text
    assert "Мафия" in text
    assert "2 ч" in text
