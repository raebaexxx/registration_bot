from __future__ import annotations

import math
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app import texts
from app.config import Settings
from app.db.models import Event
from app.keyboards import admin as admin_keyboards
from app.services import events as event_service
from app.services import registrations as registration_service
from app.services.notifier import send_offer
from app.services.registrations import Counts, OfferOutcome
from app.utils.telegram import edit_or_answer

EVENTS_PAGE_SIZE = 8
PARTICIPANTS_PAGE_SIZE = 10


async def event_counts(session: AsyncSession, event: Event) -> dict[int, Counts]:
    return await registration_service.get_counts_for_games(
        session, [game.id for game in event.games]
    )


async def show_events_list(
    callback: CallbackQuery,
    session: AsyncSession,
    page: int = 0,
    *,
    answer: bool = True,
) -> None:
    events, total = await event_service.list_events(
        session, offset=page * EVENTS_PAGE_SIZE, limit=EVENTS_PAGE_SIZE
    )
    total_pages = max(1, math.ceil(total / EVENTS_PAGE_SIZE))
    page = min(max(page, 0), total_pages - 1)
    if total and page * EVENTS_PAGE_SIZE >= total:
        events, total = await event_service.list_events(
            session, offset=(total_pages - 1) * EVENTS_PAGE_SIZE, limit=EVENTS_PAGE_SIZE
        )
        page = total_pages - 1

    await edit_or_answer(
        callback,
        texts.events_list_text(page, total_pages, total),
        admin_keyboards.events_list(events, page, total_pages),
        answer=answer,
    )


async def show_event_card(
    callback: CallbackQuery,
    session: AsyncSession,
    event_id: int,
    tz: ZoneInfo,
    *,
    answer: bool = True,
) -> None:
    event = await event_service.get_event(session, event_id)
    if event is None:
        await edit_or_answer(callback, "Встреча не найдена.", answer=answer)
        return
    counts = await event_counts(session, event)
    await edit_or_answer(
        callback,
        texts.event_card_text(event, counts, tz),
        admin_keyboards.event_card(event, counts),
        answer=answer,
    )


async def show_game_card(
    callback: CallbackQuery,
    session: AsyncSession,
    game_id: int,
    tz: ZoneInfo,
    *,
    answer: bool = True,
) -> None:
    game = await registration_service.get_game(session, game_id)
    if game is None:
        await edit_or_answer(callback, "Игра не найдена.", answer=answer)
        return
    counts = await registration_service.get_counts(session, game)
    await edit_or_answer(
        callback,
        texts.admin_game_card_text(game, counts, tz),
        admin_keyboards.game_card(game, counts),
        answer=answer,
    )


async def show_participants(
    callback: CallbackQuery,
    session: AsyncSession,
    game_id: int,
    page: int,
    tz: ZoneInfo,
    *,
    answer: bool = True,
) -> None:
    game = await registration_service.get_game(session, game_id)
    if game is None:
        await edit_or_answer(callback, "Игра не найдена.", answer=answer)
        return
    registrations = await registration_service.get_game_registrations(session, game_id)
    total_pages = max(1, math.ceil(len(registrations) / PARTICIPANTS_PAGE_SIZE))
    page = min(max(page, 0), total_pages - 1)
    page_registrations = registrations[
        page * PARTICIPANTS_PAGE_SIZE : (page + 1) * PARTICIPANTS_PAGE_SIZE
    ]
    await edit_or_answer(
        callback,
        texts.participants_text(game, page_registrations, page, total_pages, tz),
        admin_keyboards.participants(game_id, page_registrations, page, total_pages),
        answer=answer,
    )


async def notify_offers(bot: Bot, offers: list[OfferOutcome], settings: Settings) -> None:
    for offer in offers:
        await send_offer(bot, offer, settings.tz, settings.waitlist_offer_minutes)


__all__ = [
    "event_counts",
    "notify_offers",
    "show_event_card",
    "show_events_list",
    "show_game_card",
    "show_participants",
]
