from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_day_choice_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пн, Ср, Пт", callback_data="days_mon_wed_fri")],
        [InlineKeyboardButton(text="Вт, Чт", callback_data="days_tue_thu")],
        [InlineKeyboardButton(text="Все будни", callback_data="days_weekdays")]
    ])

def get_event_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="По дням недели", callback_data="event_type_days")],
        [InlineKeyboardButton(text="Еженедельный", callback_data="event_type_weekly")]
    ])

def get_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
    ])
