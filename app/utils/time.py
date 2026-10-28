from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings

WEEKDAYS_SHORT = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
MONTHS_GENITIVE = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def get_tz(tz: ZoneInfo | None = None) -> ZoneInfo:
    return tz or get_settings().tz


def to_local(value: datetime, tz: ZoneInfo | None = None) -> datetime:
    """Convert a naive UTC datetime to the configured local timezone."""

    return value.replace(tzinfo=ZoneInfo("UTC")).astimezone(get_tz(tz))


def to_utc(value: datetime, tz: ZoneInfo | None = None) -> datetime:
    """Convert an aware datetime to naive UTC."""

    return value.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def local_now(tz: ZoneInfo | None = None) -> datetime:
    return datetime.now(get_tz(tz))


def format_date(value: date) -> str:
    return f"{WEEKDAYS_SHORT[value.weekday()]}, {value.day} {MONTHS_GENITIVE[value.month - 1]}"


def format_date_long(value: date) -> str:
    return f"{value.day} {MONTHS_GENITIVE[value.month - 1]} {value.year}"


def format_date_short(value: date) -> str:
    return f"{value.day:02d}.{value.month:02d}"


def format_time(value: datetime, tz: ZoneInfo | None = None) -> str:
    return to_local(value, tz).strftime("%H:%M")


def format_datetime(value: datetime, tz: ZoneInfo | None = None) -> str:
    local = to_local(value, tz)
    return f"{format_date(local.date())} · {local.strftime('%H:%M')}"


def format_event_datetime(event_date: date, starts_at: datetime, tz: ZoneInfo | None = None) -> str:
    return f"{format_date(event_date)} · {format_time(starts_at, tz)}"


def combine_local(event_date: date, starts_at: time, tz: ZoneInfo | None = None) -> datetime:
    return to_utc(datetime.combine(event_date, starts_at, tzinfo=get_tz(tz)), tz)


def next_weekend_dates(today: date) -> tuple[date, date]:
    """Return the next Saturday and Sunday strictly after today."""

    saturday_delta = (5 - today.weekday()) % 7
    if saturday_delta == 0:
        saturday_delta = 7
    saturday = today + timedelta(days=saturday_delta)
    sunday = saturday + timedelta(days=1)
    return saturday, sunday


def parse_date_input(text: str, today: date) -> date | None:
    """Parse DD.MM.YYYY, DD.MM.YY or DD.MM (current year)."""

    cleaned = text.strip().replace("/", ".").replace("-", ".")
    parts = cleaned.split(".")
    if len(parts) not in (2, 3):
        return None
    try:
        day = int(parts[0])
        month = int(parts[1])
        year = int(parts[2]) if len(parts) == 3 else today.year
        if len(parts) == 3 and year < 100:
            year += 2000
        result = date(year, month, day)
        if len(parts) == 2 and result < today:
            result = date(year + 1, month, day)
        return result
    except ValueError:
        return None


def parse_time_input(text: str) -> time | None:
    cleaned = text.strip().replace(".", ":").replace(" ", "")
    parts = cleaned.split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        return time(hour, minute)
    except ValueError:
        return None


def format_duration(minutes: int) -> str:
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} ч"
    if minutes > 60:
        return f"{minutes // 60} ч {minutes % 60} мин"
    return f"{minutes} мин"
