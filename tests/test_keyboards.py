from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards import admin as admin_kb
from app.keyboards import user as user_kb
from app.services import events as event_service
from app.services import registrations as service
from tests.helpers import create_event, create_game, create_user

TZ = ZoneInfo("Europe/Moscow")


async def test_user_keyboards(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=5)
    user = await create_user(session)
    await service.register_for_game(session, game.id, user.tg_id)

    counts = await service.get_counts_for_games(session, [game.id])
    registrations = await service.get_active_registrations(session, user.tg_id)

    main = user_kb.main_menu(True)
    assert main.inline_keyboard[-1][0].text == "🛠 Админ-панель"

    categories = user_kb.categories()
    assert categories.inline_keyboard[0][0].callback_data == "cat:adult:0"

    games = user_kb.games_list([game], counts, "adult", 0, 1, TZ)
    assert games.inline_keyboard[0][0].callback_data == f"game:{game.id}"

    card = user_kb.game_card(game, counts[game.id], registrations[0], TZ)
    assert card.inline_keyboard[0][0].text == "❌ Отменить запись"

    my = user_kb.my_registrations(registrations, TZ)
    assert my.inline_keyboard[0][0].callback_data == f"game:{game.id}"


async def test_admin_keyboards(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=5)
    user = await create_user(session)
    await service.register_for_game(session, game.id, user.tg_id)

    event = await event_service.get_event(session, event.id)
    assert event is not None
    counts = await service.get_counts_for_games(session, [game.id])
    registrations = await service.get_game_registrations(session, game.id)

    menu = admin_kb.admin_menu()
    assert menu.inline_keyboard[0][0].callback_data == "admin:events:0"

    events = admin_kb.events_list([event], 0, 1)
    assert events.inline_keyboard[0][0].callback_data == f"admin:event:{event.id}"

    event_card = admin_kb.event_card(event, counts)
    assert any(
        button.callback_data == f"admin:game:new:{event.id}"
        for row in event_card.inline_keyboard
        for button in row
    )

    game_card = admin_kb.game_card(game, counts[game.id])
    assert any(
        button.callback_data == f"admin:game:parts:{game.id}:0"
        for row in game_card.inline_keyboard
        for button in row
    )

    participants = admin_kb.participants(game.id, registrations, 0, 1)
    assert participants.inline_keyboard[0][0].callback_data.startswith("admin:part:rmask:")

    quick = admin_kb.date_quick(date(2026, 10, 31), date(2026, 11, 1))
    assert quick.inline_keyboard[0][0].callback_data == "admin:event:newdate:2026-10-31"

    optional = admin_kb.optional_field()
    assert optional.inline_keyboard[0][0].callback_data == "fsm:skip"
    assert optional.inline_keyboard[1][0].callback_data == "fsm:cancel"
