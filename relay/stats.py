"""How many people started each relay bot, and how many times.

In memory by default, so the counts begin again after a restart. With REDIS_URL set they are
kept in Redis instead: a set of user ids and a counter per bot, under the `relay:` prefix.

These counts are only the top of the funnel. Who went on to the store, and who bought, is in
the store's own Statistics -> Campaign links, under each bot's campaign.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class Count:
    bot: str
    people: int
    starts: int


class Stats(Protocol):
    since: datetime

    async def record(self, bot: str, user_id: int) -> None: ...

    async def counts(self, bots: list[str]) -> list[Count]: ...


class MemoryStats:
    def __init__(self) -> None:
        self.since = datetime.now(UTC)
        self._people: dict[str, set[int]] = {}
        self._starts: dict[str, int] = {}

    async def record(self, bot: str, user_id: int) -> None:
        self._people.setdefault(bot, set()).add(user_id)
        self._starts[bot] = self._starts.get(bot, 0) + 1

    async def counts(self, bots: list[str]) -> list[Count]:
        return [
            Count(bot, len(self._people.get(bot, set())), self._starts.get(bot, 0)) for bot in bots
        ]


class RedisStats:
    """Counts kept in Redis; `since` is when the first count was ever written."""

    def __init__(self, redis: Any) -> None:
        self._redis = redis
        self.since = datetime.now(UTC)

    async def load(self) -> None:
        raw = await self._redis.get("relay:since")
        if raw:
            self.since = datetime.fromisoformat(raw.decode() if isinstance(raw, bytes) else raw)
        else:
            await self._redis.set("relay:since", self.since.isoformat(), nx=True)

    async def record(self, bot: str, user_id: int) -> None:
        bot = bot.lower()
        await self._redis.sadd(f"relay:{bot}:people", user_id)
        await self._redis.incr(f"relay:{bot}:starts")

    async def counts(self, bots: list[str]) -> list[Count]:
        out = []
        for bot in bots:
            key = bot.lower()
            people = await self._redis.scard(f"relay:{key}:people")
            starts = await self._redis.get(f"relay:{key}:starts")
            out.append(Count(bot, int(people or 0), int(starts or 0)))
        return out
