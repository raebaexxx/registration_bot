from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import Category, EventStatus, GameStatus, RegistrationStatus
from app.db.base import utcnow
from app.db.models import Event, Game, Registration, User
from app.utils.time import combine_local, local_now

TZ = ZoneInfo("Europe/Moscow")


async def create_user(
    session: AsyncSession,
    tg_id: int = 1001,
    username: str | None = "tester",
    first_name: str | None = "Тест",
) -> User:
    user = User(
        tg_id=tg_id,
        username=username,
        first_name=first_name,
    )
    session.add(user)
    await session.commit()
    return user


async def create_event(
    session: AsyncSession,
    *,
    title: str = "Игровая суббота",
    event_date: date | None = None,
    status: str = EventStatus.PUBLISHED.value,
) -> Event:
    event = Event(
        title=title,
        event_date=event_date or local_now(TZ).date() + timedelta(days=7),
        status=status,
    )
    session.add(event)
    await session.commit()
    return event


async def create_game(
    session: AsyncSession,
    event: Event,
    *,
    title: str = "Мафия",
    category: str = Category.ADULT.value,
    capacity: int = 2,
    starts_at: datetime | None = None,
    status: str = GameStatus.OPEN.value,
) -> Game:
    game = Game(
        event_id=event.id,
        title=title,
        category=category,
        capacity=capacity,
        starts_at=starts_at or combine_local(event.event_date, time(18, 0), TZ),
        status=status,
    )
    session.add(game)
    await session.commit()
    return game


async def create_registration(
    session: AsyncSession,
    game: Game,
    user: User,
    *,
    status: str = RegistrationStatus.CONFIRMED.value,
    registered_at: datetime | None = None,
) -> Registration:
    registration = Registration(
        game_id=game.id,
        user_id=user.tg_id,
        status=status,
        registered_at=registered_at or utcnow(),
    )
    session.add(registration)
    await session.commit()
    return registration
