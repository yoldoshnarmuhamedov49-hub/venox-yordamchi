"""Venox Yordamchi — lightning-fast inline Telegram Bot Constructor.

Everything happens inside Telegram with rich inline keyboards: a searchable
template catalog (192 templates in 16 categories), a custom bot builder,
Free / Standart / Ultra Pro tiers, and card payments with receipt review.

Run locally / on Render:
    python bot.py
"""

from __future__ import annotations

import html
import json
import logging
import os
import random
import re
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

from telegram import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from database import (
    ADMIN_ID,
    ADMIN_USERNAME,
    BOT_TOKEN,
    DEFAULT_DB_PATH,
    FREE,
    PAYMENT_CARD,
    PLANS,
    STANDART,
    ULTRA,
    Database,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
)
log = logging.getLogger("venox")
os.makedirs(os.path.dirname(os.path.abspath(DEFAULT_DB_PATH)), exist_ok=True)
db = Database()

B_NAME, B_WELCOME, B_BUTTONS, B_ANSWER, B_CONFIRM = range(5)
A_BROADCAST, A_GRANT = range(10, 12)
R_NAME, R_CONTACT, R_DESC = range(20, 23)
BUILD_STATE: Dict[str, Any] = {}
REQUEST_STATE: Dict[int, Dict[str, str]] = {}
BUILD_ID = os.getenv("BUILD_ID", "2026-11-28.2")
GITHUB_PAGES_URL = os.getenv(
    "GITHUB_PAGES_URL",
    "https://yoldoshnarmuhamedov49-hub.github.io/venox-yordamchi/",
).strip()

# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def pretty_money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


def tier_label(tier: str) -> str:
    plan = PLANS.get(tier, PLANS[FREE])
    return f"{plan['emoji']} {plan['label']}"


def check_limit(value: Optional[int], used: int) -> bool:
    return value is None or used < value


# --------------------------------------------------------------------------- #
# Keyboards
# --------------------------------------------------------------------------- #
def reply_main_keyboard() -> ReplyKeyboardMarkup:
    """Persistent bottom menu — the only chat navigation."""
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    "🚀 Bot yasash (Mini App)",
                    web_app=WebAppInfo(url=GITHUB_PAGES_URL),
                )
            ],
            [
                KeyboardButton("🤖 AI Maslahatchi"),
                KeyboardButton("💎 Tariflar"),
            ],
            [KeyboardButton("💳 To'lov / Chek yuborish")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def main_menu_keyboard(user_id: int) -> None:
    """Inline template menus are intentionally removed from chat."""
    return None


def review_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve:{payment_id}"),
                InlineKeyboardButton("❌ Rad etish", callback_data=f"reject:{payment_id}"),
            ]
        ]
    )


