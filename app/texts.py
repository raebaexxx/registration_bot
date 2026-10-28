from __future__ import annotations

from zoneinfo import ZoneInfo

from app.constants import Category, EventStatus, GameStatus, RegistrationStatus
from app.db.base import utcnow
from app.db.models import Event, Game, Registration
from app.services.registrations import Counts
from app.utils.text import esc, truncate, user_mention
from app.utils.time import (
    format_date,
    format_datetime,
    format_time,
)

EVENT_STATUS_LABELS = {
    EventStatus.DRAFT.value: "📝 Черновик",
    EventStatus.PUBLISHED.value: "✅ Опубликована",
    EventStatus.ARCHIVED.value: "🗄 В архиве",
}

GAME_STATUS_LABELS = {
    GameStatus.OPEN.value: "🟢 Открыта",
    GameStatus.CLOSED.value: "🔒 Закрыта",
    GameStatus.CANCELLED.value: "❌ Отменена",
}

REGISTRATION_STATUS_LABELS = {
    RegistrationStatus.CONFIRMED.value: "✅ Подтверждена",
    RegistrationStatus.WAITLIST.value: "⏳ Лист ожидания",
    RegistrationStatus.OFFERED.value: "🎟 Предложено место",
}


def main_menu_text(first_name: str | None) -> str:
    name = f", {esc(first_name)}" if first_name else ""
    return f"Привет{name}! 👋\n\nЭто бот записи на настольные игры.\nВыбери, что хочешь сделать:"


def help_text() -> str:
    return (
        "🎲 <b>Как это работает</b>\n\n"
        "1. Нажми «Игры» и выбери категорию: взрослые или подростковые.\n"
        "2. Выбери игру и нажми «Записаться».\n"
        "3. Счётчик мест обновится сразу. Если мест нет — можно встать "
        "в лист ожидания.\n"
        "4. Запись можно отменить в «Моих записях». Если кто-то отменит, "
        "бот предложит место первому из резерва.\n\n"
        "ФИО и телефон не нужны — бот знает твой Telegram ID."
    )


def categories_text() -> str:
    return "🎲 <b>Выбери категорию</b>\n\nДля каждой категории — свои игры и своё количество мест."


def no_games_text(category: Category) -> str:
    return (
        f"{category.emoji} <b>{category.label}</b>\n\n"
        "Пока нет открытых игр. Загляни позже — админ добавляет новые игры "
        "на каждые выходные."
    )


def games_list_text(category: Category, count: int) -> str:
    return (
        f"{category.emoji} <b>{category.label} настолки</b>\n\nОткрытых игр: {count}. Выбери игру:"
    )


def _seats_line(counts: Counts) -> str:
    line = f"👥 Занято {counts.occupied} из {counts.capacity} · свободно {counts.free}"
    if counts.waitlist:
        line += f"\n⏳ В листе ожидания: {counts.waitlist}"
    return line


def _game_availability_note(game: Game) -> str | None:
    if game.status == GameStatus.CANCELLED.value:
        return "❌ Игра отменена."
    if game.status == GameStatus.CLOSED.value:
        return "🔒 Запись закрыта."
    if game.event.status != EventStatus.PUBLISHED.value:
        return "⏳ Встреча ещё не опубликована."
    if game.starts_at <= utcnow():
        return "⏰ Игра уже началась."
    return None


def game_card_text(
    game: Game,
    counts: Counts,
    registration: Registration | None,
    waitlist_position: int | None,
    tz: ZoneInfo,
) -> str:
    category = Category(game.category)
    lines = [
        f"🎲 <b>{esc(game.title)}</b>",
        f"{category.emoji} {category.label}",
        f"📅 {format_datetime(game.starts_at, tz)}",
    ]
    if game.place:
        lines.append(f"📍 {esc(game.place)}")
    lines.append("")
    lines.append(_seats_line(counts))

    if game.description:
        lines.append("")
        lines.append(esc(truncate(game.description, 600)))

    lines.append("")

    registration_active = registration is not None and registration.status in {
        RegistrationStatus.CONFIRMED.value,
        RegistrationStatus.WAITLIST.value,
        RegistrationStatus.OFFERED.value,
    }
    if registration_active and registration is not None:
        if registration.status == RegistrationStatus.CONFIRMED.value:
            lines.append("✅ Ты записан(а).")
        elif registration.status == RegistrationStatus.WAITLIST.value:
            position = f", позиция {waitlist_position}" if waitlist_position else ""
            lines.append(f"⏳ Ты в листе ожидания{position}.")
        elif registration.status == RegistrationStatus.OFFERED.value:
            lines.append("🎟 Тебе предложено место. Подтверди его, пока действует предложение.")
        if game.status == GameStatus.CLOSED.value:
            lines.append("🔒 Новые записи закрыты, но твоя запись действует.")
        elif game.starts_at <= utcnow():
            lines.append("⏰ Игра уже началась.")
    else:
        availability = _game_availability_note(game)
        if availability:
            lines.append(availability)
        elif counts.free > 0:
            lines.append("✅ Есть свободные места.")
        else:
            lines.append("😔 Свободных мест нет, но можно встать в лист ожидания.")

    return "\n".join(lines)


