"""The relay's rules, and its handlers driven through a real dispatcher with a recording bot."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.types import Update

from relay import texts
from relay.admin import Broadcaster, Post, build_admin_router
from relay.config import BANNER, Config, ConfigError, parse_ids, parse_photo, parse_tokens
from relay.handlers import Quiet, build_router, campaign_code, store_link
from relay.store import Store

TOKEN_A = "1111111111:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
TOKEN_B = "2222222222:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
OWNER = 42


def _config(**over: Any) -> Config:
    env = {
        "BOT_TOKENS": f"{TOKEN_A}, {TOKEN_B}",
        "MAIN_BOT": "@TroveShopBot",
        "OWNER_IDS": str(OWNER),
    }
    env.update(over)
    return Config.from_env(env)


# --------------------------------------------------------------------- #
#  Configuration
# --------------------------------------------------------------------- #


def test_tokens_are_read_from_commas_spaces_and_lines_once_each():
    raw = f"{TOKEN_A},\n{TOKEN_B}  {TOKEN_A}; not-a-token"
    assert parse_tokens(raw) == [TOKEN_A, TOKEN_B]
    assert parse_ids("42, 7 x") == frozenset({42, 7})


def test_the_config_says_what_is_missing():
    with pytest.raises(ConfigError, match="BOT_TOKENS"):
        Config.from_env({"MAIN_BOT": "TroveShopBot"})
    with pytest.raises(ConfigError, match="MAIN_BOT"):
        Config.from_env({"BOT_TOKENS": TOKEN_A})
    config = _config()
    assert config.main_bot == "TroveShopBot" and config.tokens == (TOKEN_A, TOKEN_B)
    assert config.set_profile and config.campaign and config.store_name == "DigiVault"
    assert config.welcome_photo == str(BANNER) and BANNER.is_file()


def test_the_banner_can_be_another_picture_or_none():
    assert parse_photo(" https://example.com/b.jpg ") == "https://example.com/b.jpg"
    assert parse_photo("off") is None and parse_photo("") == str(BANNER)


# --------------------------------------------------------------------- #
#  The link and the words
# --------------------------------------------------------------------- #


def test_the_campaign_code_is_the_one_the_store_makes_from_the_bots_name():
    #  The store's slug(): lower case, anything else a hyphen, at most 40.
    assert campaign_code("Premium_Accounts_Bot") == "premium-accounts-bot"
    assert campaign_code("DigitalStoreBot") == "digitalstorebot"
    assert store_link(_config(), "Premium_Accounts_Bot") == (
        "https://t.me/TroveShopBot?start=c_premium-accounts-bot"
    )
    assert store_link(_config(CAMPAIGN="false"), "X_bot") == "https://t.me/TroveShopBot"


def test_the_welcome_is_in_the_readers_language_or_english():
    assert texts.language_of("pt-BR") == "pt"
    assert texts.language_of("xx") == "en" and texts.language_of(None) == "en"
    assert "এখন DigiVault-এর অংশ" in texts.welcome("bn", bot="DigitalStoreBot", store="DigiVault")
    assert "is now part of DigiVault" in texts.welcome(
        "de", bot="DigitalStoreBot", store="DigiVault"
    )
    #  Every language says where the button goes and has a button.
    assert set(texts.WELCOME) == set(texts.BUTTON)
    for language in texts.WELCOME:
        assert "{bot}" in texts.WELCOME[language] and "{store}" in texts.WELCOME[language]


def test_someone_writing_again_and_again_is_answered_once_a_minute():
    quiet = Quiet(seconds=60)
    assert quiet.allow("bot", 1, now=0)
    assert not quiet.allow("bot", 1, now=30)
    assert quiet.allow("bot", 2, now=30), "another person is answered"
    assert quiet.allow("bot", 1, now=61)
    #  /start: only a double tap is held back.
    assert not quiet.allow("bot", 1, now=62, seconds=3)
    assert quiet.allow("bot", 1, now=65, seconds=3)


# --------------------------------------------------------------------- #
#  Through the dispatcher
# --------------------------------------------------------------------- #


class Recorder(BaseSession):
    """Answers Telegram calls the way Telegram would, and keeps what was sent."""

    def __init__(self, refuse_photos: bool = False, blocked: frozenset[int] = frozenset()) -> None:
        super().__init__()
        self.sent: list[dict[str, Any]] = []
        self.refuse_photos = refuse_photos
        self.blocked = blocked

    async def close(self) -> None:  # pragma: no cover
        return None

    async def stream_content(self, *args: Any, **kwargs: Any):  # pragma: no cover
        yield b""

    async def make_request(self, bot: Bot, method: Any, timeout: Any = None) -> Any:
        from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
        from aiogram.types import Chat, Document, Message, MessageId, PhotoSize

        name = type(method).__name__
        if name == "AnswerCallbackQuery":
            return True
        if name == "SendPhoto" and self.refuse_photos:
            raise TelegramBadRequest(method, "Bad Request: wrong file identifier")
        data = method.model_dump(exclude_none=True)
        data["method"] = name
        if getattr(method, "chat_id", None) in self.blocked:
            raise TelegramForbiddenError(method, "Forbidden: bot was blocked by the user")
        for field in ("photo", "document"):
            if hasattr(method, field):
                data[field] = getattr(method, field)  # the file itself, or an id
        self.sent.append(data)
        if name == "CopyMessage":
            return MessageId(message_id=len(self.sent))
        extra: dict[str, Any] = {"text": data.get("text")}
        if name == "SendPhoto":
            size = PhotoSize(file_id=f"id-{bot.id}", file_unique_id="u", width=1, height=1)
            extra = {"caption": data.get("caption"), "photo": [size]}
        if name == "SendDocument":
            extra = {"document": Document(file_id=f"doc-{bot.id}", file_unique_id="d")}
        return Message(
            message_id=len(self.sent),
            date=datetime.now(),
            chat=Chat(id=data.get("chat_id", 0), type="private"),
            **extra,
        )


def _update(text: str, *, user_id: int = 7, language: str = "bn", chat_type: str = "private"):
    return Update.model_validate(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 0,
                "chat": {"id": user_id, "type": chat_type},
                "from": {
                    "id": user_id,
                    "is_bot": False,
                    "first_name": "Buyer",
                    "username": f"buyer{user_id}",
                    "language_code": language,
                },
                "text": text,
            },
        }
    )


def _tap(data: str, *, user_id: int = OWNER):
    return Update.model_validate(
        {
            "update_id": 2,
            "callback_query": {
                "id": "q",
                "chat_instance": "c",
                "from": {"id": user_id, "is_bot": False, "first_name": "Owner"},
                "data": data,
                "message": {
                    "message_id": 99,
                    "date": 0,
                    "chat": {"id": user_id, "type": "private"},
                    "text": "panel",
                },
            },
        }
    )


def _relay(session: Recorder | None = None, **over: Any):
    session = session or Recorder()
    bot = Bot(TOKEN_A, session=session)
    store = Store(None)
    config = _config(**over)
    usernames = {bot.id: "Premium_Accounts_Bot"}
    broadcaster = Broadcaster(config, store, {"premium_accounts_bot": bot})
    dispatcher = Dispatcher()
    dispatcher.include_router(build_admin_router(config, store, usernames, broadcaster))
    dispatcher.include_router(build_router(config, store, usernames))
    return dispatcher, bot, session, store


def _words(sent: dict[str, Any]) -> str:
    return sent.get("caption") or sent["text"]


@pytest.fixture
def relay():
    return _relay()


async def test_start_gets_the_welcome_and_the_button_to_the_store(relay):
    dispatcher, bot, session, store = relay
    await dispatcher.feed_update(bot, _update("/start"))

    sent = session.sent[0]
    assert sent["method"] == "SendPhoto" and Path(sent["photo"].path) == BANNER
    assert (
        "স্বাগতম" in sent["caption"]
        and "@Premium_Accounts_Bot এখন DigiVault-এর অংশ" in sent["caption"]
    )
    button = sent["reply_markup"]["inline_keyboard"][0][0]
    assert button["url"] == "https://t.me/TroveShopBot?start=c_premium-accounts-bot"
    assert button["text"] == "🛍 DigiVault খুলুন" and button["style"] == "primary"
    assert (await store.counts(["Premium_Accounts_Bot"]))[0].people == 1

    #  Writing again within the minute is counted, not answered.
    await dispatcher.feed_update(bot, _update("hello"))
    assert len(session.sent) == 1
    count = (await store.counts(["Premium_Accounts_Bot"]))[0]
    assert (count.people, count.starts) == (1, 2)
    person = store.page(0)[0]
    assert (person.first_name, person.username, person.language) == ("Buyer", "buyer7", "bn")


async def test_the_banner_is_uploaded_once_then_sent_by_its_id():
    dispatcher, bot, session, _ = _relay()
    await dispatcher.feed_update(bot, _update("/start", user_id=7))
    await dispatcher.feed_update(bot, _update("/start", user_id=8))
    assert session.sent[1]["photo"] == f"id-{bot.id}"


async def test_without_a_banner_or_when_it_is_refused_the_words_go_as_text():
    dispatcher, bot, session, _ = _relay(WELCOME_PHOTO="off")
    await dispatcher.feed_update(bot, _update("/start"))
    assert session.sent[0]["method"] == "SendMessage"

    dispatcher, bot, session, _ = _relay(Recorder(refuse_photos=True))
    await dispatcher.feed_update(bot, _update("/start", user_id=7))
    await dispatcher.feed_update(bot, _update("/start", user_id=8))
    assert [s["method"] for s in session.sent] == ["SendMessage", "SendMessage"]
    assert "@Premium_Accounts_Bot" in session.sent[0]["text"]


async def test_groups_are_left_alone(relay):
    dispatcher, bot, session, _ = relay
    await dispatcher.feed_update(bot, _update("/start", chat_type="group"))
    assert session.sent == []


# --------------------------------------------------------------------- #
#  The owner's panel
# --------------------------------------------------------------------- #


async def test_only_the_owner_opens_the_panel(relay):
    dispatcher, bot, session, _ = relay
    await dispatcher.feed_update(bot, _update("/start", user_id=7))
    await dispatcher.feed_update(bot, _update("/admin", user_id=8, language="en"))
    assert "is now part of DigiVault" in _words(session.sent[-1]), "a stranger gets the welcome"
    await dispatcher.feed_update(bot, _tap("adm:users:0:", user_id=8))
    assert "People" not in str(session.sent[-1]), "a stranger's tap does nothing"

    await dispatcher.feed_update(bot, _update("/admin", user_id=OWNER, language="en"))
    panel = session.sent[-1]["text"]
    assert "Relay admin" in panel and "People: <b>2</b>" in panel
    assert "in memory" in panel, "the panel says when the list will not outlive a restart"


async def test_the_people_list_pages_and_exports(relay):
    dispatcher, bot, session, _ = relay
    for user_id in range(100, 113):
        await dispatcher.feed_update(bot, _update("/start", user_id=user_id))
    await dispatcher.feed_update(bot, _tap("adm:users:0:"))
    first = session.sent[-1]
    assert first["method"] == "EditMessageText"
    assert "People</b> · 13" in first["text"] and "Page 1 of 2" in first["text"]
    assert "@buyer112" in first["text"], "the latest first"
    await dispatcher.feed_update(bot, _tap("adm:users:1:"))
    assert "Page 2 of 2" in session.sent[-1]["text"]

    await dispatcher.feed_update(bot, _tap("adm:export:0:"))
    document = session.sent[-1]
    assert document["method"] == "SendDocument"
    rows = document["document"].data.decode("utf-8-sig").splitlines()
    assert len(rows) == 14 and rows[0].startswith("bot,user_id,name")


async def test_a_broadcast_goes_once_to_each_person_and_marks_who_blocked(relay):
    dispatcher, bot, session, store = relay
    for user_id in (7, 8, 9):
        await dispatcher.feed_update(bot, _update("/start", user_id=user_id))
    session.blocked = frozenset({9})
    session.sent.clear()

    await dispatcher.feed_update(bot, _tap("adm:bc:0:"))
    assert "3 people" in str(session.sent[-1]["reply_markup"])
    await dispatcher.feed_update(bot, _tap("adm:aud:0:"))
    await dispatcher.feed_update(bot, _update("<b>Sale</b> today", user_id=OWNER, language="en"))
    assert "goes to <b>3</b> people" in session.sent[-1]["text"]

    await dispatcher.feed_update(bot, _tap("adm:send:1:"))
    import asyncio

    for _ in range(300):  # the broadcast runs beside the panel
        await asyncio.sleep(0.01)
        if any("Broadcast sent" in str(s.get("text")) for s in session.sent):
            break
    else:
        raise AssertionError([s["method"] for s in session.sent])
    copies = [s for s in session.sent if s["method"] == "CopyMessage"]
    assert sorted(c["chat_id"] for c in copies) == [7, 8]
    assert copies[0]["reply_markup"]["inline_keyboard"][0][0]["url"].endswith(
        "c_premium-accounts-bot"
    )
    done = [s for s in session.sent if "Broadcast sent" in str(s.get("text"))][-1]["text"]
    assert "Delivered: 2" in done and "Blocked the bot: 1" in done
    assert [uid for uid, _, _ in store.audience(["Premium_Accounts_Bot"])] == [8, 7]

    #  The confirm button of a finished broadcast does nothing again.
    before = len(session.sent)
    await dispatcher.feed_update(bot, _tap("adm:send:1:"))
    assert len(session.sent) == before


async def test_other_bots_post_the_same_picture_uploaded_once_each():
    from aiogram.types import BufferedInputFile

    session_a, session_b = Recorder(), Recorder()
    bot_a, bot_b = Bot(TOKEN_A, session=session_a), Bot(TOKEN_B, session=session_b)
    store = Store(None)
    await store.record("bot_a", 1, now=10)
    await store.record("bot_b", 2, now=20)
    await store.record("bot_b", 3, now=30)
    await store.record("bot_b", 1, now=5)  # person 1 wrote to bot_a last: bot_a sends
    broadcaster = Broadcaster(_config(), store, {"bot_a": bot_a, "bot_b": bot_b})

    async def fetched(post: Post) -> bytes:
        return b"jpeg"

    broadcaster._download = fetched  # type: ignore[method-assign]
    post = Post(
        bot="bot_a",
        chat_id=OWNER,
        message_id=5,
        kind="photo",
        html="<b>New</b>",
        file_id="a-file",
        file_name="p.jpg",
    )
    tally = await broadcaster.run(post, store.audience(["bot_a", "bot_b"]), button=False, pace=0)
    assert (tally.total, tally.sent) == (3, 3)
    assert [s["method"] for s in session_a.sent] == ["CopyMessage"]
    first, second = session_b.sent
    assert isinstance(first["photo"], BufferedInputFile) and first["caption"] == "<b>New</b>"
    assert second["photo"] == f"id-{bot_b.id}", "uploaded once, then sent by its id"


def test_the_list_outlives_a_restart(tmp_path):
    import asyncio

    path = tmp_path / "data" / "relay.sqlite3"
    store = Store(path)
    asyncio.run(store.record("Bot_X", 5, first_name="Ann", now=100))
    store.close()
    again = Store(path)
    assert again.lasting and again.total() == 1 and again.page(0)[0].first_name == "Ann"
    assert again.summary(now=200).new_today == 1