# --------------------------------------------------------------------------- #
# Views (text + markup) shared by button handlers and the text handler
# --------------------------------------------------------------------------- #
def build_view(user_id: int, view: str, payload: str = "") -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    if view in {"menu", "main"}:
        user = db.get_user(user_id) or {}
        name = user.get("first_name") or "do'stim"
        text = (
            f"Assalomu alaykum, {esc(name)}! 👋\n\n"
            "Men <b>Venox Yordamchi</b> — Telegram ichida ishlaydigan bot "
            f"quruvchi: <b>{db.template_count()} ta tayyor shablon</b>, "
            f"{len(db.categories())} kategoriya va o'zingizning botingizni qurish "
            "quruvchisi.\n\n"
            f"Sizning tarifingiz: {tier_label(db.effective_tier(user_id))}\n\n"
            "🧠 <b>AI Maslahatchi</b> — matn yozing, albatta javob beraman.\n"
            "🧾 <b>Chek yuborish</b> — to'lov rasmini adminga yuboraman.\n\n"
            "Quyidagi bo'limlardan birini tanlang:"
        )
        return text, main_menu_keyboard(user_id)

    if view == "catalog":
        categories = db.categories()
        buttons = [
            InlineKeyboardButton(
                f"{cat['icon']} {cat['name']} ({cat['total']})",
                callback_data=f"cat:{cat['key']}",
            )
            for cat in categories
        ]
        rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
        rows.append([InlineKeyboardButton("🔍 Barcha shablonlar", callback_data="cat:all")])
        rows.append([InlineKeyboardButton("🏠 Asosiy menyu", callback_data="menu")])
        text = (
            "🏪 <b>Botlar kutubxonasi</b>\n\n"
            f"Jami <b>{db.template_count()}</b> ta tayyor bot shabloni, "
            f"<b>{len(categories)}</b> kategoriya mavjud. "
            "Kategoriyani tanlang — barchasi shu yerda, tashqi sahifa yo'q."
        )
        return text, InlineKeyboardMarkup(rows)

    if view == "cat" or view.startswith("cat:"):
        parts = (payload or view.split(":", 1)[1]).split(":")
        key = parts[0]
        try:
            page = max(0, int(parts[1]))
        except (IndexError, ValueError):
            page = 0
        per_page = 25
        premium = db.limits(user_id)["premium_templates"]
        all_items = db.templates(category=None if key == "all" else key, include_premium=premium)
        items = all_items[page * per_page : (page + 1) * per_page]
        title = "Barcha shablonlar" if key == "all" else next(
            (c["name"] for c in db.categories() if c["key"] == key), key
        )
        lines = [
            f"📂 <b>{esc(title)}</b> — {len(all_items)} ta shablon",
            "",
        ]
        if not premium:
            lines.append("ℹ️ Sizda faqat bepul shablonlar mavjud. Premium uchun /plans")
            lines.append("")
        for item in items:
            mark = "👑" if item["is_premium"] else "🆓"
            lines.append(f"{mark} /{item['key']} — <b>{esc(item['name'])}</b>")
        rows = [
            [InlineKeyboardButton(f"➕ {esc(item['name'])}", callback_data=f"tpl:{item['key']}")]
            for item in items
        ]
        navigation = []
        if page > 0:
            navigation.append(
                InlineKeyboardButton("◀️ Oldingi", callback_data=f"cat:{key}:{page - 1}")
            )
        if (page + 1) * per_page < len(all_items):
            navigation.append(
                InlineKeyboardButton("Keyingi ▶️", callback_data=f"cat:{key}:{page + 1}")
            )
        if navigation:
            rows.append(navigation)
        rows.append([InlineKeyboardButton("◀️ Kutubxona", callback_data="catalog")])
        return "\n".join(lines), InlineKeyboardMarkup(rows)

    if view == "tpl" or view.startswith("tpl:"):
        key = payload or view.split(":", 1)[1]
        item = db.get_template(key)
        if not item:
            return "❌ Shablon topilmadi.", InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀️ Kutubxona", callback_data="catalog")]]
            )
        price = "👑 Premium" if item["is_premium"] else "🆓 Bepul"
        text = (
            f"{item['icon']} <b>{esc(item['name'])}</b>\n\n"
            f"📁 Kategoriya: {esc(item['category_name'])}\n"
            f"💎 Turi: {price}\n"
            f"🔑 Kod: <code>{esc(item['key'])}</code>\n\n"
            f"{esc(item['description'])}\n\n"
            "Mini App ichida ushbu shablon asosida bot tuzilmasini yarating."
        )
        markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("◀️ Kategoriyaga", callback_data=f"cat:{item['category']}")],
                [InlineKeyboardButton("🏠 Asosiy menyu", callback_data="menu")],
            ]
        )
        return text, markup

    if view == "mybots":
        bots = db.list_bots(user_id)
        if not bots:
            text = (
                "📦 <b>Hali botlaringiz yo'q.</b>\n\n"
                "Kutubxonadan tayyor shablon tanlang yoki o'zingizning botingizni quring."
            )
            markup = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🏪 Kutubxonaga borish", callback_data="catalog")],
                    [InlineKeyboardButton("🤖 Bot yaratish", callback_data="build")],
                    [InlineKeyboardButton("🏠 Menyu", callback_data="menu")],
                ]
            )
            return text, markup
        lines = [f"📦 <b>Mening botlarim</b> ({len(bots)})", ""]
        rows = []
        for bot in bots:
            status = "🚀 Nashr qilingan" if bot["status"] == "published" else "📝 Qoralama"
            lines.append(f"• <b>#{bot['id']}</b> {esc(bot['name'])} — {status}")
            rows.append(
                [InlineKeyboardButton(f"⚙️ #{bot['id']} {esc(bot['name'])}", callback_data=f"bot:{bot['id']}")]
            )
        rows.append([InlineKeyboardButton("🏠 Asosiy menyu", callback_data="menu")])
        return "\n".join(lines), InlineKeyboardMarkup(rows)

    if view == "bot" or view.startswith("bot:"):
        bot_id = int(payload or view.split(":", 1)[1])
        bot = db.get_bot(bot_id, user_id)
        if not bot:
            return "❌ Bot topilmadi.", InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀️ Botlarim", callback_data="mybots")]]
            )
        cfg = bot["config"]
        buttons = ", ".join(cfg.get("buttons", [])) or "—"
        created = str(bot["created_at"])[:16].replace("T", " ")
        text = (
            f"🤖 <b>{esc(bot['name'])}</b> (ID {bot['id']})\n\n"
            f"🔧 Turi: {'Custom builder' if bot['source'] == 'custom' else 'Shablon'}\n"
            f"📊 Holati: {'🚀 Nashr qilingan' if bot['status'] == 'published' else '📝 Qoralama'}\n"
            f"🕐 Yaratilgan: {esc(created)}\n"
            f"💬 Xush kelibsiz: {esc(cfg.get('welcome', '—'))}\n"
            f"🔘 Tugmalar: {esc(buttons)}\n"
        )
        rows = []
        if bot["status"] != "published":
            rows.append([InlineKeyboardButton("🚀 Nashr qilish", callback_data=f"publish:{bot_id}")])
        rows.append([InlineKeyboardButton("📥 JSON yuklab olish", callback_data=f"download:{bot_id}")])
        rows.append(
            [
                InlineKeyboardButton("✏️ Qayta sozlash", callback_data=f"rebuild:{bot_id}"),
                InlineKeyboardButton("🗑 O'chirish", callback_data=f"delconfirm:{bot_id}"),
            ]
        )
        rows.append([InlineKeyboardButton("◀️ Botlarim", callback_data="mybots")])
        return text, InlineKeyboardMarkup(rows)

    if view == "plans":
        lines = ["💳 <b>Tariflar va narxlar</b>\n"]
        rows = []
        for key in (FREE, STANDART, ULTRA):
            plan = PLANS[key]
            price = "Bepul" if not plan["price"] else f"{pretty_money(plan['price'])} UZS"
            lines.append(f"{plan['emoji']} <b>{esc(plan['label'])}</b> — {price}")
            lines.append(f"   {esc(plan['description'])}")
            for perk in plan["perks"]:
                lines.append(f"   ✅ {esc(perk)}")
            lines.append("")
            if key != FREE:
                rows.append([InlineKeyboardButton(f"{plan['emoji']} {plan['label']} tanlash", callback_data=f"pay:{key}")])
        lines.append(f"💳 To'lov kartyasi: <code>{esc(PAYMENT_CARD)}</code>")
        lines.append("To'lovdan keyin chek (skrinshot) yuboring — admin tasdiqlaydi.")
        rows.append([InlineKeyboardButton("🏠 Asosiy menyu", callback_data="menu")])
        return "\n".join(lines), InlineKeyboardMarkup(rows)

    if view == "pay" or view.startswith("pay:"):
        tier = payload or view.split(":", 1)[1]
        plan = PLANS.get(tier)
        if not plan:
            return "❌ Tarif topilmadi.", main_menu_keyboard(user_id)
        if db.is_admin(user_id):
            return (
                "👑 Siz admin/VIP sifatida barcha tariflarga cheksiz va bepul kirish huquqiga egasiz.",
                main_menu_keyboard(user_id),
            )
        text = (
            f"{plan['emoji']} <b>{esc(plan['label'])}</b> tarifini tanladingiz.\n\n"
            f"💰 Miqdor: <b>{pretty_money(plan['price'])} UZS</b>\n"
            f"⏳ Muddat: {plan['days']} kun\n"
            f"💳 Karta: <code>{esc(PAYMENT_CARD)}</code>\n\n"
            "1) Karta raqamiga to'lov qiling.\n"
            "2) To'lov cheki (skrinshot) ni yuboring.\n"
            f"3) Admin @{esc(ADMIN_USERNAME)} tasdiqlagach tarif avtomatik ochiladi.\n\n"
            "Chekni yuborish uchun quyidagi tugmani bosing."
        )
        markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📤 Chek yuborish", callback_data=f"receipt:{tier}")],
                [InlineKeyboardButton("◀️ Tariflar", callback_data="plans")],
            ]
        )
        return text, markup

    if view == "usage":
        tier = db.effective_tier(user_id)
        limits = db.limits(user_id)
        usage = db.usage(user_id)
        bots_cap = limits["bots"]
        bots_text = "cheksiz" if bots_cap is None else str(bots_cap)
        msg_cap = limits["daily_messages"]
        msgs_text = "cheksiz" if msg_cap is None else str(msg_cap)
        remain = usage["remaining"]
        remain_text = "cheksiz" if remain is None else str(remain)
        text = (
            f"📊 <b>Sizning hisobingiz</b>\n\n"
            f"🎚 Tarif: {tier_label(tier)}\n"
            f"🤖 Botlar: {db.count_bots(user_id)} / {bots_text}\n"
            f"💬 Bugungi xabarlar: {usage['used']} / {msgs_text} (qoldi: {remain_text})\n"
            f"🏪 Shablonlar: {'hammasi' if limits['premium_templates'] else 'faqat bepul'}\n"
            f"🔧 Custom quruvchi: {'ha' if limits['custom_builder'] else 'yo‘q'}\n"
            f"⚡ Tezkor rejim: ha (faqat Telegram)\n"
            f"👑 VIP/Admin: {'ha' if db.is_admin(user_id) or tier in (STANDART, ULTRA) else 'yo‘q'}"
        )
        markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💳 Tariflarga o'tish", callback_data="plans")],
                [InlineKeyboardButton("🏠 Asosiy menyu", callback_data="menu")],
            ]
        )
        return text, markup

    if view == "help":
        text = (
            "❓ <b>Venox Yordamchi bo'yicha ko'rsatma</b>\n\n"
            f"• <b>🏪 Kutubxona</b> — {db.template_count()} ta shablon, "
            f"{len(db.categories())} kategoriya (E-commerce, ChatGPT, SMM, Crypto va boshqalar). "
            "Inline tugmalar bilan bir soniyada bot yaratish.\n"
            "• <b>🤖 Bot yaratish</b> — o'zingizning botingizni qadam-baqadam qurish.\n"
            "• <b>🛠 Buyurtma</b> — noyob botni bizga buyurtma qilish.\n"
            "• <b>📦 Botlarim</b> — botlarni boshqarish va JSON yuklab olish.\n"
            "• <b>💳 Tariflar</b> — Free, Standart (60,000 UZS) va Ultra Pro (150,000 UZS).\n"
            "• <b>📊 Limitim</b> — cheklovlar va statistika.\n"
            "• <b>🚀 Ochish</b> — GitHub Pages dagi Mini App dashboard (tezkor, uxlamaydi).\n\n"
            "Buyruqlar: /start, /menu, /build, /request, /plans, /usage, /admin\n"
            f"Yordam va to'lov bo'yicha savollar: @{esc(ADMIN_USERNAME)}"
        )
        return text, main_menu_keyboard(user_id)

    if view == "admin":
        stats = db.stats()
        text = (
            "⚙️ <b>Admin panel</b> "
            f"(@{esc(ADMIN_USERNAME)})\n\n"
            f"👥 Foydalanuvchilar: <b>{stats['users']}</b>\n"
            f"👑 VIP/Premium: <b>{stats['premium']}</b>\n"
            f"🤖 Botlar: <b>{stats['bots']}</b>\n"
            f"🏪 Shablonlar: <b>{stats['templates']}</b>\n"
            f"⏳ Kutilayotgan cheklar: <b>{stats['pending']}</b>\n"
            f"✅ Tasdiqlangan to'lovlar: <b>{stats['approved']}</b>"
        )
        markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(f"📋 Cheklarni ko'rish ({stats['pending']})", callback_data="admin_pending")],
                [
                    InlineKeyboardButton("📢 Xabar yuborish", callback_data="admin_broadcast"),
                    InlineKeyboardButton("🔑 VIP berish", callback_data="admin_grant"),
                ],
                [InlineKeyboardButton("🏠 Asosiy menyu", callback_data="menu")],
            ]
        )
        return text, markup

    if view == "admin_pending":
        pending = db.pending_payments()
        if not pending:
            return "✅ Kutilayotgan chek yo'q.", InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀️ Admin panel", callback_data="admin")]]
            )
        lines = ["📋 <b>Kutilayotgan cheklar</b>\n"]
        rows = []
        for payment in pending:
            user = db.get_user(payment["user_id"]) or {}
            plan = PLANS.get(payment["tier"], PLANS[STANDART])
            lines.append(
                f"• <b>#{payment['id']}</b> — {esc(user.get('first_name') or payment['user_id'])} "
                f"({esc(user.get('username') or 'username yo‘q')}), "
                f"{esc(plan['label'])}, {pretty_money(payment['amount'])} UZS"
            )
            rows.append(
                [
                    InlineKeyboardButton("✅", callback_data=f"approve:{payment['id']}"),
                    InlineKeyboardButton("❌", callback_data=f"reject:{payment['id']}"),
                    InlineKeyboardButton(f"#{payment['id']}", callback_data=f"tpl:tpl_001"),
                ]
            )
        rows.append([InlineKeyboardButton("◀️ Admin panel", callback_data="admin")])
        return "\n".join(lines), InlineKeyboardMarkup(rows)

    return "❓ Noma'lum bo'lim.", main_menu_keyboard(user_id)