def my_registrations_text(registrations: list[Registration], tz: ZoneInfo) -> str:
    if not registrations:
        return (
            "📋 <b>Мои записи</b>\n\n"
            "У тебя пока нет записей. Загляни в «Игры», чтобы выбрать настолку."
        )

    lines = ["📋 <b>Мои записи</b>", ""]
    for registration in registrations:
        game = registration.game
        status = REGISTRATION_STATUS_LABELS.get(registration.status, registration.status)
        lines.append(f"• <b>{esc(game.title)}</b>")
        lines.append(f"  {format_datetime(game.starts_at, tz)}")
        if game.place:
            lines.append(f"  📍 {esc(game.place)}")
        lines.append(f"  {status}")
        lines.append("")
    return "\n".join(lines).strip()


def admin_menu_text() -> str:
    return "🛠 <b>Админ-панель</b>\n\nСоздавай встречи, добавляй игры и следи за записями."


def events_list_text(page: int, total_pages: int, total: int) -> str:
    return (
        f"📅 <b>Встречи</b>\n\nВсего встреч: {total}\nСтраница {page + 1} из {max(total_pages, 1)}"
    )


def event_card_text(event: Event, counts: dict[int, Counts], tz: ZoneInfo) -> str:
    lines = [
        f"📅 <b>{esc(event.title)}</b>",
        f"{format_date(event.event_date)} · {EVENT_STATUS_LABELS.get(event.status, event.status)}",
        "",
    ]

    if not event.games:
        lines.append("Пока нет игр. Добавь первую.")
        return "\n".join(lines)

    total_occupied = 0
    for category in Category:
        category_games = [game for game in event.games if game.category == category.value]
        if not category_games:
            continue
        lines.append(f"{category.emoji} <b>{category.label}</b>")
        for game in category_games:
            game_counts = counts.get(game.id, Counts(capacity=game.capacity))
            total_occupied += game_counts.occupied
            status_emoji = {
                GameStatus.OPEN.value: "🟢",
                GameStatus.CLOSED.value: "🔒",
                GameStatus.CANCELLED.value: "❌",
            }.get(game.status, "•")
            reserve = f" · резерв {game_counts.waitlist}" if game_counts.waitlist else ""
            lines.append(
                f"{status_emoji} <b>{esc(game.title)}</b> — "
                f"{format_time(game.starts_at, tz)} · "
                f"{game_counts.occupied}/{game_counts.capacity}{reserve}"
            )
        lines.append("")

    lines.append(f"Всего игр: {len(event.games)} · записей: {total_occupied}")
    return "\n".join(lines).strip()


def admin_game_card_text(game: Game, counts: Counts, tz: ZoneInfo) -> str:
    category = Category(game.category)
    lines = [
        f"🎲 <b>{esc(game.title)}</b>",
        f"{category.emoji} {category.label} · {GAME_STATUS_LABELS.get(game.status, game.status)}",
        f"📅 {format_datetime(game.starts_at, tz)}",
    ]
    if game.place:
        lines.append(f"📍 {esc(game.place)}")
    lines.append("")
    lines.append(f"👥 Занято {counts.occupied} из {counts.capacity} · свободно {counts.free}")
    lines.append(f"⏳ В листе ожидания: {counts.waitlist}")
    if counts.offered:
        lines.append(f"🎟 Предложено мест: {counts.offered}")
    if game.description:
        lines.append("")
        lines.append(esc(truncate(game.description, 600)))
    return "\n".join(lines)


