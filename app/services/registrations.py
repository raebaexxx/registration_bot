from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.constants import (
    ACTIVE_REGISTRATION_STATUSES,
    OCCUPIED_REGISTRATION_STATUSES,
    Category,
    EventStatus,
    GameStatus,
    RegistrationStatus,
)
from app.db.base import utcnow
from app.db.models import Event, Game, Registration, User

_game_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def reset_game_locks() -> None:
    """Test helper: clear in-process locks between event loops."""

    _game_locks.clear()


def _lock(game_id: int) -> asyncio.Lock:
    return _game_locks[game_id]


@dataclass(frozen=True)
class Counts:
    capacity: int
    confirmed: int = 0
    offered: int = 0
    waitlist: int = 0

    @property
    def occupied(self) -> int:
        return self.confirmed + self.offered

    @property
    def free(self) -> int:
        return max(0, self.capacity - self.occupied)


class RegisterResult(StrEnum):
    REGISTERED = "registered"
    WAITLISTED = "waitlisted"
    ALREADY_REGISTERED = "already_registered"
    ALREADY_WAITLISTED = "already_waitlisted"
    OFFER_ACCEPTED = "offer_accepted"
    UNAVAILABLE = "unavailable"
    NOT_FOUND = "not_found"


@dataclass
class RegisterOutcome:
    result: RegisterResult
    game: Game | None = None
    registration: Registration | None = None
    counts: Counts | None = None
    waitlist_position: int | None = None


class CancelResult(StrEnum):
    CANCELLED = "cancelled"
    NOT_FOUND = "not_found"


@dataclass
class OfferOutcome:
    registration: Registration
    game: Game
    user: User
    counts: Counts


@dataclass
class OfferExpired:
    registration: Registration
    game: Game
    user: User


@dataclass
class CancelOutcome:
    result: CancelResult
    game: Game | None = None
    registration: Registration | None = None
    counts: Counts | None = None
    offer: OfferOutcome | None = None


@dataclass
class ExpireOutcome:
    expired: list[OfferExpired]
    offers: list[OfferOutcome]


@dataclass
class CapacityChangeOutcome:
    ok: bool
    error: str | None = None
    game: Game | None = None
    counts: Counts | None = None
    offers: list[OfferOutcome] | None = None


async def _load_game(session: AsyncSession, game_id: int) -> Game | None:
    result = await session.execute(
        select(Game).options(joinedload(Game.event)).where(Game.id == game_id)
    )
    return result.scalar_one_or_none()


