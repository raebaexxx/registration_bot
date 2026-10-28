from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.services import registrations
from app.services.notifier import send_offer, send_offer_expired, send_reminder
from app.services.reminders import collect_due_reminders

logger = logging.getLogger(__name__)


def create_scheduler(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.tz)

    async def tick() -> None:
        try:
            async with session_factory() as session:
                closed = await registrations.close_started_games(session)
                if closed:
                    logger.info("Closed started games: %s", closed)

                expired = await registrations.expire_offers(
                    session, settings.waitlist_offer_minutes
                )
                for item in expired.expired:
                    await send_offer_expired(bot, item, settings.tz)
                for offer in expired.offers:
                    await send_offer(
                        bot,
                        offer,
                        settings.tz,
                        settings.waitlist_offer_minutes,
                    )

                reminders = await collect_due_reminders(session)
                for reminder in reminders:
                    await send_reminder(bot, reminder, settings.tz)
        except Exception:
            logger.exception("Scheduler tick failed")

    scheduler.add_job(
        tick,
        trigger="interval",
        seconds=60,
        id="bot_tick",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(settings.tz),
    )
    return scheduler
