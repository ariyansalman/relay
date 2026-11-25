"""What a relay bot does with a message: the welcome and the button, or /stats for the owner.

Only private chats are answered. A person who keeps writing is answered once a minute at most,
so the bot cannot be made to send a stream of messages.
"""

from __future__ import annotations

import html
import re
import time

from aiogram import Bot, F, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from relay import texts
from relay.config import Config
from relay.stats import Stats

#  The same rule the store uses to make a campaign code from a name (lower-case Latin letters,
#  digits and hyphens, at most 40), so a campaign named after the bot gets this bot's code.
_NOT_CODE = re.compile(r"[^a-z0-9]+")
QUIET_SECONDS = 60


def campaign_code(bot_username: str) -> str:
    return _NOT_CODE.sub("-", bot_username.lower()).strip("-")[:40].strip("-")


def store_link(config: Config, bot_username: str) -> str:
    base = f"https://t.me/{config.main_bot}"
    code = campaign_code(bot_username)
    return f"{base}?start=c_{code}" if config.campaign and code else base


def welcome_markup(config: Config, bot_username: str, language: str | None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.button(language, store=config.store_name),
                    url=store_link(config, bot_username),
                    style="success",
                )
            ]
        ]
    )


class Quiet:
    """Who was answered in the last QUIET_SECONDS, per bot."""

    def __init__(self, seconds: int = QUIET_SECONDS) -> None:
        self.seconds = seconds
        self._last: dict[tuple[str, int], float] = {}

    def allow(self, bot: str, user_id: int, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        key = (bot, user_id)
        if now - self._last.get(key, -1e9) < self.seconds:
            return False
        self._last[key] = now
        if len(self._last) > 50_000:
            cutoff = now - self.seconds
            self._last = {k: v for k, v in self._last.items() if v >= cutoff}
        return True


def build_router(config: Config, stats: Stats, usernames: dict[int, str]) -> Router:
    """`usernames`: each relay bot's id -> its username, filled in at start."""
    router = Router(name="relay")
    quiet = Quiet()

    @router.message(F.chat.type == "private", F.text.startswith("/stats"))
    async def show_stats(message: Message, bot: Bot) -> None:
        if message.from_user is None or message.from_user.id not in config.owner_ids:
            await welcome(message, bot)
            return
        bots = sorted(usernames.values(), key=str.lower)
        counts = await stats.counts(bots)
        lines = [texts.STATS_HEAD.format(since=f"{stats.since:%d %b %Y %H:%M} UTC")]
        lines += [
            texts.STATS_ROW.format(bot=html.escape(c.bot), people=c.people, starts=c.starts)
            for c in sorted(counts, key=lambda c: -c.people)
        ]
        lines.append(
            texts.STATS_TOTAL.format(
                people=sum(c.people for c in counts), starts=sum(c.starts for c in counts)
            )
        )
        await message.answer("\n".join(lines))

    @router.message(F.chat.type == "private")
    async def welcome(message: Message, bot: Bot) -> None:
        if message.from_user is None or message.from_user.is_bot:
            return
        username = usernames.get(bot.id) or (await bot.me()).username or ""
        user_id = message.from_user.id
        await stats.record(username, user_id)
        if not quiet.allow(username, user_id):
            return
        language = message.from_user.language_code
        await message.answer(
            texts.welcome(language, bot=username, store=html.escape(config.store_name)),
            reply_markup=welcome_markup(config, username, language),
        )

    return router
