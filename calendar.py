from __future__ import annotations

import calendar
from datetime import date, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]



def build_calendar(
    *,
    current_month: date,
    available_dates: set[date],
    action_prefix: str,
    back_callback: str,
    min_date: date,
    max_date: date,
) -> InlineKeyboardMarkup:
    month_first_day = current_month.replace(day=1)
    rows: list[list[InlineKeyboardButton]] = []
    rows.append(
        [
            InlineKeyboardButton(
                text=month_first_day.strftime("%B %Y").capitalize(),
                callback_data="noop",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text=day_name, callback_data="noop") for day_name in WEEKDAYS])

    month_calendar = calendar.Calendar(firstweekday=0).monthdatescalendar(
        month_first_day.year, month_first_day.month
    )

    for week in month_calendar:
        week_buttons: list[InlineKeyboardButton] = []
        for current_day in week:
            if current_day.month != month_first_day.month:
                week_buttons.append(InlineKeyboardButton(text=" ", callback_data="noop"))
            elif current_day < min_date or current_day > max_date:
                week_buttons.append(InlineKeyboardButton(text=f"·{current_day.day}", callback_data="noop"))
            elif current_day in available_dates:
                week_buttons.append(
                    InlineKeyboardButton(
                        text=str(current_day.day),
                        callback_data=f"{action_prefix}:{current_day.isoformat()}",
                    )
                )
            else:
                week_buttons.append(InlineKeyboardButton(text=f"×{current_day.day}", callback_data="noop"))
        rows.append(week_buttons)

    prev_month = (month_first_day.replace(day=1) - timedelta(days=1)).replace(day=1)
    next_month = (month_first_day + timedelta(days=32)).replace(day=1)

    nav_row: list[InlineKeyboardButton] = []
    if prev_month >= min_date.replace(day=1):
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"calnav:{action_prefix}:{prev_month.isoformat()}"))
    nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback))
    if next_month <= max_date.replace(day=1):
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"calnav:{action_prefix}:{next_month.isoformat()}"))
    rows.append(nav_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)
