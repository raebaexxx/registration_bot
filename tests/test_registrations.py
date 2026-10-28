from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    Category,
    EventStatus,
    GameStatus,
    RegistrationStatus,
)
from app.db.base import utcnow
from app.services import events as event_service
from app.services import registrations as service
from app.services.registrations import (
    CancelResult,
    RegisterResult,
)
from tests.helpers import (
    create_event,
    create_game,
    create_user,
)


async def test_capacity_duplicate_and_waitlist(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=2)
    user1 = await create_user(session, 1)
    user2 = await create_user(session, 2)
    user3 = await create_user(session, 3)

    first = await service.register_for_game(session, game.id, user1.tg_id)
    assert first.result == RegisterResult.REGISTERED
    assert first.counts is not None
    assert first.counts.confirmed == 1
    assert first.counts.free == 1

    duplicate = await service.register_for_game(session, game.id, user1.tg_id)
    assert duplicate.result == RegisterResult.ALREADY_REGISTERED

    second = await service.register_for_game(session, game.id, user2.tg_id)
    assert second.result == RegisterResult.REGISTERED
    assert second.counts is not None
    assert second.counts.confirmed == 2
    assert second.counts.free == 0

    third = await service.register_for_game(session, game.id, user3.tg_id)
    assert third.result == RegisterResult.WAITLISTED
    assert third.waitlist_position == 1
    assert third.counts is not None
    assert third.counts.waitlist == 1


async def test_waitlist_positions(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=1)
    user1 = await create_user(session, 1)
    user2 = await create_user(session, 2)
    user3 = await create_user(session, 3)

    await service.register_for_game(session, game.id, user1.tg_id)
    second = await service.register_for_game(session, game.id, user2.tg_id)
    third = await service.register_for_game(session, game.id, user3.tg_id)
    assert second.waitlist_position == 1
    assert third.waitlist_position == 2


async def test_cancel_offers_place_to_first_waiting(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=1)
    user1 = await create_user(session, 1)
    user2 = await create_user(session, 2)

    await service.register_for_game(session, game.id, user1.tg_id)
    await service.register_for_game(session, game.id, user2.tg_id)

    outcome = await service.cancel_registration(session, game.id, user1.tg_id)
    assert outcome.result == CancelResult.CANCELLED
    assert outcome.offer is not None
    assert outcome.offer.user.tg_id == user2.tg_id
    assert outcome.offer.registration.status == RegistrationStatus.OFFERED.value
    assert outcome.counts is not None
    assert outcome.counts.confirmed == 0
    assert outcome.counts.offered == 1
    assert outcome.counts.free == 0

    accepted = await service.register_for_game(session, game.id, user2.tg_id)
    assert accepted.result == RegisterResult.OFFER_ACCEPTED
    assert accepted.counts is not None
    assert accepted.counts.confirmed == 1
    assert accepted.counts.offered == 0


async def test_cancel_waitlist_does_not_offer(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=1)
    user1 = await create_user(session, 1)
    user2 = await create_user(session, 2)

    await service.register_for_game(session, game.id, user1.tg_id)
    await service.register_for_game(session, game.id, user2.tg_id)

    outcome = await service.cancel_registration(session, game.id, user2.tg_id)
    assert outcome.result == CancelResult.CANCELLED
    assert outcome.offer is None

    registration = await service.get_user_registration(session, game.id, user2.tg_id)
    assert registration is not None
    assert registration.status == RegistrationStatus.CANCELLED.value


async def test_offer_expires_and_goes_to_next(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=1)
    user1 = await create_user(session, 1)
    user2 = await create_user(session, 2)
    user3 = await create_user(session, 3)

    await service.register_for_game(session, game.id, user1.tg_id)
    await service.register_for_game(session, game.id, user2.tg_id)
    await service.register_for_game(session, game.id, user3.tg_id)

    await service.cancel_registration(session, game.id, user1.tg_id)
    result = await service.expire_offers(session, 120, now=utcnow() + timedelta(hours=3))

    assert len(result.expired) == 1
    assert result.expired[0].user.tg_id == user2.tg_id
    assert len(result.offers) == 1
    assert result.offers[0].user.tg_id == user3.tg_id

    registration2 = await service.get_user_registration(session, game.id, user2.tg_id)
    registration3 = await service.get_user_registration(session, game.id, user3.tg_id)
    assert registration2 is not None
    assert registration2.status == RegistrationStatus.WAITLIST.value
    assert registration3 is not None
    assert registration3.status == RegistrationStatus.OFFERED.value