async def send_view(update: Update, context: ContextTypes.DEFAULT_TYPE, view: str, payload: str = "") -> None:
    user = update.effective_user
    text, markup = build_view(user.id, view, payload)
    await update.effective_chat.send_message(
        text=text, reply_markup=markup, parse_mode=ParseMode.HTML
    )


async def edit_view(query: CallbackQuery, view: str, payload: str = "") -> None:
    text, markup = build_view(query.from_user.id, view, payload)
    try:
        await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.HTML)
    except Exception:
        await query.answer("Menyuni yuborib bo'lmadi, /menu buyrug'idan foydalaning.", show_alert=True)


# --------------------------------------------------------------------------- #
# Command handlers
# --------------------------------------------------------------------------- #
WELCOME_TEXT = (
    "Assalomu alaykum! 👋 Men <b>Venox Yordamchi</b> — sizning <b>AI Bot Maslahatchi</b>ingiz.\n\n"
    "Bot g'oyangizni qanday loyihalash, tuzilmasini qurish, foydalanuvchi oqimini "
    "sozlash va undan pul ishlash bo'yicha amaliy maslahat beraman.\n\n"
    "Tayyor botlarni esa pastdagi <b>🚀 Bot yasash (Mini App)</b> tugmasi orqali "
    "Mini App ichida yarating.\n\n"
    "Savol yozing yoki pastdagi tugmalardan foydalaning."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    await update.message.reply_text(
        WELCOME_TEXT, reply_markup=reply_main_keyboard(), parse_mode=ParseMode.HTML
    )


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    await update.message.reply_text(
        "🧠 <b>AI Maslahatchi</b>\n\n"
        "Botingiz nima qilishi kerakligini yozing: kimga mo'ljallangan, qanday "
        "vazifa bajaradi, qayerda ishlatiladi. Men tuzilma, komandalar va "
        "monetizatsiya bo'yicha bosqichma-bosqich maslahat beraman.",
        reply_markup=reply_main_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    context.user_data["receipt_tier"] = STANDART
    context.user_data["awaiting_receipt"] = True
    context.user_data.pop("await_receipt", None)
    await update.message.reply_text(
        "🧾 <b>To'lov / Chek yuborish</b>\n\n"
        f"Karta: <code>{esc(PAYMENT_CARD)}</code>\n\n"
        "To'lov qilgach, chek rasmini shu chatga yuboring — u admin "
        f"@{esc(ADMIN_USERNAME)} ga Tasdiqlash / Rad etish tugmalari bilan yuboriladi.",
        reply_markup=reply_main_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    await update.message.reply_text(
        WELCOME_TEXT, reply_markup=reply_main_keyboard(), parse_mode=ParseMode.HTML
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "❓ <b>Qanday ishlaydi?</b>\n\n"
        "• 🚀 Mini App — 192 ta shablon va AI Bot Yasash quruvchisi shu yerda.\n"
        "• 🤖 AI Maslahatchi — istalgan matn yozing, botingizni loyihalash, "
        "tuzilma va monetizatsiya bo'yicha maslahat oling.\n"
        "• 💎 Tariflar — Free, Standart (60,000 UZS) va Ultra Pro (150,000 UZS).\n"
        "• 💳 Chek yuborish — to'lov rasmini yuboring, admin tasdiqlaydi.",
        reply_markup=reply_main_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def plans_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text, _ = build_view(update.effective_user.id, "plans")
    await update.message.reply_text(
        text, reply_markup=reply_main_keyboard(), parse_mode=ParseMode.HTML
    )


async def usage_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text, _ = build_view(update.effective_user.id, "usage")
    await update.message.reply_text(
        text, reply_markup=reply_main_keyboard(), parse_mode=ParseMode.HTML
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Bu buyruq faqat admin uchun.")
        return
    await send_view(update, context, "admin")


# --------------------------------------------------------------------------- #
# Callback router
# --------------------------------------------------------------------------- #
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)

    if data == "close":
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.answer()
        return

    await query.answer()

    if data in {"menu", "main"}:
        await edit_view(query, "menu")
        return

    if data in {"catalog", "back:catalog"}:
        await edit_view(query, "catalog")
        return

    if data.startswith("cat:"):
        await edit_view(query, "cat", data.split(":", 1)[1])
        return

    if data.startswith("tpl:"):
        await edit_view(query, "tpl", data.split(":", 1)[1])
        return

    if data == "mybots":
        await edit_view(query, "mybots")
        return

    if data.startswith("bot:"):
        await edit_view(query, "bot", data.split(":", 1)[1])
        return

    if data.startswith("publish:"):
        bot_id = int(data.split(":", 1)[1])
        bot = db.get_bot(bot_id, user.id)
        if not bot:
            await query.answer("Bot topilmadi.", show_alert=True)
            return
        db.update_bot(bot_id, user.id, status="published")
        await query.answer("Bot tayyor holatga o'tkazildi! 🚀")
        await edit_view(query, "bot", str(bot_id))
        return

    if data.startswith("download:"):
        bot_id = int(data.split(":", 1)[1])
        bot = db.get_bot(bot_id, user.id)
        if not bot:
            await query.answer("Bot topilmadi.", show_alert=True)
            return
        content = json.dumps(
            {"id": bot["id"], "name": bot["name"], "config": bot["config"]},
            ensure_ascii=False,
            indent=2,
        )
        await query.message.reply_document(
            document=InputFile(BytesIO(content.encode("utf-8")), filename=f"venox_bot_{bot_id}.json"),
            caption=f"📥 {esc(bot['name'])} konfiguratsiyasi",
            parse_mode=ParseMode.HTML,
        )
        return

    if data.startswith("delconfirm:"):
        bot_id = data.split(":", 1)[1]
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"delete:{bot_id}"),
                    InlineKeyboardButton("❌ Bekor qilish", callback_data=f"bot:{bot_id}"),
                ]
            ]
        )
        await edit_message_text_safe(query, "🗑 Botni o'chirishni tasdiqlaysizmi?", markup)
        return

    if data.startswith("delete:"):
        bot_id = int(data.split(":", 1)[1])
        db.delete_bot(bot_id, user.id)
        await query.answer("Bot o'chirildi.")
        await edit_view(query, "mybots")
        return

    if data.startswith("rebuild:"):
        bot_id = int(data.split(":", 1)[1])
        bot = db.get_bot(bot_id, user.id)
        if not bot:
            await query.answer("Bot topilmadi.", show_alert=True)
            return
        if not db.limits(user.id)["custom_builder"]:
            await query.answer("Custom quruvchi Standart/Ultra tarifida mavjud: /plans", show_alert=True)
            return
        BUILD_STATE[user.id] = {"edit_id": bot_id, "config": dict(bot["config"])}
        context.user_data["build"] = {"stage": "name"}
        await edit_message_text_safe(
            query,
            "✏️ Bot nomini kiriting:",
            InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor qilish", callback_data="build_cancel")]]),
        )
        return B_NAME

    if data == "ai_chat":
        await query.answer("AI Maslahatchi faol 🧠")
        await edit_message_text_safe(
            query,
            "🧠 <b>AI Maslahatchi</b>\n\n"
            "Men botlar, biznes va marketing bo'yicha maslahat beraman. "
            "Oddiy matn yozing — har qanday savolga javob beraman.\n\n"
            "Misol: «Online do'kon uchun qanday bot kerak?», «tpl_001», «narxingiz qancha?»",
            InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Menyu", callback_data="menu")]]),
        )
        return

    if data == "check_start":
        context.user_data["receipt_tier"] = "standart"
        context.user_data["awaiting_receipt"] = True
        context.user_data.pop("await_receipt", None)
        await query.answer()
        await edit_message_text_safe(
            query,
            "🧾 <b>Chek yuborish</b>\n\n"
            f"Karta: <code>{esc(PAYMENT_CARD)}</code>\n\n"
            "To'lov qilgach, chek rasmini (skrinshot) shu chatga yuboring. "
            f"U to'g'ridan-to'g'ri admin @{esc(ADMIN_USERNAME)} ga yuboriladi va "
            "Tasdiqlash / Rad etish tugmalari bilan ko'rib chiqiladi.",
            InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Menyu", callback_data="menu")]]),
        )
        return

    if data == "plans":
        await edit_view(query, "plans")
        return

    if data.startswith("pay:"):
        await edit_view(query, "pay", data.split(":", 1)[1])
        return

    if data.startswith("receipt:"):
        tier = data.split(":", 1)[1]
        if db.is_admin(user.id):
            await query.answer("Siz allaqachon VIP/adminsiz.", show_alert=True)
            return
        if db.has_pending_payment(user.id):
            await query.answer("Sizda allaqachon kutilayotgan chek bor.", show_alert=True)
            return
        plan = PLANS.get(tier)
        if not plan:
            await query.answer("Tarif topilmadi.", show_alert=True)
            return
        payment_id = db.add_payment(user.id, tier, plan["price"])
        context.user_data["await_receipt"] = payment_id
        await edit_message_text_safe(
            query,
            f"📤 <b>Chek yuborish</b> (#{payment_id})\n\n"
            f"To'lov kartyasi: <code>{esc(PAYMENT_CARD)}</code>\n"
            f"Miqdor: <b>{pretty_money(plan['price'])} UZS</b>\n\n"
            "Chek rasmini (skrinshot) yoki uning matnini shu yerga yuboring. "
            f"Admin @{esc(ADMIN_USERNAME)} tekshirib tasdiqlaydi.",
            InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Tariflar", callback_data="plans")]]),
        )
        return

    if data == "usage":
        await edit_view(query, "usage")
        return

    if data == "help":
        await edit_view(query, "help")
        return

    if data == "admin":
        if not db.is_admin(user.id):
            await query.answer("Faqat admin uchun.", show_alert=True)
            return
        await edit_view(query, "admin")
        return

    if data == "admin_pending":
        if not db.is_admin(user.id):
            await query.answer("Faqat admin uchun.", show_alert=True)
            return
        await edit_view(query, "admin_pending")
        return

    if data.startswith(("approve:", "reject:")):
        if not db.is_admin(user.id):
            await query.answer("Faqat admin tasdiqlay oladi.", show_alert=True)
            return
        action, payment_id = data.split(":")
        payment_id = int(payment_id)
        payment = db.get_payment(payment_id)
        if not payment or payment["status"] != "pending":
            await query.answer("Bu chek allaqachon ko'rilgan.", show_alert=True)
            return
        status = "approved" if action == "approve" else "rejected"
        db.set_payment_status(payment_id, status, reviewer_id=user.id)
        plan = PLANS.get(payment["tier"], PLANS[STANDART])
        if status == "approved":
            result = f"✅ To'lovingiz tasdiqlandi! {esc(plan['label'])} tarifi {plan['days']} kun ochildi."
            await query.answer("Tasdiqlandi ✅")
        else:
            result = "❌ Chekingiz rad etildi. To'lovni qayta tekshirib, yana yuboring."
            await query.answer("Rad etildi ❌")
        try:
            await context.bot.send_message(
                chat_id=payment["user_id"], text=result, parse_mode=ParseMode.HTML
            )
        except Exception as exc:
            log.warning("Could not notify user %s: %s", payment["user_id"], exc)
        await edit_message_text_safe(
            query,
            f"#{payment_id} — {status}. Foydalanuvchiga xabar yuborildi.",
            InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Cheklar", callback_data="admin_pending")]]),
        )
        return

    await query.answer("Noma'lum buyruq.", show_alert=True)


