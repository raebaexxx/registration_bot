from __future__ import annotations

from datetime import date

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app import texts
from app.config import get_settings
from app.constants import EventStatus
from app.filters import IsAdmin
from app.handlers.admin.common import event_counts, show_event_card
from app.keyboards import admin as admin_keyboards
from app.services import events as event_service
from app.services.announcements import (
    build_announcement_text,
    publish_announcement,
)
from app.states import EventCreate, EventRename
from app.utils.telegram import answer_message, edit_or_answer
from app.utils.time import local_now, next_weekend_dates, parse_date_input

router = Router(name="admin_events")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def event_title_for_date(value: date) -> str:
    if value.weekday() == 5:
        return "Игровая суббота"
    if value.weekday() == 6:
        return "Игровое воскресенье"
    return "Игровой день"


async def _create_event_from_date(
    target: CallbackQuery | Message,
    value: date,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    settings = get_settings()
    today = local_now(settings.tz).date()
    if value < today:
        if isinstance(target, CallbackQuery):
            await target.answer("Дата уже прошла.", show_alert=True)
        else:
            await answer_message(target, "Дата уже прошла. Выбери будущую дату.")
        return

    event = await event_service.create_event(session, event_title_for_date(value), value)
    await state.clear()
    event = await event_service.get_event(session, event.id)
    if event is None:
        return
    counts = await event_counts(session, event)
    text = texts.event_card_text(event, counts, settings.tz)
    keyboard = admin_keyboards.event_card(event, counts)

    if isinstance(target, CallbackQuery):
        await edit_or_answer(target, text, keyboard)
    else:
        await answer_message(target, text, keyboard)


@router.callback_query(F.data.startswith("admin:event:newdate:"))
async def cb_event_new_date(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    raw = callback.data.removeprefix("admin:event:newdate:")
    try:
        value = date.fromisoformat(raw)
    except ValueError:
        await callback.answer("Некорректная дата.", show_alert=True)
        return
    await _create_event_from_date(callback, value, session, state)


@router.message(EventCreate.waiting_date)
async def msg_event_date(message: Message, session: AsyncSession, state: FSMContext) -> None:
    settings = get_settings()
    value = parse_date_input(message.text or "", local_now(settings.tz).date())
    if value is None:
        saturday, sunday = next_weekend_dates(local_now(settings.tz).date())
        await answer_message(
            message,
            texts.invalid_date_text(),
            admin_keyboards.date_quick(saturday, sunday),
        )
        return
    await _create_event_from_date(message, value, session, state)


@router.callback_query(F.data.startswith("admin:event:publish:"))
async def cb_event_publish(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    event_id = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
    event = await event_service.publish_event(session, event_id)
    if event is None:
        await callback.answer("Встреча не найдена.", show_alert=True)
        return
    await callback.answer("Встреча опубликована.")
    await show_event_card(callback, session, event_id, get_settings().tz, answer=False)


@router.callback_query(F.data.startswith("admin:event:archive:"))
async def cb_event_archive(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    event_id = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
    event = await event_service.archive_event(session, event_id)
    if event is None:
        await callback.answer("Встреча не найдена.", show_alert=True)
        return
    await callback.answer("Встреча отправлена в архив.")
    await show_event_card(callback, session, event_id, get_settings().tz, answer=False)


@router.callback_query(F.data.startswith("admin:event:rename:"))
async def cb_event_rename(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    parts = callback.data.split(":")
    event_id = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
    event = await event_service.get_event(session, event_id)
    if event is None:
        await callback.answer("Встреча не найдена.", show_alert=True)
        return
    await state.clear()
    await state.set_state(EventRename.waiting_title)
    await state.update_data(event_id=event_id)
    await edit_or_answer(callback, texts.ask_event_title_text(), admin_keyboards.fsm_cancel())


@router.message(EventRename.waiting_title)
async def msg_event_rename(message: Message, session: AsyncSession, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title or len(title) > 100:
        await answer_message(message, "Название должно быть от 1 до 100 символов.")
        return
    data = await state.get_data()
    event_id = int(data.get("event_id", 0))
    event = await event_service.rename_event(session, event_id, title)
    await state.clear()
    if event is None:
        await answer_message(message, "Встреча не найдена.")
        return
    settings = get_settings()
    event = await event_service.get_event(session, event.id)
    if event is None:
        return
    counts = await event_counts(session, event)
    await answer_message(
        message,
        texts.event_card_text(event, counts, settings.tz),
        admin_keyboards.event_card(event, counts),
    )


@router.callback_query(F.data.startswith("admin:event:copy:"))
async def cb_event_copy(callback: CallbackQuery, session: AsyncSession) -> None:
    settings = get_settings()
    parts = callback.data.split(":")
    event_id = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
    result = await event_service.copy_games_from_previous_event(session, event_id, settings.tz)
    if result.copied:
        await callback.answer(f"Скопировано игр: {result.copied} с «{result.source_title}».")
    else:
        await callback.answer("Не нашёл предыдущую встречу с играми.", show_alert=True)
        return
    await show_event_card(callback, session, event_id, settings.tz, answer=False)


@router.callback_query(F.data.startswith("admin:event:announce:"))
async def cb_event_announce(callback: CallbackQuery, session: AsyncSession) -> None:
    settings = get_settings()
    parts = callback.data.split(":")
    event_id = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
    event = await event_service.get_event(session, event_id)
    if event is None:
        await callback.answer("Встреча не найдена.", show_alert=True)
        return
    if event.status != EventStatus.PUBLISHED.value:
        await callback.answer("Сначала опубликуй встречу.", show_alert=True)
        return

    counts = await event_counts(session, event)
    text = "<b>Предпросмотр анонса</b>\n\n" + build_announcement_text(event, counts, settings.tz)
    await edit_or_answer(callback, text, admin_keyboards.announcement_preview(event_id))


@router.callback_query(F.data.startswith("admin:announce:send:"))
async def cb_announce_send(
    callback: CallbackQuery,
    session: AsyncSession,
    bot: Bot,
    bot_username: str | None = None,
) -> None:
    settings = get_settings()
    parts = callback.data.split(":")
    event_id = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
    result = await publish_announcement(
        bot,
        session,
        event_id,
        settings.channel_id,
        bot_username,
        settings.tz,
    )
    if not result.ok:
        await callback.answer(result.error or "Не удалось отправить анонс.", show_alert=True)
        return
    await callback.answer("Анонс обновлён." if result.updated else "Анонс отправлен в канал.")
    await show_event_card(callback, session, event_id, settings.tz, answer=False)


@router.callback_query(F.data.startswith("admin:event:"))
async def cb_event_card(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        await callback.answer("Встреча не найдена.", show_alert=True)
        return
    await show_event_card(
        callback,
        session,
        int(parts[2]),
        get_settings().tz,
    )


__all__ = ["router"]
