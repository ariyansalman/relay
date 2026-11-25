"""The owner's panel, in every relay bot: /admin (or /stats), for OWNER_IDS only.

  👥 People     everyone who wrote to a relay bot, newest first, ten to a page
  🤖 Bots       each bot: people, new this week, how many blocked it
  📄 Export     the whole list as a .csv file
  📢 Broadcast  one message to everyone (or to one bot's people)

A broadcast reaches each person once, through the bot they wrote to last, and never someone who
blocked that bot. The owner's message is copied as it is by the bot it was sent to; the other
bots post the same words and the same picture, video or file, uploaded once per bot (a file id
belongs to the bot that uploaded it). Telegram's pace is kept: about 20 messages a second,
waiting when Telegram asks to. Whoever blocked the bot is marked and left out next time.
"""

from __future__ import annotations

import asyncio
import html
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot, F, Router
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.filters import Command, Filter
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from relay.config import Config
from relay.handlers import welcome_markup
from relay.store import Store

log = logging.getLogger("relay")

PAGE = 10
PACE = 0.05  # seconds between two messages of a broadcast: about 20 a second
KINDS = ("text", "photo", "video", "animation", "document")


class Adm(CallbackData, prefix="adm"):
    act: str
    page: int = 0
    bot: str = ""


class Flow(StatesGroup):
    message = State()
    confirm = State()


class IsOwner(Filter):
    def __init__(self, owners: frozenset[int]) -> None:
        self.owners = owners

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return event.from_user is not None and event.from_user.id in self.owners


# --------------------------------------------------------------------- #
#  Broadcasting
# --------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Post:
    """What the owner sent, enough for any of the bots to send it again."""

    bot: str  # the bot it was sent to, lower case
    chat_id: int
    message_id: int
    kind: str
    html: str  # the text, or the caption
    file_id: str = ""
    file_name: str = ""

    @classmethod
    def of(cls, message: Message, bot: str) -> Post | None:
        kind = message.content_type
        if kind not in KINDS:
            return None
        media: Any = {
            "photo": message.photo[-1] if message.photo else None,
            "video": message.video,
            "animation": message.animation,
            "document": message.document,
        }.get(kind)
        return cls(
            bot=bot.lower(),
            chat_id=message.chat.id,
            message_id=message.message_id,
            kind=kind,
            html=message.html_text if (message.text or message.caption) else "",
            file_id=media.file_id if media else "",
            file_name=getattr(media, "file_name", None) or f"{kind}.bin",
        )


@dataclass(slots=True)
class Tally:
    total: int
    sent: int = 0
    blocked: int = 0
    failed: int = 0

    @property
    def done(self) -> int:
        return self.sent + self.blocked + self.failed


