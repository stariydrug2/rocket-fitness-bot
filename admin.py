from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder



def admin_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить слот", callback_data="admin:add_slot")
    builder.button(text="🗑 Удалить слот", callback_data="admin:delete_slot")
    builder.button(text="🔒 Закрыть день", callback_data="admin:close_day")
    builder.button(text="🔓 Открыть день", callback_data="admin:open_day")
    builder.button(text="📋 Расписание на дату", callback_data="admin:view_schedule")
    builder.button(text="🚫 Отменить запись клиента", callback_data="admin:cancel_booking")
    builder.button(text="⬅️ В меню", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()



def slots_kb(slots: list[dict], prefix: str, empty_back: str = "admin:menu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not slots:
        builder.button(text="Слотов нет", callback_data="noop")
    else:
        for slot in slots:
            extra = " 🔒" if slot.get("is_booked") else ""
            builder.button(
                text=f"{slot['time']}{extra}",
                callback_data=f"{prefix}:{slot['id']}",
            )
    builder.button(text="⬅️ Назад", callback_data=empty_back)
    builder.adjust(3)
    return builder.as_markup()



def bookings_kb(bookings: list[dict], prefix: str, empty_back: str = "admin:menu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not bookings:
        builder.button(text="Записей нет", callback_data="noop")
    else:
        for booking in bookings:
            builder.button(
                text=f"{booking['slot_time']} — {booking['full_name']}",
                callback_data=f"{prefix}:{booking['id']}",
            )
    builder.button(text="⬅️ Назад", callback_data=empty_back)
    builder.adjust(1)
    return builder.as_markup()
