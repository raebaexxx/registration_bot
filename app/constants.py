from __future__ import annotations

from enum import StrEnum


class Category(StrEnum):
    ADULT = "adult"
    TEEN = "teen"

    @property
    def label(self) -> str:
        return {
            Category.ADULT: "Взрослые",
            Category.TEEN: "Подростковые",
        }[self]

    @property
    def emoji(self) -> str:
        return {
            Category.ADULT: "🧑",
            Category.TEEN: "🧒",
        }[self]


class EventStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class GameStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class RegistrationStatus(StrEnum):
    CONFIRMED = "confirmed"
    WAITLIST = "waitlist"
    OFFERED = "offered"
    CANCELLED = "cancelled"


ACTIVE_REGISTRATION_STATUSES = (
    RegistrationStatus.CONFIRMED,
    RegistrationStatus.WAITLIST,
    RegistrationStatus.OFFERED,
)

OCCUPIED_REGISTRATION_STATUSES = (
    RegistrationStatus.CONFIRMED,
    RegistrationStatus.OFFERED,
)
