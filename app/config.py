from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    bot_token: str = ""
    admin_ids: Annotated[list[int], NoDecode] = []
    channel_id: str | None = None
    timezone: str = Field(
        default="Europe/Moscow",
        validation_alias=AliasChoices("TZ", "TIMEZONE"),
    )
    database_url: str = "sqlite+aiosqlite:///./data/bot.db"
    waitlist_offer_minutes: int = 120
    admin_notifications: bool = True
    log_level: str = "INFO"

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> object:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        return value

    @field_validator("channel_id", mode="before")
    @classmethod
    def normalize_channel_id(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return str(value).strip()

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    def ensure_data_dir(self) -> None:
        if self.is_sqlite:
            Path("data").mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