def participants_text(
    game: Game,
    registrations: list[Registration],
    page: int,
    total_pages: int,
    tz: ZoneInfo,
) -> str:
    lines = [
        f"👥 <b>{esc(game.title)}</b>",
        f"{format_datetime(game.starts_at, tz)}",
        f"Страница {page + 1} из {max(total_pages, 1)}",
        "",
    ]
    if not registrations:
        lines.append("Пока нет активных записей.")
        return "\n".join(lines)

    for index, registration in enumerate(registrations, start=page * 10 + 1):
        user = registration.user
        status_emoji = {
            RegistrationStatus.CONFIRMED.value: "✅",
            RegistrationStatus.WAITLIST.value: "⏳",
            RegistrationStatus.OFFERED.value: "🎟",
        }.get(registration.status, "•")
        username = (
            f" @{esc(user.username)}"
            if user.username and user.username != user.display_name
            else ""
        )
        lines.append(
            f"{status_emoji} {index}. {user_mention(user.tg_id, user.display_name)}"
            f"{username} · ID {user.tg_id}"
        )
    return "\n".join(lines)


def participant_remove_confirm_text(registration: Registration) -> str:
    if registration.status == RegistrationStatus.WAITLIST.value:
        consequence = "Участник будет удалён из листа ожидания."
    elif registration.status == RegistrationStatus.OFFERED.value:
        consequence = "Предложение будет отменено, а место предложат следующему в очереди."
    else:
        consequence = "Место освободится, и бот предложит его первому из листа ожидания."

    return (
        "Удалить участника?\n\n"
        f"<b>{esc(registration.user.display_name)}</b>\n"
        f"Игра: <b>{esc(registration.game.title)}</b>\n\n"
        f"{consequence}"
    )


def game_cancel_confirm_text(game: Game, tz: ZoneInfo) -> str:
    return (
        "Отменить игру?\n\n"
        f"<b>{esc(game.title)}</b>\n"
        f"{format_datetime(game.starts_at, tz)}\n\n"
        "Все активные записи будут отменены, участники получат уведомление."
    )


def game_delete_confirm_text(game: Game) -> str:
    return (
        "Удалить игру?\n\n"
        f"<b>{esc(game.title)}</b>\n\n"
        "Удалить можно только игру без записей. Если записи есть, "
        "используй отмену игры."
    )


def ask_event_date_text() -> str:
    return (
        "📅 <b>Новая встреча</b>\n\n"
        "Введи дату в формате <code>ДД.ММ.ГГГГ</code> "
        "или выбери ближайший выходной:"
    )


def ask_event_title_text() -> str:
    return "✏️ Введи новое название встречи:"


def ask_game_title_text(category: Category) -> str:
    return (
        f"🎲 <b>Новая игра</b>\n"
        f"Категория: {category.emoji} {category.label}\n\n"
        "Введи название игры:"
    )


def ask_game_time_text(event: Event) -> str:
    return (
        f"🕒 Встреча: {format_date(event.event_date)}\n\n"
        "Введи время начала в формате <code>ЧЧ:ММ</code>, например <code>18:00</code>:"
    )


def ask_game_capacity_text() -> str:
    return "👥 Сколько всего мест? Отправь число, например <code>50</code>:"


def ask_game_place_text() -> str:
    return "📍 Где проводится игра? Отправь адрес или место. Можно пропустить:"


def ask_game_description_text() -> str:
    return "📝 Добавь описание игры. Можно пропустить:"


def ask_game_limit_text(game: Game, counts: Counts) -> str:
    return (
        f"✏️ <b>Лимит мест</b>\n\n"
        f"Сейчас занято {counts.occupied} из {counts.capacity}.\n"
        "Введи новый лимит:"
    )


def invalid_date_text() -> str:
    return (
        "Не понял дату. Введи в формате <code>ДД.ММ.ГГГГ</code>, например <code>01.11.2026</code>."
    )


def invalid_time_text() -> str:
    return "Не понял время. Введи в формате <code>ЧЧ:ММ</code>, например <code>18:00</code>."


def invalid_capacity_text() -> str:
    return "Нужно целое число больше нуля. Например: <code>50</code>."


def past_datetime_text() -> str:
    return "Это время уже прошло. Укажи будущее время."


def fsm_cancelled_text() -> str:
    return "Действие отменено."


def event_created_text(event: Event) -> str:
    return f"Встреча «{esc(event.title)}» создана. Теперь добавь игры."


def no_access_text() -> str:
    return "Недостаточно прав."
