"""What a relay bot does with a message: the welcome and the button, or /stats for the owner.

The welcome is the banner with the words as its caption. The banner is uploaded once per bot
(Telegram's file ids belong to the bot that uploaded them) and sent by id after that. When a
picture cannot be sent, the same words go out as text, so nobody is left without the button.

Only private chats are answered. /start is answered every time (a double tap within a few
seconds gets one reply); anything else a person keeps writing is answered once a minute at
most, so the bot cannot be made to send a stream of messages.
"""

from __future__ import annotations

import html
import logging
import re
import time
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from relay import texts
from relay.config import Config
from relay.stats import Stats

#  The same rule the store uses to make a campaign code from a name (lower-case Latin letters,
#  digits and hyphens, at most 40), so a campaign named after the bot gets this bot's code.
_NOT_CODE = re.compile(r"[^a-z0-9]+")
QUIET_SECONDS = 60
#  /start is what someone presses when they want the button again: answer it, bar a double tap.
START_QUIET_SECONDS = 3
log = logging.getLogger("relay")


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
                    style="primary",
                )
            ]
        ]
    )


class Quiet:
    """Who was answered in the last QUIET_SECONDS, per bot."""

    def __init__(self, seconds: int = QUIET_SECONDS) -> None:
        self.seconds = seconds
        self._last: dict[tuple[str, int], float] = {}

    def allow(
        self, bot: str, user_id: int, now: float | None = None, seconds: int | None = None
    ) -> bool:
        now = time.monotonic() if now is None else now
        key = (bot, user_id)
        if now - self._last.get(key, -1e9) < (self.seconds if seconds is None else seconds):
            return False
        self._last[key] = now
        if len(self._last) > 50_000:
            cutoff = now - self.seconds
            self._last = {k: v for k, v in self._last.items() if v >= cutoff}
        return True


class Banner:
    """The picture above the welcome, and each bot's file id for it once uploaded."""

    def __init__(self, source: str | None) -> None:
        self.source = source
        self._ids: dict[int, str] = {}
        self._broken: set[int] = set()

    def photo(self, bot_id: int) -> str | FSInputFile | None:
        if self.source is None or bot_id in self._broken:
            return None
        if bot_id in self._ids:
            return self._ids[bot_id]
        if Path(self.source).is_file():
            return FSInputFile(self.source, filename="banner.jpg")
        return self.source

    def sent(self, bot_id: int, message: Message) -> None:
        if message.photo:
            self._ids[bot_id] = message.photo[-1].file_id

    def failed(self, bot_id: int) -> None:
        """Telegram refused the picture: this bot sends text until the next start."""
        self._broken.add(bot_id)


def build_router(config: Config, stats: Stats, usernames: dict[int, str]) -> Router:
    """`usernames`: each relay bot's id -> its username, filled in at start."""
    router = Router(name="relay")
    quiet = Quiet()
    banner = Banner(config.welcome_photo)

    async def count(username: str, user_id: int) -> None:
        try:
            await stats.record(username, user_id)
        except Exception as exc:  # a lost count must never stop a reply
            log.warning("start not counted: %s", type(exc).__name__)

    async def send_welcome(message: Message, bot: Bot, username: str) -> None:
        language = message.from_user.language_code if message.from_user else None
        words = texts.welcome(language, bot=username, store=html.escape(config.store_name))
        markup = welcome_markup(config, username, language)
        photo = banner.photo(bot.id)
        if photo is not None:
            try:
                sent = await message.answer_photo(photo, caption=words, reply_markup=markup)
                banner.sent(bot.id, sent)
                return
            except TelegramBadRequest as exc:
                log.warning("banner not sent by @%s: %s", username, exc.message)
                banner.failed(bot.id)
        await message.answer(words, reply_markup=markup)

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
        is_start = (message.text or "").startswith("/start")
        wait = START_QUIET_SECONDS if is_start else None
        if quiet.allow(username, user_id, seconds=wait):
            #  The reply goes first; counting it never makes anyone wait.
            await send_welcome(message, bot, username)
        await count(username, user_id)

    return router