class Broadcaster:
    def __init__(self, config: Config, store: Store, bots: dict[str, Bot]) -> None:
        """`bots`: each relay bot by its username in lower case."""
        self.config = config
        self.store = store
        self.bots = bots
        self.running = False
        self._tasks: set[asyncio.Task[Any]] = set()

    def start(self, coro: Awaitable[Any]) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def run(
        self,
        post: Post,
        audience: list[tuple[int, str, str]],
        *,
        button: bool,
        progress: Callable[[Tally], Awaitable[None]] | None = None,
        pace: float = PACE,
    ) -> Tally:
        self.running = True
        tally = Tally(total=len(audience))
        media: dict[str, str | BufferedInputFile | None] = {}
        content: bytes | None = None
        try:
            for user_id, bot_name, language in audience:
                bot = self.bots.get(bot_name)
                if bot is None:
                    tally.failed += 1
                    continue
                if post.file_id and bot_name != post.bot and bot_name not in media:
                    if content is None:
                        content = await self._download(post)
                    media[bot_name] = (
                        BufferedInputFile(content, post.file_name) if content else None
                    )
                markup = welcome_markup(self.config, bot_name, language) if button else None
                outcome = await self._send(bot, bot_name, post, user_id, markup, media)
                if outcome == "sent":
                    tally.sent += 1
                elif outcome == "blocked":
                    tally.blocked += 1
                    self.store.mark_blocked(bot_name, user_id)
                else:
                    tally.failed += 1
                if progress and tally.done % 25 == 0:
                    await _quietly(progress(tally))
                await asyncio.sleep(pace)
        finally:
            self.running = False
        if progress:
            await _quietly(progress(tally))
        log.info(
            "broadcast: %d sent, %d blocked, %d failed of %d",
            tally.sent,
            tally.blocked,
            tally.failed,
            tally.total,
        )
        return tally

    async def _download(self, post: Post) -> bytes | None:
        try:
            data = await self.bots[post.bot].download(post.file_id)
            return data.read() if data else None
        except (TelegramAPIError, KeyError) as exc:
            log.warning("broadcast file not downloaded: %s", type(exc).__name__)
            return None

    async def _send(
        self,
        bot: Bot,
        bot_name: str,
        post: Post,
        user_id: int,
        markup: InlineKeyboardMarkup | None,
        media: dict[str, str | BufferedInputFile | None],
    ) -> str:
        for attempt in (1, 2):
            try:
                if bot_name == post.bot:
                    await bot.copy_message(
                        user_id, post.chat_id, post.message_id, reply_markup=markup
                    )
                    return "sent"
                if post.kind == "text":
                    await bot.send_message(
                        user_id, post.html, parse_mode="HTML", reply_markup=markup
                    )
                    return "sent"
                file = media.get(bot_name)
                if file is None:
                    return "failed"  # the file could not be fetched for this bot
                send = {
                    "photo": bot.send_photo,
                    "video": bot.send_video,
                    "animation": bot.send_animation,
                    "document": bot.send_document,
                }[post.kind]
                sent = await send(
                    user_id,
                    file,
                    caption=post.html or None,
                    parse_mode="HTML",
                    reply_markup=markup,
                )
                kept = _file_id(sent, post.kind)
                if kept:
                    media[bot_name] = kept  # the next people get it by id, not uploaded again
                return "sent"
            except TelegramRetryAfter as exc:
                if attempt == 2:
                    return "failed"
                await asyncio.sleep(exc.retry_after + 1)
            except TelegramForbiddenError:
                return "blocked"
            except TelegramAPIError as exc:
                log.info("broadcast to a person failed: %s", exc.message)
                return "failed"
        return "failed"


async def _quietly(update: Awaitable[None]) -> None:
    """A progress line that cannot be shown must not stop the broadcast."""
    try:
        await update
    except Exception as exc:  # the count goes on regardless
        log.warning("broadcast progress not shown: %s", type(exc).__name__)


def _file_id(message: Message, kind: str) -> str:
    if kind == "photo" and message.photo:
        return message.photo[-1].file_id
    media = getattr(message, kind, None)
    return getattr(media, "file_id", "") or ""


# --------------------------------------------------------------------- #
#  Screens
# --------------------------------------------------------------------- #


def _day(stamp: int) -> str:
    return datetime.fromtimestamp(stamp, UTC).strftime("%d %b %H:%M")


def _button(text: str, data: Adm) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data.pack())


BACK = [_button("⬅️ Back", Adm(act="home"))]


def home_screen(store: Store, bots: list[str]) -> tuple[str, InlineKeyboardMarkup]:
    s = store.summary()
    lines = [
        "🛠 <b>Relay admin</b>",
        "",
        f"🤖 Bots running: <b>{len(bots)}</b>",
        f"👥 People: <b>{s.people}</b> (each counted once)",
        f"🆕 New today: <b>{s.new_today}</b> · last 7 days: <b>{s.new_week}</b>",
        f"⛔ Blocked every bot they started: <b>{s.blocked}</b>",
        "",
        f"<i>Counting since {store.since:%d %b %Y}.</i>",
    ]
    if not store.lasting:
        lines.append("⚠️ <i>The list is in memory: a restart empties it.</i>")
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("👥 People", Adm(act="users")), _button("🤖 Bots", Adm(act="bots"))],
            [_button("📢 Broadcast", Adm(act="bc")), _button("📄 Export", Adm(act="export"))],
        ]
    )
    return "\n".join(lines), markup


