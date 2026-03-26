from __future__ import annotations

from datetime import timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database.db import Database
from app.keyboards.admin import admin_menu_kb, bookings_kb, slots_kb
from app.keyboards.calendar import build_calendar
from app.services.booking_service import notify_schedule_channel
from app.services.reminders import remove_reminder_job
from app.services.utils import booking_date_range, format_date_ru, is_valid_time, parse_iso_date
from app.states import AdminStates
from config import settings

router = Router(name="admin")



def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids



def daterange_set():
    start_date, end_date = booking_date_range()
    dates = set()
    current = start_date
    while current <= end_date:
        dates.add(current)
        current += timedelta(days=1)
    return start_date, end_date, dates


async def render_admin_calendar(
    callback: CallbackQuery,
    state: FSMContext,
    target_state,
    action_prefix: str,
    title: str,
    available_dates: set,
    current_month=None,
) -> None:
    start_date, end_date, _ = daterange_set()
    month = current_month or start_date.replace(day=1)
    await state.set_state(target_state)
    await state.update_data(admin_calendar_month=month.isoformat())
    await callback.message.edit_text(
        title,
        reply_markup=build_calendar(
            current_month=month,
            available_dates=available_dates,
            action_prefix=action_prefix,
            back_callback="admin:menu",
            min_date=start_date,
            max_date=end_date,
        ),
    )


