from __future__ import annotations

from app.config import Settings


def test_admin_ids_and_channel_id_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_IDS", "123, 456")
    monkeypatch.setenv("CHANNEL_ID", "-1001234567890")

    settings = Settings(_env_file=None)
    assert settings.admin_ids == [123, 456]
    assert settings.channel_id == "-1001234567890"


def test_empty_admin_ids(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_IDS", "")

    settings = Settings(_env_file=None)
    assert settings.admin_ids == []


def test_admin_ids_accepts_list() -> None:
    settings = Settings(admin_ids=[1, 2], _env_file=None)
    assert settings.admin_ids == [1, 2]


def test_timezone_from_tz_env(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "Asia/Yekaterinburg")

    settings = Settings(_env_file=None)
    assert settings.tz.key == "Asia/Yekaterinburg"


def test_admin_notifications_env(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_NOTIFICATIONS", "false")

    settings = Settings(_env_file=None)
    assert settings.admin_notifications is False
