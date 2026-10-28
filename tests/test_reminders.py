from __future__ import annotations

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import RegistrationStatus
from app.db.base import utcnow
from app.services import registrations as service
from app.services.reminders import ReminderKind, collect_due_reminders
from tests.helpers import create_event, create_game, create_registration, create_user


async def test_24h_reminder_sent_once(session: AsyncSession) -> None:
    now = utcnow()
    event = await create_event(session)
    game = await create_game(session, event, starts_at=now + timedelta(hours=12))
    user = await create_user(session)
    await create_registration(session, game, user)

    reminders = await collect_due_reminders(session, now=now)
    assert len(reminders) == 1
    assert reminders[0].kind == ReminderKind.H24
    assert reminders[0].user.tg_id == user.tg_id

    again = await collect_due_reminders(session, now=now + timedelta(minutes=1))
    assert again == []


async def test_2h_reminder_marks_both_flags(session: AsyncSession) -> None:
    now = utcnow()
    event = await create_event(session)
    game = await create_game(session, event, starts_at=now + timedelta(hours=1))
    user = await create_user(session)
    registration = await create_registration(session, game, user)

    reminders = await collect_due_reminders(session, now=now)
    assert len(reminders) == 1
    assert reminders[0].kind == ReminderKind.H2

    await session.refresh(registration)
    assert registration.reminder_24_sent_at is not None
    assert registration.reminder_2_sent_at is not None

    again = await collect_due_reminders(session, now=now + timedelta(minutes=1))
    assert again == []


async def test_registration_within_24h_skips_24h_reminder(
    session: AsyncSession,
) -> None:
    now = utcnow()
    event = await create_event(session)
    game = await create_game(session, event, starts_at=now + timedelta(hours=12))
    user = await create_user(session)

    outcome = await service.register_for_game(session, game.id, user.tg_id)
    assert outcome.registration is not None
    await session.refresh(outcome.registration)
    assert outcome.registration.reminder_24_sent_at is not None

    reminders = await collect_due_reminders(session, now=now)
    assert reminders == []


async def test_waitlisted_user_gets_no_reminder(session: AsyncSession) -> None:
    now = utcnow()
    event = await create_event(session)
    game = await create_game(session, event, capacity=1, starts_at=now + timedelta(hours=12))
    user1 = await create_user(session, 1)
    user2 = await create_user(session, 2)

    await create_registration(session, game, user1)
    await create_registration(session, game, user2, status=RegistrationStatus.WAITLIST.value)

    reminders = await collect_due_reminders(session, now=now)
    assert len(reminders) == 1
    assert reminders[0].user.tg_id == user1.tg_id
