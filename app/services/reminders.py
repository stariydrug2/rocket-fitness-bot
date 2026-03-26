from __future__ import annotations

from datetime import timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import JobLookupError

from app.database.db import Database
from app.services.utils import appointment_datetime, format_date_ru, now_local
from config import settings


async def send_reminder(bot: Bot, db_path: str, booking_id: int) -> None:
    db = Database(db_path)
    booking = db.get_booking(booking_id)
    if not booking or booking["status"] != "active":
        return

    text = settings.reminder_text_template.format(
        date=format_date_ru(booking["slot_date"]),
        time=booking["slot_time"],
        service=booking["service_title"],
    )
    await bot.send_message(chat_id=booking["user_id"], text=text)



def reminder_job_id(booking_id: int) -> str:
    return f"booking_reminder_{booking_id}"



def remove_reminder_job(scheduler: AsyncIOScheduler, booking_id: int) -> None:
    try:
        scheduler.remove_job(reminder_job_id(booking_id))
    except JobLookupError:
        pass



def schedule_reminder(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    db: Database,
    booking_id: int,
    slot_date: str,
    slot_time: str,
) -> str | None:
    visit_dt = appointment_datetime(slot_date, slot_time)
    reminder_dt = visit_dt - timedelta(hours=24)
    if reminder_dt <= now_local():
        db.update_booking_reminder_job(booking_id, None)
        return None

    job_id = reminder_job_id(booking_id)
    scheduler.add_job(
        send_reminder,
        trigger="date",
        run_date=reminder_dt,
        kwargs={"bot": bot, "db_path": db.path, "booking_id": booking_id},
        id=job_id,
        replace_existing=True,
        misfire_grace_time=3600,
    )
    db.update_booking_reminder_job(booking_id, job_id)
    return job_id



def restore_reminders(scheduler: AsyncIOScheduler, bot: Bot, db: Database) -> None:
    for booking in db.get_future_active_bookings(now_local().strftime("%Y-%m-%d %H:%M:%S")):
        schedule_reminder(
            scheduler=scheduler,
            bot=bot,
            db=db,
            booking_id=booking["id"],
            slot_date=booking["slot_date"],
            slot_time=booking["slot_time"],
        )
