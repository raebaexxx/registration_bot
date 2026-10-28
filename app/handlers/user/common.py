from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app import texts
from app.constants import EventStatus, RegistrationStatus
from app.db.models import Game, Registration
from app.keyboards import user as user_keyboards
from app.services import registrations as registration_service
from app.services.registrations import Counts
from app.utils.telegram import answer_message, edit_or_answer


@dataclass
class GameView:
    game: Game
    counts: Counts
    registration: Registration | None
    waitlist_position: int | None
    text: str
    keyboard: InlineKeyboardMarkup


async def build_game_view(
    session: AsyncSession, game_id: int, user_id: int, tz: ZoneInfo
) -> GameView | None:
    game = await registration_service.get_game(session, game_id)
    if game is None:
        return None

    counts = await registration_service.get_counts(session, game)
    registration = await registration_service.get_user_registration(session, game_id, user_id)
    if registration is not None and registration.status == RegistrationStatus.CANCELLED.value:
        registration = None
    waitlist_position = None
    if registration is not None and registration.status == RegistrationStatus.WAITLIST.value:
        waitlist_position = await registration_service.get_waitlist_position(session, registration)

    return GameView(
        game=game,
        counts=counts,
        registration=registration,
        waitlist_position=waitlist_position,
        text=texts.game_card_text(game, counts, registration, waitlist_position, tz),
        keyboard=user_keyboards.game_card(game, counts, registration, tz),
    )


async def show_game_callback(
    callback, session, game_id, user_id, tz, *, answer: bool = True
) -> None:
    view = await build_game_view(session, game_id, user_id, tz)
    if view is None:
        await edit_or_answer(callback, "Игра не найдена.", answer=answer)
        return
    if view.game.event.status != EventStatus.PUBLISHED.value:
        await edit_or_answer(
            callback,
            "Игра недоступна: встреча ещё не опубликована.",
            user_keyboards.main_menu(False),
            answer=answer,
        )
        return
    await edit_or_answer(callback, view.text, view.keyboard, answer=answer)


async def show_game_message(message, session, game_id, user_id, tz) -> None:
    view = await build_game_view(session, game_id, user_id, tz)
    if view is None:
        await answer_message(message, "Игра не найдена.")
        return
    if view.game.event.status != EventStatus.PUBLISHED.value:
        await answer_message(
            message,
            "Игра недоступна: встреча ещё не опубликована.",
        )
        return
    await answer_message(message, view.text, view.keyboard)
