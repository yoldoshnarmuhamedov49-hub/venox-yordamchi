"""Venox Yordamchi — SaaS Telegram Bot Constructor.

Features
--------
* Web Mini App platform with 100+ ready-made bot templates
* Custom bot builder (step-by-step conversation)
* Free / Standart / Ultra (Pro) subscription tiers
* Admin (VIP, unlimited) panel with manual receipt verification
* Built-in Web Mini App HTTP server for Render / any ASGI-free host

Run locally (Telegram bot + Web Mini App in one process):
    python bot.py

HTTP-only maintenance mode (optional):
    python bot.py --webapp

Configuration is read from environment variables; see .env.example.
"""

from __future__ import annotations

import base64
import html
import json
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from telegram import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
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
    MINI_APP_URL,
    PAYMENT_CARD,
    PLANS,
    STANDART,
    TZ,
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

APP_URL = (MINI_APP_URL or os.getenv("RENDER_EXTERNAL_URL", "")).strip().rstrip("/")

B_NAME, B_WELCOME, B_BUTTONS, B_ANSWER, B_CONFIRM = range(5)
A_BROADCAST, A_GRANT = range(10, 12)
BUILD_STATE: Dict[str, Any] = {}

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


def make_bot_url(bot_id: int, config: Dict[str, Any]) -> str:
    """Build a self-contained Mini App link (config encoded in the URL)."""
    payload = {
        "name": config.get("name", "Bot"),
        "welcome": config.get("welcome", ""),
        "buttons": config.get("buttons", []),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{APP_URL}/b/{bot_id}?c={encoded}"


# --------------------------------------------------------------------------- #
# Keyboards
# --------------------------------------------------------------------------- #
def reply_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["🏪 Kutubxona", "🤖 Bot yasash"],
            ["💳 Tariflar", "📊 Limitim"],
            ["📦 Botlarim", "❓ Yordam"],
        ],
        resize_keyboard=True,
    )


def main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                f"🏪 Botlar kutubxonasi ({db.template_count()})", callback_data="catalog"
            )
        ],
        [
            InlineKeyboardButton("🤖 Bot yaratish", callback_data="build"),
            InlineKeyboardButton("📦 Mening botlarim", callback_data="mybots"),
        ],
        [
            InlineKeyboardButton("💳 Tariflar", callback_data="plans"),
            InlineKeyboardButton("📊 Limitim", callback_data="usage"),
        ],
        [InlineKeyboardButton("❓ Yordam", callback_data="help")],
    ]
    if APP_URL:
        rows.insert(
            1,
            [InlineKeyboardButton("🚀 Mini App ni ochish", web_app=WebAppInfo(url=APP_URL))],
        )
    if db.is_admin(user_id):
        rows.append([InlineKeyboardButton("⚙️ Admin panel", callback_data="admin")])
    rows.append([InlineKeyboardButton("❌ Menyuni yopish", callback_data="close")])
    return InlineKeyboardMarkup(rows)


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
            "Men <b>Venox Yordamchi</b> — Web Mini App platformasi, "
            f"<b>{db.template_count()}+ tayyor bot shabloni</b> va o'zingizning "
            "botingizni qurish quruvchisi.\n\n"
            f"Sizning tarifingiz: {tier_label(db.effective_tier(user_id))}\n"
            "Quyidagi bo'limlardan birini tanlang:"
        )
        return text, main_menu_keyboard(user_id)

    if view == "catalog":
        categories = db.categories()
        rows = []
        for cat in categories:
            rows.append(
                [
                    InlineKeyboardButton(
                        f"{cat['icon']} {cat['name']} ({cat['total']})",
                        callback_data=f"cat:{cat['key']}",
                    )
                ]
            )
        rows.append([InlineKeyboardButton("🔍 Barcha shablonlar", callback_data="cat:all")])
        rows.append([InlineKeyboardButton("🏠 Asosiy menyu", callback_data="menu")])
        text = (
            "🏪 <b>Botlar kutubxonasi</b>\n\n"
            f"Jami <b>{db.template_count()}</b> ta tayyor bot shabloni mavjud. "
            "Kategoriyani tanlang yoki mini app orqali qidirib toping."
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
            "Shablondan bot yaratish uchun tugmani bosing — u sizning "
            "botlar ro'yxatingizga qo'shiladi."
        )
        markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("➕ Shablon asosida bot yaratish", callback_data=f"create:{key}")],
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
        if bot.get("mini_app_url"):
            text += f"\n🌐 Mini App: {esc(bot['mini_app_url'])}"
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
            f"🌐 Mini App: {'ha' if limits['web_app'] else 'yo‘q'}\n"
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
            "• <b>🏪 Kutubxona</b> — 100+ tayyor bot shablonlaridan birini tanlab, "
            "bir necha soniyada bot yaratish.\n"
            "• <b>🤖 Bot yaratish</b> — o'zingizning botingizni qadam-baqadam qurish.\n"
            "• <b>📦 Botlarim</b> — yaratgan botlaringizni boshqarish, nashr qilish "
            "va JSON ko'rinishida yuklab olish.\n"
            "• <b>💳 Tariflar</b> — Free, Standart va Ultra/Pro rejalari.\n"
            "• <b>📊 Limitim</b> — cheklovlar va foydalanish statistikasi.\n\n"
            "Buyruqlar: /start, /menu, /build, /plans, /usage, /admin\n"
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
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    await update.message.reply_text(
        "Menu tayyor 👇", reply_markup=reply_main_keyboard()
    )
    await send_view(update, context, "menu")


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db.ensure_user(update.effective_user.id, update.effective_user.username, update.effective_user.first_name)
    await send_view(update, context, "menu")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_view(update, context, "help")


