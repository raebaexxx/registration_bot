from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import EventStatus, GameStatus
from app.services import events as event_service
from tests.helpers import create_event, create_game


async def test_archive_closes_games_and_restore_keeps_them_closed(
    session: AsyncSession,
) -> None:
    event = await create_event(session)
    game = await create_game(session, event)

    archived = await event_service.archive_event(session, event.id)
    assert archived is not None
    assert archived.status == EventStatus.ARCHIVED.value
    await session.refresh(game)
    assert game.status == GameStatus.CLOSED.value

    restored = await event_service.restore_event(session, event.id)
    assert restored is not None
    assert restored.status == EventStatus.PUBLISHED.value
    await session.refresh(game)
    assert game.status == GameStatus.CLOSED.value


async def test_list_events_and_pagination(session: AsyncSession) -> None:
    for _ in range(3):
        await create_event(session)

    events, total = await event_service.list_events(session, offset=0, limit=2)
    assert total == 3
    assert len(events) == 2
