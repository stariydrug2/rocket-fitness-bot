from __future__ import annotations

from calendar import monthcalendar
from datetime import date, timedelta
from typing import Iterable

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def build_calendar(
    current_month: date,
    available_dates: Iterable[date],
    action_prefix: str,
    back_callback: str,
    min_date: date,
    max_date: date,
):
    builder = InlineKeyboardBuilder()

    year = current_month.year
    month = current_month.month

    builder.row(
        InlineKeyboardButton(
            text="⬅️",
            callback_data=f"calnav:{action_prefix}:{(current_month.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()}",
        ),
        InlineKeyboardButton(text=f"{month:02}.{year}", callback_data="noop"),
        InlineKeyboardButton(
            text="➡️",
            callback_data=f"calnav:{action_prefix}:{(current_month.replace(day=28) + timedelta(days=4)).replace(day=1).isoformat()}",
        ),
    )

    for week in monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
                continue

            current_day = date(year, month, day)

            if current_day < min_date or current_day > max_date:
                text = f"{day}🔒"
                callback = f"date_locked:{current_day.isoformat()}"
            elif current_day in available_dates:
                text = str(day)
                callback = f"{action_prefix}:{current_day.isoformat()}"
            else:
                text = f"{day}❌"
                callback = f"date_unavailable:{current_day.isoformat()}"

            row.append(InlineKeyboardButton(text=text, callback_data=callback))

        builder.row(*row)

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback))

    return builder.as_markup()