async def plans_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_view(update, context, "plans")


async def usage_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_view(update, context, "usage")


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

    if data.startswith("create:"):
        key = data.split(":", 1)[1]
        template = db.get_template(key)
        if not template:
            await query.answer("Shablon topilmadi.", show_alert=True)
            return
        limits = db.limits(user.id)
        if template["is_premium"] and not limits["premium_templates"]:
            await query.answer(
                "Bu Premium shablon. Standart yoki Ultra tarifiga o'ting: /plans",
                show_alert=True,
            )
            return
        if not check_limit(limits["bots"], db.count_bots(user.id)):
            await query.answer("Botlar soni limitiga yetdingiz. /plans", show_alert=True)
            return
        config = dict(template["config"])
        config["source_template"] = key
        created = db.create_bot(
            user.id, template["name"], config, template_key=key, source="template"
        )
        if APP_URL:
            db.update_bot(
                created["id"], user.id, mini_app_url=make_bot_url(created["id"], config)
            )
        await query.answer("Bot yaratildi! ✅")
        await edit_view(query, "bot", str(created["id"]))
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
        if not APP_URL:
            await query.answer(
                "Mini App URL sozlanmagan (MINI_APP_URL / RENDER_EXTERNAL_URL).",
                show_alert=True,
            )
            return
        url = make_bot_url(bot_id, bot["config"])
        db.update_bot(bot_id, user.id, status="published", mini_app_url=url)
        await query.answer("Bot nashr qilindi! 🚀")
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
        await edit_message_text_safe(query, f"🗑 Bot #{bot_id} ni o'chirishni tasdiqlaysizmi?", markup)
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

    if data == "build":
        if not db.limits(user.id)["custom_builder"]:
            await query.answer("Custom quruvchi Standart/Ultra tarifida mavjud: /plans", show_alert=True)
            return
        if not check_limit(db.limits(user.id)["bots"], db.count_bots(user.id)):
            await query.answer("Botlar soni limitiga yetdingiz. /plans", show_alert=True)
            return
        BUILD_STATE[user.id] = {}
        context.user_data["build"] = {"stage": "name"}
        await edit_message_text_safe(
            query,
            "🤖 <b>Custom bot quruvchi</b>\n\n1-qadam: botingiz nomini yuboring.",
            InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor qilish", callback_data="build_cancel")]]),
        )
        return B_NAME

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
        message = f"✏️ Bot #{bot_id} yangilandi."
    else:
        bot = db.create_bot(user.id, state["name"], config, source="custom")
        bot_id = bot["id"]
        if APP_URL:
            db.update_bot(bot_id, user.id, mini_app_url=make_bot_url(bot_id, config))
        message = f"🤖 Bot #{bot_id} yaratildi!"
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
# Messages: receipts, Web App data, chat
# --------------------------------------------------------------------------- #
async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    raw = update.message.web_app_data.data or "{}"
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = {"action": "unknown"}
    action = payload.get("action")
    if action == "template":
        key = payload.get("key", "")
        template = db.get_template(key)
        if not template:
            await update.message.reply_text("❌ Shablon topilmadi.")
            return
        limits = db.limits(user.id)
        if template["is_premium"] and not limits["premium_templates"]:
            await update.message.reply_text("👑 Bu Premium shablon. /plans orqali tarif oling.")
            return
        if not check_limit(limits["bots"], db.count_bots(user.id)):
            await update.message.reply_text("🤖 Botlar limitiga yetdingiz. /plans")
            return
        config = dict(template["config"])
        config["source_template"] = key
        bot = db.create_bot(user.id, template["name"], config, template_key=key)
        if APP_URL:
            db.update_bot(bot["id"], user.id, mini_app_url=make_bot_url(bot["id"], config))
        text, markup = build_view(user.id, "bot", str(bot["id"]))
        await update.message.reply_text(text=text, reply_markup=markup, parse_mode=ParseMode.HTML)
    elif action == "plan":
        tier = str(payload.get("tier", ""))
        if tier not in PLANS:
            await update.message.reply_text("❌ Tarif topilmadi.")
            return
        if tier == FREE:
            await update.message.reply_text(
                "🆓 Free tarifi bepul. /build orqali botingizni yaratishingiz mumkin.",
                reply_markup=main_menu_keyboard(user.id),
            )
            return
        text, markup = build_view(user.id, "pay", tier)
        await update.message.reply_text(text=text, reply_markup=markup, parse_mode=ParseMode.HTML)
    elif action == "custom_request":
        name = str(payload.get("name", "")).strip()
        contact = str(payload.get("contact", "")).strip()
        kind = str(payload.get("type", "")).strip()
        deadline = str(payload.get("deadline", "")).strip()
        description = str(payload.get("description", "")).strip()
        if not name or not contact or not description:
            await update.message.reply_text("❌ Buyurtma ma'lumotlari to'liq emas.")
            return
        admin_text = (
            "🛠 <b>Yangi maxsus bot buyurtmasi</b>\n"
            f"👤 Mijoz: {esc(user.first_name)} (@{esc(user.username or 'yo‘q')}, {user.id})\n"
            f"📌 Nomi: {esc(name)}\n"
            f"🔧 Turi: {esc(kind)}\n"
            f"⏰ Muddat: {esc(deadline)}\n"
            f"📞 Aloqa: {esc(contact)}\n\n"
            f"📝 Tavsif:\n{esc(description)}"
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
    elif action == "bot_open":
        await update.message.reply_text(
            f"🌐 Mini App orqali bot #{payload.get('id', '?')} ochildi: {esc(payload.get('label', ''))}"
        )
    else:
        await update.message.reply_text("Mini App ma'lumoti qabul qilindi.")


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


SIMPLE_REPLIES = {
    "salom": "Assalomu alaykum! Men Venox Yordamchi. /menu orqali bot yaratishingiz mumkin.",
    "hi": "Hello! /menu — barcha imkoniyatlar shu yerda.",
    "rahmat": "Arzimaydi! 😊 Yana biror narsa kerak bo'lsa, /menu.",
    "bola": "Bot yaratish uchun /build yoki kutubxonadagi 100+ shablondan foydalaning.",
}


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    if await receipt_handler(update, context):
        return
    text = (update.message.text or "").strip()
    shortcuts = {
        "🏪 kutubxona": "catalog",
        "🤖 bot yasash": "build",
        "💳 tariflar": "plans",
        "📊 limitim": "usage",
        "📦 botlarim": "mybots",
        "❓ yordam": "help",
    }
    key = text.lower()
    if key in shortcuts:
        view = shortcuts[key]
        if view == "build":
            await build_start(update, context)
        else:
            await send_view(update, context, view)
        return
    if text.startswith("/"):
        await update.message.reply_text("Noma'lum buyruq. /menu ni sinab ko'ring.")
        return
    allowed, used, cap = db.register_message(user.id)
    if not allowed:
        await update.message.reply_text(
            "📊 Kunlik xabar limitiga yetdingiz. "
            "Cheksiz muloqot uchun /plans orqali tarif oling.",
            reply_markup=reply_main_keyboard(),
        )
        return
    lowered = text.lower()
    reply = next((v for k, v in SIMPLE_REPLIES.items() if k in lowered), None)
    if reply is None:
        reply = (
            "Men bot yaratish bo'yicha yordamchiman 🤖\n"
            "Savolingizni aniqroq yozing yoki /menu orqali kerakli bo'limni tanlang."
        )
    suffix = "" if cap is None else f"\n\n📊 Bugun: {used}/{cap} xabar."
    await update.message.reply_text(reply + suffix)


# --------------------------------------------------------------------------- #
# Web Mini App HTTP server
# --------------------------------------------------------------------------- #
INDEX_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

BOT_HTML = """<!doctype html>
<html lang="uz"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__NAME__</title><script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>body{margin:0;font-family:-apple-system,system-ui,sans-serif;background:#0f172a;color:#e2e8f0;padding:20px}h1{font-size:20px}.msg{background:#1e293b;border-radius:14px;padding:14px;margin:16px 0;line-height:1.5}.btn{display:block;width:100%;padding:12px;margin:8px 0;border:0;border-radius:12px;background:#6366f1;color:#fff;font-size:15px;cursor:pointer}.tag{font-size:11px;opacity:.6}</style></head>
<body><h1>🤖 __NAME__</h1><div class="tag">Venox Yordamchi orqali yaratilgan bot</div><div class="msg">__WELCOME__</div><div id="buttons">__BUTTONS__</div>
<script>var tg=window.Telegram?Telegram.WebApp:null;if(tg)tg.expand();function press(l){var p=JSON.stringify({action:'bot_open',id:__ID__,label:l});if(tg){tg.sendData(p);tg.close();}else alert(l);}var bs=document.querySelectorAll('.btn');for(var i=0;i<bs.length;i++){(function(b){b.onclick=function(){press(b.getAttribute('data-label'));};})(bs[i]);}</script>
</body></html>"""


class MiniAppHandler(BaseHTTPRequestHandler):
    """Serves index.html and published bot pages without external dependencies."""

    protocol_version = "HTTP/1.1"
    db_store: Database = db

    def _render(self) -> Tuple[int, str, str]:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in {"/", "/index.html"}:
            data = [
                {
                    "key": t["key"],
                    "name": t["name"],
                    "icon": t["icon"],
                    "category_name": t["category_name"],
                    "description": t["description"],
                    "premium": t["is_premium"],
                }
                for t in self.db_store.templates()
            ]
            prices = [
                {
                    "key": p["key"],
                    "label": p["label"],
                    "emoji": p["emoji"],
                    "price": p["price"],
                    "days": p["days"],
                    "perks": p["perks"],
                }
                for p in (PLANS[FREE], PLANS[STANDART], PLANS[ULTRA])
            ]
            try:
                with open(INDEX_HTML_PATH, encoding="utf-8") as handle:
                    body = handle.read()
            except OSError as exc:
                log.error("index.html is missing: %s", exc)
                body = "<h1>Venox Yordamchi</h1><p>index.html topilmadi.</p>"
            body = (
                body.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
                .replace("__PRICES__", json.dumps(prices, ensure_ascii=False).replace("</", "<\\/"))
                .replace("__CARD__", html.escape(PAYMENT_CARD))
                .replace("__ADMIN__", html.escape(ADMIN_USERNAME))
            )
            return 200, "text/html; charset=utf-8", body

        if path.startswith("/b/"):
            try:
                bot_id = int(path.split("/")[2])
            except (ValueError, IndexError):
                return 404, "text/plain; charset=utf-8", "Not found"
            cfg: Optional[Dict[str, Any]] = None
            name = ""
            query = parse_qs(urlparse(self.path).query)
            token = query.get("c", [""])[0]
            if token:
                try:
                    raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
                    decoded = json.loads(raw.decode("utf-8"))
                    if isinstance(decoded, dict):
                        cfg = decoded
                        name = str(decoded.get("name", ""))
                except (ValueError, UnicodeDecodeError) as exc:
                    log.debug("bad mini app token: %s", exc)
            if cfg is None:
                record = self.db_store.get_bot(bot_id)
                if not record:
                    return 404, "text/plain; charset=utf-8", "Not found"
                cfg, name = record["config"], record["name"]
            buttons = "".join(
                f'<button class="btn" data-label="{html.escape(str(b), quote=True)}">'
                f"{html.escape(str(b))}</button>"
                for b in cfg.get("buttons", [])
            )
            body = (
                BOT_HTML.replace("__NAME__", html.escape(name))
                .replace("__WELCOME__", html.escape(str(cfg.get("welcome", ""))).replace("\n", "<br>"))
                .replace("__BUTTONS__", buttons)
                .replace("__ID__", str(bot_id))
            )
            return 200, "text/html; charset=utf-8", body

        if path == "/health":
            payload = json.dumps({"status": "ok", "templates": self.db_store.template_count()})
            return 200, "application/json; charset=utf-8", payload
        return 404, "text/plain; charset=utf-8", "Not found"

    def _respond(self, include_body: bool = True) -> None:
        try:
            status, content_type, body = self._render()
        except Exception:
            log.exception("Mini App render failed for %s", self.path)
            status, content_type = 500, "text/plain; charset=utf-8"
            body = "Internal Server Error"
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if include_body:
            self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        self._respond()

    def do_HEAD(self) -> None:  # noqa: N802
        self._respond(include_body=False)

    def log_message(self, fmt: str, *args: Any) -> None:
        log.info("webapp %s - %s", self.address_string(), fmt % args)


def create_webapp_server() -> ThreadingHTTPServer:
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), MiniAppHandler)
    log.info("Web Mini App listening on 0.0.0.0:%s", port)
    return server


