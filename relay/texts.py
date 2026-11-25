"""What a relay bot says, in the reader's language (Telegram's language_code), English otherwise.

Honest by design: every message says plainly that this bot is now part of the store and where
the button goes. A relay bot never poses as anything else.

{bot} is the relay bot's own username, {store} the store's name. Both are plain text. The welcome
goes out as the banner's caption (Telegram allows 1024 characters there), or as plain text when
the banner is off.
"""

from __future__ import annotations

WELCOME: dict[str, str] = {
    "en": (
        "🚀 <b>Welcome!</b>\n\n"
        "Looking for premium accounts, subscriptions and digital products?\n"
        "Find everything in one place.\n\n"
        "📦 Digital products\n"
        "⚡ Automatic delivery\n"
        "🛡 Secure payment\n\n"
        "👇 @{bot} is now part of {store}. Open our main store:"
    ),
    "bn": (
        "🚀 <b>স্বাগতম!</b>\n\n"
        "প্রিমিয়াম অ্যাকাউন্ট, সাবস্ক্রিপশন বা ডিজিটাল প্রোডাক্ট খুঁজছেন?\n"
        "সব পাবেন এক জায়গায়।\n\n"
        "📦 ডিজিটাল প্রোডাক্ট\n"
        "⚡ অটো ডেলিভারি\n"
        "🛡 নিরাপদ পেমেন্ট\n\n"
        "👇 @{bot} এখন {store}-এর অংশ। আমাদের মূল দোকান খুলুন:"
    ),
    "hi": (
        "🚀 <b>स्वागत है!</b>\n\n"
        "प्रीमियम अकाउंट, सब्सक्रिप्शन या डिजिटल प्रोडक्ट ढूँढ रहे हैं?\n"
        "सब कुछ एक ही जगह मिलेगा।\n\n"
        "📦 डिजिटल प्रोडक्ट\n"
        "⚡ ऑटोमैटिक डिलीवरी\n"
        "🛡 सुरक्षित पेमेंट\n\n"
        "👇 @{bot} अब {store} का हिस्सा है। हमारा मुख्य स्टोर खोलें:"
    ),
    "ar": (
        "🚀 <b>أهلًا بك!</b>\n\n"
        "تبحث عن حسابات مميزة أو اشتراكات أو منتجات رقمية؟\n"
        "ستجد كل شيء في مكان واحد.\n\n"
        "📦 منتجات رقمية\n"
        "⚡ تسليم تلقائي\n"
        "🛡 دفع آمن\n\n"
        "👇 @{bot} أصبح الآن جزءًا من {store}. افتح متجرنا الرئيسي:"
    ),
    "ru": (
        "🚀 <b>Добро пожаловать!</b>\n\n"
        "Ищете премиум-аккаунты, подписки или цифровые товары?\n"
        "Всё в одном месте.\n\n"
        "📦 Цифровые товары\n"
        "⚡ Автоматическая выдача\n"
        "🛡 Безопасная оплата\n\n"
        "👇 @{bot} теперь часть {store}. Откройте наш основной магазин:"
    ),
    "uk": (
        "🚀 <b>Ласкаво просимо!</b>\n\n"
        "Шукаєте преміум-акаунти, підписки чи цифрові товари?\n"
        "Усе в одному місці.\n\n"
        "📦 Цифрові товари\n"
        "⚡ Автоматична видача\n"
        "🛡 Безпечна оплата\n\n"
        "👇 @{bot} тепер частина {store}. Відкрийте наш основний магазин:"
    ),
    "kk": (
        "🚀 <b>Қош келдіңіз!</b>\n\n"
        "Премиум аккаунттар, жазылымдар немесе цифрлық тауарлар іздеп жүрсіз бе?\n"
        "Бәрі бір жерде.\n\n"
        "📦 Цифрлық тауарлар\n"
        "⚡ Автоматты жеткізу\n"
        "🛡 Қауіпсіз төлем\n\n"
        "👇 @{bot} енді {store} дүкенінің бөлігі. Негізгі дүкенімізді ашыңыз:"
    ),
    "id": (
        "🚀 <b>Selamat datang!</b>\n\n"
        "Mencari akun premium, langganan, atau produk digital?\n"
        "Semuanya ada di satu tempat.\n\n"
        "📦 Produk digital\n"
        "⚡ Pengiriman otomatis\n"
        "🛡 Pembayaran aman\n\n"
        "👇 @{bot} sekarang bagian dari {store}. Buka toko utama kami:"
    ),
    "ms": (
        "🚀 <b>Selamat datang!</b>\n\n"
        "Mencari akaun premium, langganan atau produk digital?\n"
        "Semuanya ada di satu tempat.\n\n"
        "📦 Produk digital\n"
        "⚡ Penghantaran automatik\n"
        "🛡 Pembayaran selamat\n\n"
        "👇 @{bot} kini sebahagian daripada {store}. Buka kedai utama kami:"
    ),
    "pt": (
        "🚀 <b>Bem-vindo!</b>\n\n"
        "Procurando contas premium, assinaturas ou produtos digitais?\n"
        "Encontre tudo num só lugar.\n\n"
        "📦 Produtos digitais\n"
        "⚡ Entrega automática\n"
        "🛡 Pagamento seguro\n\n"
        "👇 @{bot} agora faz parte da {store}. Abra nossa loja principal:"
    ),
    "fr": (
        "🚀 <b>Bienvenue !</b>\n\n"
        "Vous cherchez des comptes premium, des abonnements ou des produits numériques ?\n"
        "Tout est réuni au même endroit.\n\n"
        "📦 Produits numériques\n"
        "⚡ Livraison automatique\n"
        "🛡 Paiement sécurisé\n\n"
        "👇 @{bot} fait désormais partie de {store}. Ouvrez notre boutique principale :"
    ),
    "tr": (
        "🚀 <b>Hoş geldiniz!</b>\n\n"
        "Premium hesap, abonelik veya dijital ürün mü arıyorsunuz?\n"
        "Hepsi tek bir yerde.\n\n"
        "📦 Dijital ürünler\n"
        "⚡ Otomatik teslimat\n"
        "🛡 Güvenli ödeme\n\n"
        "👇 @{bot} artık {store} mağazasının bir parçası. Ana mağazamızı açın:"
    ),
    "vi": (
        "🚀 <b>Chào mừng bạn!</b>\n\n"
        "Bạn đang tìm tài khoản premium, gói đăng ký hay sản phẩm số?\n"
        "Tất cả đều có ở một nơi.\n\n"
        "📦 Sản phẩm số\n"
        "⚡ Giao tự động\n"
        "🛡 Thanh toán an toàn\n\n"
        "👇 @{bot} giờ là một phần của {store}. Mở cửa hàng chính của chúng tôi:"
    ),
    "zh": (
        "🚀 <b>欢迎！</b>\n\n"
        "在找高级账号、订阅或数字商品吗？\n"
        "一站全都有。\n\n"
        "📦 数字商品\n"
        "⚡ 自动发货\n"
        "🛡 安全支付\n\n"
        "👇 @{bot} 现已并入 {store}。打开我们的主商店："
    ),
    "tl": (
        "🚀 <b>Maligayang pagdating!</b>\n\n"
        "Naghahanap ng premium accounts, subscriptions o digital products?\n"
        "Nandito na lahat sa iisang lugar.\n\n"
        "📦 Digital products\n"
        "⚡ Awtomatikong delivery\n"
        "🛡 Ligtas na bayad\n\n"
        "👇 Bahagi na ng {store} ang @{bot}. Buksan ang aming pangunahing tindahan:"
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


def language_of(code: str | None) -> str:
    """ "pt-BR" -> "pt"; anything unknown -> "en"."""
    base = (code or "").split("-")[0].split("_")[0].lower()
    return base if base in WELCOME else "en"


def welcome(code: str | None, *, bot: str, store: str) -> str:
    return WELCOME[language_of(code)].format(bot=bot, store=store)


def button(code: str | None, *, store: str) -> str:
    return BUTTON[language_of(code)].format(store=store)
