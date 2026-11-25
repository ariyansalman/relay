"""The relay's rules, and its handlers driven through a real dispatcher with a recording bot."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.types import Update

from relay import texts
from relay.config import Config, ConfigError, parse_ids, parse_tokens
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
    assert config.set_profile and config.campaign and config.store_name == "Trove"


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
    assert "এখন Trove-এর অংশ" in texts.welcome("bn", bot="DigitalStoreBot", store="Trove")
    assert "is now part of Trove" in texts.welcome("de", bot="DigitalStoreBot", store="Trove")
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
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[dict[str, Any]] = []

    async def close(self) -> None:  # pragma: no cover
        return None

    async def stream_content(self, *args: Any, **kwargs: Any):  # pragma: no cover
        yield b""

    async def make_request(self, bot: Bot, method: Any, timeout: Any = None) -> Any:
        name = type(method).__name__
        if name == "SendMessage":
            data = method.model_dump(exclude_none=True)
            self.sent.append(data)
            from aiogram.types import Chat, Message

            return Message(
                message_id=len(self.sent),
                date=datetime.now(),
                chat=Chat(id=data["chat_id"], type="private"),
                text=data["text"],
            )
        raise AssertionError(f"unexpected call {name}")


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


@pytest.fixture
def relay():
    session = Recorder()
    bot = Bot(TOKEN_A, session=session)
    stats = MemoryStats()
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(_config(), stats, {bot.id: "Premium_Accounts_Bot"}))
    return dispatcher, bot, session, stats


async def test_start_gets_the_welcome_and_the_button_to_the_store(relay):
    dispatcher, bot, session, stats = relay
    await dispatcher.feed_update(bot, _update("/start"))

    sent = session.sent[0]
    assert "@Premium_Accounts_Bot এখন Trove-এর অংশ" in sent["text"]
    button = sent["reply_markup"]["inline_keyboard"][0][0]
    assert button["url"] == "https://t.me/TroveShopBot?start=c_premium-accounts-bot"
    assert button["text"] == "🛍 Trove খুলুন"
    assert (await stats.counts(["Premium_Accounts_Bot"]))[0].people == 1

    #  Writing again within the minute is counted, not answered.
    await dispatcher.feed_update(bot, _update("hello"))
    assert len(session.sent) == 1
    count = (await stats.counts(["Premium_Accounts_Bot"]))[0]
    assert (count.people, count.starts) == (1, 2)


async def test_groups_are_left_alone(relay):
    dispatcher, bot, session, _ = relay
    await dispatcher.feed_update(bot, _update("/start", chat_type="group"))
    assert session.sent == []


async def test_only_the_owner_sees_stats(relay):
    dispatcher, bot, session, _ = relay
    await dispatcher.feed_update(bot, _update("/start", user_id=7))
    await dispatcher.feed_update(bot, _update("/stats", user_id=8, language="en"))
    assert "is now part of Trove" in session.sent[-1]["text"], "a stranger gets the welcome"

    await dispatcher.feed_update(bot, _update("/stats", user_id=OWNER, language="en"))
    report = session.sent[-1]["text"]
    assert "Relay bots" in report and "@Premium_Accounts_Bot: <b>2</b> people" in report
