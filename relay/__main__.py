"""Start every relay bot: python -m relay

Each token is checked with getMe first. One that Telegram refuses (revoked, mistyped) is
reported by its position in BOT_TOKENS and skipped, so one bad token never stops the others.
A webhook left from where a bot ran before is removed, so polling gets its messages. Then,
with SET_PROFILE on, each bot's description and about text are written (only when they
differ), and all of them are polled by one dispatcher. No webhook, so the service needs no
public address.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError, TelegramUnauthorizedError

from relay import texts
from relay.config import Config, ConfigError
from relay.handlers import build_router
from relay.stats import MemoryStats, RedisStats, Stats

log = logging.getLogger("relay")


async def _profile(bot: Bot, config: Config) -> None:
    """Write the bot's description and about text, when they say something else."""
    description = texts.DESCRIPTION.format(store=config.store_name)
    short = texts.SHORT_DESCRIPTION.format(store=config.store_name)
    try:
        if (await bot.get_my_description()).description != description:
            await bot.set_my_description(description)
        if (await bot.get_my_short_description()).short_description != short:
            await bot.set_my_short_description(short)
    except TelegramAPIError as exc:
        #  Telegram limits how often these may be changed; the next start tries again.
        log.warning("profile not written for a bot: %s", type(exc).__name__)


async def _stats(config: Config) -> Stats:
    if not config.redis_url:
        return MemoryStats()
    from redis.asyncio import Redis

    stats = RedisStats(Redis.from_url(config.redis_url, socket_timeout=2, socket_connect_timeout=2))
    await stats.load()
    return stats


async def start(config: Config) -> None:
    bots: list[Bot] = []
    usernames: dict[int, str] = {}
    for position, token in enumerate(config.tokens, start=1):
        bot = Bot(token, default=DefaultBotProperties(parse_mode="HTML"))
        try:
            me = await bot.get_me()
        except TelegramUnauthorizedError:
            log.error(
                "token %d of %d was refused by Telegram; skipped", position, len(config.tokens)
            )
            await bot.session.close()
            continue
        if me.username and me.username.lower() == config.main_bot.lower():
            log.error("token %d is the store bot itself; skipped", position)
            await bot.session.close()
            continue
        usernames[me.id] = me.username or str(me.id)
        bots.append(bot)
        #  A bot that ran somewhere else may still have a webhook set; polling cannot get its
        #  messages until it is removed. Messages already waiting are kept and answered.
        try:
            await bot.delete_webhook(drop_pending_updates=False)
        except TelegramAPIError as exc:
            log.warning("webhook not removed for @%s: %s", me.username, type(exc).__name__)
        if config.set_profile:
            await _profile(bot, config)
    if not bots:
        raise ConfigError("No token in BOT_TOKENS was accepted by Telegram.")

    log.info(
        "relaying %d bots to @%s: %s",
        len(bots),
        config.main_bot,
        ", ".join(f"@{name}" for name in sorted(usernames.values(), key=str.lower)),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(config, await _stats(config), usernames))
    await dispatcher.start_polling(*bots, allowed_updates=["message"])


def main() -> None:
    #  stdout: Railway marks everything on stderr as an error, normal lines included.
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout
    )
    #  aiogram logs every update at INFO; the relay's own lines are what matter.
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    try:
        config = Config.from_env()
    except ConfigError as exc:
        log.error("%s", exc)
        sys.exit(2)
    asyncio.run(start(config))


if __name__ == "__main__":
    main()
