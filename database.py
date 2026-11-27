"""Storage and shared configuration for the Venox Yordamchi SaaS platform.

The module is intentionally dependency free (only the standard library) so it
can be imported by both the Telegram worker and the Web Mini App server.

SQLite is used by default.  Set ``DATABASE_PATH`` to a path on a persistent
volume when deploying so accounts, bots and payment records survive restarts.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional


def _load_dotenv(path: str = ".env") -> None:
    """Minimal stdlib .env loader; real environment variables take priority."""
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

# --------------------------------------------------------------------------- #
# Configuration (environment variables always win over these local defaults)
# --------------------------------------------------------------------------- #
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "8527026238"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "THE_VENOX").lstrip("@")
PAYMENT_CARD = os.getenv("PAYMENT_CARD", "5614 6830 1549 1525").strip()
MINI_APP_URL = os.getenv("MINI_APP_URL", "").strip().rstrip("/")
GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip()
DEFAULT_DB_PATH = os.getenv("DATABASE_PATH", "venox.db")

# Asia/Tashkent is UTC+5 and has no daylight saving time.
TZ = timezone(timedelta(hours=5))

FREE = "free"
STANDART = "standart"
ULTRA = "ultra"

PLANS: Dict[str, Dict[str, Any]] = {
    FREE: {
        "key": FREE,
        "label": "Free",
        "emoji": "🆓",
        "price": 0,
        "days": 0,
        "description": "Bepul boshlang'ich reja",
        "perks": [
            "1 ta bot yaratish",
            "24 ta bepul shablon",
            "Kuniga 10 ta xabar",
            "Asosiy yordam",
        ],
    },
    STANDART: {
        "key": STANDART,
        "label": "Standart",
        "emoji": "✅",
        "price": 60_000,
        "days": 30,
        "description": "Eng mashhur reja — 30 kun",
        "perks": [
            "10 tagacha bot",
            "100+ shablon — hammasi",
            "Cheksiz xabar va so'rov",
            "Custom bot quruvchi",
            "Web Mini App ulanishi",
        ],
    },
    ULTRA: {
        "key": ULTRA,
        "label": "Ultra Pro",
        "emoji": "👑",
        "price": 150_000,
        "days": 90,
        "description": "Professional reja — 90 kun",
        "perks": [
            "Cheksiz botlar",
            "Barcha shablonlar + custom quruvchi",
            "Cheksiz xabar va so'rov",
            "Ustuvor yordam va tezkor javob",
            "Shaxsiy Web Mini App",
            "VIP status va barcha kelgusi funksiyalar",
        ],
    },
}

TIER_LIMITS: Dict[str, Dict[str, Any]] = {
    FREE: {
        "bots": 1,
        "premium_templates": False,
        "custom_builder": False,
        "daily_messages": 10,
        "web_app": False,
        "priority": False,
    },
    STANDART: {
        "bots": 10,
        "premium_templates": True,
        "custom_builder": True,
        "daily_messages": None,
        "web_app": True,
        "priority": False,
    },
    ULTRA: {
        "bots": None,
        "premium_templates": True,
        "custom_builder": True,
        "daily_messages": None,
        "web_app": True,
        "priority": True,
    },
}

# --------------------------------------------------------------------------- #
# 100+ ready-made bot templates
# --------------------------------------------------------------------------- #
CATEGORIES: List[Dict[str, str]] = [
    {"key": "ecommerce", "name": "E-commerce", "icon": "🛒"},
    {"key": "education", "name": "Ta'lim", "icon": "🎓"},
    {"key": "content", "name": "Kontent & Yangiliklar", "icon": "📰"},
    {"key": "ai", "name": "AI & Utility", "icon": "🤖"},
    {"key": "games", "name": "O'yin & Zavq", "icon": "🎮"},
    {"key": "business", "name": "Biznes & CRM", "icon": "💼"},
    {"key": "health", "name": "Sog'liq & Fitness", "icon": "🏥"},
    {"key": "services", "name": "Xizmatlar", "icon": "🏠"},
    {"key": "utility", "name": "Foydali vositalar", "icon": "🔧"},
    {"key": "chatgpt", "name": "ChatGPT & AI", "icon": "🧠"},
    {"key": "smm", "name": "SMM", "icon": "📱"},
    {"key": "crypto", "name": "Crypto", "icon": "₿"},
]

_TEMPLATE_NAMES: Dict[str, List[str]] = {
    "ecommerce": [
        "Onlayn do'kon", "Savatcha bot", "Mahsulot katalogi", "Buyurtma kuzatuv",
        "Chegirma va promokod", "Mahsulot qidiruv", "Wishlist bot", "To'lov hisobi",
        "Yetkazib berish", "Sharhlar boti", "Hisob-faktura", "Ombor hisobi",
    ],
    "education": [
        "Quiz bot", "Kurs boti", "Dars jadvali", "Lug'at bot", "Flashcard bot",
        "Vazifa boti", "Imtihon tayyorgarlik", "Til o'rganish", "Davomat boti",
        "Sertifikat boti", "Kutubxona boti", "Repetitor boti",
    ],
    "content": [
        "Yangiliklar boti", "RSS agregator", "Blog boti", "E'lonlar boti",
        "Kunlik digest", "So'rovnoma boti", "Iqtiboslar boti", "G'oronoskop",
        "Ob-havo boti", "Memlar boti", "Maqolalar boti", "Newsletter boti",
    ],
    "ai": [
        "AI chat bot", "Tarjimon bot", "Matn qisqartiruvchi", "Rasm yaratish",
        "QR kod bot", "Havola qisqartiruvchi", "Kalkulyator", "Valyuta konvertor",
        "Parol generator", "AI avatar", "Matnni ovozga", "Kod yordamchisi",
    ],
    "games": [
        "Trivia bot", "Dice o'yini", "Ruletka", "X o'yini", "Hangman",
        "Kartalar o'yini", "Lotereya", "Slime simulator", "Clicker", "Puzzle bot",
        "Jang o'yini", "Quest bot",
    ],
    "business": [
        "Lead generator", "Uchrashuv boti", "Bron qilish", "Ticketing support",
        "FAQ bot", "Fikr-mulohaza", "Survey bot", "CRM bot", "Hisob-faktura",
        "HR bot", "Vazifalar boti", "Hisobot boti",
    ],
    "health": [
        "Workout bot", "Diyeta boti", "Kaloriya hisoblash", "Eslatma boti",
        "Meditatsiya", "Symptom check", "Dorixona boti", "Qabulga yozilish",
        "Yoga bot", "Qadam hisoblagich", "Suv eslatmasi", "BMI kalkulyator",
    ],
    "services": [
        "Restoran buyurtma", "Mehmonxona bron", "Taksi boti", "Yetkazib berish",
        "Tozalash xizmati", "Go'zallik saloni", "Ko'chmas mulk", "Tadbirlar boti",
        "Kino chipta", "Dorixona buyurtma", "Kir yuvish", "Uy ta'mirlash",
    ],
    "utility": [
        "Fayl konvertor", "Yuklab oluvchi", "Vaqt boti", "Eslatmalar",
        "To-do bot", "Poll bot", "Anonim chat", "Kalendar", "Xarajat hisobi",
        "Odat kuzatuvchisi", "Notepad bot", "Statistika boti",
    ],
    "chatgpt": [
        "ChatGPT yordamchi", "AI kontent yozuvchi", "Kod yordamchisi AI", "AI tarjimon",
        "AI matn qisqartiruvchi", "AI tasvir yaratish", "AI savol-javob", "AI email yozuvchi",
        "AI rejalashtiruvchi", "AI quiz yaratuvchi", "AI shaxsiy murabbiy", "AI tahlilchi",
    ],
    "smm": [
        "SMM panel", "Post rejalashtiruvchi", "Instagram yordamchi", "Kanal boshqaruvchi",
        "SMM hisobot boti", "Auditoriya tahlili", "Kontent kalendari", "Reklama yordamchisi",
        "Obunachi hisobi", "Story yaratuvchi", "Hashtag generator", "Engagement boti",
    ],
    "crypto": [
        "Crypto narx boti", "Portfolio tracker", "Trading signal bot", "Coin ma'lumotlari",
        "Trading ogohlantirish", "Airdrop bot", "Staking kalkulyator", "Gas tracker",
        "NFT yordamchi", "Whale alert", "DEX skreener", "Crypto quiz",
    ],
}


def build_template_catalog() -> List[Dict[str, Any]]:
    """Return the full catalogue of ready-made bot templates.

    Two templates in every category stay free (24 total); the rest require a
    paid plan.  The returned configs are plain JSON-serialisable dictionaries.
    """
    catalog: List[Dict[str, Any]] = []
    index = 0
    for category in CATEGORIES:
        for position, name in enumerate(_TEMPLATE_NAMES[category["key"]]):
            index += 1
            catalog.append(
                {
                    "key": f"tpl_{index:03d}",
                    "name": name,
                    "category": category["key"],
                    "category_name": category["name"],
                    "icon": category["icon"],
                    "description": (
                        f"{name} — {category['name']} sohasi uchun tayyor bot. "
                        "1 daqiqada ishga tushirib, o'zingizga moslashtiring."
                    ),
                    "is_premium": position >= 2,
                    "config": {
                        "name": name,
                        "category": category["key"],
                        "welcome": (
                            f"Assalomu alaykum! 👋\n{name} botiga xush kelibsiz. "
                            "Quyidagi tugmalardan birini tanlang."
                        ),
                        "buttons": ["Boshlash", "Ma'lumot", "Yordam"],
                        "commands": ["/start", "/menu", "/help"],
                        "auto_reply": (
                            f"{name} sizning so'rovingizni qabul qildi. "
                            "Tez orada javob beramiz ✅"
                        ),
                    },
                }
            )
    return catalog


TEMPLATE_CATALOG = build_template_catalog()


def get_tier_limits(tier: str) -> Dict[str, Any]:
    """Return a copy of the limits for ``tier`` (unknown tiers fall back to Free)."""
    return dict(TIER_LIMITS.get(tier, TIER_LIMITS[FREE]))


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
def _now() -> str:
    return datetime.now(TZ).isoformat()


def _today() -> str:
    return datetime.now(TZ).date().isoformat()


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class Database:
    """Thread-safe SQLite wrapper holding users, templates, bots and payments."""

    def __init__(self, path: str = DEFAULT_DB_PATH, seed: bool = True) -> None:
        self.path = path
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()
        if seed:
            self.seed_templates()

    # ------------------------------------------------------------------ #
    # schema / helpers
    # ------------------------------------------------------------------ #
    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id          INTEGER PRIMARY KEY,
                    username         TEXT,
                    first_name       TEXT,
                    tier             TEXT NOT NULL DEFAULT 'free',
                    is_admin         INTEGER NOT NULL DEFAULT 0,
                    is_vip           INTEGER NOT NULL DEFAULT 0,
                    vip_until        TEXT,
                    daily_messages   INTEGER NOT NULL DEFAULT 0,
                    last_message_date TEXT,
                    created_at       TEXT NOT NULL,
                    updated_at       TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS templates (
                    key            TEXT PRIMARY KEY,
                    name           TEXT NOT NULL,
                    category       TEXT NOT NULL,
                    category_name  TEXT NOT NULL,
                    icon           TEXT NOT NULL,
                    description    TEXT NOT NULL,
                    is_premium     INTEGER NOT NULL DEFAULT 0,
                    config         TEXT NOT NULL,
                    created_at     TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bots (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       INTEGER NOT NULL,
                    name          TEXT NOT NULL,
                    template_key  TEXT,
                    source        TEXT NOT NULL DEFAULT 'template',
                    config        TEXT NOT NULL,
                    status        TEXT NOT NULL DEFAULT 'draft',
                    mini_app_url  TEXT,
                    created_at    TEXT NOT NULL,
                    updated_at    TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS payments (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id         INTEGER NOT NULL,
                    tier            TEXT NOT NULL,
                    amount          INTEGER NOT NULL,
                    receipt_file_id TEXT,
                    receipt_caption TEXT,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    created_at      TEXT NOT NULL,
                    reviewed_at     TEXT,
                    reviewer_id     INTEGER,
                    note            TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE INDEX IF NOT EXISTS idx_bots_user     ON bots(user_id);
                CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
                CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
                """
            )
            self._conn.commit()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    @staticmethod
    def _as_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        return dict(row) if row is not None else None

    @staticmethod
    def _parse_bot(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        data = Database._as_dict(row)
        if data is not None:
            data["config"] = _loads(data.get("config"), {})
        return data

    @staticmethod
    def _parse_template(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        data = Database._as_dict(row)
        if data is not None:
            data["config"] = _loads(data.get("config"), {})
            data["is_premium"] = bool(data.get("is_premium"))
        return data

    # ------------------------------------------------------------------ #
    # users / tiers
    # ------------------------------------------------------------------ #
    def ensure_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a user if needed and return the current row.

        The configured admin always receives Ultra/VIP status for free.
        """
        is_admin = user_id == ADMIN_ID
        now = _now()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO users
                    (user_id, username, first_name, is_admin, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, username, first_name, int(is_admin), now, now),
            )
            if is_admin:
                forever = (datetime.now(TZ) + timedelta(days=365 * 20)).isoformat()
                conn.execute(
                    """
                    UPDATE users
                    SET is_admin = 1, is_vip = 1, tier = ?, vip_until = ?,
                        username = COALESCE(?, username),
                        first_name = COALESCE(?, first_name), updated_at = ?
                    WHERE user_id = ?
                    """,
                    (ULTRA, forever, username, first_name, now, user_id),
                )
            elif username or first_name:
                conn.execute(
                    "UPDATE users SET username = ?, first_name = ?, updated_at = ? "
                    "WHERE user_id = ?",
                    (username, first_name, now, user_id),
                )
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            return dict(row)

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._as_dict(
                self._conn.execute(
                    "SELECT * FROM users WHERE user_id = ?", (user_id,)
                ).fetchone()
            )

    def is_admin(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        return bool(user and user["is_admin"])

    def effective_tier(self, user_id: int) -> str:
        """Resolve the active plan, honouring VIP expiry."""
        user = self.get_user(user_id)
        if not user:
            return FREE
        if user["is_admin"]:
            return ULTRA
        until = user.get("vip_until")
        if until:
            try:
                if datetime.fromisoformat(until) <= datetime.now(TZ):
                    return FREE
            except ValueError:
                return FREE
            return user["tier"] if user["tier"] in PLANS else FREE
        return FREE

    def limits(self, user_id: int) -> Dict[str, Any]:
        """Limits for a user; admins bypass every numeric cap."""
        limits = get_tier_limits(self.effective_tier(user_id))
        if self.is_admin(user_id):
            limits["bots"] = None
            limits["daily_messages"] = None
            limits["premium_templates"] = True
            limits["custom_builder"] = True
            limits["web_app"] = True
            limits["priority"] = True
        return limits

    def set_tier(self, user_id: int, tier: str, days: Optional[int] = None) -> None:
        if tier not in PLANS:
            raise ValueError(f"unknown tier: {tier}")
        plan = PLANS[tier]
        duration = days if days is not None else plan["days"]
        until = None
        if duration:
            until = (datetime.now(TZ) + timedelta(days=duration)).isoformat()
        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE users
                SET tier = ?, is_vip = ?, vip_until = ?, daily_messages = 0,
                    last_message_date = NULL, updated_at = ?
                WHERE user_id = ?
                """,
                (tier, int(bool(until)), until, _now(), user_id),
            )

    def register_message(self, user_id: int) -> tuple[bool, int, Optional[int]]:
        """Count one billable message.

        Returns ``(allowed, used_today, daily_limit)``.  ``daily_limit`` is
        ``None`` for users without a cap.  Daily counters reset lazily.
        """
        limits = self.limits(user_id)
        cap = limits["daily_messages"]
        today = _today()
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT daily_messages, last_message_date FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                return False, 0, cap
            used = row["daily_messages"] if row["last_message_date"] == today else 0
            if cap is not None and used >= cap:
                return False, used, cap
            used += 1
            conn.execute(
                "UPDATE users SET daily_messages = ?, last_message_date = ?, "
                "updated_at = ? WHERE user_id = ?",
                (used, today, _now(), user_id),
            )
            return True, used, cap

    def usage(self, user_id: int) -> Dict[str, Any]:
        limits = self.limits(user_id)
        user = self.get_user(user_id) or {}
        cap = limits["daily_messages"]
        used = (
            int(user.get("daily_messages", 0))
            if user.get("last_message_date") == _today()
            else 0
        )
        return {
            "used": used,
            "limit": cap,
            "remaining": None if cap is None else max(0, cap - used),
            "unlimited": cap is None,
        }

    # ------------------------------------------------------------------ #
    # templates
    # ------------------------------------------------------------------ #
    def seed_templates(self) -> int:
        """Idempotently insert the catalogue; returns the number of rows."""
        now = _now()
        with self.transaction() as conn:
            for item in TEMPLATE_CATALOG:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO templates
                        (key, name, category, category_name, icon, description,
                         is_premium, config, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["key"], item["name"], item["category"],
                        item["category_name"], item["icon"], item["description"],
                        int(item["is_premium"]), _dumps(item["config"]), now,
                    ),
                )
            return int(
                conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
            )

    def template_count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0])

    def categories(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT category AS key, MAX(category_name) AS name, MAX(icon) AS icon, "
                "COUNT(*) AS total, SUM(CASE WHEN is_premium = 0 THEN 1 ELSE 0 END) AS free "
                "FROM templates GROUP BY category ORDER BY MIN(rowid)"
            ).fetchall()
            return [dict(row) for row in rows]

    def templates(
        self,
        category: Optional[str] = None,
        include_premium: bool = True,
        search: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if category:
            clauses.append("category = ?")
            params.append(category)
        if not include_premium:
            clauses.append("is_premium = 0")
        if search:
            clauses.append("(name LIKE ? OR description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        sql = "SELECT * FROM templates"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY rowid"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
            return [self._parse_template(row) for row in rows]  # type: ignore[misc]

    def get_template(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._parse_template(
                self._conn.execute(
                    "SELECT * FROM templates WHERE key = ?", (key,)
                ).fetchone()
            )

    # ------------------------------------------------------------------ #
    # generated bots
    # ------------------------------------------------------------------ #
    def count_bots(self, user_id: int) -> int:
        with self._lock:
            return int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM bots WHERE user_id = ?", (user_id,)
                ).fetchone()[0]
            )

    def create_bot(
        self,
        user_id: int,
        name: str,
        config: Dict[str, Any],
        template_key: Optional[str] = None,
        source: str = "template",
        mini_app_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _now()
        with self.transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO bots
                    (user_id, name, template_key, source, config, status,
                     mini_app_url, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?)
                """,
                (
                    user_id, name, template_key, source, _dumps(config),
                    mini_app_url, now, now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM bots WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
            return self._parse_bot(row)  # type: ignore[return-value]

    def get_bot(self, bot_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM bots WHERE id = ?"
        params: List[Any] = [bot_id]
        if user_id is not None:
            sql += " AND user_id = ?"
            params.append(user_id)
        with self._lock:
            return self._parse_bot(self._conn.execute(sql, params).fetchone())

    def list_bots(self, user_id: int, limit: int = 30) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM bots WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [self._parse_bot(row) for row in rows]  # type: ignore[misc]

    def update_bot(self, bot_id: int, user_id: int, **fields: Any) -> None:
        allowed = {"name", "config", "status", "mini_app_url"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        if "config" in updates:
            updates["config"] = _dumps(updates["config"])
        updates["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        with self.transaction() as conn:
            conn.execute(
                f"UPDATE bots SET {assignments} WHERE id = ? AND user_id = ?",
                (*updates.values(), bot_id, user_id),
            )

    def delete_bot(self, bot_id: int, user_id: int) -> bool:
        with self.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM bots WHERE id = ? AND user_id = ?", (bot_id, user_id)
            )
            return cur.rowcount > 0

    # ------------------------------------------------------------------ #
    # payments
    # ------------------------------------------------------------------ #
    def add_payment(
        self,
        user_id: int,
        tier: str,
        amount: int,
        receipt_file_id: Optional[str] = None,
        receipt_caption: Optional[str] = None,
    ) -> int:
        with self.transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO payments
                    (user_id, tier, amount, receipt_file_id, receipt_caption,
                     status, created_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
                """,
                (user_id, tier, amount, receipt_file_id, receipt_caption, _now()),
            )
            return int(cur.lastrowid)

    def attach_receipt(self, payment_id: int, file_id: str, caption: Optional[str] = None) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE payments SET receipt_file_id = ?, receipt_caption = ? WHERE id = ?",
                (file_id, caption, payment_id),
            )

    def get_payment(self, payment_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._as_dict(
                self._conn.execute(
                    "SELECT * FROM payments WHERE id = ?", (payment_id,)
                ).fetchone()
            )

    def set_payment_status(
        self,
        payment_id: int,
        status: str,
        reviewer_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> None:
        if status not in {"pending", "approved", "rejected"}:
            raise ValueError(f"unknown status: {status}")
        payment = self.get_payment(payment_id)
        if not payment:
            return
        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE payments
                SET status = ?, reviewed_at = ?, reviewer_id = ?, note = ?
                WHERE id = ?
                """,
                (status, _now(), reviewer_id, note, payment_id),
            )
            if status == "approved":
                plan = PLANS.get(payment["tier"], PLANS[STANDART])
                until = (
                    datetime.now(TZ) + timedelta(days=plan["days"])
                ).isoformat()
                conn.execute(
                    """
                    UPDATE users
                    SET tier = ?, is_vip = 1, vip_until = ?, daily_messages = 0,
                        last_message_date = NULL, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (payment["tier"], until, _now(), payment["user_id"]),
                )

    def pending_payments(self, limit: int = 30) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM payments WHERE status = 'pending' "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def has_pending_payment(self, user_id: int) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM payments WHERE user_id = ? AND status = 'pending' "
                "LIMIT 1",
                (user_id,),
            ).fetchone()
            return row is not None

    def user_payments(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM payments WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    # ------------------------------------------------------------------ #
    # stats
    # ------------------------------------------------------------------ #
    def stats(self) -> Dict[str, int]:
        with self._lock:
            def scalar(sql: str, params: tuple[Any, ...] = ()) -> int:
                return int(self._conn.execute(sql, params).fetchone()[0])

            return {
                "users": scalar("SELECT COUNT(*) FROM users"),
                "premium": scalar(
                    "SELECT COUNT(*) FROM users WHERE is_vip = 1 OR is_admin = 1"
                ),
                "bots": scalar("SELECT COUNT(*) FROM bots"),
                "templates": scalar("SELECT COUNT(*) FROM templates"),
                "pending": scalar("SELECT COUNT(*) FROM payments WHERE status = 'pending'"),
                "approved": scalar("SELECT COUNT(*) FROM payments WHERE status = 'approved'"),
            }
