"""Venox Yordamchi — a production-ready Telegram assistant bot.

Run locally:  python bot.py
Deploy:       use the included render.yaml (Render background worker).
Configuration is read from environment variables; see .env.example.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional, Sequence, Tuple

from telegram import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from database import Database, MESSAGE_LIMIT

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
def _load_dotenv(path: str = ".env") -> None:
    """Minimal stdlib .env loader so local runs need no extra dependency."""
    try:
        with open(path, encoding="utf-8") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(
                    key.strip(), value.strip().strip('"').strip("'")
                )
    except FileNotFoundError:
        pass


_load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is not set. Copy .env.example to .env and fill in your token."
    )
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PAYMENT_CARD = os.getenv("PAYMENT_CARD", "").strip() or "Admin bilan bog'laning"
BOT_NAME = "Venox Yordamchi"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TZ = timezone(timedelta(hours=5))  # Asia/Tashkent (UTC+5)

PLANS: Dict[str, Dict[str, Any]] = {
    "standart": {
        "label": "Standart",
        "amount": 60_000,
        "days": 30,
        "perks": [
            "Cheksiz chat rejimi",
            "Cheksiz kod yozish va bot yasash",
            "Rasm / video / GIF / emoji qo'llab-quvvatlash",
            "Ob-havo va vaqt ma'lumotlari",
        ],
    },
    "ultra": {
        "label": "Ultra",
        "amount": 150_000,
        "days": 90,
        "perks": [
            "Standartning barcha imkoniyatlari",
            "90 kunlik VIP muddat",
            "Murakkab bot va kodi yozish ustuvorligi",
            "Shaxsiy yordam va tezkor javob",
        ],
    },
}

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
)
log = logging.getLogger("venox")
db = Database()

# --------------------------------------------------------------------------- #
# Keyboards
# --------------------------------------------------------------------------- #
def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["💬 Chat", "🤖 Bot yasash"],
            ["💳 Tariflar", "📊 Limitim"],
            ["🌤 Ob-havo", "🕐 Vaqt", "❓ Yordam"],
        ],
        resize_keyboard=True,
    )


def mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💬 Chat qilish", callback_data="mode:chat")],
            [InlineKeyboardButton("🤖 Bot yasash", callback_data="mode:build")],
        ]
    )


def plans_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Standart — 60 000 UZS", callback_data="pay:standart"
                )
            ],
            [InlineKeyboardButton("Ultra — 150 000 UZS", callback_data="pay:ultra")],
        ]
    )


def review_keyboard(payment_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Tasdiqlash",
                    callback_data=f"approve:{payment_id}:{user_id}",
                ),
                InlineKeyboardButton(
                    "❌ Rad etish", callback_data=f"reject:{payment_id}:{user_id}"
                ),
            ]
        ]
    )


# --------------------------------------------------------------------------- #
# Text helpers
# --------------------------------------------------------------------------- #
WITTY_LINES: Sequence[str] = (
    "Men ham bugun motivational post o'qidim — endi hech narsa qila olmayman.",
    "Bu savolga javob berishdan oldin kofe ichishim kerak. Qani, kutib turing ☕",
    "Aqlim bulutlarda, lekin ob-havoni ham bilib beraman.",
    "Men sun'iy intellektman: tabassum qila olmayman, lekin sizni aldash ham qila olmayman.",
    "Men telepat bo'lishni xohlardim, lekin siz xabar yozmaguningizcha hech narsa bilmayman.",
    "Muammo 90% ehtimol bilan kodingizda, qolgan 10% esa men ham bilmayman.",
    "Bugun rejalarim: kod yozish, bot yasash va yana kod yozish. Va albatta sizga yordam berish.",
    "Agar javobim qisqa bo'lsa — bilib qiling, bu ham javob.",
)


def _local_reply(text: str, name: str) -> str:
    low = text.lower()
    if any(w in low for w in ("salom", "assalom", "hi ", "hello", "привет")):
        return f"Assalomu alaykum, {name}! 👋 Men {BOT_NAME}. Nima qilishni xohlaysiz — chatlashamizmi yoki bot yasaymizmi?"
    if any(w in low for w in ("kim", "who are you", "кто ты", "nima qilasan")):
        return (
            f"Men {BOT_NAME} — sizning chat hamkoringiz va bot yasash bo'yicha yordamchingiz. "
            "Matn, rasm, video, GIF va emoji bilan ishlayman, ob-havo va vaqtni aytaman, kod yozaman."
        )
    if "?" in text or any(w in low for w in ("nima", "why", "how", "как", "почему")):
        return (
            f"{random.choice(WITTY_LINES)}\n\n"
            "Qisqa javob: bu haqda ko'proq ma'lumot berishingiz bilan aniqroq javob beraman."
        )
    if any(w in low for w in ("rahmat", "thanks", "спасибо")):
        return "Arzimaydi! 😊 Yana biror narsa kerak bo'lsa — men bu yerda."
    if any(w in low for w in ("kod", "code", "бот", "bot", "yasash", "yasab")):
        return "Kod yozishni xohlaysizmi? 🤖 Bot yasash rejimiga o'ting — sizga tayyor fayllar yuboraman."
    return random.choice(WITTY_LINES)


def _openai_reply(messages: List[Dict[str, str]]) -> str:
    body = json.dumps(
        {
            "model": OPENAI_MODEL,
            "messages": messages,
            "max_tokens": 400,
            "temperature": 0.8,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        data = json.load(response)
    return str(data["choices"][0]["message"]["content"]).strip()


async def ai_reply(text: str, name: str, context: ContextTypes.DEFAULT_TYPE) -> str:
    if OPENAI_API_KEY:
        history: List[Dict[str, str]] = context.user_data.get("history", [])
        system = {
            "role": "system",
            "content": (
                f"Siz {BOT_NAME}, o'zbek tilida so'zlashadigan qisqa, hazil-mutoyiba bilan "
                "javob beradigan yordamchi. Foydalanuvchi: {name}. Qisqa va do'stona bo'ling."
            ).format(name=name),
        }
        history.append({"role": "user", "content": text})
        history = history[-10:]
        try:
            answer = await asyncio.to_thread(_openai_reply, [system, *history])
            history.append({"role": "assistant", "content": answer})
            context.user_data["history"] = history[-10:]
            return answer
        except Exception as exc:  # network / API errors -> local fallback
            log.warning("OpenAI call failed: %s", exc)
    return _local_reply(text, name)


# --------------------------------------------------------------------------- #
# Code generation
# --------------------------------------------------------------------------- #
def _template_echo() -> Dict[str, str]:
    return {
        "bot.py": '''"""Simple echo bot generated by Venox Yordamchi."""
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_TOKEN_HERE")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Assalomu alaykum! Men echo botman.")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(update.message.text)


if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.run_polling()
''',
        "requirements.txt": "python-telegram-bot>=21.0,<22\n",
    }


def _template_weather() -> Dict[str, str]:
    return {
        "bot.py": '''"""Weather bot generated by Venox Yordamchi (Open-Meteo, no API key)."""
import json
import os
import urllib.parse
import urllib.request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_TOKEN_HERE")


def fetch(url):
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.load(response)


async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Shahar nomini yozing: /weather Tashkent")
        return
    city = " ".join(context.args)
    try:
        geo = fetch("https://geocoding-api.open-meteo.com/v1/search?name="
                    + urllib.parse.quote(city) + "&count=1&language=en&format=json")
        place = geo["results"][0]
        data = fetch("https://api.open-meteo.com/v1/forecast?latitude="
                     + str(place["latitude"]) + "&longitude=" + str(place["longitude"])
                     + "&current=temperature_2m,relative_humidity_2m,wind_speed_10m&timezone=auto")
        cur = data["current"]
        await update.message.reply_text(
            f"{place['name']}: {cur['temperature_2m']}°C, "
            f"namlik {cur['relative_humidity_2m']}%, shamol {cur['wind_speed_10m']} km/soat")
    except Exception as exc:
        await update.message.reply_text(f"Ob-havoni ola olmadim: {exc}")


if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("weather", weather))
    app.run_polling()
''',
        "requirements.txt": "python-telegram-bot>=21.0,<22\n",
    }


def _template_admin() -> Dict[str, str]:
    return {
        "bot.py": '''"""Broadcast bot generated by Venox Yordamchi."""
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
users = set()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users.add(update.effective_user.id)
    await update.message.reply_text("Xush kelibsiz! Yangiliklarga obuna bo'ldingiz.")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID or not context.args:
        return
    message = " ".join(context.args)
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=message)
        except Exception:
            pass


if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.run_polling()
''',
        "requirements.txt": "python-telegram-bot>=21.0,<22\n",
    }


def generate_project(prompt: str) -> Tuple[str, Dict[str, str]]:
    low = prompt.lower()
    if any(w in low for w in ("weather", "ob-havo", "погода")):
        return "Ob-havo boti", _template_weather()
    if any(w in low for w in ("admin", "broadcast", "рассыл", "tarqat")):
        return "Broadcast bot", _template_admin()
    return "Echo bot", _template_echo()


async def send_project(
    update: Update, context: ContextTypes.DEFAULT_TYPE, title: str, project: Dict[str, str]
) -> None:
    user_id = update.effective_user.id
    for filename, content in project.items():
        db.save_generated_file(user_id, filename, content)
        await update.effective_message.reply_document(
            document=InputFile(BytesIO(content.encode("utf-8")), filename=filename),
            caption=f"{title} — {filename}",
        )
    await update.effective_message.reply_text(
        "Fayllar tayyor! ✅ Ularni tejab, o'zingizning BOT_TOKEN bilan ishga tushiring. "
        "Yana boshqa bot kerak bo'lsa, talabingizni yozing."
    )


# --------------------------------------------------------------------------- #
# Weather / time
# --------------------------------------------------------------------------- #
def _fetch_json(url: str) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.load(response)


async def fetch_weather(city: str) -> str:
    geo = await asyncio.to_thread(
        _fetch_json,
        "https://geocoding-api.open-meteo.com/v1/search?name="
        + urllib.parse.quote(city)
        + "&count=1&language=en&format=json",
    )
    results = geo.get("results") or []
    if not results:
        return "Bunday shahar topilmadi. Boshqa nom bilan urinib ko'ring."
    place = results[0]
    data = await asyncio.to_thread(
        _fetch_json,
        "https://api.open-meteo.com/v1/forecast?latitude="
        + str(place["latitude"])
        + "&longitude="
        + str(place["longitude"])
        + "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        + "&timezone=auto",
    )
    cur = data["current"]
    return (
        f"🌤 {place['name']}, {place.get('country', '')}: "
        f"{cur['temperature_2m']}°C\n"
        f"Namlik: {cur['relative_humidity_2m']}%\n"
        f"Shamol: {cur['wind_speed_10m']} km/soat\n"
        f"Ob-havo kodi: {cur['weather_code']}"
    )


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name, user.id == ADMIN_ID)
    text = (
        f"Assalomu alaykum! Men *{BOT_NAME}* 👋\n\n"
        "Men siz bilan hazil-mutoyiba bilan suhbatlashaman, kod yozaman va tayyor "
        "bot fayllarini yuboraman. Rasm, video, GIF va emojilarni ham tushunaman.\n\n"
        "Oddiy foydalanuvchilar uchun *25 ta xabar* limiti bor. Cheksiz foydalanish "
        "uchun VIP tarifga obuna bo'ling.\n\n"
        "Nima qilishni xohlaysiz?"
    )
    await update.message.reply_text(
        text, reply_markup=mode_keyboard(), parse_mode=ParseMode.MARKDOWN
    )
    await update.message.reply_text(
        "Quyidagi tugmalardan ham foydalanishingiz mumkin:", reply_markup=main_keyboard()
    )


async def cmd_plans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "💳 *Obuna tariflari*\n\n"
        "💠 *Standart* — 60 000 UZS / 30 kun\n"
        + "\n".join(f"  • {p}" for p in PLANS["standart"]["perks"])
        + "\n\n⭐ *Ultra* — 150 000 UZS / 90 kun\n"
        + "\n".join(f"  • {p}" for p in PLANS["ultra"]["perks"])
        + f"\n\nTo'lov karti: `{PAYMENT_CARD}`\n"
        "To'lov qilgandan so'ng chek (skrinshot) rasm sifatida yuboring — "
        "admin tasdiqlagach VIP faollashadi.\n\n"
        "Tarif tanlang:"
    )
    await update.message.reply_text(
        text, reply_markup=plans_keyboard(), parse_mode=ParseMode.MARKDOWN
    )


async def cmd_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name, user.id == ADMIN_ID)
    db.set_mode(user.id, "chat")
    await update.message.reply_text(
        "💬 Chat rejimiga o'tdik. Endi menga istagan narsangizni yozing — "
        "hazil bilan javob beraman. /plans bilan VIP olishingiz mumkin.",
        reply_markup=main_keyboard(),
    )


async def cmd_build(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name, user.id == ADMIN_ID)
    db.set_mode(user.id, "build")
    await update.message.reply_text(
        "🤖 Bot yasash rejimiga o'tdik. Menga qanday bot kerakligini yozing "
        "(masalan: 'ob-havo boti', 'echo bot', 'broadcast bot') — "
        "tayyor kod fayllarini yuboraman.\n\n"
        "Agar kodingiz bo'lsa, uni ```python ... ``` blokida yuborsangiz, "
        "alohida fayl sifatida saqlab beraman.",
        reply_markup=main_keyboard(),
    )


async def cmd_weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Shahar nomini yozing: /weather Tashkent")
        return
    city = " ".join(context.args)
    await update.message.reply_chat_action(ChatAction.TYPING)
    try:
        await update.message.reply_text(await fetch_weather(city))
    except Exception as exc:
        log.warning("weather failed: %s", exc)
        await update.message.reply_text("Ob-havo ma'lumotini ola olmadim. Keyinroq urinib ko'ring.")


async def cmd_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.now(TZ)
    await update.message.reply_text(
        f"🕐 Hozirgi vaqt (Toshkent): {now:%Y-%m-%d %H:%M:%S} ({now:%A})"
    )


async def cmd_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name, user.id == ADMIN_ID)
    usage = db.usage(user.id)
    if usage["unlimited"]:
        text = f"♾ Siz cheksiz foydalanasiz (VIP/Admin). Jami yuborgan xabarlaringiz: {db.get_user(user.id)['total_messages']}"
    else:
        text = (
            f"📊 Xabar limiti: {usage['used']}/{usage['limit']}\n"
            f"Qoldi: {usage['remaining']} ta xabar.\n"
            "Cheksiz uchun /plans buyrug'iga qarang."
        )
    await update.message.reply_text(text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "❓ *Yordam*\n\n"
        "/start — boshlash\n"
        "/chat — suhbat rejimi\n"
        "/build — bot yasash rejimi\n"
        "/plans — obuna tariflari\n"
        "/weather Shahar — ob-havo\n"
        "/time — vaqt\n"
        "/limit — xabar limiti\n"
        "/admin — admin panel (faqat admin)\n\n"
        "Rasm, video, GIF va emoji yuborishingiz ham mumkin."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Bu buyruq faqat admin uchun.")
        return
    stats = db.stats()
    await update.message.reply_text(
        "🔐 *Admin panel*\n"
        f"Foydalanuvchilar: {stats['users']}\n"
        f"VIP/admin: {stats['vip']}\n"
        f"Kutilayotgan to'lovlar: {stats['pending']}\n"
        f"Yaratilgan fayllar: {stats['files']}",
        parse_mode=ParseMode.MARKDOWN,
    )
    pending = db.pending_payments()
    if not pending:
        await update.message.reply_text("Kutilayotgan to'lov yo'q.")
        return
    for payment in pending:
        user = db.get_user(payment["user_id"]) or {}
        caption = (
            f"To'lov #{payment['id']}\n"
            f"Foydalanuvchi: {user.get('first_name', '?')} "
            f"(@{user.get('username', '?')}) — {payment['user_id']}\n"
            f"Tarif: {payment['plan']} — {payment['amount']} UZS"
        )
        file_id = payment.get("receipt_file_id")
        if file_id:
            await update.effective_message.reply_photo(
                photo=file_id,
                caption=caption,
                reply_markup=review_keyboard(payment["id"], payment["user_id"]),
            )
        else:
            await update.effective_message.reply_text(
                caption, reply_markup=review_keyboard(payment["id"], payment["user_id"])
            )


# --------------------------------------------------------------------------- #
# Message handlers
# --------------------------------------------------------------------------- #
async def _button_route(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    normalized = text.strip().lower()
    if normalized in ("💬 chat", "chat", "💬 chat qilish"):
        await cmd_chat(update, context)
        return True
    if normalized in ("🤖 bot yasash", "bot yasash", "bot", "build"):
        await cmd_build(update, context)
        return True
    if normalized in ("💳 tariflar", "tariflar", "plans"):
        await cmd_plans(update, context)
        return True
    if normalized in ("📊 limitim", "limit", "limitim"):
        await cmd_limit(update, context)
        return True
    if normalized in ("🌤 ob-havo", "ob-havo", "ob havo"):
        await update.message.reply_text("Shahar nomini yozing: /weather Tashkent")
        return True
    if normalized in ("🕐 vaqt", "vaqt", "time"):
        await cmd_time(update, context)
        return True
    if normalized in ("❓ yordam", "yordam", "help"):
        await cmd_help(update, context)
        return True
    return False


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = (update.message.text or "").strip()
    record = db.ensure_user(user.id, user.username, user.first_name, user.id == ADMIN_ID)

    if await _button_route(update, context, text):
        return

    # Explicit fenced code -> save as a file.
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            code = parts[1]
            lang = ""
            if "\n" in code:
                first, rest = code.split("\n", 1)
                if first.strip().isalpha() and len(first.strip()) <= 12:
                    lang = first.strip()
                    code = rest
            filename = f"snippet.{lang or 'txt'}"
            db.save_generated_file(user.id, filename, code)
            await update.effective_message.reply_document(
                document=InputFile(BytesIO(code.encode("utf-8")), filename=filename),
                caption="Kodingiz fayl sifatida saqlandi ✅",
            )
            return

    mode = record["mode"]
    if mode == "welcome":
        await update.message.reply_text(
            "Xush kelibsiz! Siz bilan nima qilishni xohlaysiz?",
            reply_markup=mode_keyboard(),
        )
        return

    allowed, count = db.register_message(user.id)
    if not allowed:
        await update.message.reply_text(
            f"🚫 Sizning {MESSAGE_LIMIT} xabar limitingiz tugadi. "
            "Cheksiz suhbat va kod yozish uchun VIP tarifga obuna bo'ling.",
            reply_markup=plans_keyboard(),
        )
        return

    await update.message.reply_chat_action(ChatAction.TYPING)
    if mode == "build":
        title, project = generate_project(text)
        await send_project(update, context, title, project)
    else:
        answer = await ai_reply(text, user.first_name or "do'stim", context)
        if not db.is_unlimited(user.id):
            answer += f"\n\n_{count}/{MESSAGE_LIMIT} xabar ishlatildi._"
        await update.message.reply_text(answer, parse_mode=ParseMode.MARKDOWN)


def _payment_caption(payment: Dict[str, Any], user: Any) -> str:
    return (
        f"💳 Yangi to'lov cheki #{payment['id']}\n"
        f"Foydalanuvchi: {user.first_name or '?'} (@{user.username or '?'}) — {user.id}\n"
        f"Tarif: {payment['plan']} — {payment['amount']} UZS\n"
        "Tasdiqlasangiz VIP faollashadi."
    )


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name, user.id == ADMIN_ID)
    plan_key = context.user_data.get("awaiting_receipt")

    if plan_key in PLANS:
        plan = PLANS[plan_key]
        file_id = update.message.photo[-1].file_id
        payment_id = db.add_payment(user.id, plan_key, plan["amount"], file_id)
        context.user_data.pop("awaiting_receipt", None)
        await update.message.reply_text(
            "Chekingiz admina yuborildi ✅. Tasdiqlangach sizga xabar beraman."
        )
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=file_id,
            caption=_payment_caption(db.get_payment(payment_id), user),
            reply_markup=review_keyboard(payment_id, user.id),
        )
        return

    await update.message.reply_text(
        "📸 Rasmni ko'rdim! Uni qanday ishlatishni xohlaysiz — chat qilamizmi yoki bot yasaymizmi?",
        reply_markup=mode_keyboard(),
    )


async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎬 Videoni qabul qildim! Men matn, rasm, video, GIF va emoji bilan ishlayman. "
        "Chat yoki bot yasash rejimini tanlang.",
        reply_markup=mode_keyboard(),
    )


async def on_animation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎞 GIF ko'rdim, kayfiyatim ko'tarildi! 😄 Chatlashamizmi yoki bot yasaymizmi?",
        reply_markup=mode_keyboard(),
    )


async def on_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sticker = update.message.sticker
    if sticker and sticker.emoji:
        await update.message.reply_text(f"{sticker.emoji} Emoji qabul qilindi! Yana yuboring 😄")
    else:
        await update.message.reply_text("Stiker qabul qilindi! 😄")


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    content = (
        f"📄 Fayl qabul qilindi: {document.file_name}\n"
        "Agar bu kod bo'lsa, uni matn sifatida ```python ... ``` blokida yuborsangiz, "
        "tayyor .py fayl qilib beraman."
    )
    await update.message.reply_text(content)


# --------------------------------------------------------------------------- #
# Callback handlers
# --------------------------------------------------------------------------- #
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query: CallbackQuery = update.callback_query
    await query.answer()
    data = query.data or ""
    user = query.from_user

    if data.startswith("mode:"):
        mode = data.split(":", 1)[1]
        db.ensure_user(user.id, user.username, user.first_name, user.id == ADMIN_ID)
        db.set_mode(user.id, mode)
        if mode == "chat":
            text = "💬 Chat rejimi yoqildi. Yozing, menga nima deysiz?"
        else:
            text = "🤖 Bot yasash rejimi yoqildi. Qanday bot kerakligini yozing."
        await query.edit_message_text(text)
        return

    if data.startswith("pay:"):
        plan_key = data.split(":", 1)[1]
        if plan_key not in PLANS:
            return
        plan = PLANS[plan_key]
        context.user_data["awaiting_receipt"] = plan_key
        await query.edit_message_text(
            f"*{plan['label']}* tarifini tanladingiz — {plan['amount']} UZS\n\n"
            f"To'lov karti: `{PAYMENT_CARD}`\n\n"
            "To'lov qilgach, chek (skrinshot) ni rasm sifatida yuboring. "
            "Admin tasdiqlagach VIP faollashadi.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if data.startswith(("approve:", "reject:")):
        if user.id != ADMIN_ID:
            await query.answer("Faqat admin tasdiqlashi mumkin!", show_alert=True)
            return
        action, payment_id_s, user_id_s = data.split(":")
        payment_id, target_id = int(payment_id_s), int(user_id_s)
        payment = db.get_payment(payment_id)
        if not payment or payment["status"] != "pending":
            await query.edit_message_caption(caption="Bu to'lov allaqachon ko'rib chiqilgan.")
            return
        if action == "approve":
            db.set_payment_status(payment_id, "approved")
            plan = PLANS.get(payment["plan"], PLANS["standart"])
            db.set_vip(target_id, days=plan["days"])
            await query.edit_message_caption(caption=f"✅ To'lov #{payment_id} tasdiqlandi. VIP faollashdi.")
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🎉 To'lovingiz tasdiqlandi! Sizga *{plan['label']}* VIP huquqi berildi ({plan['days']} kun). Endi cheksiz foydalaning.",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            db.set_payment_status(payment_id, "rejected")
            await query.edit_message_caption(caption=f"❌ To'lov #{payment_id} rad etildi.")
            await context.bot.send_message(
                chat_id=target_id,
                text="Kechirasiz, to'lovingiz rad etildi. Savollar bo'lsa admin bilan bog'laning.",
            )
        return


# --------------------------------------------------------------------------- #
# App entrypoint
# --------------------------------------------------------------------------- #
async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Botni boshlash"),
            BotCommand("chat", "Suhbat rejimi"),
            BotCommand("build", "Bot yasash rejimi"),
            BotCommand("plans", "Obuna tariflari"),
            BotCommand("weather", "Ob-havo: /weather Tashkent"),
            BotCommand("time", "Vaqt"),
            BotCommand("limit", "Xabar limiti"),
            BotCommand("help", "Yordam"),
        ]
    )
    log.info("Bot initialized")


def build_application() -> Application:
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("plans", cmd_plans))
    application.add_handler(CommandHandler("chat", cmd_chat))
    application.add_handler(CommandHandler("build", cmd_build))
    application.add_handler(CommandHandler("weather", cmd_weather))
    application.add_handler(CommandHandler("time", cmd_time))
    application.add_handler(CommandHandler("limit", cmd_limit))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("admin", cmd_admin))

    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(MessageHandler(filters.PHOTO, on_photo))
    application.add_handler(MessageHandler(filters.VIDEO, on_video))
    application.add_handler(MessageHandler(filters.ANIMATION, on_animation))
    application.add_handler(MessageHandler(filters.Sticker.ALL, on_sticker))
    application.add_handler(MessageHandler(filters.Document.ALL, on_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    return application


def main() -> None:
    log.info("Starting %s", BOT_NAME)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    application = build_application()
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