@router.message(Command("admin"))
async def open_admin_panel(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к админ-панели.")
        return
    await state.clear()
    await message.answer("<b>Админ-панель</b>", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin:menu")
async def admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text("<b>Админ-панель</b>", reply_markup=admin_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:add_slot")
async def admin_add_slot(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    _, _, all_dates = daterange_set()
    await render_admin_calendar(
        callback,
        state,
        AdminStates.choosing_date_for_add_slot,
        "adminpick:addslot",
        "<b>Выберите дату, на которую нужно добавить слот</b>",
        all_dates,
    )
    await callback.answer()


@router.callback_query(AdminStates.choosing_date_for_add_slot, F.data.startswith("calnav:adminpick:addslot:"))
async def admin_nav_add_slot(callback: CallbackQuery, state: FSMContext) -> None:
    month_date = parse_iso_date(callback.data.rsplit(":", maxsplit=1)[1])
    _, _, all_dates = daterange_set()
    await render_admin_calendar(
        callback,
        state,
        AdminStates.choosing_date_for_add_slot,
        "adminpick:addslot",
        "<b>Выберите дату, на которую нужно добавить слот</b>",
        all_dates,
        current_month=month_date,
    )
    await callback.answer()


@router.callback_query(AdminStates.choosing_date_for_add_slot, F.data.startswith("adminpick:addslot:"))
async def admin_pick_add_slot(callback: CallbackQuery, state: FSMContext) -> None:
    slot_date = callback.data.rsplit(":", maxsplit=1)[1]
    await state.update_data(slot_date=slot_date)
    await state.set_state(AdminStates.entering_slot_time)
    await callback.message.edit_text(
        f"Дата: <b>{format_date_ru(slot_date)}</b>\n\nВведите время слота в формате <code>HH:MM</code>, например <code>18:30</code>."
    )
    await callback.answer()


@router.message(AdminStates.entering_slot_time)
async def admin_enter_slot_time(message: Message, state: FSMContext, db: Database) -> None:
    if not is_admin(message.from_user.id):
        return
    slot_time = message.text.strip()
    if not is_valid_time(slot_time):
        await message.answer("Неверный формат времени. Пример: 18:30")
        return
    data = await state.get_data()
    created = db.add_slot(data["slot_date"], slot_time)
    await state.clear()
    await message.answer(
        "Слот добавлен ✅" if created else "Такой слот уже существует.",
        reply_markup=admin_menu_kb(),
    )


@router.callback_query(F.data == "admin:delete_slot")
async def admin_delete_slot(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    start_date, end_date, all_dates = daterange_set()
    available = {current for current in all_dates if db.get_slots_for_date(current.isoformat())}
    if not available:
        await callback.message.edit_text("На ближайший месяц нет слотов.", reply_markup=admin_menu_kb())
        await callback.answer()
        return
    await render_admin_calendar(
        callback,
        state,
        AdminStates.choosing_date_for_delete_slot,
        "adminpick:delslot",
        "<b>Выберите дату, на которой нужно удалить слот</b>",
        available,
    )
    await callback.answer()


@router.callback_query(AdminStates.choosing_date_for_delete_slot, F.data.startswith("calnav:adminpick:delslot:"))
async def admin_nav_delete_slot(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    month_date = parse_iso_date(callback.data.rsplit(":", maxsplit=1)[1])
    _, _, all_dates = daterange_set()
    available = {current for current in all_dates if db.get_slots_for_date(current.isoformat())}
    await render_admin_calendar(
        callback,
        state,
        AdminStates.choosing_date_for_delete_slot,
        "adminpick:delslot",
        "<b>Выберите дату, на которой нужно удалить слот</b>",
        available,
        current_month=month_date,
    )
    await callback.answer()


@router.callback_query(AdminStates.choosing_date_for_delete_slot, F.data.startswith("adminpick:delslot:"))
async def admin_pick_delete_slot(callback: CallbackQuery, db: Database) -> None:
    slot_date = callback.data.rsplit(":", maxsplit=1)[1]
    slots = db.get_slots_for_date(slot_date)
    await callback.message.edit_text(
        f"<b>Слоты на {format_date_ru(slot_date)}</b>\n🔒 — слот уже занят и не может быть удалён.",
        reply_markup=slots_kb(slots, prefix="adminslot:delete", empty_back="admin:menu"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adminslot:delete:"))
async def admin_delete_slot_action(callback: CallbackQuery, db: Database) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    slot_id = int(callback.data.rsplit(":", maxsplit=1)[1])
    success = db.delete_slot(slot_id)
    if success:
        await callback.message.edit_text("Слот удалён ✅", reply_markup=admin_menu_kb())
        await callback.answer()
    else:
        await callback.answer("Нельзя удалить слот с активной записью", show_alert=True)


@router.callback_query(F.data == "admin:close_day")
async def admin_close_day(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    _, _, all_dates = daterange_set()
    available = {current for current in all_dates if not db.is_day_closed(current.isoformat())}
    await render_admin_calendar(
        callback,
        state,
        AdminStates.choosing_date_for_close_day,
        "adminpick:closeday",
        "<b>Выберите день, который нужно закрыть</b>",
        available,
    )
    await callback.answer()


@router.callback_query(AdminStates.choosing_date_for_close_day, F.data.startswith("calnav:adminpick:closeday:"))
async def admin_nav_close_day(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    month_date = parse_iso_date(callback.data.rsplit(":", maxsplit=1)[1])
    _, _, all_dates = daterange_set()
    available = {current for current in all_dates if not db.is_day_closed(current.isoformat())}
    await render_admin_calendar(
        callback,
        state,
        AdminStates.choosing_date_for_close_day,
        "adminpick:closeday",
        "<b>Выберите день, который нужно закрыть</b>",
        available,
        current_month=month_date,
    )
    await callback.answer()


@router.callback_query(AdminStates.choosing_date_for_close_day, F.data.startswith("adminpick:closeday:"))
async def admin_pick_close_day(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    slot_date = callback.data.rsplit(":", maxsplit=1)[1]
    db.close_day(slot_date)
    await state.clear()
    await callback.message.edit_text(
        f"День <b>{format_date_ru(slot_date)}</b> закрыт ✅", reply_markup=admin_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:open_day")
async def admin_open_day(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    start_date, end_date = booking_date_range()
    available = {parse_iso_date(day) for day in db.get_closed_days(start_date.isoformat(), end_date.isoformat())}
    if not available:
        await callback.message.edit_text("Закрытых дней на ближайший месяц нет.", reply_markup=admin_menu_kb())
        await callback.answer()
        return
    await render_admin_calendar(
        callback,
        state,
        AdminStates.choosing_date_for_open_day,
        "adminpick:openday",
        "<b>Выберите день, который нужно открыть</b>",
        available,
    )
    await callback.answer()


@router.callback_query(AdminStates.choosing_date_for_open_day, F.data.startswith("calnav:adminpick:openday:"))
async def admin_nav_open_day(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    month_date = parse_iso_date(callback.data.rsplit(":", maxsplit=1)[1])
    start_date, end_date = booking_date_range()
    available = {parse_iso_date(day) for day in db.get_closed_days(start_date.isoformat(), end_date.isoformat())}
    await render_admin_calendar(
        callback,
        state,
        AdminStates.choosing_date_for_open_day,
        "adminpick:openday",
        "<b>Выберите день, который нужно открыть</b>",
        available,
        current_month=month_date,
    )
    await callback.answer()


@router.callback_query(AdminStates.choosing_date_for_open_day, F.data.startswith("adminpick:openday:"))
async def admin_pick_open_day(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    slot_date = callback.data.rsplit(":", maxsplit=1)[1]
    db.open_day(slot_date)
    await state.clear()
    await callback.message.edit_text(
        f"День <b>{format_date_ru(slot_date)}</b> снова открыт ✅", reply_markup=admin_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:view_schedule")
async def admin_view_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    _, _, all_dates = daterange_set()
    await render_admin_calendar(
        callback,
        state,
        AdminStates.choosing_date_for_schedule,
        "adminpick:schedule",
        "<b>Выберите дату для просмотра расписания</b>",
        all_dates,
    )
    await callback.answer()


@router.callback_query(AdminStates.choosing_date_for_schedule, F.data.startswith("calnav:adminpick:schedule:"))
async def admin_nav_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    month_date = parse_iso_date(callback.data.rsplit(":", maxsplit=1)[1])
    _, _, all_dates = daterange_set()
    await render_admin_calendar(
        callback,
        state,
        AdminStates.choosing_date_for_schedule,
        "adminpick:schedule",
        "<b>Выберите дату для просмотра расписания</b>",
        all_dates,
        current_month=month_date,
    )
    await callback.answer()


@router.callback_query(AdminStates.choosing_date_for_schedule, F.data.startswith("adminpick:schedule:"))
async def admin_pick_schedule(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    slot_date = callback.data.rsplit(":", maxsplit=1)[1]
    schedule = db.get_schedule_for_date(slot_date)
    lines = [f"<b>Расписание на {format_date_ru(slot_date)}</b>"]
    lines.append(f"Статус дня: {'🔒 закрыт' if schedule['is_closed'] else '🟢 открыт'}")
    lines.append("")
    lines.append("<b>Слоты:</b>")
    if schedule["slots"]:
        for slot in schedule["slots"]:
            lines.append(f"• {slot['time']} {'— занято' if slot['is_booked'] else '— свободно'}")
    else:
        lines.append("• Слотов нет")
    lines.append("")
    lines.append("<b>Активные записи:</b>")
    if schedule["bookings"]:
        for booking in schedule["bookings"]:
            lines.append(
                f"• {booking['slot_time']} — {booking['full_name']} ({booking['phone']}) / {booking['service_title']}"
            )
    else:
        lines.append("• Записей нет")
    await state.clear()
    await callback.message.edit_text("\n".join(lines), reply_markup=admin_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:cancel_booking")
async def admin_cancel_booking(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    _, _, all_dates = daterange_set()
    available = {current for current in all_dates if db.get_active_bookings_for_date(current.isoformat())}
    if not available:
        await callback.message.edit_text("Активных записей на ближайший месяц нет.", reply_markup=admin_menu_kb())
        await callback.answer()
        return
    await render_admin_calendar(
        callback,
        state,
        AdminStates.choosing_date_for_cancel_booking,
        "adminpick:cancelbook",
        "<b>Выберите дату, на которой нужно отменить запись клиента</b>",
        available,
    )
    await callback.answer()


@router.callback_query(AdminStates.choosing_date_for_cancel_booking, F.data.startswith("calnav:adminpick:cancelbook:"))
async def admin_nav_cancel_booking(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    month_date = parse_iso_date(callback.data.rsplit(":", maxsplit=1)[1])
    _, _, all_dates = daterange_set()
    available = {current for current in all_dates if db.get_active_bookings_for_date(current.isoformat())}
    await render_admin_calendar(
        callback,
        state,
        AdminStates.choosing_date_for_cancel_booking,
        "adminpick:cancelbook",
        "<b>Выберите дату, на которой нужно отменить запись клиента</b>",
        available,
        current_month=month_date,
    )
    await callback.answer()


@router.callback_query(AdminStates.choosing_date_for_cancel_booking, F.data.startswith("adminpick:cancelbook:"))
async def admin_pick_cancel_booking(callback: CallbackQuery, db: Database) -> None:
    slot_date = callback.data.rsplit(":", maxsplit=1)[1]
    bookings = db.get_active_bookings_for_date(slot_date)
    await callback.message.edit_text(
        f"<b>Выберите запись для отмены на {format_date_ru(slot_date)}</b>",
        reply_markup=bookings_kb(bookings, prefix="adminbook:cancel", empty_back="admin:menu"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adminbook:cancel:"))
async def admin_cancel_booking_action(
    callback: CallbackQuery,
    db: Database,
    bot: Bot,
    scheduler: AsyncIOScheduler,
) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    booking_id = int(callback.data.rsplit(":", maxsplit=1)[1])
    booking = db.cancel_booking(booking_id)
    if not booking:
        await callback.answer("Запись уже отменена или не найдена", show_alert=True)
        return
    remove_reminder_job(scheduler, booking_id)
    await notify_schedule_channel(bot, booking, "cancelled")
    await bot.send_message(
        booking["user_id"],
        "Ваша запись в фитнес-зал «Ракета» была отменена администратором. Для новой записи воспользуйтесь ботом снова.",
    )
    await callback.message.edit_text("Запись клиента отменена ✅", reply_markup=admin_menu_kb())
    await callback.answer()
