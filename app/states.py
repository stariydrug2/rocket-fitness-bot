from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    choosing_service = State()
    choosing_date = State()
    choosing_time = State()
    entering_name = State()
    entering_phone = State()
    choosing_goal = State()
    entering_custom_goal = State()
    confirming = State()


class AdminStates(StatesGroup):
    choosing_date_for_add_slot = State()
    entering_slot_time = State()
    choosing_date_for_delete_slot = State()
    choosing_date_for_close_day = State()
    choosing_date_for_open_day = State()
    choosing_date_for_schedule = State()
    choosing_date_for_cancel_booking = State()
