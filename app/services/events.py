from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.constants import (
    ACTIVE_REGISTRATION_STATUSES,
    Category,
    EventStatus,
    GameStatus,
    RegistrationStatus,
)
from app.db.base import utcnow
from app.db.models import Event, Game, Registration
from app.utils.time import combine_local, to_local


async def create_event(session: AsyncSession, title: str, event_date: date) -> Event:
    event = Event(title=title.strip(), event_date=event_date, status=EventStatus.DRAFT.value)
    session.add(event)
    await session.commit()
    return event


async def get_event(session: AsyncSession, event_id: int) -> Event | None:
    result = await session.execute(
        select(Event)
        .options(selectinload(Event.games), joinedload(Event.channel_post))
        .where(Event.id == event_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def list_events(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 8,
    include_archived: bool = True,
) -> tuple[list[Event], int]:
    conditions = []
    if not include_archived:
        conditions.append(Event.status != EventStatus.ARCHIVED.value)

    total = await session.scalar(select(func.count()).select_from(Event).where(*conditions))
    result = await session.execute(
        select(Event)
        .options(selectinload(Event.games))
        .where(*conditions)
        .order_by(Event.event_date.desc(), Event.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().unique().all()), int(total or 0)


async def publish_event(session: AsyncSession, event_id: int) -> Event | None:
    event = await get_event(session, event_id)
    if event is None:
        return None
    event.status = EventStatus.PUBLISHED.value
    await session.commit()
    return event


async def archive_event(session: AsyncSession, event_id: int) -> Event | None:
    event = await get_event(session, event_id)
    if event is None:
        return None
    event.status = EventStatus.ARCHIVED.value
    for game in event.games:
        if game.status == GameStatus.OPEN.value:
            game.status = GameStatus.CLOSED.value
    await session.commit()
    return event


async def restore_event(session: AsyncSession, event_id: int) -> Event | None:
    event = await get_event(session, event_id)
    if event is None:
        return None
    event.status = EventStatus.PUBLISHED.value
    await session.commit()
    return event


async def rename_event(session: AsyncSession, event_id: int, title: str) -> Event | None:
    event = await get_event(session, event_id)
    if event is None:
        return None
    event.title = title.strip()
    await session.commit()
    return event


async def add_game(
    session: AsyncSession,
    event_id: int,
    category: Category,
    title: str,
    starts_at: datetime,
    capacity: int,
    place: str | None = None,
    description: str | None = None,
) -> Game | None:
    event = await session.get(Event, event_id)
    if event is None:
        return None
    game = Game(
        event_id=event_id,
        category=category.value,
        title=title.strip(),
        description=description.strip() if description else None,
        place=place.strip() if place else None,
        starts_at=starts_at,
        capacity=capacity,
        status=GameStatus.OPEN.value,
    )
    session.add(game)
    await session.commit()
    return game


async def get_game_with_event(session: AsyncSession, game_id: int) -> Game | None:
    result = await session.execute(
        select(Game).options(joinedload(Game.event)).where(Game.id == game_id)
    )
    return result.scalar_one_or_none()


async def set_game_status(session: AsyncSession, game_id: int, status: GameStatus) -> Game | None:
    game = await get_game_with_event(session, game_id)
    if game is None:
        return None
    game.status = status.value
    await session.commit()
    return game


async def cancel_game(
    session: AsyncSession, game_id: int
) -> tuple[Game | None, list[Registration]]:
    result = await session.execute(
        select(Game)
        .options(
            joinedload(Game.event),
            selectinload(Game.registrations).joinedload(Registration.user),
        )
        .where(Game.id == game_id)
    )
    game = result.scalar_one_or_none()
    if game is None:
        return None, []

    now = utcnow()
    active_statuses = {status.value for status in ACTIVE_REGISTRATION_STATUSES}
    affected: list[Registration] = []
    game.status = GameStatus.CANCELLED.value
    for registration in game.registrations:
        if registration.status in active_statuses:
            registration.status = RegistrationStatus.CANCELLED.value
            registration.cancelled_at = now
            registration.offer_expires_at = None
            affected.append(registration)
    await session.commit()
    return game, affected


async def delete_game(session: AsyncSession, game_id: int) -> bool:
    registrations_count = await session.scalar(
        select(func.count()).select_from(Registration).where(Registration.game_id == game_id)
    )
    if registrations_count:
        return False
    game = await session.get(Game, game_id)
    if game is None:
        return False
    await session.delete(game)
    await session.commit()
    return True


@dataclass
class CopyResult:
    copied: int
    source_title: str | None = None
    source_date: date | None = None


async def copy_games_from_previous_event(
    session: AsyncSession,
    target_event_id: int,
    tz: ZoneInfo,
) -> CopyResult:
    target = await get_event(session, target_event_id)
    if target is None:
        return CopyResult(copied=0)

    source_result = await session.execute(
        select(Event)
        .options(selectinload(Event.games))
        .where(
            Event.id != target.id,
            Event.event_date < target.event_date,
        )
        .order_by(Event.event_date.desc(), Event.id.desc())
        .limit(1)
    )
    source = source_result.scalar_one_or_none()
    if source is None or not source.games:
        return CopyResult(copied=0)

    for source_game in source.games:
        local_time = to_local(source_game.starts_at, tz).time()
        session.add(
            Game(
                event_id=target.id,
                category=source_game.category,
                title=source_game.title,
                description=source_game.description,
                place=source_game.place,
                starts_at=combine_local(target.event_date, local_time, tz),
                capacity=source_game.capacity,
                status=GameStatus.OPEN.value,
            )
        )
    await session.commit()
    return CopyResult(
        copied=len(source.games),
        source_title=source.title,
        source_date=source.event_date,
    )
