from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup

from app.db.models import Game, Registration
from app.services.notifications import (
    build_game_cancelled_text,
    build_offer_expired_text,
    build_offer_text,
    build_reminder_text,
    offer_keyboard,
    reminder_keyboard,
)
from app.services.registrations import OfferExpired, OfferOutcome
from app.services.reminders import Reminder

logger = logging.getLogger(__name__)


async def _send(
    bot: Bot,
    chat_id: int,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
) -> bool:
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return True
    except TelegramForbiddenError:
        logger.info("User %s blocked the bot", chat_id)
    except TelegramAPIError:
        logger.exception("Failed to send message to %s", chat_id)
    return False


async def send_offer(bot: Bot, offer: OfferOutcome, tz, offer_minutes: int) -> bool:
    return await _send(
        bot,
        offer.user.tg_id,
        build_offer_text(offer, tz, offer_minutes),
        offer_keyboard(offer.game.id),
    )


async def send_offer_expired(bot: Bot, expired: OfferExpired, tz) -> bool:
    return await _send(
        bot,
        expired.user.tg_id,
        build_offer_expired_text(expired, tz),
    )


async def send_reminder(bot: Bot, reminder: Reminder, tz) -> bool:
    return await _send(
        bot,
        reminder.user.tg_id,
        build_reminder_text(reminder, tz),
        reminder_keyboard(reminder.game.id),
    )


async def send_game_cancelled(bot: Bot, game: Game, affected: list[Registration], tz) -> int:
    sent = 0
    for registration in affected:
        if await _send(
            bot,
            registration.user.tg_id,
            build_game_cancelled_text(game, tz),
        ):
            sent += 1
    return sent
