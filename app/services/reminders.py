from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.constants import EventStatus, GameStatus, RegistrationStatus
from app.db.base import utcnow
from app.db.models import Event, Game, Registration, User


class ReminderKind(StrEnum):
    H24 = "24h"
    H2 = "2h"


@dataclass
class Reminder:
    kind: ReminderKind
    registration: Registration
    game: Game
    user: User


async def collect_due_reminders(
    session: AsyncSession, now: datetime | None = None
) -> list[Reminder]:
    now = now or utcnow()
    result = await session.execute(
        select(Registration)
        .join(Registration.game)
        .join(Game.event)
        .options(
            joinedload(Registration.user),
            joinedload(Registration.game).joinedload(Game.event),
        )
        .where(
            Registration.status == RegistrationStatus.CONFIRMED.value,
            Event.status == EventStatus.PUBLISHED.value,
            Game.status != GameStatus.CANCELLED.value,
            Game.starts_at > now,
            Game.starts_at <= now + timedelta(hours=24),
            or_(
                Registration.reminder_24_sent_at.is_(None),
                Registration.reminder_2_sent_at.is_(None),
            ),
        )
        .order_by(Game.starts_at, Registration.id)
    )
    registrations = list(result.scalars().unique().all())

    reminders: list[Reminder] = []
    for registration in registrations:
        game = registration.game
        if game.starts_at <= now + timedelta(hours=2):
            if registration.reminder_2_sent_at is not None:
                continue
            registration.reminder_2_sent_at = now
            if registration.reminder_24_sent_at is None:
                registration.reminder_24_sent_at = now
            reminders.append(
                Reminder(
                    kind=ReminderKind.H2,
                    registration=registration,
                    game=game,
                    user=registration.user,
                )
            )
        elif registration.reminder_24_sent_at is None:
            registration.reminder_24_sent_at = now
            reminders.append(
                Reminder(
                    kind=ReminderKind.H24,
                    registration=registration,
                    game=game,
                    user=registration.user,
                )
            )

    if reminders:
        await session.commit()
    return reminders
