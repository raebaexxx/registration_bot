from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiogram.types.error_event import ErrorEvent

from app.config import get_settings
from app.db.session import create_engine, create_session_factory
from app.handlers import admin_router, user_router
from app.middlewares import AppMiddleware
from app.scheduler import create_scheduler

logger = logging.getLogger(__name__)


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="my", description="Мои записи"),
            BotCommand(command="help", description="Как это работает"),
            BotCommand(command="admin", description="Админ-панель"),
        ]
    )


async def on_error(event: ErrorEvent) -> None:
    logger.exception(
        "Update handling failed: %s",
        event.exception,
        exc_info=event.exception,
    )


async def main() -> None:
    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN не задан. Скопируй .env.example в .env и заполни токен.")

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    if not settings.admin_ids:
        logger.warning("ADMIN_IDS пуст: админ-панель будет недоступна.")
    if not settings.channel_id:
        logger.warning("CHANNEL_ID не задан: анонсы в канал отправляться не будут.")

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    middleware = AppMiddleware(session_factory)
    dispatcher.message.middleware(middleware)
    dispatcher.callback_query.middleware(middleware)

    dispatcher.include_router(admin_router)
    dispatcher.include_router(user_router)
    dispatcher.errors.register(on_error)

    me = await bot.get_me()
    dispatcher["bot_username"] = me.username
    logger.info("Starting bot @%s", me.username)

    await set_commands(bot)
    scheduler = create_scheduler(bot, session_factory, settings)
    scheduler.start()

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
