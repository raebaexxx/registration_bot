from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


def backup(source: Path, destination_dir: Path) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = destination_dir / f"bot_{timestamp}.db"

    with sqlite3.connect(source) as source_connection:
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)

    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a consistent SQLite backup.")
    parser.add_argument("--source", type=Path, default=Path("data/bot.db"))
    parser.add_argument("--destination", type=Path, default=Path("backups"))
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"Database not found: {args.source}")

    result = backup(args.source, args.destination)
    print(result)


if __name__ == "__main__":
    main()