async def test_capacity_increase_offers_waitlist(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=1)
    user1 = await create_user(session, 1)
    user2 = await create_user(session, 2)

    await service.register_for_game(session, game.id, user1.tg_id)
    await service.register_for_game(session, game.id, user2.tg_id)

    outcome = await service.change_capacity(session, game.id, 2)
    assert outcome.ok is True
    assert len(outcome.offers or []) == 1
    assert (outcome.offers or [])[0].user.tg_id == user2.tg_id

    accepted = await service.register_for_game(session, game.id, user2.tg_id)
    assert accepted.result == RegisterResult.OFFER_ACCEPTED
    assert accepted.counts is not None
    assert accepted.counts.confirmed == 2


async def test_cannot_reduce_below_occupied(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=2)
    user1 = await create_user(session, 1)
    user2 = await create_user(session, 2)

    await service.register_for_game(session, game.id, user1.tg_id)
    await service.register_for_game(session, game.id, user2.tg_id)

    outcome = await service.change_capacity(session, game.id, 1)
    assert outcome.ok is False
    assert outcome.error is not None


async def test_draft_event_is_not_bookable(session: AsyncSession) -> None:
    event = await create_event(session, status=EventStatus.DRAFT.value)
    game = await create_game(session, event)
    user = await create_user(session)

    outcome = await service.register_for_game(session, game.id, user.tg_id)
    assert outcome.result == RegisterResult.UNAVAILABLE


async def test_closed_game_is_not_bookable(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, status=GameStatus.CLOSED.value)
    user = await create_user(session)

    outcome = await service.register_for_game(session, game.id, user.tg_id)
    assert outcome.result == RegisterResult.UNAVAILABLE


async def test_remove_registration_by_id_offers_next(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=1)
    user1 = await create_user(session, 1)
    user2 = await create_user(session, 2)

    first = await service.register_for_game(session, game.id, user1.tg_id)
    await service.register_for_game(session, game.id, user2.tg_id)
    assert first.registration is not None

    outcome = await service.remove_registration_by_id(session, first.registration.id)
    assert outcome.result == CancelResult.CANCELLED
    assert outcome.offer is not None
    assert outcome.offer.user.tg_id == user2.tg_id


async def test_visible_games_filters(session: AsyncSession) -> None:
    published = await create_event(session)
    draft = await create_event(session, status=EventStatus.DRAFT.value)
    adult = await create_game(session, published, title="Мафия", capacity=5)
    await create_game(session, published, title="Бункер", category=Category.TEEN.value)
    await create_game(session, published, title="Закрытая", status=GameStatus.CLOSED.value)
    await create_game(session, draft, title="Черновик")
    past = await create_game(
        session,
        published,
        title="Прошлая",
        starts_at=utcnow() - timedelta(hours=1),
    )

    games = await service.get_visible_games(session, Category.ADULT)
    ids = {game.id for game in games}
    assert adult.id in ids
    assert past.id not in ids
    assert all(game.category == Category.ADULT.value for game in games)
    assert all(game.status == GameStatus.OPEN.value for game in games)


async def test_close_started_games(session: AsyncSession) -> None:
    event = await create_event(session)
    game = await create_game(
        session,
        event,
        starts_at=utcnow() - timedelta(minutes=5),
    )

    closed = await service.close_started_games(session)
    assert closed == 1
    await session.refresh(game)
    assert game.status == GameStatus.CLOSED.value


async def test_copy_games_from_previous_event(session: AsyncSession) -> None:
    from app.utils.time import to_local

    source = await create_event(session, event_date=date(2026, 11, 1))
    source_game = await create_game(session, source, title="Мафия", capacity=8)
    target = await create_event(session, event_date=date(2026, 11, 8))

    result = await event_service.copy_games_from_previous_event(
        session, target.id, ZoneInfo("Europe/Moscow")
    )
    assert result.copied == 1
    assert result.source_title == source.title

    target_event = await event_service.get_event(session, target.id)
    assert target_event is not None
    assert len(target_event.games) == 1
    copied = target_event.games[0]
    assert copied.title == "Мафия"
    assert copied.capacity == 8
    assert to_local(copied.starts_at).time() == to_local(source_game.starts_at).time()


@pytest.mark.parametrize("capacity", [1, 2, 5])
async def test_counts_are_consistent(session: AsyncSession, capacity: int) -> None:
    event = await create_event(session)
    game = await create_game(session, event, capacity=capacity)
    for index in range(capacity):
        user = await create_user(session, index + 1)
        outcome = await service.register_for_game(session, game.id, user.tg_id)
        assert outcome.result == RegisterResult.REGISTERED

    counts = await service.get_counts(session, game)
    assert counts.confirmed == capacity
    assert counts.free == 0
