from __future__ import annotations

from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app import callbacks as cb
from app.constants import EventStatus, GameStatus
from app.db.models import Event, Game, Registration
from app.services.registrations import Counts
from app.utils.text import truncate
from app.utils.time import format_date_short

EVENT_STATUS_EMOJI = {
    EventStatus.DRAFT.value: "📝",
    EventStatus.PUBLISHED.value: "✅",
    EventStatus.ARCHIVED.value: "🗄",
}

GAME_STATUS_EMOJI = {
    GameStatus.OPEN.value: "🟢",
    GameStatus.CLOSED.value: "🔒",
    GameStatus.CANCELLED.value: "❌",
}


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Встречи", callback_data=cb.admin_events(0))],
            [InlineKeyboardButton(text="⬅️ Главное меню", callback_data=cb.MAIN)],
        ]
    )


def events_list(events: list[Event], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for event in events:
        emoji = EVENT_STATUS_EMOJI.get(event.status, "📅")
        label = f"{emoji} {format_date_short(event.event_date)} · {event.title}"
        rows.append(
            [InlineKeyboardButton(text=truncate(label, 62), callback_data=cb.admin_event(event.id))]
        )

    rows.append([InlineKeyboardButton(text="➕ Создать встречу", callback_data=cb.ADMIN_EVENT_NEW)])

    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=cb.admin_events(page - 1)))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data=cb.NOOP))
        if page + 1 < total_pages:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=cb.admin_events(page + 1)))
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="⬅️ Админ-панель", callback_data=cb.admin_menu())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def event_card(event: Event, counts: dict[int, Counts]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if event.status != EventStatus.ARCHIVED.value:
        rows.append(
            [
                InlineKeyboardButton(
                    text="➕ Добавить игру", callback_data=cb.admin_game_new(event.id)
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="📋 Скопировать с прошлой встречи",
                    callback_data=cb.admin_event_copy(event.id),
                )
            ]
        )

    if event.status == EventStatus.DRAFT.value:
        rows.append(
            [
                InlineKeyboardButton(
                    text="✅ Опубликовать",
                    callback_data=cb.admin_event_publish(event.id),
                )
            ]
        )
    elif event.status == EventStatus.PUBLISHED.value:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📢 Анонс в канал",
                    callback_data=cb.admin_event_announce(event.id),
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="🗄 В архив",
                    callback_data=cb.admin_event_archive(event.id),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="✏️ Переименовать",
                callback_data=cb.admin_event_rename(event.id),
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="⬅️ К встречам", callback_data=cb.admin_events(0))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def game_card(game: Game, counts: Counts) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="👥 Участники",
                callback_data=cb.admin_game_participants(game.id, 0),
            )
        ],
        [
            InlineKeyboardButton(
                text="✏️ Изменить лимит",
                callback_data=cb.admin_game_limit(game.id),
            )
        ],
    ]

    if game.status == GameStatus.OPEN.value:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔒 Закрыть запись",
                    callback_data=cb.admin_game_close(game.id),
                )
            ]
        )
    elif game.status == GameStatus.CLOSED.value:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔓 Открыть запись",
                    callback_data=cb.admin_game_open(game.id),
                )
            ]
        )

    if game.status != GameStatus.CANCELLED.value:
        rows.append(
            [
                InlineKeyboardButton(
                    text="❌ Отменить игру",
                    callback_data=cb.admin_game_cancel_ask(game.id),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="🗑 Удалить игру",
                callback_data=cb.admin_game_delete_ask(game.id),
            )
        ]
    )
    rows.append(
        [InlineKeyboardButton(text="⬅️ К встрече", callback_data=cb.admin_event(game.event_id))]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def participants(
    game_id: int,
    registrations: list[Registration],
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for registration in registrations:
        name = registration.user.display_name
        rows.append(
            [
                InlineKeyboardButton(
                    text=truncate(f"❌ {name}", 60),
                    callback_data=cb.admin_part_remove_ask(game_id, registration.id, page),
                )
            ]
        )

    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=cb.admin_game_participants(game_id, page - 1),
                )
            )
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data=cb.NOOP))
        if page + 1 < total_pages:
            nav.append(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=cb.admin_game_participants(game_id, page + 1),
                )
            )
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="⬅️ К игре", callback_data=cb.admin_game(game_id))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_remove(game_id: int, registration_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data=cb.admin_part_remove(game_id, registration_id, page),
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=cb.admin_game_participants(game_id, page),
                )
            ],
        ]
    )


def confirm_cancel_game(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, отменить игру",
                    callback_data=cb.admin_game_cancel(game_id),
                )
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=cb.admin_game(game_id))],
        ]
    )


def confirm_delete_game(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить игру",
                    callback_data=cb.admin_game_delete(game_id),
                )
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=cb.admin_game(game_id))],
        ]
    )


def announcement_preview(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Отправить в канал",
                    callback_data=cb.admin_announce_send(event_id),
                )
            ],
            [InlineKeyboardButton(text="⬅️ К встрече", callback_data=cb.admin_event(event_id))],
        ]
    )


def date_quick(saturday: date, sunday: date) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Сб, {format_date_short(saturday)}",
                    callback_data=cb.admin_event_new_date(saturday.isoformat()),
                ),
                InlineKeyboardButton(
                    text=f"Вс, {format_date_short(sunday)}",
                    callback_data=cb.admin_event_new_date(sunday.isoformat()),
                ),
            ],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data=cb.fsm_cancel())],
        ]
    )


def game_category(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧑 Взрослые",
                    callback_data=cb.admin_game_category(event_id, "adult"),
                ),
                InlineKeyboardButton(
                    text="🧒 Подростковые",
                    callback_data=cb.admin_game_category(event_id, "teen"),
                ),
            ],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data=cb.admin_event(event_id))],
        ]
    )


def optional_field() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data=cb.fsm_skip())],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data=cb.fsm_cancel())],
        ]
    )


def fsm_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data=cb.fsm_cancel())]]
    )
