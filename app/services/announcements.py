from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import Category, EventStatus, GameStatus
from app.db.base import utcnow
from app.db.models import ChannelPost, Event, Game
from app.services import events as event_service
from app.services import registrations as registration_service
from app.services.registrations import Counts
from app.utils.text import esc, truncate
from app.utils.time import format_date, format_time


@dataclass
class AnnouncementResult:
    ok: bool
    error: str | None = None
    message_id: int | None = None
    updated: bool = False


def _open_games(event: Event, now: datetime | None = None) -> list[Game]:
    now = now or utcnow()
    return [
        game
        for game in sorted(event.games, key=lambda item: item.starts_at)
        if game.status == GameStatus.OPEN.value and game.starts_at > now
    ]


def build_announcement_text(
    event: Event,
    counts: dict[int, Counts],
    tz: ZoneInfo,
    now: datetime | None = None,
) -> str:
    games = _open_games(event, now)
    lines = [
        f"🎲 <b>{esc(event.title)}</b>",
        f"📅 {format_date(event.event_date)}",
        "",
    ]

    for category in Category:
        category_games = [game for game in games if game.category == category.value]
        if not category_games:
            continue
        lines.append(f"{category.emoji} <b>{category.label}</b>")
        for game in category_games:
            game_counts = counts.get(game.id, Counts(capacity=game.capacity))
            if game_counts.free > 0:
                seats = f"свободно {game_counts.free} из {game_counts.capacity}"
            else:
                seats = "мест нет · лист ожидания"
            lines.append(
                f"• <b>{esc(game.title)}</b> — {format_time(game.starts_at, tz)} · {seats}"
            )
        lines.append("")

    lines.append("Выбери игру и запишись в боте 👇")
    return "\n".join(lines).strip()


def build_announcement_keyboard(
    event: Event,
    bot_username: str,
    tz: ZoneInfo,
    now: datetime | None = None,
) -> InlineKeyboardMarkup | None:
    games = _open_games(event, now)
    if not games:
        return None
    rows = [
        [
            InlineKeyboardButton(
                text=truncate(f"🎲 {game.title} · {format_time(game.starts_at, tz)}", 60),
                url=f"https://t.me/{bot_username}?start=game_{game.id}",
            )
        ]
        for game in games
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_channel_id(value: str) -> int | str:
    stripped = value.strip()
    if stripped.startswith("@"):
        return stripped
    candidate = stripped.removeprefix("-")
    if candidate.isdigit():
        return int(stripped)
    return stripped


async def publish_announcement(
    bot: Bot,
    session: AsyncSession,
    event_id: int,
    channel_id: str | None,
    bot_username: str | None,
    tz: ZoneInfo,
) -> AnnouncementResult:
    if not channel_id:
        return AnnouncementResult(
            ok=False,
            error="CHANNEL_ID не настроен. Добавь ID канала в .env и перезапусти бота.",
        )
    if not bot_username:
        return AnnouncementResult(ok=False, error="Не удалось определить username бота.")

    event = await event_service.get_event(session, event_id)
    if event is None:
        return AnnouncementResult(ok=False, error="Встреча не найдена.")
    if event.status != EventStatus.PUBLISHED.value:
        return AnnouncementResult(
            ok=False, error="Сначала опубликуй встречу, потом отправляй анонс."
        )

    games = _open_games(event)
    if not games:
        return AnnouncementResult(ok=False, error="В встрече нет открытых игр для анонса.")

    counts = await registration_service.get_counts_for_games(session, [game.id for game in games])
    text = build_announcement_text(event, counts, tz)
    keyboard = build_announcement_keyboard(event, bot_username, tz)
    if keyboard is None:
        return AnnouncementResult(ok=False, error="Не удалось собрать кнопки анонса.")

    chat_id = parse_channel_id(channel_id)
    post = event.channel_post
    updated = False

    try:
        if post is not None:
            try:
                await bot.edit_message_text(
                    chat_id=post.chat_id,
                    message_id=post.message_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                updated = True
                message_id = post.message_id
            except TelegramBadRequest as exc:
                if "message is not modified" in str(exc):
                    updated = True
                    message_id = post.message_id
                else:
                    sent = await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                    post.chat_id = str(chat_id)
                    post.message_id = sent.message_id
                    await session.commit()
                    message_id = sent.message_id
        else:
            sent = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            session.add(
                ChannelPost(
                    event_id=event.id,
                    chat_id=str(chat_id),
                    message_id=sent.message_id,
                )
            )
            await session.commit()
            message_id = sent.message_id
    except TelegramAPIError as exc:
        return AnnouncementResult(
            ok=False,
            error=f"Telegram не дал отправить сообщение: {exc.message}",
        )

    return AnnouncementResult(ok=True, message_id=message_id, updated=updated)
