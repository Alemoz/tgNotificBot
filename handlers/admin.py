import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from states import EventCreation
from database import add_event, get_all_events, delete_event
from asyncio import sleep
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

router = Router()

load_dotenv()

admin_ids_str = os.getenv("ADMIN_USER_IDS", "")
ADMIN_IDS = set(map(int, admin_ids_str.split(','))) if admin_ids_str else set()
WEEKDAY_SHORT_RU = {
    "mon": "Пн",
    "tue": "Вт",
    "wed": "Ср",
    "thu": "Чт",
    "fri": "Пт",
    "sat": "Сб",
    "sun": "Вс"
}
EVENT_TYPE_RU = {
    "weekly_once": "1 раз в неделю",
    "weekly_multiple": "несколько дней в неделю",
    "once": "одноразовый",
    "weekday": "будничный"
}
DAY_ORDER = {'mon': 1, 'tue': 2, 'wed': 3, 'thu': 4, 'fri': 5, 'sat': 6, 'sun': 7}
DAY_GROUPS = {
    "Пн, Ср, Пт": {"mon", "wed", "fri"},
    "Вт, Чт": {"tue", "thu"},
    "Будни": {"mon", "tue", "wed", "thu", "fri"},
    "Все дни недели": {"mon", "tue", "wed", "thu", "fri", "sat", "sun"},
}

def classify_days(days_str):
    if not days_str:
        return None

    days = set(days_str.split(","))
    for name, group_days in DAY_GROUPS.items():
        if days == group_days:
            return name
    return "Прочее"

def time_key(event):
    try:
        return datetime.strptime(event[4], "%H:%M")
    except:
        return datetime.strptime("00:00", "%H:%M")

def get_event_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Еженедельные ивенты (несколько дней)", callback_data="weekly_multiple")],
        [InlineKeyboardButton(text="Еженедельный ивент (1 рза в неделю)", callback_data="weekly_once")],
        # [InlineKeyboardButton(text="Будничный ивент", callback_data="weekdays")],
        [InlineKeyboardButton(text="Одноразовый ивент", callback_data="once")]
    ])


def get_days_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пн, Ср, Пт", callback_data="mon,wed,fri")],
        [InlineKeyboardButton(text="Вт, Чт", callback_data="tue,thu")],
        [InlineKeyboardButton(text="Будни", callback_data="mon,tue,wed,thu,fri")],
        [InlineKeyboardButton(text="Все дни недели", callback_data="mon,tue,wed,thu,fri,sat,sun")]
    ])


def get_weekday_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Понедельник", callback_data="mon")],
        [InlineKeyboardButton(text="Вторник", callback_data="tue")],
        [InlineKeyboardButton(text="Среда", callback_data="wed")],
        [InlineKeyboardButton(text="Четверг", callback_data="thu")],
        [InlineKeyboardButton(text="Пятница", callback_data="fri")],
        [InlineKeyboardButton(text="Суббота", callback_data="sat")],
        [InlineKeyboardButton(text="Воскресенье", callback_data="sun")],
    ])


def admin_only(handler):
    async def wrapper(message: Message, state: FSMContext, *args, **kwargs):
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("❌ У вас нет прав для использования этой команды.")
            return
        return await handler(message, state, *args, **kwargs)

    return wrapper


def convert_days_to_ru(days_str: str) -> str:
    if not days_str:
        return ""
    days_list = days_str.split(",")
    ru_days = [WEEKDAY_SHORT_RU.get(day, day) for day in days_list]
    return ", ".join(ru_days)


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⚠️ У вас нет доступа к админ панели.")
        return

    await state.clear()

    # Текущее время сервера (UTC)
    utc_now = datetime.now(timezone.utc)

    # Время по GMT+3
    gmt3_now = utc_now.astimezone(timezone(timedelta(hours=3)))

    # Форматируем строки
    server_time_str = utc_now.strftime("%Y-%m-%d %H:%M:%S UTC")
    local_time_str = gmt3_now.strftime("%Y-%m-%d %H:%M:%S GMT+3")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать ивент", callback_data="create_event")],
        [InlineKeyboardButton(text="Список ивентов", callback_data="list_events")]
    ])

    await message.answer(
        f"📋 <b>Панель администратора</b>\n\n"
        f"🕒 <b>Время сервера (UTC):</b> {server_time_str}\n"
        f"🕒 <b>Местное время (GMT+3):</b> {local_time_str}",
        reply_markup=kb
    )


