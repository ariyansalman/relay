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
from relay.config import BANNER, Config, ConfigError, parse_ids, parse_photo, parse_tokens
from relay.handlers import Quiet, build_router, campaign_code, store_link
from relay.stats import MemoryStats

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


# --------------------------------------------------------------------- #
#  Through the dispatcher
# --------------------------------------------------------------------- #


class Recorder(BaseSession):
    def __init__(self, refuse_photos: bool = False) -> None:
        super().__init__()
        self.sent: list[dict[str, Any]] = []
        self.refuse_photos = refuse_photos

    async def close(self) -> None:  # pragma: no cover
        return None

    async def stream_content(self, *args: Any, **kwargs: Any):  # pragma: no cover
        yield b""

    async def make_request(self, bot: Bot, method: Any, timeout: Any = None) -> Any:
        from aiogram.exceptions import TelegramBadRequest
        from aiogram.types import Chat, Message, PhotoSize

        name = type(method).__name__
        if name not in ("SendMessage", "SendPhoto"):
            raise AssertionError(f"unexpected call {name}")
        if name == "SendPhoto" and self.refuse_photos:
            raise TelegramBadRequest(method, "Bad Request: wrong file identifier")
        data = method.model_dump(exclude_none=True)
        data["method"] = name
        if name == "SendPhoto":
            data["photo"] = method.photo  # the file itself, or the id sent the time before
        self.sent.append(data)
        extra: dict[str, Any] = {"text": data.get("text")}
        if name == "SendPhoto":
            size = PhotoSize(file_id="id-from-telegram", file_unique_id="u", width=1, height=1)
            extra = {"caption": data["caption"], "photo": [size]}
        return Message(
            message_id=len(self.sent),
            date=datetime.now(),
            chat=Chat(id=data["chat_id"], type="private"),
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
                    "language_code": language,
                },
                "text": text,
            },
        }
    )


def _relay(session: Recorder | None = None, **over: Any):
    session = session or Recorder()
    bot = Bot(TOKEN_A, session=session)
    stats = MemoryStats()
    dispatcher = Dispatcher()
    dispatcher.include_router(
        build_router(_config(**over), stats, {bot.id: "Premium_Accounts_Bot"})
    )
    return dispatcher, bot, session, stats


def _words(sent: dict[str, Any]) -> str:
    return sent.get("caption") or sent["text"]


@pytest.fixture
def relay():
    return _relay()


async def test_start_gets_the_welcome_and_the_button_to_the_store(relay):
    dispatcher, bot, session, stats = relay
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
    assert (await stats.counts(["Premium_Accounts_Bot"]))[0].people == 1

    #  Writing again within the minute is counted, not answered.
    await dispatcher.feed_update(bot, _update("hello"))
    assert len(session.sent) == 1
    count = (await stats.counts(["Premium_Accounts_Bot"]))[0]
    assert (count.people, count.starts) == (1, 2)


async def test_the_banner_is_uploaded_once_then_sent_by_its_id():
    dispatcher, bot, session, _ = _relay()
    await dispatcher.feed_update(bot, _update("/start", user_id=7))
    await dispatcher.feed_update(bot, _update("/start", user_id=8))
    assert session.sent[1]["photo"] == "id-from-telegram"


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


async def test_only_the_owner_sees_stats(relay):
    dispatcher, bot, session, _ = relay
    await dispatcher.feed_update(bot, _update("/start", user_id=7))
    await dispatcher.feed_update(bot, _update("/stats", user_id=8, language="en"))
    assert "is now part of DigiVault" in _words(session.sent[-1]), "a stranger gets the welcome"

    await dispatcher.feed_update(bot, _update("/stats", user_id=OWNER, language="en"))
    report = session.sent[-1]["text"]
    assert "Relay bots" in report and "@Premium_Accounts_Bot: <b>2</b> people" in report