def people_screen(store: Store, page: int) -> tuple[str, InlineKeyboardMarkup]:
    total = store.total()
    pages = max(1, -(-total // PAGE))
    page = min(max(page, 0), pages - 1)
    rows = store.page(page * PAGE, PAGE)
    lines = [f"👥 <b>People</b> · {total}, latest first", ""]
    for n, p in enumerate(rows, start=page * PAGE + 1):
        name = html.escape(p.first_name or str(p.user_id))
        who = f'<a href="tg://user?id={p.user_id}">{name}</a>'
        handle = f" @{html.escape(p.username)}" if p.username else ""
        mark = " ⛔" if p.blocked else ""
        lines.append(
            f"{n}. {who}{handle}{mark}\n    @{p.bot} · {_day(p.last_seen)} · {p.starts} msg"
        )
    if not rows:
        lines.append("<i>No one yet.</i>")
    lines.append(f"\n<i>Page {page + 1} of {pages} · ⛔ blocked the bot</i>")
    nav = []
    if page > 0:
        nav.append(_button("◀️", Adm(act="users", page=page - 1)))
    if page < pages - 1:
        nav.append(_button("▶️", Adm(act="users", page=page + 1)))
    keyboard = [nav] if nav else []
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=[*keyboard, BACK])


async def bots_screen(store: Store, bots: list[str]) -> tuple[str, InlineKeyboardMarkup]:
    counts = sorted(await store.counts(bots), key=lambda c: -c.people)
    lines = ["🤖 <b>Bots</b>", ""]
    for c in counts:
        lines.append(
            f"@{html.escape(c.bot)}\n    👥 {c.people} · 🆕 {c.new_week} this week · "
            f"⛔ {c.blocked} · {c.starts} messages"
        )
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=[BACK])


def audience_screen(store: Store, bots: list[str]) -> tuple[str, InlineKeyboardMarkup]:
    everyone = len(store.audience(bots))
    keyboard = [[_button(f"📢 Every bot · {everyone} people", Adm(act="aud"))]]
    for bot in bots:
        n = len(store.audience([bot]))
        keyboard.append([_button(f"@{bot} · {n}", Adm(act="aud", bot=bot.lower()))])
    text = (
        "📢 <b>Broadcast</b>\n\nWho should get it? Each person gets it once, from the bot they "
        "wrote to last. People who blocked a bot are left out."
    )
    return text, InlineKeyboardMarkup(inline_keyboard=[*keyboard, BACK])


def confirm_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("✅ Send with the store button", Adm(act="send", page=1))],
            [_button("✅ Send as it is", Adm(act="send", page=0))],
            [_button("❌ Cancel", Adm(act="home"))],
        ]
    )


def tally_text(tally: Tally, started: float, finished: bool) -> str:
    head = "✅ <b>Broadcast sent</b>" if finished else "📢 <b>Sending…</b>"
    minutes = (time.monotonic() - started) / 60
    return (
        f"{head}\n\n"
        f"Done: <b>{tally.done}</b> of {tally.total}\n"
        f"✅ Delivered: {tally.sent}\n"
        f"⛔ Blocked the bot: {tally.blocked}\n"
        f"⚠️ Failed: {tally.failed}\n\n"
        f"<i>{minutes:.1f} min</i>"
    )


# --------------------------------------------------------------------- #
#  The router
# --------------------------------------------------------------------- #


