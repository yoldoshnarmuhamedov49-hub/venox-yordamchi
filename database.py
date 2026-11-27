"""Storage layer for the Venox Yordamchi Telegram bot.

SQLite is used by default.  Set ``DATABASE_PATH`` to a path on a persistent
volume when deploying so user state and payment records survive restarts.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple

DEFAULT_DB_PATH = os.getenv("DATABASE_PATH", "venox.db")
MESSAGE_LIMIT = int(os.getenv("MESSAGE_LIMIT", "25"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    """Small, thread-safe SQLite wrapper holding users, payments and files."""

    def __init__(self, path: str = DEFAULT_DB_PATH) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    # ------------------------------------------------------------------ #
    # schema / helpers
    # ------------------------------------------------------------------ #
    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id        INTEGER PRIMARY KEY,
                    username       TEXT,
                    first_name     TEXT,
                    is_admin       INTEGER NOT NULL DEFAULT 0,
                    is_vip         INTEGER NOT NULL DEFAULT 0,
                    vip_until      TEXT,
                    mode           TEXT NOT NULL DEFAULT 'welcome',
                    message_count  INTEGER NOT NULL DEFAULT 0,
                    total_messages INTEGER NOT NULL DEFAULT 0,
                    created_at     TEXT NOT NULL,
                    updated_at     TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS payments (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id         INTEGER NOT NULL,
                    plan            TEXT NOT NULL,
                    amount          INTEGER NOT NULL,
                    receipt_file_id TEXT,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    created_at      TEXT NOT NULL,
                    reviewed_at     TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS generated_files (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER NOT NULL,
                    filename   TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
                CREATE INDEX IF NOT EXISTS idx_payments_user   ON payments(user_id);
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

    # ------------------------------------------------------------------ #
    # users
    # ------------------------------------------------------------------ #
    def ensure_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        is_admin: bool = False,
    ) -> Dict[str, Any]:
        with self.transaction() as conn:
            now = _now()
            conn.execute(
                """
                INSERT OR IGNORE INTO users
                    (user_id, username, first_name, is_admin, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, username, first_name, int(is_admin), now, now),
            )
            if is_admin:
                conn.execute(
                    "UPDATE users SET is_admin = 1, updated_at = ? WHERE user_id = ?",
                    (now, user_id),
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
            row = self._conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            return self._as_dict(row)

    def set_mode(self, user_id: int, mode: str) -> None:
        if mode not in {"welcome", "chat", "build"}:
            raise ValueError(f"unknown mode: {mode}")
        with self.transaction() as conn:
            conn.execute(
                "UPDATE users SET mode = ?, updated_at = ? WHERE user_id = ?",
                (mode, _now(), user_id),
            )

    def is_unlimited(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        if user["is_admin"] or user["is_vip"]:
            return True
        until = user.get("vip_until")
        if until:
            try:
                if datetime.fromisoformat(until) > datetime.now(timezone.utc):
                    return True
            except ValueError:
                pass
        return False

    def register_message(self, user_id: int) -> Tuple[bool, int]:
        """Count one billable message.

        Returns ``(allowed, count)``.  VIP/admin users always get
        ``(True, -1)``; regular users are capped at ``MESSAGE_LIMIT``.
        """
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT is_vip, is_admin, vip_until, message_count "
                "FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                return False, 0

            unlimited = bool(row["is_vip"] or row["is_admin"])
            until = row["vip_until"]
            if until:
                try:
                    unlimited = unlimited or (
                        datetime.fromisoformat(until) > datetime.now(timezone.utc)
                    )
                except ValueError:
                    pass

            if unlimited:
                conn.execute(
                    "UPDATE users SET message_count = message_count + 1, "
                    "total_messages = total_messages + 1, updated_at = ? "
                    "WHERE user_id = ?",
                    (_now(), user_id),
                )
                return True, -1

            if row["message_count"] >= MESSAGE_LIMIT:
                return False, row["message_count"]

            new_count = row["message_count"] + 1
            conn.execute(
                "UPDATE users SET message_count = ?, total_messages = "
                "total_messages + 1, updated_at = ? WHERE user_id = ?",
                (new_count, _now(), user_id),
            )
            return True, new_count

    def usage(self, user_id: int) -> Dict[str, Any]:
        user = self.get_user(user_id) or {}
        unlimited = self.is_unlimited(user_id)
        used = int(user.get("message_count", 0))
        return {
            "used": used,
            "limit": MESSAGE_LIMIT,
            "remaining": 0 if unlimited else max(0, MESSAGE_LIMIT - used),
            "unlimited": unlimited,
            "vip": bool(user.get("is_vip") or user.get("is_admin")),
        }

    def set_vip(self, user_id: int, days: int = 30) -> None:
        until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        with self.transaction() as conn:
            conn.execute(
                "UPDATE users SET is_vip = 1, vip_until = ?, "
                "message_count = 0, updated_at = ? WHERE user_id = ?",
                (until, _now(), user_id),
            )

    # ------------------------------------------------------------------ #
    # payments
    # ------------------------------------------------------------------ #
    def add_payment(
        self, user_id: int, plan: str, amount: int, receipt_file_id: Optional[str] = None
    ) -> int:
        with self.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO payments (user_id, plan, amount, receipt_file_id, "
                "status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
                (user_id, plan, amount, receipt_file_id, _now()),
            )
            return int(cur.lastrowid)

    def attach_receipt(self, payment_id: int, file_id: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE payments SET receipt_file_id = ? WHERE id = ?",
                (file_id, payment_id),
            )

    def get_payment(self, payment_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM payments WHERE id = ?", (payment_id,)
            ).fetchone()
            return self._as_dict(row)

    def set_payment_status(self, payment_id: int, status: str) -> None:
        if status not in {"pending", "approved", "rejected"}:
            raise ValueError(f"unknown status: {status}")
        with self.transaction() as conn:
            conn.execute(
                "UPDATE payments SET status = ?, reviewed_at = ? WHERE id = ?",
                (status, _now(), payment_id),
            )

    def pending_payments(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM payments WHERE status = 'pending' "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def has_pending_payment(self, user_id: int) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM payments WHERE user_id = ? AND status = 'pending' "
                "LIMIT 1",
                (user_id,),
            ).fetchone()
            return row is not None

    # ------------------------------------------------------------------ #
    # generated files
    # ------------------------------------------------------------------ #
    def save_generated_file(self, user_id: int, filename: str, content: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO generated_files (user_id, filename, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, filename, content, _now()),
            )

    def generated_files(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT filename, created_at FROM generated_files "
                "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def stats(self) -> Dict[str, int]:
        with self._lock:
            users = self._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            vip = self._conn.execute(
                "SELECT COUNT(*) FROM users WHERE is_vip = 1 OR is_admin = 1"
            ).fetchone()[0]
            pending = self._conn.execute(
                "SELECT COUNT(*) FROM payments WHERE status = 'pending'"
            ).fetchone()[0]
            files = self._conn.execute(
                "SELECT COUNT(*) FROM generated_files"
            ).fetchone()[0]
        return {"users": users, "vip": vip, "pending": pending, "files": files}
