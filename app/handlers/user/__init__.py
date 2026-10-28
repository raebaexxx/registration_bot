from aiogram import Router

from app.handlers.user import games, start

router = Router(name="user")
router.include_router(start.router)
router.include_router(games.router)

__all__ = ["router"]
