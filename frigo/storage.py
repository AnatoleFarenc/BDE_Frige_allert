import os
import sqlite3
from datetime import date


class DutyStore:
    """Fridge duty assignments: one row per (date, Discord user ID)."""

    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS duties ("
            " day TEXT NOT NULL,"
            " user_id INTEGER NOT NULL,"
            " PRIMARY KEY (day, user_id))"
        )
        self._db.commit()

    def get(self, day: date) -> set[int]:
        rows = self._db.execute("SELECT user_id FROM duties WHERE day = ?", (day.isoformat(),))
        return {row[0] for row in rows}

    def get_range(self, start: date, end: date) -> dict[str, list[int]]:
        rows = self._db.execute(
            "SELECT day, user_id FROM duties WHERE day BETWEEN ? AND ? ORDER BY day",
            (start.isoformat(), end.isoformat()),
        )
        result: dict[str, list[int]] = {}
        for day, user_id in rows:
            result.setdefault(day, []).append(user_id)
        return result

    def set(self, day: date, user_ids: set[int]) -> None:
        with self._db:
            self._db.execute("DELETE FROM duties WHERE day = ?", (day.isoformat(),))
            self._db.executemany(
                "INSERT INTO duties (day, user_id) VALUES (?, ?)",
                [(day.isoformat(), uid) for uid in user_ids],
            )
