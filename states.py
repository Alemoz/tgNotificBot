from aiogram.fsm.state import StatesGroup, State

class EventCreation(StatesGroup):
    choosing_type = State()
    choosing_days = State()           # для weekly_multiple
    choosing_day_once = State()       # для weekly_once (один день)
    entering_date = State()           # для once
    entering_time = State()
    entering_description = State()




