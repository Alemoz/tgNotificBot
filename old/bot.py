import os
import asyncio
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
import logging

from collections import defaultdict
from datetime import datetime

# Загрузка переменных из .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002582897974"))

admin_ids_str = os.getenv("ADMIN_USER_IDS", "")
ADMIN_USER_IDS = set(int(admin_id.strip()) for admin_id in admin_ids_str.split(",") if admin_id.strip())

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.WARNING)

DB_PATH = "events.db"
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# --- Работа с базой ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_datetime TEXT NOT NULL,
                description TEXT NOT NULL,
                sent INTEGER DEFAULT 0,
                repeat_weekly INTEGER DEFAULT 0,
                repeat_daily INTEGER DEFAULT 0,
                repeat_on_weekdays TEXT DEFAULT NULL, -- Новое поле
                user_id INTEGER
            )
        """)
        await db.commit()

async def migrate_add_user_id_column():
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем, есть ли колонка user_id
        cursor = await db.execute("PRAGMA table_info(events)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        if "user_id" not in column_names:
            await db.execute("ALTER TABLE events ADD COLUMN user_id INTEGER")
            await db.commit()
            print("✅ Колонка user_id добавлена в таблицу events.")
        else:
            print("ℹ️ Колонка user_id уже существует.")

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Добавить ивент", callback_data="add_event")],
        [InlineKeyboardButton(text="🔁 Добавить еженедельный", callback_data="add_event_weekly")],
        [InlineKeyboardButton(text="📆 Добавить ежедневный", callback_data="add_event_daily")],
        [InlineKeyboardButton(text="📝 Изменить ивент", callback_data="edit_event")],
        [InlineKeyboardButton(text="📋 Список ивентов", callback_data="list_events")],
        [InlineKeyboardButton(text="❌ Удалить ивент", callback_data="delete_event")],
    ])

def start_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠 Открыть админ-панель", callback_data="open_admin")]
    ])

def close_event_list_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_event_list")]
    ])
    return kb

async def add_event_to_db(event_datetime, description, user_id, repeat_weekly=False, repeat_weekdays=None):
    repeat_weekdays_str = ",".join(repeat_weekdays) if repeat_weekdays else None
    query = """
    INSERT INTO events (event_datetime, description, repeat_weekly, repeat_weekdays, user_id)
    VALUES (?, ?, ?, ?, ?)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, (
            event_datetime.isoformat(),
            description,
            1 if repeat_weekly else 0,
            repeat_weekdays_str,
            user_id
        ))
    await db.commit()

