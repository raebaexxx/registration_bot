from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """Return naive UTC time.

    SQLite does not preserve timezone information, so the whole application
    stores and compares naive UTC datetimes and converts to the configured
    timezone only for display.
    """

    return datetime.now(UTC).replace(tzinfo=None)