def start_webapp() -> ThreadingHTTPServer:
    """Start the HTTP server in a daemon thread alongside the Telegram bot."""
    server = create_webapp_server()
    threading.Thread(
        target=server.serve_forever, name="venox-miniapp", daemon=True
    ).start()
    return server


def run_webapp() -> None:
    """HTTP-only mode: serve in the main thread so Render sees a live port."""
    server = create_webapp_server()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Botni ishga tushirish"),
            BotCommand("menu", "Asosiy menyu"),
            BotCommand("build", "Custom bot yaratish"),
            BotCommand("plans", "Tariflar va narxlar"),
            BotCommand("usage", "Mening limitim"),
            BotCommand("admin", "Admin panel"),
            BotCommand("cancel", "Quruvchidan chiqish"),
        ]
    )
    log.info(
        "Venox Yordamchi ready: %s templates, admin %s, card %s",
        db.template_count(), ADMIN_ID, PAYMENT_CARD,
    )


def build_application() -> Application:
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    builder_conv = ConversationHandler(
        entry_points=[
            CommandHandler("build", build_start),
            CallbackQueryHandler(build_start, pattern="^build$"),
        ],
        states={
            B_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, build_name)],
            B_WELCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, build_welcome)],
            B_BUTTONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, build_buttons)],
            B_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, build_answer)],
            B_CONFIRM: [CallbackQueryHandler(build_save, pattern="^build_save$")],
        },
        fallbacks=[
            CommandHandler("cancel", build_cancel),
            CallbackQueryHandler(build_cancel, pattern="^build_cancel$"),
        ],
        per_message=False,
    )

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

    application.add_handler(builder_conv)
    application.add_handler(admin_conv)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("plans", plans_command))
    application.add_handler(CommandHandler("usage", usage_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.WEB_APP_DATA, text_handler))
    return application


def main() -> None:
    # The dashboard does not need a Telegram token; check it only for bot mode.
    if "--webapp" in sys.argv[1:]:
        run_webapp()
        return
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured.")
    start_webapp()
    application = build_application()
    application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
