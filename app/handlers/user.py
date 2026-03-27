from __future__ import annotations

import sqlite3

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database.db import Database
from app.keyboards.calendar import build_calendar
from app.keyboards.common import (
    confirm_booking_kb,
    goals_kb,
    main_menu_kb,
    my_booking_kb,
    reviews_kb,
    services_kb,
    subscription_kb,
)
from app.services.booking_service import (
    booking_summary,
    is_subscribed,
    notify_admins,
    notify_schedule_channel,
)
from app.services.reminders import remove_reminder_job, schedule_reminder
from app.services.utils import (
    booking_date_range,
    format_date_ru,
    is_valid_phone,
    parse_iso_date,
)
from app.states import BookingStates
from config import settings

router = Router(name="user")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(settings.welcome_text, reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu:home")
async def menu_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(settings.welcome_text, reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:prices")
async def menu_prices(callback: CallbackQuery) -> None:
    await callback.message.edit_text(settings.prices_text, reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:about")
async def menu_about(callback: CallbackQuery) -> None:
    await callback.message.edit_text(settings.about_text, reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:reviews")
async def menu_reviews(callback: CallbackQuery) -> None:
    await callback.message.edit_text(settings.reviews_text, reply_markup=reviews_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:my_booking")
async def menu_my_booking(callback: CallbackQuery, db: Database) -> None:
    booking = db.get_active_booking_by_user(callback.from_user.id)
    if not booking:
        text = "<b>У вас пока нет активной записи.</b>"
        markup = my_booking_kb(False)
    else:
        text = booking_summary(booking)
        markup = my_booking_kb(True)
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == "book:start")
async def start_booking(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    if db.user_has_active_booking(callback.from_user.id):
        await callback.message.edit_text(
            "У вас уже есть активная запись. Сначала отмените её в разделе «Моя запись».",
            reply_markup=my_booking_kb(True),
        )
        await callback.answer()
        return

    if not await is_subscribed(bot, callback.from_user.id):
        await callback.message.edit_text(
            "Для записи необходимо подписаться на канал.",
            reply_markup=subscription_kb(),
        )
        await callback.answer()
        return

    await state.set_state(BookingStates.choosing_service)
    await callback.message.edit_text(
        "<b>Выберите формат записи</b>",
        reply_markup=services_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "sub:check")
async def check_subscription(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if await is_subscribed(bot, callback.from_user.id):
        await state.set_state(BookingStates.choosing_service)
        await callback.message.edit_text(
            "Подписка подтверждена ✅\n\n<b>Выберите формат записи</b>",
            reply_markup=services_kb(),
        )
        await callback.answer()
        return

    await callback.answer("Подписка пока не найдена", show_alert=True)


@router.callback_query(BookingStates.choosing_service, F.data.startswith("service:"))
async def choose_service(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    service_code = callback.data.split(":", maxsplit=1)[1]
    service = next((item for item in settings.services if item.code == service_code), None)
    if not service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    start_date, end_date = booking_date_range()
    available = {parse_iso_date(item) for item in db.get_available_dates(start_date.isoformat(), end_date.isoformat())}

    await state.update_data(
        service_code=service.code,
        service_title=service.title,
        calendar_month=start_date.replace(day=1).isoformat(),
    )
    await state.set_state(BookingStates.choosing_date)
    await callback.message.edit_text(
        (
            f"<b>{service.title}</b>\n"
            f"{service.description}\n\n"
            "Выберите дату для записи.\n"
            "Доступные даты — обычным числом, недоступные — с символом ×."
        ),
        reply_markup=build_calendar(
            current_month=start_date.replace(day=1),
            available_dates=available,
            action_prefix="pickdate",
            back_callback="book:start",
            min_date=start_date,
            max_date=end_date,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("calnav:pickdate:"))
async def navigate_booking_calendar(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    month_str = callback.data.split(":", maxsplit=2)[2]
    month_date = parse_iso_date(month_str)
    start_date, end_date = booking_date_range()
    available = {parse_iso_date(item) for item in db.get_available_dates(start_date.isoformat(), end_date.isoformat())}
    await state.update_data(calendar_month=month_date.isoformat())
    await callback.message.edit_reply_markup(
        reply_markup=build_calendar(
            current_month=month_date,
            available_dates=available,
            action_prefix="pickdate",
            back_callback="book:start",
            min_date=start_date,
            max_date=end_date,
        )
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pickdate:"))
async def choose_date(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    if "service_code" not in data:
        await callback.answer("Сначала выберите услугу", show_alert=True)
        return

    selected_date = callback.data.split(":", maxsplit=1)[1]
    slots = db.get_free_slots_for_date(selected_date)
    if not slots:
        await callback.answer("На эту дату слотов уже нет", show_alert=True)
        return

    await state.update_data(slot_date=selected_date)
    await state.set_state(BookingStates.choosing_time)

    builder = InlineKeyboardBuilder()
    for slot in slots:
        builder.button(text=slot["time"], callback_data=f"pickslot:{slot['id']}")
    builder.button(text="⬅️ Назад к датам", callback_data="book:back_to_dates")
    builder.adjust(3)

    await callback.message.edit_text(
        f"<b>Дата:</b> {format_date_ru(selected_date)}\n\nВыберите свободное время:",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(BookingStates.choosing_time, F.data == "book:back_to_dates")
async def back_to_dates(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    current_month = parse_iso_date(data.get("calendar_month", booking_date_range()[0].replace(day=1).isoformat()))
    start_date, end_date = booking_date_range()
    available = {parse_iso_date(item) for item in db.get_available_dates(start_date.isoformat(), end_date.isoformat())}
    await state.set_state(BookingStates.choosing_date)
    await callback.message.edit_text(
        "<b>Выберите дату для записи</b>",
        reply_markup=build_calendar(
            current_month=current_month,
            available_dates=available,
            action_prefix="pickdate",
            back_callback="book:start",
            min_date=start_date,
            max_date=end_date,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pickslot:"))
async def choose_time(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    slot_id = int(callback.data.split(":", maxsplit=1)[1])
    slot = db.get_slot(slot_id)
    if not slot:
        await callback.answer("Слот не найден", show_alert=True)
        return
    if db.is_day_closed(slot["date"]):
        await callback.answer("День закрыт администратором", show_alert=True)
        return
    free_slots = {item["id"] for item in db.get_free_slots_for_date(slot["date"])}
    if slot_id not in free_slots:
        await callback.answer("Этот слот уже занят", show_alert=True)
        return

    await state.update_data(slot_id=slot_id, slot_time=slot["time"])
    await state.set_state(BookingStates.entering_name)
    await callback.message.edit_text("Введите ваше имя:")
    await callback.answer()


@router.message(BookingStates.entering_name)
async def enter_name(message: Message, state: FSMContext) -> None:
    full_name = (message.text or "").strip()
    if len(full_name) < 2:
        await message.answer("Введите корректное имя.")
        return
    await state.update_data(full_name=full_name)
    await state.set_state(BookingStates.entering_phone)
    await message.answer("Введите номер телефона для связи:")


@router.message(BookingStates.entering_phone)
async def enter_phone(message: Message, state: FSMContext) -> None:
    phone = (message.text or "").strip()
    if not is_valid_phone(phone):
        await message.answer("Введите телефон в корректном формате. Пример: +7 999 123-45-67")
        return
    await state.update_data(phone=phone)
    await state.set_state(BookingStates.choosing_goal)
    await message.answer("Выберите цель тренировки:", reply_markup=goals_kb())


@router.callback_query(BookingStates.choosing_goal, F.data.startswith("goal:"))
async def choose_goal(callback: CallbackQuery, state: FSMContext) -> None:
    goal = callback.data.split(":", maxsplit=1)[1]
    if goal == "Другое":
        await state.set_state(BookingStates.entering_custom_goal)
        await callback.message.edit_text("Напишите вашу цель тренировки одним сообщением:")
        await callback.answer()
        return

    await finalize_preview(callback, state, goal)


@router.message(BookingStates.entering_custom_goal)
async def custom_goal(message: Message, state: FSMContext) -> None:
    goal = (message.text or "").strip()
    if len(goal) < 3:
        await message.answer("Опишите цель чуть подробнее.")
        return
    await finalize_preview(message, state, goal)


async def finalize_preview(event: Message | CallbackQuery, state: FSMContext, goal: str) -> None:
    await state.update_data(goal=goal)
    data = await state.get_data()
    await state.set_state(BookingStates.confirming)
    text = (
        "<b>Проверьте запись</b>\n\n"
        f"Услуга: <b>{data['service_title']}</b>\n"
        f"Дата: <b>{format_date_ru(data['slot_date'])}</b>\n"
        f"Время: <b>{data['slot_time']}</b>\n"
        f"Имя: <b>{data['full_name']}</b>\n"
        f"Телефон: <b>{data['phone']}</b>\n"
        f"Цель: <b>{goal}</b>"
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=confirm_booking_kb())
        await event.answer()
    else:
        await event.answer(text, reply_markup=confirm_booking_kb())


@router.callback_query(BookingStates.confirming, F.data == "booking:confirm")
async def confirm_booking(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    bot: Bot,
    scheduler: AsyncIOScheduler,
) -> None:
    data = await state.get_data()
    slot_id = data["slot_id"]
    slot = db.get_slot(slot_id)
    if not slot:
        await callback.answer("Слот больше не существует", show_alert=True)
        await state.clear()
        return
    if db.user_has_active_booking(callback.from_user.id):
        await callback.answer("У вас уже есть активная запись", show_alert=True)
        await state.clear()
        return
    free_slots = {item["id"] for item in db.get_free_slots_for_date(slot["date"])}
    if slot_id not in free_slots:
        await callback.answer("Этот слот уже заняли. Выберите другой.", show_alert=True)
        await state.clear()
        return

    try:
        booking_id = db.create_booking(
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            full_name=data["full_name"],
            phone=data["phone"],
            goal=data["goal"],
            service_code=data["service_code"],
            service_title=data["service_title"],
            slot_id=slot_id,
            reminder_job_id=None,
        )
    except sqlite3.IntegrityError:
        await callback.answer("Этот слот уже занят или у вас уже есть запись", show_alert=True)
        await state.clear()
        return

    schedule_reminder(
        scheduler=scheduler,
        bot=bot,
        db=db,
        booking_id=booking_id,
        slot_date=slot["date"],
        slot_time=slot["time"],
    )

    booking = db.get_booking(booking_id)
    await notify_admins(bot, booking)
    await notify_schedule_channel(bot, booking, "created")

    await state.clear()
    await callback.message.edit_text(
        "<b>Запись подтверждена ✅</b>\n\n" + booking_summary(booking),
        reply_markup=my_booking_kb(True),
    )
    await callback.answer()


@router.callback_query(F.data == "booking:cancel_own")
async def cancel_own_booking(
    callback: CallbackQuery,
    db: Database,
    bot: Bot,
    scheduler: AsyncIOScheduler,
) -> None:
    booking = db.get_active_booking_by_user(callback.from_user.id)
    if not booking:
        await callback.answer("Активная запись не найдена", show_alert=True)
        return
    cancelled = db.cancel_booking(booking["id"])
    remove_reminder_job(scheduler, booking["id"])
    if cancelled:
        await notify_schedule_channel(bot, cancelled, "cancelled")
    await callback.message.edit_text(
        "Ваша запись отменена. Слот снова стал доступным для бронирования.",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("date_unavailable:"))
async def date_unavailable(callback: CallbackQuery) -> None:
    await callback.answer("На эту дату пока нет свободных слотов", show_alert=True)


@router.callback_query(F.data.startswith("date_locked:"))
async def date_locked(callback: CallbackQuery) -> None:
    await callback.answer("Эта дата недоступна для записи", show_alert=True)


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()