async def edit_message_text_safe(query: CallbackQuery, text: str, markup: Any = None) -> None:
    try:
        await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.HTML)
    except Exception as exc:
        log.debug("edit_message_text failed: %s", exc)


# --------------------------------------------------------------------------- #
# Custom bot builder conversation
# --------------------------------------------------------------------------- #
CANCEL_MARKUP = InlineKeyboardMarkup(
    [[InlineKeyboardButton("❌ Bekor qilish", callback_data="build_cancel")]]
)


async def build_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    if not db.limits(user.id)["custom_builder"]:
        text = "🔒 Custom bot quruvchi faqat Standart/Ultra tarifida mavjud. /plans"
        if update.callback_query:
            await update.callback_query.answer(text, show_alert=True)
        else:
            await update.message.reply_text(text)
        return ConversationHandler.END
    if not check_limit(db.limits(user.id)["bots"], db.count_bots(user.id)):
        text = "🔒 Botlar soni limitiga yetdingiz. Tarifni kengaytiring: /plans"
        if update.callback_query:
            await update.callback_query.answer(text, show_alert=True)
        else:
            await update.message.reply_text(text)
        return ConversationHandler.END
    BUILD_STATE[user.id] = {}
    context.user_data["build"] = {"stage": "name"}
    prompt = "🤖 <b>Custom bot quruvchi</b>\n\n1-qadam: botingiz nomini yuboring."
    if update.callback_query:
        await edit_message_text_safe(update.callback_query, prompt, CANCEL_MARKUP)
    else:
        await update.message.reply_text(prompt, reply_markup=CANCEL_MARKUP, parse_mode=ParseMode.HTML)
    return B_NAME