@router.message(Command("getdb"))
async def send_db_file(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет доступа.")
        return

    try:
        file = FSInputFile("events.db")
        await message.answer_document(file, caption="📦 Файл базы данных")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка при отправке файла: {e}")


@router.callback_query(F.data == "create_event")
async def create_event(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EventCreation.choosing_type)
    await callback.answer()
    await callback.message.answer("Выберите тип ивента:", reply_markup=get_event_type_kb())


# Шаг 1: Выбор типа ивента
@router.callback_query(F.data.in_({"weekly_multiple", "weekly_once", "once", "weekdays"}))
async def choose_type(callback: CallbackQuery, state: FSMContext):
    await state.update_data(type=callback.data)
    if callback.data == "weekly_multiple":
        await callback.message.edit_text("Выберите дни для ивента:", reply_markup=get_days_kb())
        await state.set_state(EventCreation.choosing_days)
    elif callback.data == "weekly_once":
        await callback.message.edit_text("Выберите день недели для ивента:", reply_markup=get_weekday_kb())
        await state.set_state(EventCreation.choosing_day_once)
    elif callback.data == "once":
        await callback.message.edit_text("Введите дату ивента (в формате ГГГГ-ММ-ДД):")
        await state.set_state(EventCreation.entering_date)
    elif callback.data == "weekdays":
        # Устанавливаем фиксированные будние дни
        await state.update_data(days="mon,tue,wed,thu,fri")
        time_msg = await callback.message.answer("Введите время начала ивента (формат HH:MM):")
        await state.update_data(time_prompt_id=time_msg.message_id)
        await state.set_state(EventCreation.entering_time)


@router.callback_query(EventCreation.choosing_day_once)
async def choose_day_once(callback: CallbackQuery, state: FSMContext):
    await state.update_data(day=callback.data)
    try:
        await callback.message.delete()
    except Exception:
        pass
    time_msg = await callback.message.answer("Введите время начала ивента (формат HH:MM):")
    await state.update_data(time_prompt_id=time_msg.message_id)

    await state.set_state(EventCreation.entering_time)


@router.callback_query(EventCreation.choosing_days)
async def choose_multiple_days(callback: CallbackQuery, state: FSMContext):
    await state.update_data(days=callback.data)

    try:
        await callback.message.delete()
    except Exception:
        pass

    time_msg = await callback.message.answer("Введите время начала ивента (формат HH:MM):")
    await state.update_data(time_prompt_id=time_msg.message_id)
    await state.set_state(EventCreation.entering_time)


@router.message(EventCreation.entering_time)
async def enter_time(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(time=message.text)

    try:
        await message.delete()
    except Exception:
        pass

    if "time_prompt_id" in data:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=data["time_prompt_id"])
        except Exception:
            pass

    # Отправляем "Введите описание..." и сохраняем ID
    next_msg = await message.answer("Введите описание ивента:")
    await state.update_data(description_prompt_id=next_msg.message_id)

    await state.set_state(EventCreation.entering_description)


@router.message(EventCreation.entering_description)
async def enter_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    data = await state.get_data()

    # Удаление сообщений
    try:
        await message.delete()
    except Exception:
        pass

    if "description_prompt_id" in data:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=data["description_prompt_id"])
        except Exception:
            pass
    if data.get("type") == "weekly_once" and not data.get("days"):
        data["days"] = data.get("day")  # day='mon', например
    # Сохранение события в БД
    add_event(
        event_type=data.get("type"),
        days=data.get("days"),
        date=data.get("date"),
        time=data.get("time"),
        description=data.get("description")
    )

    msg = await message.answer("✅ Ивент сохранён.")
    await sleep(5)
    try:
        await msg.delete()
    except Exception:
        pass
    await state.clear()


@router.callback_query(F.data == "list_events")
async def list_events(callback: CallbackQuery):
    events = get_all_events()
    if not events:
        await callback.message.edit_text("⚠️ Ивенты не найдены.", reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="hide_list")]]
        ))
        return

    # Группировка
    grouped = {
        "Пн, Ср, Пт": [],
        "Вт, Чт": [],
        "Будни": [],
        "Все дни недели": [],
        "Прочее": []
    }

    for e in events:
        _, type_, days, date, time, description = e
        group_name = classify_days(days)
        grouped[group_name].append(e)

    # Формируем текст
    text = "📋 <b>Ивенты:</b>\n\n"
    for group_name in ["Пн, Ср, Пт", "Вт, Чт", "Будни", "Все дни недели", "Прочее"]:
        events_in_group = sorted(grouped[group_name], key=time_key)
        if not events_in_group:
            continue
        text += f"🔹 <b>{group_name}</b>\n"
        for e in events_in_group:
            event_id = e[0]
            event_type = e[1]
            days = e[2]
            date = e[3]
            time = e[4]
            description = e[5]

            ru_type = EVENT_TYPE_RU.get(event_type, event_type)
            days_display = convert_days_to_ru(days) if days else date

            text += (
                "━━━━━━━━━━━━━━\n"
                f"🆔 <b>{event_id}</b> | <i>{ru_type}</i>\n"
                f"📅 <b>{days_display}</b> ⏰ <b>{time}</b>\n"
                f"📝 <i>{description}</i>\n"
            )
        text += "━━━━━━━━━━━━━━\n\n"

    text += "Чтобы удалить: /delete ID"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Скрыть", callback_data="hide_list")]]
    ))


@router.callback_query(F.data == "hide_list")
async def hide_list(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать ивент", callback_data="create_event")],
        [InlineKeyboardButton(text="Список ивентов", callback_data="list_events")]
    ])
    await callback.message.edit_text("Панель администратора", reply_markup=kb)


@router.message(Command("delete"))
async def delete_by_id(message: Message):
    try:
        event_id = int(message.text.split()[1])
        delete_event(event_id)
        sent_msg = await message.answer("🗑️ Ивент удалён.")
        await sleep(5)

        # Удаляем сообщение пользователя (с вводом описания)
        await message.delete()
        # Удаляем сообщение бота с подтверждением
        await sent_msg.delete()
    except:
        await message.answer("⚠️ Укажите ID: /delete 1")
