from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
from datetime import datetime
from database import get_all_events
import logging

async def schedule_event_notifications(bot, group_id):
    while True:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        weekday = now.strftime("%a").lower()
        print(weekday)
        current_time = now.strftime("%H:%M")

        try:
            events = get_all_events()
        except Exception as e:
            logging.error(f"Ошибка при получении ивентов из БД: {e}")
            await asyncio.sleep(5)
            continue

        for event in events:
            event_id, type_, days, date, time_, desc = event

            try:
                if type_ == "weekly":
                    if days and weekday in days.split(",") and time_ == current_time:
                        await bot.send_message(group_id, f"🔁 <b>Ивент:</b> {desc}\n🕒 {time_}")

                elif type_ == "once":
                    if date == today and time_ == current_time:
                        await bot.send_message(group_id, f"📌 <b>Одноразовый ивент:</b> {desc}\n🕒 {time_}")
                        # Тут можно удалить/отметить отправленным в БД

                elif type_ == "weekly_once":
                    if weekday in (days or "") and time_ == current_time:
                        await bot.send_message(group_id, f"🔂 <b>Еженедельный разовый ивент:</b> {desc}\n🕒 {time_}")
                        # Тут можно обновить дату на +7 дней, чтобы не спамил
                elif type_ == "weekly_multiple":
                    if weekday in (days or "") and time_ == current_time:
                        await bot.send_message(group_id, f"🔂 <b>Будничный ивент:</b> {desc}\n🕒 {time_}")
                        # Тут можно обновить дату на +7 дней, чтобы не спамил

            except Exception as e:
                logging.error(f"Ошибка при обработке ивента {event_id}: {e}")
        await asyncio.sleep(60)