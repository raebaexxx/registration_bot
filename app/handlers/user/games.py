from __future__ import annotations

import math

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app import callbacks as cb
from app import texts
from app.config import get_settings
from app.constants import Category, RegistrationStatus
from app.db.models import User
from app.handlers.user.common import show_game_callback
from app.keyboards import user as user_keyboards
from app.services import registrations as registration_service
from app.services.notifier import send_offer
from app.services.registrations import CancelResult, RegisterResult
from app.utils.telegram import answer_message, edit_or_answer
from app.utils.time import format_datetime

router = Router(name="user_games")
PAGE_SIZE = 8


@router.message(Command("my"))
async def cmd_my(message: Message, user: User, session: AsyncSession) -> None:
    settings = get_settings()
    registrations = await registration_service.get_active_registrations(session, user.tg_id)
    await answer_message(
        message,
        texts.my_registrations_text(registrations, settings.tz),
        user_keyboards.my_registrations(registrations, settings.tz),
    )


@router.callback_query(F.data == cb.MY)
async def cb_my(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    settings = get_settings()
    registrations = await registration_service.get_active_registrations(session, user.tg_id)
    await edit_or_answer(
        callback,
        texts.my_registrations_text(registrations, settings.tz),
        user_keyboards.my_registrations(registrations, settings.tz),
    )


@router.callback_query(F.data.startswith("cat:"))
async def cb_category(callback: CallbackQuery, session: AsyncSession) -> None:
    settings = get_settings()
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("Некорректная категория.", show_alert=True)
        return

    try:
        category = Category(parts[1])
    except ValueError:
        await callback.answer("Неизвестная категория.", show_alert=True)
        return

    page = 0
    if len(parts) >= 3 and parts[2].isdigit():
        page = int(parts[2])

    games = await registration_service.get_visible_games(session, category)
    if not games:
        await edit_or_answer(
            callback,
            texts.no_games_text(category),
            user_keyboards.categories(),
        )
        return

    counts = await registration_service.get_counts_for_games(session, [game.id for game in games])
    total_pages = max(1, math.ceil(len(games) / PAGE_SIZE))
    page = min(max(page, 0), total_pages - 1)
    page_games = games[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    await edit_or_answer(
        callback,
        texts.games_list_text(category, len(games)),
        user_keyboards.games_list(
            page_games,
            counts,
            category.value,
            page,
            total_pages,
            settings.tz,
        ),
    )


@router.callback_query(F.data.startswith("game:"))
async def cb_game(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    if len(parts) != 2 or not parts[1].isdigit():
        await callback.answer("Игра не найдена.", show_alert=True)
        return
    await show_game_callback(callback, session, int(parts[1]), user.tg_id, get_settings().tz)


@router.callback_query(F.data.startswith("reg:"))
async def cb_register(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    settings = get_settings()
    parts = callback.data.split(":")
    if len(parts) != 2 or not parts[1].isdigit():
        await callback.answer("Игра не найдена.", show_alert=True)
        return
    game_id = int(parts[1])

    outcome = await registration_service.register_for_game(
        session,
        game_id,
        user.tg_id,
        settings.waitlist_offer_minutes,
    )

    messages = {
        RegisterResult.REGISTERED: "Готово! Ты записан(а).",
        RegisterResult.WAITLISTED: (
            f"Мест нет — ты в листе ожидания, позиция {outcome.waitlist_position}."
        ),
        RegisterResult.ALREADY_REGISTERED: "Ты уже записан(а) на эту игру.",
        RegisterResult.ALREADY_WAITLISTED: (
            f"Ты уже в листе ожидания, позиция {outcome.waitlist_position}."
        ),
        RegisterResult.OFFER_ACCEPTED: "Место закреплено за тобой!",
        RegisterResult.UNAVAILABLE: "Запись на эту игру недоступна.",
        RegisterResult.NOT_FOUND: "Игра не найдена.",
    }
    await callback.answer(messages.get(outcome.result, "Готово."))
    await show_game_callback(callback, session, game_id, user.tg_id, settings.tz, answer=False)


@router.callback_query(F.data.startswith("cancelask:"))
async def cb_cancel_ask(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    settings = get_settings()
    parts = callback.data.split(":")
    if len(parts) != 2 or not parts[1].isdigit():
        await callback.answer("Игра не найдена.", show_alert=True)
        return
    game_id = int(parts[1])
    game = await registration_service.get_game(session, game_id)
    registration = await registration_service.get_user_registration(session, game_id, user.tg_id)
    if game is None or registration is None:
        await callback.answer("Запись не найдена.", show_alert=True)
        return

    if registration.status == RegistrationStatus.WAITLIST.value:
        text = (
            f"Выйти из листа ожидания на «{game.title}»?\n\n"
            "Если место освободится, бот больше не сможет тебе его предложить."
        )
    elif registration.status == RegistrationStatus.OFFERED.value:
        text = (
            f"Отказаться от предложенного места на «{game.title}»?\n\n"
            f"{format_datetime(game.starts_at, settings.tz)}"
        )
    else:
        text = (
            f"Отменить запись на «{game.title}»?\n\n{format_datetime(game.starts_at, settings.tz)}"
        )

    await edit_or_answer(callback, text, user_keyboards.cancel_confirm(game_id))


@router.callback_query(F.data.startswith("cancel:"))
async def cb_cancel(callback: CallbackQuery, user: User, session: AsyncSession, bot: Bot) -> None:
    settings = get_settings()
    parts = callback.data.split(":")
    if len(parts) != 2 or not parts[1].isdigit():
        await callback.answer("Игра не найдена.", show_alert=True)
        return
    game_id = int(parts[1])

    outcome = await registration_service.cancel_registration(
        session,
        game_id,
        user.tg_id,
        settings.waitlist_offer_minutes,
    )
    if outcome.result == CancelResult.NOT_FOUND:
        await callback.answer("Запись не найдена.", show_alert=True)
        return

    if outcome.offer is not None:
        await send_offer(bot, outcome.offer, settings.tz, settings.waitlist_offer_minutes)

    await callback.answer("Запись отменена.")
    await show_game_callback(callback, session, game_id, user.tg_id, settings.tz, answer=False)


@router.callback_query(F.data.startswith("offer:accept:"))
async def cb_offer_accept(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    settings = get_settings()
    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        await callback.answer("Игра не найдена.", show_alert=True)
        return
    game_id = int(parts[2])
    outcome = await registration_service.register_for_game(
        session, game_id, user.tg_id, settings.waitlist_offer_minutes
    )
    if outcome.result == RegisterResult.OFFER_ACCEPTED:
        await callback.answer("Место закреплено за тобой!")
    elif outcome.result == RegisterResult.REGISTERED:
        await callback.answer("Готово! Ты записан(а).")
    elif outcome.result == RegisterResult.WAITLISTED:
        await callback.answer("Место уже занято, ты снова в листе ожидания.")
    else:
        await callback.answer("Не удалось занять место.", show_alert=True)
    await show_game_callback(callback, session, game_id, user.tg_id, settings.tz, answer=False)


@router.callback_query(F.data.startswith("offer:decline:"))
async def cb_offer_decline(
    callback: CallbackQuery, user: User, session: AsyncSession, bot: Bot
) -> None:
    settings = get_settings()
    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        await callback.answer("Игра не найдена.", show_alert=True)
        return
    game_id = int(parts[2])
    outcome = await registration_service.cancel_registration(
        session, game_id, user.tg_id, settings.waitlist_offer_minutes
    )
    if outcome.result == CancelResult.NOT_FOUND:
        await callback.answer("Запись не найдена.", show_alert=True)
        return
    if outcome.offer is not None:
        await send_offer(bot, outcome.offer, settings.tz, settings.waitlist_offer_minutes)
    await callback.answer("Ты отказался от места.")
    await show_game_callback(callback, session, game_id, user.tg_id, settings.tz, answer=False)