async def build_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = (update.message.text or "").strip()
    if len(name) < 2 or len(name) > 60:
        await update.message.reply_text("Bot nomi 2 dan 60 gacha belgi bo'lishi kerak. Qayta yuboring:")
        return B_NAME
    BUILD_STATE[update.effective_user.id]["name"] = name
    context.user_data["build"]["stage"] = "welcome"
    await update.message.reply_text(
        "2-qadam: botning xush kelibsiz xabarini yozing.\n(Misol: Assalomu alaykum! Men sizning botingiz.)",
        reply_markup=CANCEL_MARKUP,
    )
    return B_WELCOME


async def build_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Xabar bo'sh bo'lishi mumkin emas. Qayta yuboring:")
        return B_WELCOME
    BUILD_STATE[update.effective_user.id]["welcome"] = text
    context.user_data["build"]["stage"] = "buttons"
    await update.message.reply_text(
        "3-qadam: menyu tugmalarini vergul bilan ajratib yozing.\n(Misol: Boshlash, Ma'lumot, Aloqa)",
        reply_markup=CANCEL_MARKUP,
    )
    return B_BUTTONS


async def build_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.message.text or "").strip()
    buttons = [part.strip() for part in raw.split(",") if part.strip()]
    if not buttons:
        await update.message.reply_text("Kamida bitta tugma yozing:")
        return B_BUTTONS
    if len(buttons) > 12:
        await update.message.reply_text("Eng ko'pi bilan 12 ta tugma yuboring:")
        return B_BUTTONS
    BUILD_STATE[update.effective_user.id]["buttons"] = buttons[:12]
    context.user_data["build"]["stage"] = "answer"
    await update.message.reply_text(
        "4-qadam: botning avtomatik javob matnini yozing.",
        reply_markup=CANCEL_MARKUP,
    )
    return B_ANSWER


async def build_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Javob matni bo'sh bo'lishi mumkin emas:")
        return B_ANSWER
    state = BUILD_STATE[update.effective_user.id]
    state["answer"] = text
    summary = (
        "✅ <b>Bot tayyor!</b>\n\n"
        f"🤖 Nomi: {esc(state['name'])}\n"
        f"💬 Xush kelibsiz: {esc(state['welcome'])}\n"
        f"🔘 Tugmalar: {esc(', '.join(state['buttons']))}\n"
        f"↩️ Avtomatik javob: {esc(text)}\n\n"
        "Saqlash uchun tasdiqlang:"
    )
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Saqlash", callback_data="build_save"),
                InlineKeyboardButton("❌ Bekor qilish", callback_data="build_cancel"),
            ]
        ]
    )
    await update.message.reply_text(summary, reply_markup=markup, parse_mode=ParseMode.HTML)
    context.user_data["build"]["stage"] = "confirm"
    return B_CONFIRM


async def build_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    state = BUILD_STATE.get(user.id)
    if not state:
        await edit_message_text_safe(query, "Ma'lumotlar yo'qolgan. /build qaytadan boshlang.")
        return ConversationHandler.END
    limits = db.limits(user.id)
    if not check_limit(limits["bots"], db.count_bots(user.id)) and "edit_id" not in state:
        await query.answer("Botlar soni limitiga yetdingiz.", show_alert=True)
        return ConversationHandler.END
    config = {
        "name": state["name"],
        "welcome": state["welcome"],
        "buttons": state["buttons"],
        "auto_reply": state["answer"],
        "commands": ["/start", "/menu", "/help"],
        "source": "custom",
    }
    if state.get("edit_id"):
        bot_id = state["edit_id"]
        db.update_bot(bot_id, user.id, name=state["name"], config=config)
        message = "✏️ Bot yangilandi."
    else:
        bot = db.create_bot(user.id, state["name"], config, source="custom")
        bot_id = bot["id"]
        message = "🤖 Bot tayyor."
    BUILD_STATE.pop(user.id, None)
    context.user_data.pop("build", None)
    await edit_view(query, "bot", str(bot_id))
    await query.message.reply_text(message)
    return ConversationHandler.END


async def build_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    BUILD_STATE.pop(update.effective_user.id, None)
    context.user_data.pop("build", None)
    if update.callback_query:
        await update.callback_query.answer("Bekor qilindi.")
        await edit_message_text_safe(
            update.callback_query, "❌ Quruvchi bekor qilindi.", main_menu_keyboard(update.effective_user.id)
        )
    else:
        await update.message.reply_text("❌ Quruvchi bekor qilindi.", reply_markup=reply_main_keyboard())
    return ConversationHandler.END


# --------------------------------------------------------------------------- #
# Admin conversations
# --------------------------------------------------------------------------- #
async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    query = update.callback_query
    if query:
        await query.answer()
        await edit_message_text_safe(query, "📢 Barcha foydalanuvchilarga yuboriladigan xabarni yozing:")
    else:
        await update.message.reply_text("📢 Barcha foydalanuvchilarga yuboriladigan xabarni yozing:")
    return A_BROADCAST


