from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from app.database.db import Database
from app.services.utils import format_date_ru
from config import settings


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    if not settings.require_subscription_for_booking:
        return True
    try:
        member = await bot.get_chat_member(settings.channel_id, user_id)
    except TelegramBadRequest:
        return False
    return member.status not in {"left", "kicked"}



def booking_summary(booking: dict) -> str:
    return (
        "<b>Ваша запись</b>\n\n"
        f"Услуга: <b>{booking['service_title']}</b>\n"
        f"Дата: <b>{format_date_ru(booking['slot_date'])}</b>\n"
        f"Время: <b>{booking['slot_time']}</b>\n"
        f"Имя: <b>{booking['full_name']}</b>\n"
        f"Телефон: <b>{booking['phone']}</b>\n"
        f"Цель: <b>{booking['goal']}</b>"
    )


async def notify_admins(bot: Bot, booking: dict) -> None:
    username = f"@{booking['username']}" if booking.get("username") else "—"
    text = (
        "<b>Новая запись в «Ракету»</b>\n\n"
        f"Услуга: <b>{booking['service_title']}</b>\n"
        f"Дата: <b>{format_date_ru(booking['slot_date'])}</b>\n"
        f"Время: <b>{booking['slot_time']}</b>\n"
        f"Имя: <b>{booking['full_name']}</b>\n"
        f"Телефон: <b>{booking['phone']}</b>\n"
        f"Цель: <b>{booking['goal']}</b>\n"
        f"Telegram: <b>{username}</b>\n"
        f"User ID: <code>{booking['user_id']}</code>"
    )
    for admin_id in settings.admin_ids:
        await bot.send_message(admin_id, text)


async def notify_schedule_channel(bot: Bot, booking: dict, action: str) -> None:
    if not settings.schedule_channel_id:
        return
    action_text = "Новая запись" if action == "created" else "Отмена записи"
    text = (
        f"<b>{action_text}</b>\n\n"
        f"Услуга: <b>{booking['service_title']}</b>\n"
        f"Дата: <b>{format_date_ru(booking['slot_date'])}</b>\n"
        f"Время: <b>{booking['slot_time']}</b>\n"
        f"Клиент: <b>{booking['full_name']}</b>\n"
        f"Телефон: <b>{booking['phone']}</b>"
    )
    await bot.send_message(settings.schedule_channel_id, text)
