"""Everything the relay reads from its environment (Railway -> the service -> Variables).

  BOT_TOKENS     the bots' tokens from BotFather, separated by commas, spaces or new lines
  MAIN_BOT       the store's bot, the one every relay bot points to (TroveShopBot)
  OWNER_IDS      Telegram user ids allowed to open /admin, separated by commas
  STORE_NAME     the store's name as the welcome message says it (DigiVault)
  DATA_DIR       optional, /data by default: where the people list (SQLite) is kept; on Railway a
                 volume mounted there keeps it across deploys
  SET_PROFILE    optional, "true" by default: write each bot's description and about text
  CAMPAIGN       optional, "true" by default: link with the bot's own campaign code (c_<slug>)
  WELCOME_PHOTO  optional: the banner above the welcome. Empty: the store's banner in
                 relay/assets/banner.jpg. A link (https://...) to another picture. "off": text only.

Tokens are never logged: a bot is named by its username once it has answered getMe.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_SPLIT = re.compile(r"[\s,;]+")
_TOKEN = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")
_USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
BANNER = Path(__file__).parent / "assets" / "banner.jpg"


class ConfigError(ValueError):
    """The environment cannot start the relay; the message says what to set."""


def _flag(raw: str | None, default: bool) -> bool:
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def parse_tokens(raw: str | None) -> list[str]:
    """Every distinct token that looks like one, in the order given."""
    seen: list[str] = []
    for piece in _SPLIT.split(raw or ""):
        piece = piece.strip()
        if piece and _TOKEN.match(piece) and piece not in seen:
            seen.append(piece)
    return seen


def parse_photo(raw: str | None) -> str | None:
    """The banner: the bundled file, another picture's link or file id, or None for none."""
    value = (raw or "").strip()
    if not value:
        return str(BANNER)
    if value.lower() in ("off", "false", "no", "none", "0"):
        return None
    return value


def parse_ids(raw: str | None) -> frozenset[int]:
    return frozenset(int(p) for p in _SPLIT.split(raw or "") if p.strip().isdigit())


@dataclass(frozen=True, slots=True)
class Config:
    tokens: tuple[str, ...]
    main_bot: str
    owner_ids: frozenset[int]
    store_name: str
    set_profile: bool
    campaign: bool
    welcome_photo: str | None = str(BANNER)
    data_dir: str = "/data"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Config:
        env = dict(os.environ if env is None else env)
        tokens = parse_tokens(env.get("BOT_TOKENS"))
        if not tokens:
            raise ConfigError("Set BOT_TOKENS: the bots' tokens from BotFather, comma separated.")
        main_bot = (env.get("MAIN_BOT") or "").strip().lstrip("@")
        if not _USERNAME.match(main_bot):
            raise ConfigError("Set MAIN_BOT: the store bot's username, like TroveShopBot.")
        return cls(
            tokens=tuple(tokens),
            main_bot=main_bot,
            owner_ids=parse_ids(env.get("OWNER_IDS")),
            store_name=(env.get("STORE_NAME") or "DigiVault").strip()[:40] or "DigiVault",
            set_profile=_flag(env.get("SET_PROFILE"), True),
            campaign=_flag(env.get("CAMPAIGN"), True),
            welcome_photo=parse_photo(env.get("WELCOME_PHOTO")),
            data_dir=(env.get("DATA_DIR") or "/data").strip() or "/data",
        )
