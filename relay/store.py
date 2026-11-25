"""Everyone who wrote to a relay bot, kept in SQLite so a restart forgets no one.

One row per bot and person: name, username, language, first and last time seen, how many times
they wrote, and whether Telegram last said they blocked the bot. The file lives in DATA_DIR, a
Railway volume, so it outlives deploys. If that folder cannot be written, the store runs in
memory and says so in the log: the bots keep relaying, the list just starts over at restart.

The file is small and every query takes a millisecond, so it is used directly from the event
loop, one connection, no threads.
"""

from __future__ import annotations

import csv
import io
import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger("relay")

_SCHEMA = """
create table if not exists people (
    bot         text    not null,
    user_id     integer not null,
    first_name  text    not null default '',
    username    text    not null default '',
    language    text    not null default '',
    first_seen  integer not null,
    last_seen   integer not null,
    starts      integer not null default 0,
    blocked     integer not null default 0,
    primary key (bot, user_id)
);
create index if not exists people_last_seen on people (last_seen desc);
create table if not exists meta (key text primary key, value text not null);
"""

DAY = 86_400


@dataclass(frozen=True, slots=True)
class Count:
    bot: str
    people: int
    starts: int
    blocked: int = 0
    new_week: int = 0


@dataclass(frozen=True, slots=True)
class Person:
    bot: str
    user_id: int
    first_name: str
    username: str
    language: str
    first_seen: int
    last_seen: int
    starts: int
    blocked: bool


@dataclass(frozen=True, slots=True)
class Summary:
    people: int
    new_today: int
    new_week: int
    blocked: int


class Store:
    def __init__(self, path: str | Path | None) -> None:
        self.path = str(path) if path else ":memory:"
        try:
            if self.path != ":memory:":
                Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(self.path)
            self._db.executescript(_SCHEMA)
        except (OSError, sqlite3.Error) as exc:
            log.error("people list kept in memory, %s cannot be written: %s", self.path, exc)
            self.path = ":memory:"
            self._db = sqlite3.connect(self.path)
            self._db.executescript(_SCHEMA)
        if self.path != ":memory:":
            self._db.execute("pragma journal_mode = wal")
        self._db.execute(
            "insert or ignore into meta (key, value) values ('since', ?)", (str(int(time.time())),)
        )
        self._db.commit()

    @property
    def lasting(self) -> bool:
        return self.path != ":memory:"

    @property
    def since(self) -> datetime:
        row = self._db.execute("select value from meta where key = 'since'").fetchone()
        return datetime.fromtimestamp(int(row[0]), UTC)

    def close(self) -> None:
        self._db.close()

    # ----------------------------------------------------------------- writing

    async def record(
        self,
        bot: str,
        user_id: int,
        *,
        first_name: str = "",
        username: str = "",
        language: str = "",
        now: int | None = None,
    ) -> None:
        """Someone wrote to `bot`: add them, or refresh them and count one more."""
        now = int(time.time()) if now is None else now
        self._db.execute(
            """
            insert into people (bot, user_id, first_name, username, language,
                                first_seen, last_seen, starts)
            values (?, ?, ?, ?, ?, ?, ?, 1)
            on conflict (bot, user_id) do update set
                first_name = excluded.first_name,
                username = excluded.username,
                language = excluded.language,
                last_seen = excluded.last_seen,
                starts = people.starts + 1,
                blocked = 0
            """,
            (bot.lower(), user_id, first_name[:64], username[:32], (language or "")[:8], now, now),
        )
        self._db.commit()

    def mark_blocked(self, bot: str, user_id: int) -> None:
        self._db.execute(
            "update people set blocked = 1 where bot = ? and user_id = ?", (bot.lower(), user_id)
        )
        self._db.commit()

    # ----------------------------------------------------------------- reading

    async def counts(self, bots: list[str], now: int | None = None) -> list[Count]:
        week_ago = (int(time.time()) if now is None else now) - 7 * DAY
        out = []
        for bot in bots:
            people, starts, blocked, new_week = self._db.execute(
                """
                select count(*), coalesce(sum(starts), 0), coalesce(sum(blocked), 0),
                       coalesce(sum(first_seen >= ?), 0)
                from people where bot = ?
                """,
                (week_ago, bot.lower()),
            ).fetchone()
            out.append(Count(bot, people, starts, blocked, new_week))
        return out

    def summary(self, now: int | None = None) -> Summary:
        """Each person once, however many of the bots they started."""
        now = int(time.time()) if now is None else now
        people, new_today, new_week, blocked = self._db.execute(
            """
            select count(*), coalesce(sum(first >= ?), 0), coalesce(sum(first >= ?), 0),
                   coalesce(sum(all_blocked), 0)
            from (select user_id, min(first_seen) as first, min(blocked) as all_blocked
                  from people group by user_id)
            """,
            (now - DAY, now - 7 * DAY),
        ).fetchone()
        return Summary(people, new_today, new_week, blocked)

    def page(self, offset: int, limit: int = 10, bot: str | None = None) -> list[Person]:
        """The people who wrote most recently first."""
        where, args = ("where bot = ?", [bot.lower()]) if bot else ("", [])
        rows = self._db.execute(
            f"select * from people {where} order by last_seen desc, rowid desc limit ? offset ?",  # noqa: S608
            (*args, limit, offset),
        ).fetchall()
        return [Person(*row[:8], bool(row[8])) for row in rows]

    def total(self, bot: str | None = None) -> int:
        if bot:
            return self._db.execute(
                "select count(*) from people where bot = ?", (bot.lower(),)
            ).fetchone()[0]
        return self._db.execute("select count(*) from people").fetchone()[0]

    def audience(self, bots: list[str]) -> list[tuple[int, str, str]]:
        """(person, bot, language) for a broadcast: each person once, through the bot they
        wrote to last, and never someone who blocked that bot."""
        wanted = {b.lower() for b in bots}
        seen: set[int] = set()
        out = []
        for bot, user_id, language in self._db.execute(
            "select bot, user_id, language from people where blocked = 0"
            " order by last_seen desc, rowid desc"
        ):
            if bot in wanted and user_id not in seen:
                seen.add(user_id)
                out.append((user_id, bot, language))
        return out

    def export_csv(self) -> bytes:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "bot",
                "user_id",
                "name",
                "username",
                "language",
                "first_seen_utc",
                "last_seen_utc",
                "messages",
                "blocked",
            ]
        )
        for person in self.page(0, limit=1_000_000):
            writer.writerow(
                [
                    "@" + person.bot,
                    person.user_id,
                    person.first_name,
                    "@" + person.username if person.username else "",
                    person.language,
                    _utc(person.first_seen),
                    _utc(person.last_seen),
                    person.starts,
                    "yes" if person.blocked else "",
                ]
            )
        #  The byte-order mark lets Excel open the names in any alphabet correctly.
        return ("﻿" + buffer.getvalue()).encode()


def _utc(stamp: int) -> str:
    return datetime.fromtimestamp(stamp, UTC).strftime("%Y-%m-%d %H:%M")