def build_admin_router(
    config: Config, store: Store, usernames: dict[int, str], broadcaster: Broadcaster
) -> Router:
    router = Router(name="relay-admin")
    owner = IsOwner(config.owner_ids)
    router.message.filter(F.chat.type == "private", owner)
    router.callback_query.filter(owner)

    def bots() -> list[str]:
        return sorted(usernames.values(), key=str.lower)

    def bot_name(bot: Bot) -> str:
        return usernames.get(bot.id, "").lower()

    async def show(target: Message | CallbackQuery, screen: tuple[str, Any]) -> None:
        text, markup = screen
        if isinstance(target, CallbackQuery):
            await target.answer()
            if isinstance(target.message, Message):
                try:
                    await target.message.edit_text(text, reply_markup=markup)
                    return
                except TelegramAPIError as exc:
                    if "not modified" in str(exc):
                        return  # the same screen tapped again
                    #  Too old to edit: send it afresh.
                await target.message.answer(text, reply_markup=markup)
            return
        await target.answer(text, reply_markup=markup)

    @router.message(Command("admin", "stats"))
    async def admin(message: Message, state: FSMContext) -> None:
        await state.clear()
        await show(message, home_screen(store, bots()))

    @router.message(Command("cancel"))
    async def cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await show(message, home_screen(store, bots()))

    @router.callback_query(Adm.filter(F.act == "home"))
    async def home(query: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await show(query, home_screen(store, bots()))

    @router.callback_query(Adm.filter(F.act == "users"))
    async def people(query: CallbackQuery, callback_data: Adm) -> None:
        await show(query, people_screen(store, callback_data.page))

    @router.callback_query(Adm.filter(F.act == "bots"))
    async def bot_list(query: CallbackQuery) -> None:
        await show(query, await bots_screen(store, bots()))

    @router.callback_query(Adm.filter(F.act == "export"))
    async def export(query: CallbackQuery) -> None:
        await query.answer()
        name = f"relay-people-{datetime.now(UTC):%Y%m%d-%H%M}.csv"
        if isinstance(query.message, Message):
            await query.message.answer_document(
                BufferedInputFile(store.export_csv(), name),
                caption=f"👥 {store.total()} rows: one per person and bot.",
            )

    @router.callback_query(Adm.filter(F.act == "bc"))
    async def broadcast(query: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        if broadcaster.running:
            await query.answer("A broadcast is still being sent.", show_alert=True)
            return
        await show(query, audience_screen(store, bots()))

    @router.callback_query(Adm.filter(F.act == "aud"))
    async def audience(query: CallbackQuery, callback_data: Adm, state: FSMContext) -> None:
        await state.set_state(Flow.message)
        await state.update_data(audience=callback_data.bot)
        who = f"@{callback_data.bot}'s people" if callback_data.bot else "everyone"
        await show(
            query,
            (
                f"📢 <b>Broadcast to {html.escape(who)}</b>\n\n"
                "Send the message now: text, a photo, a video, a GIF or a file, with a caption "
                "if you like. Bold, links and premium emoji are kept.\n\n/cancel to stop.",
                InlineKeyboardMarkup(inline_keyboard=[[_button("❌ Cancel", Adm(act="home"))]]),
            ),
        )

    @router.message(Flow.message)
    async def compose(message: Message, bot: Bot, state: FSMContext) -> None:
        post = Post.of(message, bot_name(bot))
        if post is None:
            await message.answer("Send text, a photo, a video, a GIF or a file. /cancel to stop.")
            return
        data = await state.get_data()
        chosen = [data["audience"]] if data.get("audience") else bots()
        count = len(store.audience(chosen))
        await state.set_state(Flow.confirm)
        await state.update_data(post=asdict(post))
        where = f"@{data['audience']}" if data.get("audience") else f"{len(chosen)} bots"
        await message.answer(
            f"👆 That is how it will look.\n\nIt goes to <b>{count}</b> people through {where}.\n"
            "The store button opens the store with each bot's own campaign link.",
            reply_markup=confirm_markup(),
        )

    @router.callback_query(Flow.confirm, Adm.filter(F.act == "send"))
    async def send(query: CallbackQuery, callback_data: Adm, state: FSMContext, bot: Bot) -> None:
        panel_bot = bot
        data = await state.get_data()
        await state.clear()
        if broadcaster.running:
            await query.answer("A broadcast is still being sent.", show_alert=True)
            return
        post = Post(**data["post"])
        chosen = [data["audience"]] if data.get("audience") else bots()
        audience = store.audience(chosen)
        await query.answer("Sending…")
        if not isinstance(query.message, Message):
            return
        status = await query.message.answer(
            tally_text(Tally(len(audience)), time.monotonic(), False)
        )
        started = time.monotonic()

        async def progress(tally: Tally) -> None:
            finished = tally.done == tally.total and not broadcaster.running
            try:
                await panel_bot.edit_message_text(
                    tally_text(tally, started, finished),
                    chat_id=status.chat.id,
                    message_id=status.message_id,
                )
            except TelegramAPIError:
                pass  # the same numbers twice, or the message is gone

        broadcaster.start(
            broadcaster.run(post, audience, button=bool(callback_data.page), progress=progress)
        )

    @router.callback_query(Adm.filter(F.act == "send"))
    async def stale_send(query: CallbackQuery) -> None:
        await query.answer("This broadcast was already sent or cancelled.", show_alert=True)

    return router
