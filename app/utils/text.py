from __future__ import annotations

import html


def esc(value: object | None) -> str:
    """Escape user-provided text for Telegram HTML messages."""

    if value is None:
        return ""
    return html.escape(str(value), quote=False)


def truncate(value: str, limit: int = 120) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def user_mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{esc(name)}</a>'
