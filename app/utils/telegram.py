from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message


async def edit_or_answer(
    callback: CallbackQuery,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
    *,
    answer: bool = True,
) -> None:
    if callback.message is not None:
        try:
            await callback.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc):
                raise
    if answer:
        await callback.answer()


async def answer_message(
    message: Message,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
) -> Message:
    return await message.answer(
        text,
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def toast(callback: CallbackQuery, text: str, *, alert: bool = False) -> None:
    await callback.answer(text, show_alert=alert)
