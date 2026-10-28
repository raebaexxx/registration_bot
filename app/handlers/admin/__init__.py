from aiogram import Router

from app.handlers.admin import events, games, menu

router = Router(name="admin")
router.include_router(menu.router)
router.include_router(events.router)
router.include_router(games.router)

__all__ = ["router"]
