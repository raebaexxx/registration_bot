from __future__ import annotations

from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.constants import Category, RegistrationStatus
from app.db.models import Game, User
from app.services.registrations import (
    CancelOutcome,
    Counts,
    OfferExpired,
    OfferOutcome,
    RegisterOutcome,
    RegisterResult,
)
from app.services.reminders import Reminder, ReminderKind
from app.utils.text import esc, user_mention
from app.utils.time import format_datetime, format_duration


def offer_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Занять место", callback_data=f"offer:accept:{game_id}")],
            [InlineKeyboardButton(text="❌ Отказаться", callback_data=f"offer:decline:{game_id}")],
        ]
    )


def build_offer_text(offer: OfferOutcome, tz: ZoneInfo, offer_minutes: int) -> str:
    game = offer.game
    place = f"\n📍 {esc(game.place)}" if game.place else ""
    return (
        "🎟 <b>Место освободилось!</b>\n\n"
        f"<b>{esc(game.title)}</b>\n"
        f"📅 {format_datetime(game.starts_at, tz)}{place}\n\n"
        f"У тебя есть <b>{format_duration(offer_minutes)}</b>, чтобы занять место. "
        "Если не успеешь, предложение перейдёт следующему в листе ожидания."
    )


def build_offer_expired_text(expired: OfferExpired, tz: ZoneInfo) -> str:
    return (
        "⌛ <b>Предложение места истекло</b>\n\n"
        f"«{esc(expired.game.title)}» · {format_datetime(expired.game.starts_at, tz)}\n\n"
        "Ты остался в листе ожидания. Если место освободится снова, бот напишет."
    )


def build_game_cancelled_text(game: Game, tz: ZoneInfo) -> str:
    return (
        "❌ <b>Игра отменена</b>\n\n"
        f"<b>{esc(game.title)}</b>\n"
        f"📅 {format_datetime(game.starts_at, tz)}\n\n"
        "Запись закрыта. Следи за новыми анонсами в канале."
    )


def reminder_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"cancelask:{game_id}")],
            [InlineKeyboardButton(text="📋 Мои записи", callback_data="my:list")],
        ]
    )


def build_reminder_text(reminder: Reminder, tz: ZoneInfo) -> str:
    game = reminder.game
    if reminder.kind == ReminderKind.H2:
        header = "⏰ <b>Через 2 часа игра</b>"
    else:
        header = "⏰ <b>Напоминаем: завтра игра</b>"

    place = f"\n📍 {esc(game.place)}" if game.place else ""
    return (
        f"{header}\n\n"
        f"<b>{esc(game.title)}</b>\n"
        f"📅 {format_datetime(game.starts_at, tz)}{place}\n\n"
        "Если планы изменились, отмени запись, чтобы место досталось другому."
    )


def _user_line(user: User) -> str:
    username = (
        f" @{esc(user.username)}" if user.username and user.username != user.display_name else ""
    )
    return f"👤 {user_mention(user.tg_id, user.display_name)}{username} · ID {user.tg_id}"


def _admin_counts_line(counts: Counts) -> str:
    line = f"👥 Занято {counts.occupied} из {counts.capacity} · свободно {counts.free}"
    if counts.waitlist:
        line += f"\n⏳ В листе ожидания: {counts.waitlist}"
    return line


def _game_line(game: Game, tz: ZoneInfo) -> str:
    category = Category(game.category)
    place = f"\n📍 {esc(game.place)}" if game.place else ""
    return (
        f"🎲 <b>{esc(game.title)}</b>\n"
        f"📅 {format_datetime(game.starts_at, tz)}\n"
        f"{category.emoji} {category.label}{place}"
    )


def admin_game_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎲 Открыть игру",
                    callback_data=f"admin:game:{game_id}",
                )
            ]
        ]
    )


def build_admin_registration_text(user: User, outcome: RegisterOutcome, tz: ZoneInfo) -> str:
    game = outcome.game
    if game is None:
        return ""

    if outcome.result == RegisterResult.WAITLISTED:
        header = "⏳ <b>Новая запись в лист ожидания</b>"
        status = "⏳ Лист ожидания"
        if outcome.waitlist_position:
            status += f", позиция {outcome.waitlist_position}"
    elif outcome.result == RegisterResult.OFFER_ACCEPTED:
        header = "✅ <b>Место из резерва занято</b>"
        status = "✅ Подтверждена"
    else:
        header = "🆕 <b>Новая запись</b>"
        status = "✅ Подтверждена"

    counts = outcome.counts or Counts(capacity=game.capacity)
    return "\n".join(
        [
            header,
            "",
            _user_line(user),
            "",
            _game_line(game, tz),
            "",
            status,
            "",
            _admin_counts_line(counts),
        ]
    )


def build_admin_cancellation_text(user: User, outcome: CancelOutcome, tz: ZoneInfo) -> str:
    game = outcome.game
    if game is None:
        return ""

    counts = outcome.counts or Counts(capacity=game.capacity)
    previous = outcome.previous_status
    if previous == RegistrationStatus.WAITLIST.value:
        previous_label = "⏳ Лист ожидания"
        consequence = "Участник вышел из листа ожидания."
    elif previous == RegistrationStatus.OFFERED.value:
        previous_label = "🎟 Предложено место"
        consequence = "Участник отказался от предложенного места."
    else:
        previous_label = "✅ Подтверждена"
        consequence = "Место освободилось."

    if outcome.offer is not None:
        consequence += " Предложение отправлено следующему в очереди."
    elif previous == RegistrationStatus.CONFIRMED.value:
        if counts.waitlist:
            consequence += " Предложение не отправлено: запись на игру закрыта."
        else:
            consequence += " Желающих в листе ожидания нет."

    return "\n".join(
        [
            "❌ <b>Запись отменена</b>",
            "",
            _user_line(user),
            "",
            _game_line(game, tz),
            "",
            f"Было: {previous_label}",
            consequence,
            "",
            _admin_counts_line(counts),
        ]
    )