async def admin_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Xabar bo'sh. Qayta yuboring:")
        return A_BROADCAST
    with db.transaction() as conn:
        rows = conn.execute("SELECT user_id FROM users").fetchall()
    sent = 0
    for row in rows:
        try:
            await context.bot.send_message(chat_id=row["user_id"], text=text)
            sent += 1
        except Exception as exc:
            log.debug("broadcast to %s failed: %s", row["user_id"], exc)
    await update.message.reply_text(f"✅ {sent} ta foydalanuvchiga xabar yuborildi.")
    return ConversationHandler.END


async def admin_grant_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    query = update.callback_query
    prompt = "🔑 Foydalanuvchi ID va tarifni yozing.\n(Misol: 123456789 standart yoki 123456789 ultra)"
    if query:
        await query.answer()
        await edit_message_text_safe(query, prompt)
    else:
        await update.message.reply_text(prompt)
    return A_GRANT


async def admin_grant_apply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not db.is_admin(update.effective_user.id):
        return ConversationHandler.END
    parts = (update.message.text or "").strip().split()
    if len(parts) != 2:
        await update.message.reply_text("Format: <user_id> <free|standart|ultra>. Qayta yuboring:")
        return A_GRANT
    try:
        target = int(parts[0])
    except ValueError:
        await update.message.reply_text("User ID butun son bo'lishi kerak:")
        return A_GRANT
    tier = parts[1].lower()
    if tier not in PLANS:
        await update.message.reply_text("Tarif: free, standart yoki ultra bo'lishi kerak:")
        return A_GRANT
    db.ensure_user(target)
    db.set_tier(target, tier)
    try:
        await context.bot.send_message(
            chat_id=target,
            text=f"🎁 Sizga <b>{esc(PLANS[tier]['label'])}</b> tarifi berildi! /menu",
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        log.debug("grant notify failed: %s", exc)
    await update.message.reply_text(f"✅ {target} ga {tier} tarifi berildi.")
    return ConversationHandler.END


async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer("Bekor qilindi.")
        await edit_view(update.callback_query, "admin")
    else:
        await update.message.reply_text("Bekor qilindi.", reply_markup=reply_main_keyboard())
    return ConversationHandler.END


# --------------------------------------------------------------------------- #
# Custom development request (inline-only conversation)
# --------------------------------------------------------------------------- #
REQUEST_CANCEL = InlineKeyboardMarkup(
    [[InlineKeyboardButton("❌ Bekor qilish", callback_data="request_cancel")]]
)


async def request_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    REQUEST_STATE[user.id] = {}
    context.user_data["request"] = True
    prompt = (
        "🛠 <b>Maxsus bot buyurtmasi</b>\n\n"
        f"Jami <b>{db.template_count()}</b> ta shablon mavjud, lekin o'z g'oyangiz bormi? "
        "1-qadam: loyiha / bot nomini yuboring."
    )
    if update.callback_query:
        await update.callback_query.answer()
        await edit_message_text_safe(update.callback_query, prompt, REQUEST_CANCEL)
    else:
        await update.message.reply_text(prompt, reply_markup=REQUEST_CANCEL, parse_mode=ParseMode.HTML)
    return R_NAME


async def request_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = (update.message.text or "").strip()
    if not 2 <= len(value) <= 60:
        await update.message.reply_text("Nomi 2-60 belgi bo'lishi kerak. Qayta yuboring:", reply_markup=REQUEST_CANCEL)
        return R_NAME
    REQUEST_STATE[update.effective_user.id]["name"] = value
    await update.message.reply_text(
        "2-qadam: aloqa uchun @username yoki telefon raqamingizni yuboring.",
        reply_markup=REQUEST_CANCEL,
    )
    return R_CONTACT


async def request_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = (update.message.text or "").strip()
    if len(value) < 3:
        await update.message.reply_text("Aloqa ma'lumotini yuboring:", reply_markup=REQUEST_CANCEL)
        return R_CONTACT
    REQUEST_STATE[update.effective_user.id]["contact"] = value
    await update.message.reply_text(
        "3-qadam: bot nima qilishi kerakligini batafsil yozing "
        "(funksiyalar, auditoriya, muddat).",
        reply_markup=REQUEST_CANCEL,
    )
    return R_DESC


async def request_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = (update.message.text or "").strip()
    if len(value) < 10:
        await update.message.reply_text("Bir oz batafsil yozing:", reply_markup=REQUEST_CANCEL)
        return R_DESC
    user = update.effective_user
    state = REQUEST_STATE.pop(user.id, {})
    context.user_data.pop("request", None)
    admin_text = (
        "🛠 <b>Yangi maxsus bot buyurtmasi</b>\n"
        f"👤 Mijoz: {esc(user.first_name)} (@{esc(user.username or 'yo‘q')}, {user.id})\n"
        f"📌 Nomi: {esc(state.get('name', '—'))}\n"
        f"📞 Aloqa: {esc(state.get('contact', '—'))}\n\n"
        f"📝 Tavsif:\n{esc(value)}"
    )
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID, text=admin_text, parse_mode=ParseMode.HTML
        )
    except Exception as exc:
        log.error("Could not forward custom request to admin: %s", exc)
    await update.message.reply_text(
        "✅ Buyurtmangiz adminga yuborildi. Tez orada bog'lanamiz.",
        reply_markup=main_menu_keyboard(user.id),
    )
    return ConversationHandler.END


async def request_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    REQUEST_STATE.pop(update.effective_user.id, None)
    context.user_data.pop("request", None)
    if update.callback_query:
        await update.callback_query.answer("Bekor qilindi.")
        await edit_message_text_safe(
            update.callback_query, "❌ Buyurtma bekor qilindi.", main_menu_keyboard(update.effective_user.id)
        )
    else:
        await update.message.reply_text("❌ Buyurtma bekor qilindi.", reply_markup=reply_main_keyboard())
    return ConversationHandler.END


