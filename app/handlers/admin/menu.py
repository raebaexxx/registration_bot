from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app import callbacks as cb
from app import texts
from app.config import get_settings
from app.filters import IsAdmin
from app.handlers.admin.common import show_events_list
from app.keyboards import admin as admin_keyboards
from app.states import EventCreate
from app.utils.telegram import answer_message, edit_or_answer
from app.utils.time import local_now, next_weekend_dates

router = Router(name="admin_menu")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await answer_message(message, texts.admin_menu_text(), admin_keyboards.admin_menu())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await answer_message(message, texts.admin_menu_text(), admin_keyboards.admin_menu())


@router.callback_query(F.data == cb.admin_menu())
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await edit_or_answer(callback, texts.admin_menu_text(), admin_keyboards.admin_menu())


@router.callback_query(F.data.startswith("admin:events:"))
async def cb_events_list(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    parts = callback.data.split(":")
    page = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 0
    await show_events_list(callback, session, page)


@router.callback_query(F.data == cb.ADMIN_EVENT_NEW)
async def cb_event_new(callback: CallbackQuery, state: FSMContext) -> None:
    settings = get_settings()
    saturday, sunday = next_weekend_dates(local_now(settings.tz).date())
    await state.clear()
    await state.set_state(EventCreate.waiting_date)
    await edit_or_answer(
        callback,
        texts.ask_event_date_text(),
        admin_keyboards.date_quick(saturday, sunday),
    )
