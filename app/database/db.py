from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional


class Database:
    def __init__(self, path: str):
        self.path = path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS closed_days (
                    date TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS slots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slot_date TEXT NOT NULL,
                    slot_time TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(slot_date, slot_time)
                );

                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    service_code TEXT NOT NULL,
                    service_title TEXT NOT NULL,
                    slot_id INTEGER NOT NULL,
                    slot_date TEXT NOT NULL,
                    slot_time TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    reminder_job_id TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    cancelled_at TEXT,
                    FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE CASCADE
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_one_active_per_user
                ON bookings(user_id)
                WHERE status = 'active';

                CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_one_active_per_slot
                ON bookings(slot_id)
                WHERE status = 'active';
                """
            )

    def add_slot(self, slot_date: str, slot_time: str) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO slots (slot_date, slot_time) VALUES (?, ?)",
                (slot_date, slot_time),
            )
            return cursor.rowcount > 0

    def delete_slot(self, slot_id: int) -> bool:
        with self.connection() as conn:
            active = conn.execute(
                "SELECT 1 FROM bookings WHERE slot_id = ? AND status = 'active'",
                (slot_id,),
            ).fetchone()
            if active:
                return False
            cursor = conn.execute("DELETE FROM slots WHERE id = ?", (slot_id,))
            return cursor.rowcount > 0

    def close_day(self, slot_date: str) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO closed_days (date) VALUES (?)",
                (slot_date,),
            )
            return cursor.rowcount > 0

    def open_day(self, slot_date: str) -> bool:
        with self.connection() as conn:
            cursor = conn.execute("DELETE FROM closed_days WHERE date = ?", (slot_date,))
            return cursor.rowcount > 0

    def is_day_closed(self, slot_date: str) -> bool:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM closed_days WHERE date = ?",
                (slot_date,),
            ).fetchone()
            return row is not None

    def get_closed_days(self, start_date: str, end_date: str) -> list[str]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT date FROM closed_days WHERE date BETWEEN ? AND ? ORDER BY date",
                (start_date, end_date),
            ).fetchall()
            return [row["date"] for row in rows]

    def get_available_dates(self, start_date: str, end_date: str) -> list[str]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT s.slot_date
                FROM slots s
                LEFT JOIN closed_days cd ON cd.date = s.slot_date
                LEFT JOIN bookings b ON b.slot_id = s.id AND b.status = 'active'
                WHERE s.slot_date BETWEEN ? AND ?
                  AND cd.date IS NULL
                  AND b.id IS NULL
                ORDER BY s.slot_date
                """,
                (start_date, end_date),
            ).fetchall()
            return [row["slot_date"] for row in rows]

    def get_slots_for_date(self, slot_date: str) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.slot_time,
                       CASE WHEN b.id IS NOT NULL THEN 1 ELSE 0 END AS is_booked
                FROM slots s
                LEFT JOIN bookings b ON b.slot_id = s.id AND b.status = 'active'
                WHERE s.slot_date = ?
                ORDER BY s.slot_time
                """,
                (slot_date,),
            ).fetchall()
            return [
                {"id": row["id"], "time": row["slot_time"], "is_booked": bool(row["is_booked"])}
                for row in rows
            ]

    def get_free_slots_for_date(self, slot_date: str) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.slot_time
                FROM slots s
                LEFT JOIN closed_days cd ON cd.date = s.slot_date
                LEFT JOIN bookings b ON b.slot_id = s.id AND b.status = 'active'
                WHERE s.slot_date = ?
                  AND cd.date IS NULL
                  AND b.id IS NULL
                ORDER BY s.slot_time
                """,
                (slot_date,),
            ).fetchall()
            return [{"id": row["id"], "time": row["slot_time"]} for row in rows]

    def get_slot(self, slot_id: int) -> Optional[dict]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT id, slot_date, slot_time FROM slots WHERE id = ?",
                (slot_id,),
            ).fetchone()
            if not row:
                return None
            return {"id": row["id"], "date": row["slot_date"], "time": row["slot_time"]}

    def user_has_active_booking(self, user_id: int) -> bool:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM bookings WHERE user_id = ? AND status = 'active'",
                (user_id,),
            ).fetchone()
            return row is not None

    def create_booking(
        self,
        *,
        user_id: int,
        username: str | None,
        full_name: str,
        phone: str,
        goal: str,
        service_code: str,
        service_title: str,
        slot_id: int,
        reminder_job_id: str | None,
    ) -> int:
        slot = self.get_slot(slot_id)
        if not slot:
            raise ValueError("Slot not found")
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO bookings (
                    user_id, username, full_name, phone, goal,
                    service_code, service_title, slot_id, slot_date, slot_time,
                    reminder_job_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    username,
                    full_name,
                    phone,
                    goal,
                    service_code,
                    service_title,
                    slot_id,
                    slot["date"],
                    slot["time"],
                    reminder_job_id,
                ),
            )
            return int(cursor.lastrowid)

    def get_active_booking_by_user(self, user_id: int) -> Optional[dict]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM bookings WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_booking(self, booking_id: int) -> Optional[dict]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM bookings WHERE id = ?",
                (booking_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_active_bookings_for_date(self, slot_date: str) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM bookings WHERE slot_date = ? AND status = 'active' ORDER BY slot_time",
                (slot_date,),
            ).fetchall()
            return [dict(row) for row in rows]

    def cancel_booking(self, booking_id: int) -> Optional[dict]:
        with self.connection() as conn:
            booking = conn.execute(
                "SELECT * FROM bookings WHERE id = ? AND status = 'active'",
                (booking_id,),
            ).fetchone()
            if not booking:
                return None
            conn.execute(
                "UPDATE bookings SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP WHERE id = ?",
                (booking_id,),
            )
            return dict(booking)

    def update_booking_reminder_job(self, booking_id: int, reminder_job_id: str | None) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE bookings SET reminder_job_id = ? WHERE id = ?",
                (reminder_job_id, booking_id),
            )

    def get_future_active_bookings(self, now_iso: str) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM bookings
                WHERE status = 'active'
                  AND datetime(slot_date || ' ' || slot_time || ':00') > datetime(?)
                ORDER BY slot_date, slot_time
                """,
                (now_iso,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_schedule_for_date(self, slot_date: str) -> dict:
        slots = self.get_slots_for_date(slot_date)
        bookings = self.get_active_bookings_for_date(slot_date)
        is_closed = self.is_day_closed(slot_date)
        return {"slots": slots, "bookings": bookings, "is_closed": is_closed}
