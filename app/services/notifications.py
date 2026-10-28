from __future__ import annotations

from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import Game
from app.services.registrations import OfferExpired, OfferOutcome
from app.services.reminders import Reminder, ReminderKind
from app.utils.text import esc
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
