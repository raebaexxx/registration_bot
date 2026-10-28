from __future__ import annotations

from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app import callbacks as cb
from app.constants import EventStatus, GameStatus, RegistrationStatus
from app.db.base import utcnow
from app.db.models import Game, Registration
from app.services.registrations import Counts
from app.utils.text import truncate
from app.utils.time import format_date_short, format_time, to_local


def main_menu(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🎲 Игры", callback_data=cb.GAMES)],
        [InlineKeyboardButton(text="📋 Мои записи", callback_data=cb.MY)],
        [InlineKeyboardButton(text="ℹ️ Как это работает", callback_data=cb.HELP)],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data=cb.admin_menu())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def categories() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🧑 Взрослые", callback_data=cb.category("adult")),
                InlineKeyboardButton(text="🧒 Подростковые", callback_data=cb.category("teen")),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=cb.MAIN)],
        ]
    )


def games_list(
    games: list[Game],
    counts: dict[int, Counts],
    category_value: str,
    page: int,
    total_pages: int,
    tz: ZoneInfo,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for game in games:
        game_counts = counts.get(game.id, Counts(capacity=game.capacity))
        local_date = to_local(game.starts_at, tz).date()
        label = (
            f"{game.title} · {format_date_short(local_date)} · "
            f"{format_time(game.starts_at, tz)} · {game_counts.free}/{game.capacity}"
        )
        rows.append(
            [InlineKeyboardButton(text=truncate(label, 62), callback_data=cb.game(game.id))]
        )

    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(text="⬅️", callback_data=cb.category(category_value, page - 1))
            )
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data=cb.NOOP))
        if page + 1 < total_pages:
            nav.append(
                InlineKeyboardButton(text="➡️", callback_data=cb.category(category_value, page + 1))
            )
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="⬅️ К категориям", callback_data=cb.GAMES)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def game_card(
    game: Game,
    counts: Counts,
    registration: Registration | None,
    tz: ZoneInfo,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    bookable = (
        game.status == GameStatus.OPEN.value
        and game.event.status == EventStatus.PUBLISHED.value
        and game.starts_at > utcnow()
    )
    registration_active = registration is not None and registration.status in {
        RegistrationStatus.CONFIRMED.value,
        RegistrationStatus.WAITLIST.value,
        RegistrationStatus.OFFERED.value,
    }
    manageable = (
        registration_active
        and game.event.status == EventStatus.PUBLISHED.value
        and game.starts_at > utcnow()
    )

    if manageable and registration is not None:
        if registration.status == RegistrationStatus.CONFIRMED.value:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="❌ Отменить запись",
                        callback_data=cb.cancel_ask(game.id),
                    )
                ]
            )
        elif registration.status == RegistrationStatus.WAITLIST.value:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="❌ Выйти из листа ожидания",
                        callback_data=cb.cancel_ask(game.id),
                    )
                ]
            )
        elif registration.status == RegistrationStatus.OFFERED.value:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="✅ Занять место",
                        callback_data=cb.offer_accept(game.id),
                    )
                ]
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        text="❌ Отказаться",
                        callback_data=cb.offer_decline(game.id),
                    )
                ]
            )
    elif bookable:
        if counts.free > 0:
            rows.append(
                [InlineKeyboardButton(text="✅ Записаться", callback_data=cb.register(game.id))]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="⏳ В лист ожидания", callback_data=cb.register(game.id)
                    )
                ]
            )

    rows.append([InlineKeyboardButton(text="📋 Мои записи", callback_data=cb.MY)])
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ К играм",
                callback_data=cb.category(game.category, 0),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def my_registrations(registrations: list[Registration], tz: ZoneInfo) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for registration in registrations:
        game = registration.game
        local_date = to_local(game.starts_at, tz).date()
        label = (
            f"{game.title} · {format_date_short(local_date)} · {format_time(game.starts_at, tz)}"
        )
        rows.append(
            [InlineKeyboardButton(text=truncate(label, 62), callback_data=cb.game(game.id))]
        )
    rows.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data=cb.MAIN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_confirm(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, отменить", callback_data=cb.cancel_yes(game_id))],
            [InlineKeyboardButton(text="⬅️ Нет, назад", callback_data=cb.game(game_id))],
        ]
    )
