from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings



def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗓 Записаться", callback_data="book:start")
    builder.button(text="💳 Услуги и цены", callback_data="menu:prices")
    builder.button(text="ℹ️ О нас", callback_data="menu:about")
    builder.button(text="⭐ Отзывы и соцсети", callback_data="menu:reviews")
    builder.button(text="📌 Моя запись", callback_data="menu:my_booking")
    builder.adjust(1)
    return builder.as_markup()



def services_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for service in settings.services:
        builder.button(
            text=f"{service.title} — {service.price}",
            callback_data=f"service:{service.code}",
        )
    builder.button(text="⬅️ Назад", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()



def goals_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for goal in settings.goals:
        builder.button(text=goal, callback_data=f"goal:{goal}")
    builder.button(text="⬅️ Отмена", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()



def confirm_booking_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="booking:confirm")
    builder.button(text="❌ Отменить", callback_data="menu:home")
    builder.adjust(2)
    return builder.as_markup()



def subscription_kb() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться", url=settings.channel_link)],
            [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="sub:check")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:home")],
        ]
    )
    return markup



def my_booking_kb(has_booking: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_booking:
        builder.button(text="❌ Отменить запись", callback_data="booking:cancel_own")
    builder.button(text="⬅️ В меню", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()



def reviews_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for text, url in settings.review_links.items():
        builder.button(text=text, url=url)
    builder.button(text="⬅️ В меню", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()
