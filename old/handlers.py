from aiogram import types
from config import ADMIN_IDS
from old.db import add_event
from datetime import datetime

async def handle_add_event(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("⛔️ У вас нет доступа.")
        return

    try:
        _, dt_part, time_part, *text_parts = message.text.split()
        dt_str = f"{dt_part}T{time_part}"
        datetime.fromisoformat(dt_str)  # проверка формата
        text = ' '.join(text_parts)
        add_event(dt_str, text)
        await message.reply("✅ Ивент добавлен.")
    except Exception as e:
        await message.reply("❌ Ошибка. Используй: /addevent YYYY-MM-DD HH:MM Описание")
