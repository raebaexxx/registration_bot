from __future__ import annotations

from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app import callbacks as cb
from app import texts
from app.config import get_settings
from app.constants import Category, GameStatus
from app.db.base import utcnow
from app.filters import IsAdmin
from app.handlers.admin.common import (
    notify_offers,
    show_event_card,
    show_game_card,
    show_participants,
)
from app.keyboards import admin as admin_keyboards
from app.services import events as event_service
from app.services import registrations as registration_service
from app.services.notifier import send_game_cancelled
from app.services.registrations import CancelResult
from app.states import GameCreate, GameLimit
from app.utils.telegram import answer_message, edit_or_answer
from app.utils.time import (
    combine_local,
    format_date,
    parse_time_input,
)

router = Router(name="admin_games")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


async def _finish_game_creation(
    target: CallbackQuery | Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    settings = get_settings()
    data = await state.get_data()
    await state.clear()

    try:
        event_id = int(data["event_id"])
        category = Category(data["category"])
        starts_at = datetime.fromisoformat(data["starts_at"])
        capacity = int(data["capacity"])
        title = str(data["title"])
    except (KeyError, TypeError, ValueError):
        if isinstance(target, CallbackQuery):
            await target.answer("Не удалось создать игру.", show_alert=True)
        else:
            await answer_message(target, "Не удалось создать игру.")
        return

    event = await event_service.get_event(session, event_id)
    if event is None:
        if isinstance(target, CallbackQuery):
            await target.answer("Встреча не найдена.", show_alert=True)
        else:
            await answer_message(target, "Встреча не найдена.")
        return

    game = await event_service.add_game(
        session,
        event_id,
        category,
        title,
        starts_at,
        capacity,
        data.get("place"),
        data.get("description"),
    )
    if game is None:
        if isinstance(target, CallbackQuery):
            await target.answer("Не удалось создать игру.", show_alert=True)
        else:
            await answer_message(target, "Не удалось создать игру.")
        return

    game = await event_service.get_game_with_event(session, game.id)
    if game is None:
        return
    counts = await registration_service.get_counts(session, game)
    text = texts.admin_game_card_text(game, counts, settings.tz)
    keyboard = admin_keyboards.game_card(game, counts)

    if isinstance(target, CallbackQuery):
        await edit_or_answer(target, text, keyboard)
    else:
        await answer_message(target, text, keyboard)


@router.callback_query(F.data.startswith("admin:game:new:"))
async def cb_game_new(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    parts = callback.data.split(":")
    event_id = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
    event = await event_service.get_event(session, event_id)
    if event is None:
        await callback.answer("Встреча не найдена.", show_alert=True)
        return
    await edit_or_answer(
        callback,
        f"➕ <b>Новая игра</b>\nВстреча: {format_date(event.event_date)}\n\nВыбери категорию:",
        admin_keyboards.game_category(event_id),
    )


@router.callback_query(F.data.startswith("admin:game:cat:"))
async def cb_game_category(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    parts = callback.data.split(":")
    if len(parts) < 5 or not parts[3].isdigit():
        await callback.answer("Некорректные данные.", show_alert=True)
        return
    event_id = int(parts[3])
    try:
        category = Category(parts[4])
    except ValueError:
        await callback.answer("Неизвестная категория.", show_alert=True)
        return

    event = await event_service.get_event(session, event_id)
    if event is None:
        await callback.answer("Встреча не найдена.", show_alert=True)
        return

    await state.clear()
    await state.set_state(GameCreate.waiting_title)
    await state.update_data(event_id=event_id, category=category.value)
    await edit_or_answer(
        callback,
        texts.ask_game_title_text(category),
        admin_keyboards.fsm_cancel(),
    )


@router.message(GameCreate.waiting_title)
async def msg_game_title(message: Message, session: AsyncSession, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title or len(title) > 100:
        await answer_message(message, "Название должно быть от 1 до 100 символов.")
        return

    data = await state.get_data()
    event_id = int(data.get("event_id", 0))
    event = await event_service.get_event(session, event_id)
    if event is None:
        await state.clear()
        await answer_message(message, "Встреча не найдена.")
        return

    await state.update_data(title=title)
    await state.set_state(GameCreate.waiting_time)
    await answer_message(
        message,
        texts.ask_game_time_text(event),
        admin_keyboards.fsm_cancel(),
    )


@router.message(GameCreate.waiting_time)
async def msg_game_time(message: Message, session: AsyncSession, state: FSMContext) -> None:
    parsed = parse_time_input(message.text or "")
    if parsed is None:
        await answer_message(message, texts.invalid_time_text(), admin_keyboards.fsm_cancel())
        return

    settings = get_settings()
    data = await state.get_data()
    event_id = int(data.get("event_id", 0))
    event = await event_service.get_event(session, event_id)
    if event is None:
        await state.clear()
        await answer_message(message, "Встреча не найдена.")
        return

    starts_at = combine_local(event.event_date, parsed, settings.tz)
    if starts_at <= utcnow():
        await answer_message(
            message,
            texts.past_datetime_text(),
            admin_keyboards.fsm_cancel(),
        )
        return

    await state.update_data(starts_at=starts_at.isoformat())
    await state.set_state(GameCreate.waiting_capacity)
    await answer_message(
        message,
        texts.ask_game_capacity_text(),
        admin_keyboards.fsm_cancel(),
    )


@router.message(GameCreate.waiting_capacity)
async def msg_game_capacity(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    try:
        capacity = int(raw)
    except ValueError:
        await answer_message(
            message,
            texts.invalid_capacity_text(),
            admin_keyboards.fsm_cancel(),
        )
        return
    if capacity <= 0 or capacity > 1000:
        await answer_message(
            message,
            "Лимит должен быть от 1 до 1000.",
            admin_keyboards.fsm_cancel(),
        )
        return

    await state.update_data(capacity=capacity)
    await state.set_state(GameCreate.waiting_place)
    await answer_message(
        message,
        texts.ask_game_place_text(),
        admin_keyboards.optional_field(),
    )


@router.message(GameCreate.waiting_place)
async def msg_game_place(message: Message, state: FSMContext) -> None:
    place = (message.text or "").strip()
    if len(place) > 200:
        await answer_message(
            message,
            "Слишком длинное место (до 200 символов).",
            admin_keyboards.optional_field(),
        )
        return
    await state.update_data(place=place or None)
    await state.set_state(GameCreate.waiting_description)
    await answer_message(
        message,
        texts.ask_game_description_text(),
        admin_keyboards.optional_field(),
    )


@router.message(GameCreate.waiting_description)
async def msg_game_description(message: Message, session: AsyncSession, state: FSMContext) -> None:
    description = (message.text or "").strip()
    if len(description) > 1000:
        await answer_message(
            message,
            "Слишком длинное описание (до 1000 символов).",
            admin_keyboards.optional_field(),
        )
        return
    await state.update_data(description=description or None)
    await _finish_game_creation(message, session, state)


@router.callback_query(F.data == cb.fsm_skip())
async def cb_skip_optional(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    current = await state.get_state()
    if current == GameCreate.waiting_place.state:
        await state.update_data(place=None)
        await state.set_state(GameCreate.waiting_description)
        await edit_or_answer(
            callback,
            texts.ask_game_description_text(),
            admin_keyboards.optional_field(),
        )
        return
    if current == GameCreate.waiting_description.state:
        await state.update_data(description=None)
        await _finish_game_creation(callback, session, state)
        return
    await callback.answer()


@router.callback_query(F.data == cb.fsm_cancel())
async def cb_fsm_cancel(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    settings = get_settings()

    game_id = data.get("game_id")
    if game_id:
        await show_game_card(callback, session, int(game_id), settings.tz)
        return
    event_id = data.get("event_id")
    if event_id:
        await show_event_card(callback, session, int(event_id), settings.tz)
        return
    await edit_or_answer(callback, texts.admin_menu_text(), admin_keyboards.admin_menu())


@router.callback_query(F.data.startswith("admin:game:parts:"))
async def cb_game_participants(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    await state.clear()
    parts = callback.data.split(":")
    if len(parts) < 5 or not parts[3].isdigit():
        await callback.answer("Игра не найдена.", show_alert=True)
        return
    game_id = int(parts[3])
    page = int(parts[4]) if parts[4].isdigit() else 0
    await show_participants(callback, session, game_id, page, get_settings().tz)


@router.callback_query(F.data.startswith("admin:game:limit:"))
async def cb_game_limit(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    parts = callback.data.split(":")
    game_id = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
    game = await registration_service.get_game(session, game_id)
    if game is None:
        await callback.answer("Игра не найдена.", show_alert=True)
        return
    counts = await registration_service.get_counts(session, game)
    await state.clear()
    await state.set_state(GameLimit.waiting_value)
    await state.update_data(game_id=game_id)
    await edit_or_answer(
        callback,
        texts.ask_game_limit_text(game, counts),
        admin_keyboards.fsm_cancel(),
    )


@router.message(GameLimit.waiting_value)
async def msg_game_limit(
    message: Message, session: AsyncSession, state: FSMContext, bot: Bot
) -> None:
    try:
        value = int((message.text or "").strip())
    except ValueError:
        await answer_message(
            message,
            texts.invalid_capacity_text(),
            admin_keyboards.fsm_cancel(),
        )
        return
    if value <= 0 or value > 1000:
        await answer_message(
            message,
            "Лимит должен быть от 1 до 1000.",
            admin_keyboards.fsm_cancel(),
        )
        return

    settings = get_settings()
    data = await state.get_data()
    game_id = int(data.get("game_id", 0))
    outcome = await registration_service.change_capacity(
        session, game_id, value, settings.waitlist_offer_minutes
    )
    if not outcome.ok:
        await answer_message(
            message,
            outcome.error or "Не удалось изменить лимит.",
            admin_keyboards.fsm_cancel(),
        )
        return

    await state.clear()
    if outcome.offers:
        await notify_offers(bot, outcome.offers, settings)

    game = await registration_service.get_game(session, game_id)
    if game is None:
        await answer_message(message, "Игра не найдена.")
        return
    counts = await registration_service.get_counts(session, game)
    await answer_message(
        message,
        texts.admin_game_card_text(game, counts, settings.tz),
        admin_keyboards.game_card(game, counts),
    )


@router.callback_query(F.data.startswith("admin:game:close:"))
async def cb_game_close(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    game_id = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
    game = await event_service.set_game_status(session, game_id, GameStatus.CLOSED)
    if game is None:
        await callback.answer("Игра не найдена.", show_alert=True)
        return
    await callback.answer("Запись закрыта.")
    await show_game_card(callback, session, game_id, get_settings().tz, answer=False)


@router.callback_query(F.data.startswith("admin:game:open:"))
async def cb_game_open(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    game_id = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
    game = await event_service.set_game_status(session, game_id, GameStatus.OPEN)
    if game is None:
        await callback.answer("Игра не найдена.", show_alert=True)
        return
    await callback.answer("Запись открыта.")
    await show_game_card(callback, session, game_id, get_settings().tz, answer=False)


@router.callback_query(F.data.startswith("admin:game:cancelask:"))
async def cb_game_cancel_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    game_id = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
    game = await registration_service.get_game(session, game_id)
    if game is None:
        await callback.answer("Игра не найдена.", show_alert=True)
        return
    await edit_or_answer(
        callback,
        texts.game_cancel_confirm_text(game, get_settings().tz),
        admin_keyboards.confirm_cancel_game(game_id),
    )


@router.callback_query(F.data.startswith("admin:game:cancel:"))
async def cb_game_cancel(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    settings = get_settings()
    parts = callback.data.split(":")
    game_id = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
    game, affected = await event_service.cancel_game(session, game_id)
    if game is None:
        await callback.answer("Игра не найдена.", show_alert=True)
        return
    await send_game_cancelled(bot, game, affected, settings.tz)
    await callback.answer(f"Игра отменена. Уведомлений: {len(affected)}.")
    await show_event_card(callback, session, game.event_id, settings.tz, answer=False)


@router.callback_query(F.data.startswith("admin:game:deleteask:"))
async def cb_game_delete_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    game_id = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
    game = await registration_service.get_game(session, game_id)
    if game is None:
        await callback.answer("Игра не найдена.", show_alert=True)
        return
    await edit_or_answer(
        callback,
        texts.game_delete_confirm_text(game),
        admin_keyboards.confirm_delete_game(game_id),
    )


@router.callback_query(F.data.startswith("admin:game:delete:"))
async def cb_game_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    settings = get_settings()
    parts = callback.data.split(":")
    game_id = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
    game = await registration_service.get_game(session, game_id)
    if game is None:
        await callback.answer("Игра не найдена.", show_alert=True)
        return
    event_id = game.event_id
    deleted = await event_service.delete_game(session, game_id)
    if not deleted:
        await callback.answer(
            "Нельзя удалить игру с записями. Сначала отмени игру.",
            show_alert=True,
        )
        return
    await callback.answer("Игра удалена.")
    await show_event_card(callback, session, event_id, settings.tz, answer=False)


@router.callback_query(F.data.startswith("admin:part:rmask:"))
async def cb_part_remove_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    if len(parts) < 6:
        await callback.answer("Участник не найден.", show_alert=True)
        return
    game_id = int(parts[3]) if parts[3].isdigit() else 0
    registration_id = int(parts[4]) if parts[4].isdigit() else 0
    page = int(parts[5]) if parts[5].isdigit() else 0
    registration = await registration_service.get_registration(session, registration_id)
    if registration is None:
        await callback.answer("Участник не найден.", show_alert=True)
        return
    await edit_or_answer(
        callback,
        texts.participant_remove_confirm_text(registration),
        admin_keyboards.confirm_remove(game_id, registration_id, page),
    )


@router.callback_query(F.data.startswith("admin:part:rm:"))
async def cb_part_remove(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    settings = get_settings()
    parts = callback.data.split(":")
    if len(parts) < 6:
        await callback.answer("Участник не найден.", show_alert=True)
        return
    game_id = int(parts[3]) if parts[3].isdigit() else 0
    registration_id = int(parts[4]) if parts[4].isdigit() else 0
    page = int(parts[5]) if parts[5].isdigit() else 0
    outcome = await registration_service.remove_registration_by_id(
        session, registration_id, settings.waitlist_offer_minutes
    )
    if outcome.result == CancelResult.NOT_FOUND:
        await callback.answer("Участник не найден.", show_alert=True)
        return
    if outcome.offer is not None:
        await notify_offers(bot, [outcome.offer], settings)
    await callback.answer("Участник удалён.")
    await show_participants(callback, session, game_id, page, settings.tz, answer=False)


@router.callback_query(F.data.startswith("admin:game:"))
async def cb_game_card(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        await callback.answer("Игра не найдена.", show_alert=True)
        return
    await show_game_card(callback, session, int(parts[2]), get_settings().tz)


__all__ = ["router"]
