from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app import callbacks as cb
from app import texts
from app.config import get_settings
from app.db.models import User
from app.handlers.user.common import show_game_message
from app.keyboards import user as user_keyboards
from app.utils.access import is_admin
from app.utils.telegram import answer_message, edit_or_answer

router = Router(name="user_start")


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    user: User,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await state.clear()
    payload = ""
    if message.text and len(message.text.split(maxsplit=1)) == 2:
        payload = message.text.split(maxsplit=1)[1].strip()

    if payload.startswith("game_"):
        raw_id = payload.removeprefix("game_")
        if raw_id.isdigit():
            await show_game_message(
                message,
                session,
                int(raw_id),
                user.tg_id,
                get_settings().tz,
            )
            return

    await answer_message(
        message,
        texts.main_menu_text(user.first_name),
        user_keyboards.main_menu(is_admin(user)),
    )


@router.message(Command("help"))
async def cmd_help(message: Message, user: User, state: FSMContext) -> None:
    await state.clear()
    await answer_message(message, texts.help_text(), user_keyboards.main_menu(is_admin(user)))


@router.message(Command("admin"))
async def cmd_admin_denied(message: Message, user: User) -> None:
    if not is_admin(user):
        await answer_message(message, texts.no_access_text())


@router.callback_query(F.data == cb.MAIN)
async def cb_main(callback: CallbackQuery, user: User, state: FSMContext) -> None:
    await state.clear()
    await edit_or_answer(
        callback,
        texts.main_menu_text(user.first_name),
        user_keyboards.main_menu(is_admin(user)),
    )


@router.callback_query(F.data == cb.HELP)
async def cb_help(callback: CallbackQuery, user: User, state: FSMContext) -> None:
    await state.clear()
    await edit_or_answer(callback, texts.help_text(), user_keyboards.main_menu(is_admin(user)))


@router.callback_query(F.data == cb.GAMES)
async def cb_games(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await edit_or_answer(callback, texts.categories_text(), user_keyboards.categories())


@router.callback_query(F.data == cb.NOOP)
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("admin:"))
async def cb_admin_denied(callback: CallbackQuery, user: User) -> None:
    if is_admin(user):
        await callback.answer("Кнопка устарела. Открой /admin заново.", show_alert=True)
    else:
        await callback.answer(texts.no_access_text(), show_alert=True)
