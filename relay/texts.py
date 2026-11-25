"""What a relay bot says, in the reader's language (Telegram's language_code), English otherwise.

Honest by design: every message says plainly that this bot is now part of the store and where
the button goes. A relay bot never poses as anything else.

{bot} is the relay bot's own username, {store} the store's name. Both are plain text.
"""

from __future__ import annotations

WELCOME: dict[str, str] = {
    "en": (
        "🛍 <b>@{bot} is now part of {store}</b>\n\n"
        "Premium accounts, subscriptions and digital products, delivered automatically.\n"
        "Tap below to open the store."
    ),
    "bn": (
        "🛍 <b>@{bot} এখন {store}-এর অংশ</b>\n\n"
        "প্রিমিয়াম অ্যাকাউন্ট, সাবস্ক্রিপশন আর ডিজিটাল প্রোডাক্ট, অটো ডেলিভারি।\n"
        "দোকান খুলতে নিচে চাপুন।"
    ),
    "hi": (
        "🛍 <b>@{bot} अब {store} का हिस्सा है</b>\n\n"
        "प्रीमियम अकाउंट, सब्सक्रिप्शन और डिजिटल प्रोडक्ट, ऑटोमैटिक डिलीवरी।\n"
        "स्टोर खोलने के लिए नीचे दबाएँ।"
    ),
    "ar": (
        "🛍 <b>@{bot} أصبح الآن جزءًا من {store}</b>\n\n"
        "حسابات مميزة واشتراكات ومنتجات رقمية، بتسليم تلقائي.\n"
        "اضغط بالأسفل لفتح المتجر."
    ),
    "ru": (
        "🛍 <b>@{bot} теперь часть {store}</b>\n\n"
        "Премиум-аккаунты, подписки и цифровые товары с автоматической выдачей.\n"
        "Нажмите ниже, чтобы открыть магазин."
    ),
    "uk": (
        "🛍 <b>@{bot} тепер частина {store}</b>\n\n"
        "Преміум-акаунти, підписки та цифрові товари з автоматичною видачею.\n"
        "Натисніть нижче, щоб відкрити магазин."
    ),
    "kk": (
        "🛍 <b>@{bot} енді {store} дүкенінің бөлігі</b>\n\n"
        "Премиум аккаунттар, жазылымдар және цифрлық тауарлар, автоматты жеткізу.\n"
        "Дүкенді ашу үшін төмендегіні басыңыз."
    ),
    "id": (
        "🛍 <b>@{bot} sekarang bagian dari {store}</b>\n\n"
        "Akun premium, langganan, dan produk digital, dikirim otomatis.\n"
        "Ketuk di bawah untuk membuka toko."
    ),
    "ms": (
        "🛍 <b>@{bot} kini sebahagian daripada {store}</b>\n\n"
        "Akaun premium, langganan dan produk digital, dihantar secara automatik.\n"
        "Tekan di bawah untuk membuka kedai."
    ),
    "pt": (
        "🛍 <b>@{bot} agora faz parte da {store}</b>\n\n"
        "Contas premium, assinaturas e produtos digitais, com entrega automática.\n"
        "Toque abaixo para abrir a loja."
    ),
    "fr": (
        "🛍 <b>@{bot} fait désormais partie de {store}</b>\n\n"
        "Comptes premium, abonnements et produits numériques, livrés automatiquement.\n"
        "Appuyez ci-dessous pour ouvrir la boutique."
    ),
    "tr": (
        "🛍 <b>@{bot} artık {store} mağazasının bir parçası</b>\n\n"
        "Premium hesaplar, abonelikler ve dijital ürünler, otomatik teslimat.\n"
        "Mağazayı açmak için aşağıya dokunun."
    ),
    "vi": (
        "🛍 <b>@{bot} giờ là một phần của {store}</b>\n\n"
        "Tài khoản premium, gói đăng ký và sản phẩm số, giao tự động.\n"
        "Nhấn bên dưới để mở cửa hàng."
    ),
    "zh": (
        "🛍 <b>@{bot} 现已并入 {store}</b>\n\n"
        "高级账号、订阅和数字商品，自动发货。\n"
        "点击下方打开商店。"
    ),
    "tl": (
        "🛍 <b>Bahagi na ng {store} ang @{bot}</b>\n\n"
        "Premium accounts, subscriptions at digital products, awtomatikong naide-deliver.\n"
        "I-tap sa ibaba para buksan ang tindahan."
    ),
}

BUTTON: dict[str, str] = {
    "en": "🛍 Open {store}",
    "bn": "🛍 {store} খুলুন",
    "hi": "🛍 {store} खोलें",
    "ar": "🛍 افتح {store}",
    "ru": "🛍 Открыть {store}",
    "uk": "🛍 Відкрити {store}",
    "kk": "🛍 {store} ашу",
    "id": "🛍 Buka {store}",
    "ms": "🛍 Buka {store}",
    "pt": "🛍 Abrir {store}",
    "fr": "🛍 Ouvrir {store}",
    "tr": "🛍 {store} aç",
    "vi": "🛍 Mở {store}",
    "zh": "🛍 打开 {store}",
    "tl": "🛍 Buksan ang {store}",
}

#  The bot's profile, written once at start when SET_PROFILE is on. Telegram's limits: the
#  description 512 characters, the short description ("about") 120.
DESCRIPTION = (
    "This bot is now part of {store}: premium accounts, subscriptions and digital products, "
    "delivered automatically. Press Start to open the store."
)
SHORT_DESCRIPTION = "Part of {store}: premium accounts and digital products. Press Start."

STATS_HEAD = "📊 <b>Relay bots</b> · since {since}"
STATS_ROW = "@{bot}: <b>{people}</b> people, {starts} starts"
STATS_TOTAL = "\nTotal: <b>{people}</b> people, {starts} starts"


def language_of(code: str | None) -> str:
    """ "pt-BR" -> "pt"; anything unknown -> "en"."""
    base = (code or "").split("-")[0].split("_")[0].lower()
    return base if base in WELCOME else "en"


def welcome(code: str | None, *, bot: str, store: str) -> str:
    return WELCOME[language_of(code)].format(bot=bot, store=store)


def button(code: str | None, *, store: str) -> str:
    return BUTTON[language_of(code)].format(store=store)