async def receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle a receipt when the user is in the payment flow. Returns handled flag."""
    payment_id = context.user_data.get("await_receipt")
    if not payment_id:
        return False
    message = update.message
    if not (message.photo or message.document or message.text or message.caption):
        return False
    payment = db.get_payment(int(payment_id))
    if not payment or payment["status"] != "pending":
        context.user_data.pop("await_receipt", None)
        return False
    user = update.effective_user
    file_id: Optional[str] = None
    caption = message.caption or message.text or ""
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    db.attach_receipt(int(payment_id), file_id or "", caption or None)
    plan = PLANS.get(payment["tier"], PLANS[STANDART])
    admin_text = (
        f"🧾 <b>Yangi chek #{payment_id}</b>\n"
        f"👤 Foydalanuvchi: {esc(user.first_name)} "
        f"(@{esc(user.username or 'yo‘q')}, {user.id})\n"
        f"💎 Tarif: {esc(plan['label'])}\n"
        f"💰 Miqdor: {pretty_money(payment['amount'])} UZS\n"
        + (f"📝 Izoh: {esc(caption)}\n" if caption else "")
    )
    try:
        if file_id and message.photo:
            await context.bot.send_photo(
                chat_id=ADMIN_ID, photo=file_id, caption=admin_text,
                reply_markup=review_keyboard(int(payment_id)), parse_mode=ParseMode.HTML,
            )
        elif file_id and message.document:
            await context.bot.send_document(
                chat_id=ADMIN_ID, document=file_id, caption=admin_text,
                reply_markup=review_keyboard(int(payment_id)), parse_mode=ParseMode.HTML,
            )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_ID, text=admin_text,
                reply_markup=review_keyboard(int(payment_id)), parse_mode=ParseMode.HTML,
            )
    except Exception as exc:
        log.error("Could not forward receipt to admin: %s", exc)
        await message.reply_text("❌ Chekni adminga yuborib bo'lmadi. Keyinroq qayta urining.")
        return True
    context.user_data.pop("await_receipt", None)
    await message.reply_text(
        f"✅ Chek #{payment_id} adminga yuborildi. "
        f"@{esc(ADMIN_USERNAME)} tasdiqlagach tarifingiz ochiladi.",
        reply_markup=reply_main_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    return True


AI_RULES = [
    (
        ("salom", "assalom", "hi ", "hello", "привет"),
        "Assalomu alaykum! 👋 Men sizning AI Bot Maslahatchiingiz. "
        "Bot g'oyasini tuzilma, komandalar va monetizatsiya nuqtai nazaridan "
        "qanday rivojlantirishni bosqichma-bosqich tushuntirib beraman. "
        "G'oyangizni yozib bering.",
    ),
    (
        ("rahmat", "thanks", "спасибо"),
        "Arzimaydi! 😊 Keyingi qadamni ham birgalikda rejalashtiramiz — "
        "botingiz uchun maqsadli harakatni yozing, men unga mos tuzilma taklif qilaman.",
    ),
    (
        ("narx", "price", "tarif", "qancha", "стоим", "standart", "ultra", "pro"),
        "💳 Tariflar: Free — bepul; Standart — 60,000 UZS / 30 kun (10 bot, 192 shablon, "
        "AI quruvchi); Ultra Pro — 150,000 UZS / 90 kun (cheksiz bot, ustuvor yordam). "
        "Monetizatsiya bo'yicha maslahat: avval bitta bot bilan real mijoz oqimini sinang, "
        "so'ng tarifni shunga qarab tanlang. Karta: 5614 6830 1549 1525.",
    ),
    (
        ("chek", "to'lov", "tolov", "karta", "оплат", "receipt", "inkasso"),
        "🧾 Karta: 5614 6830 1549 1525. To'lov qilgach, chek rasmini shu chatga yuboring — "
        "u admin @THE_VENOX ga Tasdiqlash / Rad etish tugmalari bilan yuboriladi. "
        "Tasdiqlangach tarif avtomatik ochiladi.",
    ),
    (
        ("__shablon__",), "__special_shablon__"
    ),
    (
        ("tuzilma", "structure", "komanda", "command", "qurish", "loyiha", "design", "bot yasash"),
        "__special_blueprint__",
    ),
    (
        ("monetizatsiya", "pul", "daromad", "earn", "money", "sotish", "foyda", "ishlatish"),
        "💰 Monetizatsiya bo'yicha amaliy yo'nalishlar:\n"
        "1) obuna/tarif (Standart 60,000 UZS, Ultra Pro 150,000 UZS);\n"
        "2) har bir buyurtma yoki bron uchun komissiya;\n"
        "3) reklama va hamkorlik (SMM, affiliate);\n"
        "4) premium funksiyalar: AI tahlil, hisobot, avtomatik eslatma.\n\n"
        "Avval bitta aniq 'og'riq'ni hal qiling — shunda odamlar to'lashga tayyor bo'ladi.",
    ),
    (
        ("biznes", "business", "sotuv", "mijoz", "marketing", "reklama", "smm", "trafik"),
        "💡 Biznes uchun eng ishonchli oqim: katalog → savatcha → buyurtma → to'lov → "
        "eslatma. Mijozni bot ichida ushlab turish uchun 3 ta narsa kerak: tezkor javob, "
        "aniq narx va keyingi qadamni ko'rsatadigan tugma. CRM va SMM botlari bilan "
        "qayta sotuvni avtomatlashtiring.",
    ),
    (
        ("ai", "chatgpt", "sun'iy", "gpt", "assistent"),
        "🧠 AI bot yordamchilari savol-javob, kontent, tarjima va tahlil uchun foydali. "
        "Tuzilma maslahati: /start → vazifa tanlash → natija → 'yana'/'tahrirlash' tugmalari. "
        "Mini App ichidagi 'AI Bot Yasash' bo'limida shablon tanlab, tayyor komandalar "
        "va sozlash bosqichlarini olishingiz mumkin.",
    ),
    (
        ("crypto", "kripto", "bitcoin", "trading", "invest"),
        "₿ Crypto botlari narx kuzatish, portfel va ogohlantirish uchun yaxshi. "
        "Tuzilma: /price, /portfolio, /alerts, /help. Monetizatsiya: obuna + signal "
        "paketlari. Xavf haqida aniq ogohlantirish qo'shishni unutmang.",
    ),
    (
        ("yordam", "help", "nima qilasan", "кто ты", "who are you"),
        "Men faqat maslahat beraman — botlarni avtomatik yaratmayman. "
        "Tayyor bot tuzilmasini Mini App ichidagi 'AI Bot Yasash' bo'limida oling. "
        "Bu yerda esa g'oyangizni yozing: men loyiha, tuzilma va monetizatsiya bo'yicha "
        "amaliy maslahat beraman.",
    ),
]

AI_FALLBACKS = [
    "🤖 Amaliy maslahat: avval bitta aniq vazifani tanlang. Menyu 3-4 tugmadan oshmasin: "
    "Boshlash, Katalog/Ma'lumot, Buyurtma/Bron, Aloqa. Keyin foydalanuvchi yo'lini "
    "1 daqiqada sinab ko'ring.",
    "💡 Tuzilma bo'yicha: /start — tanishtirish, /menu — tugmalar, /help — yordam, "
    "va bitta asosiy harakat komandasi. Har bir bosqichda keyingi qadamni ko'rsatadigan "
    "tugma qo'ying.",
    "💰 Monetizatsiya: avval bepul sinov, keyin obuna yoki buyurtma komissiyasi. "
    "Foydalanuvchiga aniq foyda (vaqt tejash, xatolik kamaytirish) ko'rsatilsa, to'lov osonroq bo'ladi.",
    "📌 G'oyangizni bir oz batafsil yozing — kimga mo'ljallangan, qanday harakat bajaradi, "
    "qayerda ishlatiladi? Shunga qarab aniq tuzilma va monetizatsiya taklif qilaman.",
]


def advisor_blueprint(text: str) -> str:
    """Generate practical design/structure/monetization advice from a free-form idea."""
    low = text.lower()
    modules: List[str] = []
    if any(w in low for w in ("do'kon", "savat", "buyurtma", "katalog", "mahsulot", "sotuv")):
        modules.append("Katalog → Savatcha → Buyurtma → To'lov")
    if any(w in low for w in ("bron", "uchrashuv", "buyurtma", "qabul", "serve", "restoran")):
        modules.append("Sana vaqt tanlash → Bron tasdiqlash → Eslatma")
    if any(w in low for w in ("faq", "ma'lumot", "savol", "javob", "yordam")):
        modules.append("FAQ / Savol-javob bazasi")
    if any(w in low for w in ("ai", "gpt", "tahlil", "tasvir", "text", "matn")):
        modules.append("AI so'rov → Natija → Tahrirlash")
    if any(w in low for w in ("crypto", "kripto", "narx", "portfel")):
        modules.append("Narx/portfel → Ogohlantirish → Hisobot")
    if not modules:
        modules = ["Xush kelibsiz → Asosiy menyu → Ma'lumot", "Aloqa / Yordam"]

    commands = [
        "/start — bot bilan tanishtirish va asosiy tugmalar",
        "/menu — doimiy menyuni qayta ko'rsatish",
        "/help — foydalanish tartibi va yordam",
        "/order — asosiy harakatni boshlash (buyurtma/bron/so'rov)",
    ]
    if any(w in low for w in ("admin", "hisobot", "statistika")):
        commands.append("/admin — buyurtmalar va statistika (faqat egalari uchun)")

    money = (
        "Obuna (Standart 60,000 UZS / Ultra Pro 150,000 UZS), buyurtma komissiyasi "
        "yoki premium funksiya (AI tahlil, avtomatik hisobot)."
    )
    return (
        "🧠 <b>AI Bot Maslahatchi tuzilmasi</b>\n\n"
        f"🎯 <b>Maqsad:</b> {esc(text[:180])}\n\n"
        "1️⃣ <b>Foydalanuvchi oqimi</b>\n" + "\n".join(f"• {esc(m)}" for m in modules) + "\n\n"
        "2️⃣ <b>Komandalar</b>\n" + "\n".join(f"• {esc(c)}" for c in commands) + "\n\n"
        "3️⃣ <b>Asosiy tugmalar</b>\n• Boshlash • Katalog/Ma'lumot • Buyurtma/Bron • Aloqa\n\n"
        f"4️⃣ <b>Monetizatsiya</b>\n• {money}\n\n"
        "5️⃣ <b>Keyingi qadam</b>\n"
        "Mini App → '🤖 AI Bot Yasash' bo'limida shu tuzilmani tanlab, tayyor komandalar "
        "va sozlash bosqichlarini oling. Bot shu yerda faqat maslahat beradi."
    )


def ai_reply(text: str) -> str:
    """Smart built-in advisor. Always returns practical Uzbek advice."""
    lowered = text.lower()
    match = re.search(r"tpl_\d{3}", lowered)
    if match:
        template = db.get_template(match.group(0))
        if template:
            return (
                f"🧩 <b>{esc(template['name'])}</b> — {esc(template['category_name'])} kategoriyasidagi "
                f"{'Premium' if template['is_premium'] else 'bepul'} shablon.\n\n"
                f"{esc(template['description'])}\n\n"
                "Maslahat: xush kelibsiz xabarini qisqa qiling, 3-4 ta tugma qo'ying va "
                "bitta aniq harakatni (buyurtma, bron, ma'lumot) sinab ko'ring. "
                "Tayyor tuzilmani Mini App ichidagi 'AI Bot Yasash' bo'limida oling."
            )
    for keywords, reply in AI_RULES:
        if reply == "__special_shablon__":
            if any(w in lowered for w in ("shablon", "template", "katalog", "bot turi")):
                return (
                    f"🏪 Katalogda {db.template_count()} ta shablon, {len(db.categories())} kategoriya bor: "
                    "E-commerce, ChatGPT & AI, SMM, Crypto va boshqalar. "
                    "Mini App ichida shablonni tanlab, 'AI Bot Yasash' bo'limida uning "
                    "asosida bot tuzilmasini oling."
                )
            continue
        if reply == "__special_blueprint__":
            if any(w in lowered for w in ("tuzilma", "structure", "komanda", "command", "qurish", "loyiha", "bot yasash")):
                return advisor_blueprint(text)
            continue
        if any(word in lowered for word in keywords):
            return reply
    if len(text.strip()) >= 35:
        return advisor_blueprint(text)
    return random.choice(AI_FALLBACKS)


async def direct_receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Forward any photo/document from chat straight to the admin for review."""
    message = update.message
    if not (message.photo or message.document):
        return
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    if not context.user_data.get("await_receipt"):
        tier = context.user_data.get("receipt_tier", STANDART)
        if tier not in PLANS or tier == FREE:
            tier = STANDART
        plan = PLANS[tier]
        file_id = (
            message.photo[-1].file_id
            if message.photo
            else message.document.file_id
        )
        context.user_data["await_receipt"] = db.add_payment(
            user.id, tier, plan["price"], file_id, message.caption or ""
        )
    await receipt_handler(update, context)
    context.user_data.pop("awaiting_receipt", None)
    context.user_data.pop("receipt_tier", None)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Every text message gets practical bot-advisor advice."""
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    if await receipt_handler(update, context):
        return
    text = (update.message.text or "").strip()
    key = text.lower()
    if key == "💎 tariflar":
        await plans_command(update, context)
        return
    if key == "💳 to'lov / chek yuborish":
        await check_command(update, context)
        return
    if key == "🤖 ai maslahatchi":
        await ai_command(update, context)
        return
    if key == "🚀 bot yasash (mini app)":
        await update.message.reply_text(
            "🚀 Mini App tugmasi orqali bot tuzilmasini yarating. Bu yerda men faqat "
            "maslahat beraman — g'oyangizni yozing.",
            reply_markup=reply_main_keyboard(),
        )
        return
    db.register_message(user.id)
    await update.message.reply_text(
        ai_reply(text), parse_mode=ParseMode.HTML, reply_markup=reply_main_keyboard()
    )


# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Botni ishga tushirish"),
            BotCommand("menu", "Asosiy menyu"),
            BotCommand("ai", "AI Maslahatchi"),
            BotCommand("chek", "Chek yuborish"),
            BotCommand("plans", "Tariflar va narxlar"),
            BotCommand("admin", "Admin panel"),
        ]
    )
    log.info(
        "Venox Yordamchi build %s ready: %s templates, admin %s, card %s",
        BUILD_ID, db.template_count(), ADMIN_ID, PAYMENT_CARD,
    )


def build_application() -> Application:
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    admin_conv = ConversationHandler(
        entry_points=[
            CommandHandler("broadcast", admin_broadcast_start),
            CommandHandler("grant", admin_grant_start),
            CallbackQueryHandler(admin_broadcast_start, pattern="^admin_broadcast$"),
            CallbackQueryHandler(admin_grant_start, pattern="^admin_grant$"),
        ],
        states={
            A_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_send)],
            A_GRANT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_grant_apply)],
        },
        fallbacks=[CommandHandler("cancel", admin_cancel)],
        per_message=False,
    )

    application.add_handler(admin_conv)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("ai", ai_command))
    application.add_handler(CommandHandler("chek", check_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("plans", plans_command))
    application.add_handler(CommandHandler("usage", usage_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(
        MessageHandler(
            (filters.PHOTO | filters.Document.ALL)
            & ~filters.StatusUpdate.WEB_APP_DATA,
            direct_receipt_handler,
        )
    )
    application.add_handler(
        MessageHandler(filters.ALL & ~filters.StatusUpdate.WEB_APP_DATA, text_handler)
    )
    return application


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured.")
    application = build_application()
    application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
