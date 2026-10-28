from __future__ import annotations


def game(game_id: int) -> str:
    return f"game:{game_id}"


def category(category_value: str, page: int = 0) -> str:
    return f"cat:{category_value}:{page}"


def register(game_id: int) -> str:
    return f"reg:{game_id}"


def cancel_ask(game_id: int) -> str:
    return f"cancelask:{game_id}"


def cancel_yes(game_id: int) -> str:
    return f"cancel:{game_id}"


def offer_accept(game_id: int) -> str:
    return f"offer:accept:{game_id}"


def offer_decline(game_id: int) -> str:
    return f"offer:decline:{game_id}"


MY = "my:list"
MAIN = "menu:main"
GAMES = "menu:games"
HELP = "menu:help"
NOOP = "noop"


def admin_menu() -> str:
    return "admin:menu"


def admin_events(page: int = 0) -> str:
    return f"admin:events:{page}"


def admin_event(event_id: int) -> str:
    return f"admin:event:{event_id}"


ADMIN_EVENT_NEW = "admin:event:new"


def admin_event_new_date(iso_date: str) -> str:
    return f"admin:event:newdate:{iso_date}"


def admin_event_publish(event_id: int) -> str:
    return f"admin:event:publish:{event_id}"


def admin_event_archive(event_id: int) -> str:
    return f"admin:event:archive:{event_id}"


def admin_event_rename(event_id: int) -> str:
    return f"admin:event:rename:{event_id}"


def admin_event_copy(event_id: int) -> str:
    return f"admin:event:copy:{event_id}"


def admin_event_announce(event_id: int) -> str:
    return f"admin:event:announce:{event_id}"


def admin_announce_send(event_id: int) -> str:
    return f"admin:announce:send:{event_id}"


def admin_game_new(event_id: int) -> str:
    return f"admin:game:new:{event_id}"


def admin_game_category(event_id: int, category_value: str) -> str:
    return f"admin:game:cat:{event_id}:{category_value}"


def admin_game(game_id: int) -> str:
    return f"admin:game:{game_id}"


def admin_game_participants(game_id: int, page: int = 0) -> str:
    return f"admin:game:parts:{game_id}:{page}"


def admin_game_limit(game_id: int) -> str:
    return f"admin:game:limit:{game_id}"


def admin_game_close(game_id: int) -> str:
    return f"admin:game:close:{game_id}"


def admin_game_open(game_id: int) -> str:
    return f"admin:game:open:{game_id}"


def admin_game_cancel_ask(game_id: int) -> str:
    return f"admin:game:cancelask:{game_id}"


def admin_game_cancel(game_id: int) -> str:
    return f"admin:game:cancel:{game_id}"


def admin_game_delete_ask(game_id: int) -> str:
    return f"admin:game:deleteask:{game_id}"


def admin_game_delete(game_id: int) -> str:
    return f"admin:game:delete:{game_id}"


def admin_part_remove_ask(game_id: int, registration_id: int, page: int) -> str:
    return f"admin:part:rmask:{game_id}:{registration_id}:{page}"


def admin_part_remove(game_id: int, registration_id: int, page: int) -> str:
    return f"admin:part:rm:{game_id}:{registration_id}:{page}"


def fsm_skip() -> str:
    return "fsm:skip"


def fsm_cancel() -> str:
    return "fsm:cancel"