async def get_pending_events():
    now = datetime.now()
    current_day = now.strftime("%a")  # 'Mon', 'Tue', etc.

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
               SELECT id, event_datetime, description, repeat_weekly, repeat_daily, repeat_on_weekdays, user_id
               FROM events
               WHERE (
                   sent = 0 AND datetime(event_datetime) <= datetime(?)
               ) OR (
                   repeat_on_weekdays IS NOT NULL AND instr(repeat_on_weekdays, ?) > 0
               )
           """, (now.isoformat(), current_day))
        return await cursor.fetchall()

async def mark_event_sent(event_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE events SET sent=1 WHERE id=?", (event_id,))
        await db.commit()

async def update_event_datetime(event_id: int, new_datetime: datetime):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE events SET event_datetime=?, sent=0 WHERE id=?", (new_datetime.isoformat(), event_id))
        await db.commit()

async def list_all_events():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, event_datetime, description, sent, repeat_weekly FROM events ORDER BY event_datetime")
        return await cursor.fetchall()

async def delete_event(event_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM events WHERE id=?", (event_id,))
        await db.commit()
        return cursor.rowcount > 0

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS

def create_weekdays_keyboard(selected_days: set):
    # Формируем кнопки по рядам, например по 4 кнопки в ряд
    keyboard = []
    row = []
    for i, day in enumerate(WEEKDAYS, start=1):
        prefix = "✅" if day in selected_days else "⬜️"
        button = InlineKeyboardButton(text=f"{prefix} {day}", callback_data=f"weekday_{day}")
        row.append(button)
        if i % 4 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    # Добавляем отдельным рядом кнопку "Готово"
    keyboard.append([InlineKeyboardButton(text="Готово ✅", callback_data="weekday_done")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- FSM States ---
class AddEventStates(StatesGroup):
    waiting_for_datetime = State()
    waiting_for_description = State()

class AddEventDailyStates(StatesGroup):
    waiting_for_datetime_d = State()
    waiting_for_description_d = State()

class AddEventWeeklyStates(StatesGroup):
    waiting_for_datetime_w = State()
    waiting_for_description_w = State()
    waiting_for_weekdays_selection = State()

class AddEventWeekdaysStates(StatesGroup):
    waiting_for_datetime_wd = State()
    waiting_for_description_wd = State()
    waiting_for_weekdays_selection = State()

class EditEventStates(StatesGroup):
    waiting_for_edit_id = State()
    waiting_for_new_dt = State()
    waiting_for_new_desc = State()

# --- Хендлеры команд ---
@dp.message(Command(commands=["start"]))
async def cmd_start(message: types.Message):
    text = (
        "Привет! Я бот для управления игровыми ивентами.\n\n"
        "Доступные команды:\n"
        "/addevent — добавить ивент\n"
        "/addeventw — добавить повторяющийся ивент\n"
        "/events — список всех ивентов\n"
        "/delevent — удалить ивент\n"
    )
    if is_admin(message.from_user.id):
        await message.answer(text, reply_markup=start_menu())
    else:
        await message.answer(text)

@dp.message(Command(commands=["addevent"]))
async def cmd_add_event(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ У тебя нет доступа к этой команде.")
        return
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.reply("Использование:\n/addevent ГГГГ-ММ-ДД ЧЧ:ММ Описание ивента")
        return
    date_str, time_str, description = args[1], args[2], args[3]
    try:
        event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        await message.reply("❌ Неверный формат даты или времени. Используй ГГГГ-ММ-ДД ЧЧ:ММ")
        return
    await add_event_to_db(event_dt, description, message.from_user.id, repeat_weekly=False)
    await message.reply(f"✅ Ивент добавлен на {event_dt.strftime('%Y-%m-%d %H:%M')}:\n{description}")

@dp.message(Command(commands=["addeventd"]))
async def cmd_add_event_daily(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ У тебя нет доступа к этой команде.")
        return
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.reply("Использование:\n/addeventd ГГГГ-ММ-ДД ЧЧ:ММ Описание ивента (ежедневный)")
        return
    date_str, time_str, description = args[1], args[2], args[3]
    try:
        event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        await message.reply("❌ Неверный формат даты или времени. Используй ГГГГ-ММ-ДД ЧЧ:ММ")
        return
    await add_event_to_db(event_dt, description, message.from_user.id, repeat_daily=True)
    await message.reply(f"✅ Ежедневный ивент добавлен на {event_dt.strftime('%Y-%m-%d %H:%М')}:\n{description}")

@dp.message(Command(commands=["addeventwd"]))
async def cmd_add_event_weekdays(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ У тебя нет доступа к этой команде.")
        return
    args = message.text.split(maxsplit=4)
    if len(args) < 5:
        await message.reply("Использование:\n/addeventwd ГГГГ-ММ-ДД ЧЧ:ММ Дни_недели Описание\n"
                            "Пример: /addeventwd 2024-06-15 14:00 Mon,Wed,Sun Ивент в выходные")
        return
    date_str, time_str, weekdays_str, description = args[1], args[2], args[3], args[4]
    try:
        event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        await message.reply("❌ Неверный формат даты или времени. Используй ГГГГ-ММ-ДД ЧЧ:ММ")
        return

    # Очистка и проверка дней недели
    weekdays_list = [d.strip().capitalize()[:3] for d in weekdays_str.split(",")]
    valid_days = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
    if not all(day in valid_days for day in weekdays_list):
        await message.reply("❌ Неверный формат дней недели. Используй сокращения: Mon,Tue,Wed,...")
        return
    repeat_days = ",".join(weekdays_list)

    await add_event_to_db(event_dt, description, message.from_user.id, repeat_on_weekdays=repeat_days)
    await message.reply(f"✅ Ивент по дням недели ({repeat_days}) добавлен на {event_dt.strftime('%Y-%m-%d %H:%M')}:\n{description}")

@dp.message(Command(commands=["addeventw"]))
async def cmd_add_event_weekly(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ У тебя нет доступа к этой команде.")
        return
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.reply("Использование:\n/addeventw ГГГГ-ММ-ДД ЧЧ:ММ Описание ивента (еженедельный)")
        return
    date_str, time_str, description = args[1], args[2], args[3]
    try:
        event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        await message.reply("❌ Неверный формат даты или времени. Используй ГГГГ-ММ-ДД ЧЧ:ММ")
        return
    await add_event_to_db(event_dt, description, message.from_user.id, repeat_weekly=True)
    await message.reply(f"✅ Повторяющийся еженедельный ивент добавлен на {event_dt.strftime('%Y-%m-%d %H:%M')}:\n{description}")

@dp.message(Command(commands=["events"]))
async def cmd_list_events(message: types.Message, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, event_datetime, description, repeat_daily FROM events ORDER BY event_datetime"
        )
        events = await cursor.fetchall()
    if not events:
        await message.answer("📭 У тебя пока нет ивентов.")
        return

    text = "📅 <b>Список ивентов:</b>\n\n"
    for ev in events:
        dt = datetime.fromisoformat(ev[1])
        daily_mark = " 🔁 (Ежедневно)" if ev[3] else ""
        text += f"<b>ID:</b> {ev[0]} | <b>⏰</b> {dt.strftime('%Y-%m-%d %H:%M')}{daily_mark}\n📌 {ev[2]}\n\n"
    msg = await message.answer(text, reply_markup=close_event_list_kb(), parse_mode="HTML")
    fsm_messages[message.from_user.id].append(msg)

@dp.callback_query(F.data == "close_event_list")
async def close_event_list(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Закрыто ✅", show_alert=False)

@dp.message(Command(commands=["delevent"]))
async def cmd_delete_event(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ У тебя нет доступа к этой команде.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].isdigit():
        await message.reply("Использование:\n/delevent ID (где ID — число из списка ивентов)")
        return
    event_id = int(args[1])
    deleted = await delete_event(event_id)
    if deleted:
        await message.reply(f"✅ Ивент с ID {event_id} удалён.")
    else:
        await message.reply(f"❌ Ивент с ID {event_id} не найден.")

@dp.message(Command(commands=["getid"]))
async def cmd_getid(message: types.Message):
    await message.answer(f"🆔 Твой ID: <code>{message.from_user.id}</code>")

# --- Обработка коллбеков ---
@dp.callback_query()
async def handle_admin_callbacks(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("❌ У тебя нет доступа к админ-панели.", show_alert=True)
        return
    await cleanup_fsm_messages(user_id)
    data = callback.data
    if data == "open_admin":
        await callback.message.edit_text("🛠 Выбери действие:", reply_markup=admin_menu())
        await callback.answer()

    elif data == "add_event":
        msg = await callback.message.answer("📅 Введи дату и время ивента (ГГГГ-ММ-ДД ЧЧ:ММ):")
        fsm_messages[callback.from_user.id].append(msg)
        await state.set_state(AddEventStates.waiting_for_datetime)
        await callback.answer()
    elif data == "add_event_daily":
        msg = await callback.message.answer("📅 Введи дату и время ежедневного ивента (ГГГГ-ММ-ДД ЧЧ:ММ):")
        fsm_messages[callback.from_user.id].append(msg)
        await state.set_state(AddEventDailyStates.waiting_for_datetime_d)
        await callback.answer()
    elif data == "add_event_weekly":
        msg = await bot.send_message(callback.from_user.id, "📅 Введи дату и время еженедельного ивента (ГГГГ-ММ-ДД ЧЧ:ММ):")
        fsm_messages[callback.from_user.id].append(msg)
        await state.set_state(AddEventWeeklyStates.waiting_for_datetime_w)
        await callback.answer()
    elif data == "add_event_weekdays":
        msg = await callback.message.answer(
            "📅 Введи дату и время ивента, повторяющегося по дням недели (ГГГГ-ММ-ДД ЧЧ:ММ):")
        fsm_messages[callback.from_user.id].append(msg)
        await state.set_state(AddEventWeekdaysStates.waiting_for_datetime_wd)
        await callback.answer()

    elif data == "edit_event":
        msg = await callback.message.answer("🆔 Введи ID ивента, который хочешь изменить:")
        fsm_messages[callback.from_user.id].append(msg)
        await state.set_state(EditEventStates.waiting_for_edit_id)
        await callback.answer()

    elif data == "list_events":
        await cmd_list_events(callback.message, user_id=callback.from_user.id)
        await callback.answer()

    elif data == "delete_event":
        msg = await callback.message.answer("🗑 Введи /delevent ID, чтобы удалить ивент")
        fsm_messages[callback.from_user.id].append(msg)
        await callback.answer()
    elif data and data.startswith(
            "weekday_") and await state.get_state() == AddEventWeeklyStates.waiting_for_weekdays_selection.state:
        stored_data = await state.get_data()
        selected = set(stored_data.get("selected_weekdays", []))

        action = data[len("weekday_"):]

        if action == "done":
            if not selected:
                await callback.answer("❗ Нужно выбрать хотя бы один день!", show_alert=True)
                return

            event_dt = stored_data.get("event_datetime")
            description = stored_data.get("description")
            selected_days = list(selected)

            await add_event_to_db(event_dt, description, user_id, repeat_weekly=True, repeat_weekdays=selected_days)

            await callback.message.answer(
                f"✅ Ивент добавлен с повторением по дням: {', '.join(selected_days)}\n"
                f"Дата и время старта: {event_dt.strftime('%Y-%m-%d %H:%M')}\n"
                f"Описание: {description}"
            )
            await state.clear()
            await callback.answer()
        else:
            # Toggle выбранного дня недели
            if action in selected:
                selected.remove(action)
            else:
                selected.add(action)
            await state.update_data(selected_weekdays=list(selected))

            # Обновляем клавиатуру с выделением выбранных дней (если есть)
            keyboard = create_weekdays_keyboard(selected)  # Ваша функция для генерации клавиатуры
            await callback.message.edit_reply_markup(reply_markup=keyboard)
            await callback.answer()
# --- FSM для добавления одноразового ивента ---

fsm_messages = defaultdict(list)

async def cleanup_fsm_messages(user_id: int):
    for msg in fsm_messages[user_id]:
        try:
            await msg.delete()
        except Exception:
            pass
    fsm_messages[user_id].clear()

@dp.message(AddEventStates.waiting_for_datetime)
async def fsm_add_datetime(message: types.Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
        await state.update_data(event_datetime=dt)
        try:
            await message.delete()
        except Exception:
            pass
        await cleanup_fsm_messages(message.from_user.id)  # Очистка старых сообщений
        msg = await message.answer("📝 Теперь введи описание:")
        fsm_messages[message.from_user.id].append(msg)
        await state.set_state(AddEventStates.waiting_for_description)
    except ValueError:
        try:
            await message.delete()
        except Exception:
            pass
        await cleanup_fsm_messages(message.from_user.id)
        msg = await message.answer("❌ Неверный формат. Попробуй ещё раз.")
        fsm_messages[message.from_user.id].append(msg)

@dp.message(AddEventStates.waiting_for_description)
async def fsm_add_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    dt = data["event_datetime"]
    desc = message.text.strip()
    try:
        await message.delete()
    except Exception:
        pass
    await add_event_to_db(dt, desc, message.from_user.id, repeat_weekly=False)
    await cleanup_fsm_messages(message.from_user.id)
    msg = await message.answer(f"✅ Ивент добавлен на {dt.strftime('%Y-%m-%d %H:%M')}:\n{desc}")
    fsm_messages[message.from_user.id].append(msg)
    await state.clear()

@dp.message(AddEventDailyStates.waiting_for_datetime_d)
async def fsm_add_daily_datetime(message: types.Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
        await state.update_data(event_datetime=dt)
        try:
            await message.delete()
        except Exception:
            pass
        await cleanup_fsm_messages(message.from_user.id)
        msg = await message.answer("📝 Теперь введи описание ежедневного ивента:")
        fsm_messages[message.from_user.id].append(msg)
        await state.set_state(AddEventDailyStates.waiting_for_description_d)
    except ValueError:
        try:
            await message.delete()
        except Exception:
            pass
        await cleanup_fsm_messages(message.from_user.id)
        msg = await message.answer("❌ Неверный формат даты или времени. Попробуй ещё раз (ГГГГ-ММ-ДД ЧЧ:ММ).")
        fsm_messages[message.from_user.id].append(msg)

@dp.message(AddEventDailyStates.waiting_for_description_d)
async def fsm_add_daily_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    dt = data["event_datetime"]
    desc = message.text.strip()
    try:
        await message.delete()
    except Exception:
        pass
    # Добавляем ивент с repeat_daily=1
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO events (event_datetime, description, repeat_daily, user_id) VALUES (?, ?, 1, ?)",
            (dt.isoformat(), desc, message.from_user.id)
        )
        await db.commit()
    await cleanup_fsm_messages(message.from_user.id)
    msg = await message.answer(f"✅ Ежедневный ивент добавлен на {dt.strftime('%Y-%m-%d %H:%M')}:\n{desc}")
    fsm_messages[message.from_user.id].append(msg)
    await state.clear()

@dp.message(AddEventWeeklyStates.waiting_for_datetime_w)
async def fsm_weekly_datetime(message: types.Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
        await state.update_data(event_datetime=dt)
        try:
            await message.delete()
        except Exception:
            pass
        await cleanup_fsm_messages(message.from_user.id)
        msg = await message.answer("📝 Теперь введи описание:")
        fsm_messages[message.from_user.id].append(msg)
        await state.set_state(AddEventWeeklyStates.waiting_for_description_w)
    except ValueError:
        try:
            await message.delete()
        except Exception:
            pass
        await cleanup_fsm_messages(message.from_user.id)
        msg = await message.answer("❌ Неверный формат. Попробуй ещё раз (ГГГГ-ММ-ДД ЧЧ:ММ)")
        fsm_messages[message.from_user.id].append(msg)


async def fsm_weekly_description(message: types.Message, state: FSMContext):
    desc = message.text.strip()
    data = await state.get_data()
    dt = data["event_datetime"]

    await state.update_data(description=desc)
    await state.update_data(selected_weekdays=set())  # используем set для удобства

    kb = create_weekdays_keyboard(set())  # стартовая клавиатура без выбранных дней

    await message.answer(
        "Выбери дни недели, по которым будет повторяться ивент.\n"
        "Нажимай на дни, чтобы выбрать/отменить.\n"
        "Когда закончишь — нажми кнопку 'Готово'.",
        reply_markup=kb
    )
    await state.set_state(AddEventWeeklyStates.waiting_for_weekdays_selection)
    dp.message.register(
    fsm_weekly_description,
    filters=StateFilter(AddEventWeeklyStates.waiting_for_description_w)
)


@dp.message(EditEventStates.waiting_for_edit_id)
async def fsm_edit_id(message: types.Message, state: FSMContext):
    try:
        event_id = int(message.text.strip())
        await state.update_data(event_id=event_id)
        try:
            await message.delete()
        except Exception:
            pass
        await cleanup_fsm_messages(message.from_user.id)
        msg = await message.answer("📅 Введи новую дату и время (ГГГГ-ММ-ДД ЧЧ:ММ):")
        fsm_messages[message.from_user.id].append(msg)
        await state.set_state(EditEventStates.waiting_for_new_dt)
    except ValueError:
        try:
            await message.delete()
        except Exception:
            pass
        await cleanup_fsm_messages(message.from_user.id)
        msg = await message.answer("❌ ID должен быть числом. Попробуй снова.")
        fsm_messages[message.from_user.id].append(msg)


@dp.message(EditEventStates.waiting_for_new_dt)
async def fsm_edit_dt(message: types.Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
        await state.update_data(new_dt=dt)
        try:
            await message.delete()
        except Exception:
            pass
        await cleanup_fsm_messages(message.from_user.id)
        msg = await message.answer("📝 Теперь описание:")
        fsm_messages[message.from_user.id].append(msg)
        await state.set_state(EditEventStates.waiting_for_new_desc)
    except ValueError:
        try:
            await message.delete()
        except Exception:
            pass
        await cleanup_fsm_messages(message.from_user.id)
        msg = await message.answer("❌ Неверный формат даты. Попробуй снова.")
        fsm_messages[message.from_user.id].append(msg)


@dp.message(EditEventStates.waiting_for_new_desc)
async def fsm_edit_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ev_id, new_dt = data["event_id"], data["new_dt"]
    desc = message.text.strip()
    try:
        await message.delete()
    except Exception:
        pass
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE events SET event_datetime=?, description=?, sent=0 WHERE id=?",
            (new_dt.isoformat(), desc, ev_id))
        await db.commit()
    await cleanup_fsm_messages(message.from_user.id)
    if cursor.rowcount:
        msg = await message.answer("✅ Ивент обновлён.")
    else:
        msg = await message.answer("❌ Ивент с таким ID не найден.")
    fsm_messages[message.from_user.id].append(msg)
    await state.clear()

# --- Фоновая задача отправки ивентов ---
async def event_sender_task():
    while True:
        now = datetime.now()
        current_day = now.strftime("%a")  # например, "Mon"
        events = await get_pending_events()

        for event in events:
            event_id, dt_str, description, repeat_weekly, repeat_daily, repeat_on_weekdays, user_id = event
            dt = datetime.fromisoformat(dt_str)

            should_send = False

            # Проверяем повторение по конкретным дням недели
            if repeat_on_weekdays:
                weekdays = repeat_on_weekdays.split(",")  # например ["Mon", "Wed", "Fri"]
                # Сравниваем день недели
                if current_day in weekdays:
                    # Проверяем, совпадает ли время события с текущим в пределах 1 минуты
                    delta = abs((now - dt).total_seconds())
                    if delta < 60:
                        should_send = True

            # Если событие не повторяется по дням недели, проверяем остальные варианты
            elif now >= dt:
                should_send = True

            if not should_send:
                continue

            try:
                await bot.send_message(
                    CHANNEL_ID,
                    f"📢 <b>Напоминание об ивенте:</b>\n⏰ {dt.strftime('%Y-%m-%d %H:%M')}\n📌 {description}"
                )

                # Обработка даты для повторений
                if repeat_on_weekdays:
                    # Обновляем дату на следующую неделю, чтобы не слать каждую минуту в этот день
                    new_dt = dt + timedelta(weeks=1)
                    await update_event_datetime(event_id, new_dt)

                elif repeat_daily:
                    new_dt = dt + timedelta(days=1)
                    await update_event_datetime(event_id, new_dt)

                elif repeat_weekly:
                    new_dt = dt + timedelta(weeks=1)
                    await update_event_datetime(event_id, new_dt)

                else:
                    await mark_event_sent(event_id)

            except Exception as e:
                print(f"Ошибка при отправке ивента {event_id}: {e}")

        await asyncio.sleep(60)


# --- Запуск ---
@dp.startup()
async def on_startup(bot: Bot):
    print("Бот запущен")
    asyncio.create_task(event_sender_task())

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
