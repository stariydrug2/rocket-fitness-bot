from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from config import settings


PHONE_RE = re.compile(r"^[\d\+\-\(\)\s]{7,20}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")



def now_local() -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))



def booking_date_range() -> tuple[date, date]:
    today = now_local().date()
    max_day = today + timedelta(days=settings.booking_horizon_days - 1)
    return today, max_day



def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()



def format_date_ru(value: str) -> str:
    dt = parse_iso_date(value)
    months = [
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    ]
    return f"{dt.day} {months[dt.month - 1]} {dt.year}"



def is_valid_phone(phone: str) -> bool:
    return bool(PHONE_RE.fullmatch(phone.strip()))



def is_valid_time(time_text: str) -> bool:
    return bool(TIME_RE.fullmatch(time_text.strip()))



def appointment_datetime(slot_date: str, slot_time: str) -> datetime:
    naive = datetime.strptime(f"{slot_date} {slot_time}", "%Y-%m-%d %H:%M")
    return naive.replace(tzinfo=ZoneInfo(settings.timezone))
