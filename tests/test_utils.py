from __future__ import annotations

from datetime import date, time
from zoneinfo import ZoneInfo

from app.utils.time import (
    combine_local,
    format_date,
    format_time,
    next_weekend_dates,
    parse_date_input,
    parse_time_input,
    to_local,
)

TZ = ZoneInfo("Europe/Moscow")


def test_parse_date_input() -> None:
    today = date(2026, 10, 29)
    assert parse_date_input("01.11.2026", today) == date(2026, 11, 1)
    assert parse_date_input("01.11.26", today) == date(2026, 11, 1)
    assert parse_date_input("01.11", today) == date(2026, 11, 1)
    assert parse_date_input("1/11/2026", today) == date(2026, 11, 1)
    assert parse_date_input("01.01", date(2026, 12, 30)) == date(2027, 1, 1)
    assert parse_date_input("32.11.2026", today) is None
    assert parse_date_input("завтра", today) is None


def test_parse_time_input() -> None:
    assert parse_time_input("18:00") == time(18, 0)
    assert parse_time_input("9.30") == time(9, 30)
    assert parse_time_input("25:00") is None
    assert parse_time_input("18") is None


def test_next_weekend_dates() -> None:
    assert next_weekend_dates(date(2026, 10, 29)) == (
        date(2026, 10, 31),
        date(2026, 11, 1),
    )
    assert next_weekend_dates(date(2026, 10, 31)) == (
        date(2026, 11, 7),
        date(2026, 11, 8),
    )


def test_format_date_and_time() -> None:
    assert format_date(date(2026, 11, 1)) == "Вс, 1 ноября"
    utc_value = combine_local(date(2026, 11, 1), time(18, 0), TZ)
    assert utc_value.hour == 15
    assert format_time(utc_value, TZ) == "18:00"
    assert to_local(utc_value, TZ).hour == 18