async def _load_registration(
    session: AsyncSession, game_id: int, user_id: int
) -> Registration | None:
    result = await session.execute(
        select(Registration)
        .options(joinedload(Registration.user))
        .where(Registration.game_id == game_id, Registration.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_game(session: AsyncSession, game_id: int) -> Game | None:
    return await _load_game(session, game_id)


async def get_user_registration(
    session: AsyncSession, game_id: int, user_id: int
) -> Registration | None:
    return await _load_registration(session, game_id, user_id)


async def get_counts(session: AsyncSession, game: Game) -> Counts:
    result = await session.execute(
        select(Registration.status, func.count())
        .where(Registration.game_id == game.id)
        .group_by(Registration.status)
    )
    by_status = dict(result.all())
    return Counts(
        capacity=game.capacity,
        confirmed=by_status.get(RegistrationStatus.CONFIRMED.value, 0),
        offered=by_status.get(RegistrationStatus.OFFERED.value, 0),
        waitlist=by_status.get(RegistrationStatus.WAITLIST.value, 0),
    )


async def get_counts_for_games(session: AsyncSession, game_ids: list[int]) -> dict[int, Counts]:
    if not game_ids:
        return {}

    games_result = await session.execute(
        select(Game.id, Game.capacity).where(Game.id.in_(game_ids))
    )
    capacities = dict(games_result.all())

    result = await session.execute(
        select(Registration.game_id, Registration.status, func.count())
        .where(Registration.game_id.in_(game_ids))
        .group_by(Registration.game_id, Registration.status)
    )
    grouped: dict[int, dict[str, int]] = defaultdict(dict)
    for game_id, status, count in result.all():
        grouped[game_id][status] = count

    counts: dict[int, Counts] = {}
    for game_id, capacity in capacities.items():
        by_status = grouped.get(game_id, {})
        counts[game_id] = Counts(
            capacity=capacity,
            confirmed=by_status.get(RegistrationStatus.CONFIRMED.value, 0),
            offered=by_status.get(RegistrationStatus.OFFERED.value, 0),
            waitlist=by_status.get(RegistrationStatus.WAITLIST.value, 0),
        )
    return counts


async def get_waitlist_position(session: AsyncSession, registration: Registration) -> int:
    result = await session.scalar(
        select(func.count())
        .select_from(Registration)
        .where(
            Registration.game_id == registration.game_id,
            Registration.status == RegistrationStatus.WAITLIST.value,
            or_(
                Registration.registered_at < registration.registered_at,
                and_(
                    Registration.registered_at == registration.registered_at,
                    Registration.id < registration.id,
                ),
            ),
        )
    )
    return int(result or 0) + 1


def _is_bookable(game: Game, now: datetime) -> bool:
    return (
        game.status == GameStatus.OPEN.value
        and game.event.status == EventStatus.PUBLISHED.value
        and game.starts_at > now
    )


def _is_offer_acceptable(game: Game, now: datetime) -> bool:
    """An already reserved seat can be confirmed even after registration closes."""

    return (
        game.status != GameStatus.CANCELLED.value
        and game.event.status == EventStatus.PUBLISHED.value
        and game.starts_at > now
    )


def _mark_reminders_for_new_confirmation(
    registration: Registration, game: Game, now: datetime
) -> None:
    """Skip reminders the user would otherwise receive right after registering."""

    registration.reminder_24_sent_at = None
    registration.reminder_2_sent_at = None
    if game.starts_at <= now + timedelta(hours=2):
        registration.reminder_24_sent_at = now
        registration.reminder_2_sent_at = now
    elif game.starts_at <= now + timedelta(hours=24):
        registration.reminder_24_sent_at = now


async def register_for_game(
    session: AsyncSession,
    game_id: int,
    user_id: int,
    offer_minutes: int = 120,
) -> RegisterOutcome:
    async with _lock(game_id):
        now = utcnow()
        game = await _load_game(session, game_id)
        if game is None:
            return RegisterOutcome(RegisterResult.NOT_FOUND)

        registration = await _load_registration(session, game_id, user_id)

        if registration is not None and registration.status == RegistrationStatus.OFFERED.value:
            offer_expired = (
                registration.offer_expires_at is not None and registration.offer_expires_at <= now
            )
            if not offer_expired:
                if not _is_offer_acceptable(game, now):
                    return RegisterOutcome(
                        RegisterResult.UNAVAILABLE,
                        game=game,
                        registration=registration,
                    )
                registration.status = RegistrationStatus.CONFIRMED.value
                registration.offer_expires_at = None
                registration.cancelled_at = None
                _mark_reminders_for_new_confirmation(registration, game, now)
                await session.commit()
                counts = await get_counts(session, game)
                return RegisterOutcome(
                    RegisterResult.OFFER_ACCEPTED,
                    game=game,
                    registration=registration,
                    counts=counts,
                )

            # Expired offer: release the reserved seat and put the user back
            # at the end of the waitlist before trying to register again.
            registration.status = RegistrationStatus.WAITLIST.value
            registration.offer_expires_at = None
            registration.registered_at = now
            await session.commit()

        if not _is_bookable(game, now):
            return RegisterOutcome(
                RegisterResult.UNAVAILABLE,
                game=game,
                registration=registration,
            )

        counts = await get_counts(session, game)

        if registration is not None:
            if registration.status == RegistrationStatus.CONFIRMED.value:
                return RegisterOutcome(
                    RegisterResult.ALREADY_REGISTERED,
                    game=game,
                    registration=registration,
                    counts=counts,
                )

            if registration.status == RegistrationStatus.WAITLIST.value:
                if counts.free > 0:
                    registration.status = RegistrationStatus.CONFIRMED.value
                    registration.cancelled_at = None
                    _mark_reminders_for_new_confirmation(registration, game, now)
                    await session.commit()
                    counts = await get_counts(session, game)
                    return RegisterOutcome(
                        RegisterResult.REGISTERED,
                        game=game,
                        registration=registration,
                        counts=counts,
                    )
                await session.commit()
                position = await get_waitlist_position(session, registration)
                return RegisterOutcome(
                    RegisterResult.ALREADY_WAITLISTED,
                    game=game,
                    registration=registration,
                    counts=counts,
                    waitlist_position=position,
                )

        if counts.free > 0:
            status = RegistrationStatus.CONFIRMED.value
        else:
            status = RegistrationStatus.WAITLIST.value

        if registration is None:
            registration = Registration(
                game_id=game.id,
                user_id=user_id,
                status=status,
                registered_at=now,
            )
            session.add(registration)
        else:
            registration.status = status
            registration.registered_at = now
            registration.offer_expires_at = None
            registration.cancelled_at = None

        if status == RegistrationStatus.CONFIRMED.value:
            _mark_reminders_for_new_confirmation(registration, game, now)

        await session.commit()
        counts = await get_counts(session, game)
        position = None
        if status == RegistrationStatus.WAITLIST.value:
            position = await get_waitlist_position(session, registration)

        return RegisterOutcome(
            RegisterResult.REGISTERED
            if status == RegistrationStatus.CONFIRMED.value
            else RegisterResult.WAITLISTED,
            game=game,
            registration=registration,
            counts=counts,
            waitlist_position=position,
        )


async def _offer_next_locked(
    session: AsyncSession,
    game_id: int,
    now: datetime,
    offer_minutes: int,
    exclude_user_ids: set[int] | None = None,
) -> OfferOutcome | None:
    game = await _load_game(session, game_id)
    if game is None or not _is_bookable(game, now):
        return None

    counts = await get_counts(session, game)
    if counts.free <= 0:
        return None

    statement = (
        select(Registration)
        .options(joinedload(Registration.user))
        .where(
            Registration.game_id == game_id,
            Registration.status == RegistrationStatus.WAITLIST.value,
        )
        .order_by(Registration.registered_at, Registration.id)
        .limit(1)
    )
    if exclude_user_ids:
        statement = statement.where(Registration.user_id.notin_(exclude_user_ids))

    result = await session.execute(statement)
    registration = result.scalar_one_or_none()
    if registration is None:
        return None

    registration.status = RegistrationStatus.OFFERED.value
    registration.offer_expires_at = now + timedelta(minutes=offer_minutes)
    registration.cancelled_at = None
    await session.commit()
    counts = await get_counts(session, game)
    return OfferOutcome(
        registration=registration,
        game=game,
        user=registration.user,
        counts=counts,
    )


async def offer_next(
    session: AsyncSession, game_id: int, offer_minutes: int = 120
) -> OfferOutcome | None:
    async with _lock(game_id):
        return await _offer_next_locked(session, game_id, utcnow(), offer_minutes)


async def cancel_registration(
    session: AsyncSession,
    game_id: int,
    user_id: int,
    offer_minutes: int = 120,
) -> CancelOutcome:
    async with _lock(game_id):
        now = utcnow()
        game = await _load_game(session, game_id)
        registration = await _load_registration(session, game_id, user_id)
        if registration is None or registration.status == RegistrationStatus.CANCELLED.value:
            return CancelOutcome(CancelResult.NOT_FOUND, game=game)

        was_occupied = registration.status in {
            status.value for status in OCCUPIED_REGISTRATION_STATUSES
        }
        registration.status = RegistrationStatus.CANCELLED.value
        registration.cancelled_at = now
        registration.offer_expires_at = None
        await session.commit()

        offer = None
        if was_occupied and game is not None:
            offer = await _offer_next_locked(session, game_id, now, offer_minutes)

        counts = await get_counts(session, game) if game is not None else None
        return CancelOutcome(
            CancelResult.CANCELLED,
            game=game,
            registration=registration,
            counts=counts,
            offer=offer,
        )


async def remove_registration_by_id(
    session: AsyncSession, registration_id: int, offer_minutes: int = 120
) -> CancelOutcome:
    registration = await session.get(Registration, registration_id)
    if registration is None or registration.status == RegistrationStatus.CANCELLED.value:
        return CancelOutcome(CancelResult.NOT_FOUND)

    return await cancel_registration(
        session, registration.game_id, registration.user_id, offer_minutes
    )


async def expire_offers(
    session: AsyncSession,
    offer_minutes: int = 120,
    now: datetime | None = None,
) -> ExpireOutcome:
    now = now or utcnow()
    game_ids_result = await session.execute(
        select(Registration.game_id)
        .where(
            Registration.status == RegistrationStatus.OFFERED.value,
            Registration.offer_expires_at.is_not(None),
            Registration.offer_expires_at <= now,
        )
        .distinct()
    )
    game_ids = list(game_ids_result.scalars().all())

    expired: list[OfferExpired] = []
    offers: list[OfferOutcome] = []

    for game_id in game_ids:
        async with _lock(game_id):
            result = await session.execute(
                select(Registration)
                .options(
                    joinedload(Registration.user),
                    joinedload(Registration.game).joinedload(Game.event),
                )
                .where(
                    Registration.game_id == game_id,
                    Registration.status == RegistrationStatus.OFFERED.value,
                    Registration.offer_expires_at.is_not(None),
                    Registration.offer_expires_at <= now,
                )
            )
            registrations = result.scalars().all()
            if not registrations:
                continue

            expired_user_ids: set[int] = set()
            for registration in registrations:
                registration.status = RegistrationStatus.WAITLIST.value
                registration.offer_expires_at = None
                registration.registered_at = now
                expired_user_ids.add(registration.user_id)
                expired.append(
                    OfferExpired(
                        registration=registration,
                        game=registration.game,
                        user=registration.user,
                    )
                )
            await session.commit()

            while True:
                offer = await _offer_next_locked(
                    session,
                    game_id,
                    now,
                    offer_minutes,
                    exclude_user_ids=expired_user_ids,
                )
                if offer is None:
                    break
                offers.append(offer)

    return ExpireOutcome(expired=expired, offers=offers)


async def change_capacity(
    session: AsyncSession,
    game_id: int,
    new_capacity: int,
    offer_minutes: int = 120,
) -> CapacityChangeOutcome:
    async with _lock(game_id):
        game = await _load_game(session, game_id)
        if game is None:
            return CapacityChangeOutcome(False, error="Игра не найдена.")

        counts = await get_counts(session, game)
        if new_capacity < counts.occupied:
            return CapacityChangeOutcome(
                False,
                error=(
                    f"Нельзя поставить {new_capacity} мест: уже занято "
                    f"{counts.occupied} (включая предложенные места)."
                ),
                game=game,
                counts=counts,
            )

        game.capacity = new_capacity
        await session.commit()

        offers: list[OfferOutcome] = []
        while True:
            offer = await _offer_next_locked(session, game_id, utcnow(), offer_minutes)
            if offer is None:
                break
            offers.append(offer)

        counts = await get_counts(session, game)
        return CapacityChangeOutcome(True, game=game, counts=counts, offers=offers)


async def get_visible_games(
    session: AsyncSession, category: Category, now: datetime | None = None
) -> list[Game]:
    now = now or utcnow()
    result = await session.execute(
        select(Game)
        .join(Game.event)
        .options(joinedload(Game.event))
        .where(
            Game.category == category.value,
            Game.status == GameStatus.OPEN.value,
            Game.starts_at > now,
            Event.status == EventStatus.PUBLISHED.value,
        )
        .order_by(Game.starts_at, Game.id)
    )
    return list(result.scalars().unique().all())


async def get_registration(session: AsyncSession, registration_id: int) -> Registration | None:
    result = await session.execute(
        select(Registration)
        .options(
            joinedload(Registration.user),
            joinedload(Registration.game).joinedload(Game.event),
        )
        .where(Registration.id == registration_id)
    )
    return result.scalar_one_or_none()


async def get_game_registrations(session: AsyncSession, game_id: int) -> list[Registration]:
    status_order = case(
        (Registration.status == RegistrationStatus.CONFIRMED.value, 0),
        (Registration.status == RegistrationStatus.OFFERED.value, 1),
        (Registration.status == RegistrationStatus.WAITLIST.value, 2),
        else_=3,
    )
    result = await session.execute(
        select(Registration)
        .options(joinedload(Registration.user))
        .where(
            Registration.game_id == game_id,
            Registration.status.in_([status.value for status in ACTIVE_REGISTRATION_STATUSES]),
        )
        .order_by(status_order, Registration.registered_at, Registration.id)
    )
    return list(result.scalars().unique().all())


async def get_active_registrations(
    session: AsyncSession, user_id: int, now: datetime | None = None
) -> list[Registration]:
    now = now or utcnow()
    result = await session.execute(
        select(Registration)
        .join(Registration.game)
        .join(Game.event)
        .options(joinedload(Registration.game).joinedload(Game.event))
        .where(
            Registration.user_id == user_id,
            Registration.status.in_([status.value for status in ACTIVE_REGISTRATION_STATUSES]),
            Game.starts_at > now,
            Event.status == EventStatus.PUBLISHED.value,
        )
        .order_by(Game.starts_at, Registration.id)
    )
    return list(result.scalars().unique().all())


async def close_started_games(session: AsyncSession, now: datetime | None = None) -> int:
    now = now or utcnow()
    result = await session.execute(
        select(Game).where(
            Game.status == GameStatus.OPEN.value,
            Game.starts_at <= now,
        )
    )
    games = list(result.scalars().all())
    for game in games:
        game.status = GameStatus.CLOSED.value
    if games:
        await session.commit()
    return len(games)
