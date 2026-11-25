# Relay

Telegram bots that send whoever starts them to the store bot.

Each bot answers a `/start` (or any message, at most once a minute per person) with the store's
banner and a short welcome under it in the reader's language — 15 languages — and one button
that opens the store bot. The welcome says plainly that the bot is now part of the store; a relay
bot never poses as anything else. Each bot links with its own campaign code, so the store's **Statistics → Campaign links**
shows how many people each bot brought and how many of them bought.

Only private chats are answered. Bots cannot message anyone first, so a relay bot speaks only to
people who opened it.

## Settings (Railway → the service → Variables)

| Variable | Required | What it is |
|---|---|---|
| `BOT_TOKENS` | yes | The bots' tokens from BotFather, separated by commas |
| `MAIN_BOT` | yes | The store bot's username, without @ (`TroveShopBot`) |
| `OWNER_IDS` | for `/stats` | Telegram user ids allowed to send `/stats`, comma separated |
| `STORE_NAME` | no | The store's name in the welcome (`DigiVault`) |
| `WELCOME_PHOTO` | no | Empty: the banner in `relay/assets/banner.jpg`. A picture's link to use another. `off`: text only |
| `REDIS_URL` | no | Keeps the start counts across restarts; without it they reset on each deploy |
| `SET_PROFILE` | no | `true` (default): write each bot's description and about text at start |
| `CAMPAIGN` | no | `true` (default): link with `?start=c_<bot username>` |

A token Telegram refuses is reported by its position and skipped; the others keep running. The
store bot's own token is refused, so it cannot be relayed to itself by mistake.

## Counting in the store

The link is `https://t.me/<MAIN_BOT>?start=c_<code>`, where the code is the bot's username in
lower case with anything that is not a letter or digit turned into `-`
(`Premium_Accounts_Bot` → `premium-accounts-bot`). That is the code the store makes for a
campaign named after the bot, so for each relay bot: store admin → Statistics → Campaign links →
New, and name it exactly as the bot's username. Without a matching campaign the link still
opens the store; the person is simply not counted to that bot.

`/stats`, sent by an owner to any relay bot, lists every bot with how many people started it.

## Running

```
python -m relay
```

Polling, not webhooks: the service needs no public address. The Docker image runs exactly the
versions in `requirements.lock` (`uv pip compile pyproject.toml -o requirements.lock` after
changing a dependency). Tests: `pytest`.

---

## বাংলায়: চালু করার ধাপ

1. Railway → **New Project** (দোকানের প্রজেক্ট থেকে আলাদা) → **GitHub Repo → ariyansalman/relay**। চাইলে একই প্রজেক্টে **New → Database → Redis** যোগ করে `REDIS_URL` দিন।
2. সেই service → **Variables**:
   - `BOT_TOKENS` = সব বটের token, কমা দিয়ে (BotFather থেকে)
   - `MAIN_BOT` = `TroveShopBot`
   - `OWNER_IDS` = আপনার Telegram ID (শুধু আপনি `/stats` দেখতে পারবেন)
3. Save করলে service নিজে চালু হবে। Deploy log-এ লেখা আসবে "relaying N bots to @TroveShopBot"।
4. প্রতিটা বট যেন Trove-এর হিসাবে আসে: Trove Admin → Statistics → Campaign links → New, নাম দিন
   বটের username হুবহু (যেমন `Premium_Accounts_Bot`)।
5. নতুন বট যোগ করতে শুধু `BOT_TOKENS`-এ আরেকটা token কমা দিয়ে জুড়ে দিন।
6. ব্যানার বদলাতে `relay/assets/banner.jpg` বদলে দিন, অথবা `WELCOME_PHOTO`-এ ছবির লিংক দিন। ছবি ছাড়া শুধু লেখা চাইলে `WELCOME_PHOTO` = `off`।
