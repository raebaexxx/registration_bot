from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import (
    Category,
    EventStatus,
    GameStatus,
    RegistrationStatus,
)
from app.db.base import Base, utcnow


class User(Base):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    registrations: Mapped[list[Registration]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def display_name(self) -> str:
        name = " ".join(part for part in (self.first_name, self.last_name) if part)
        return name or self.username or str(self.tg_id)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16), default=EventStatus.DRAFT.value, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    games: Mapped[list[Game]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="Game.starts_at",
    )
    channel_post: Mapped[ChannelPost | None] = relationship(
        back_populates="event", cascade="all, delete-orphan", uselist=False
    )

    @property
    def is_public(self) -> bool:
        return self.status == EventStatus.PUBLISHED


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    place: Mapped[str | None] = mapped_column(String(255))
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=GameStatus.OPEN.value, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    event: Mapped[Event] = relationship(back_populates="games")
    registrations: Mapped[list[Registration]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )

    @property
    def category_enum(self) -> Category:
        return Category(self.category)

    @property
    def is_open(self) -> bool:
        return self.status == GameStatus.OPEN.value


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("game_id", "user_id", name="uq_registration_game_user"),
        Index("ix_registrations_game_status", "game_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.tg_id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default=RegistrationStatus.CONFIRMED.value, nullable=False
    )
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    offer_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    reminder_24_sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    reminder_2_sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    game: Mapped[Game] = relationship(back_populates="registrations")
    user: Mapped[User] = relationship(back_populates="registrations")

    @property
    def status_enum(self) -> RegistrationStatus:
        return RegistrationStatus(self.status)


class ChannelPost(Base):
    __tablename__ = "channel_posts"
    __table_args__ = (UniqueConstraint("event_id", name="uq_channel_post_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    event: Mapped[Event] = relationship(back_populates="channel_post")
