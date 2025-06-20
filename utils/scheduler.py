import asyncio
from datetime import datetime, timezone, timedelta
from database import get_all_events
import logging


async def schedule_event_notifications(bot, group_id):
    # Смещение для UTC+3
    tz_offset = timedelta(hours=3)

    while True:
        # Текущее время на сервере в UTC
        now_utc = datetime.now(timezone.utc)
        # Преобразуем в UTC+3
        now_local = now_utc.astimezone(timezone(tz_offset))

        today = now_local.strftime("%Y-%m-%d")
        weekday = now_local.strftime("%a").lower()
        current_time = now_local.strftime("%H:%M")
        timestamp = now_local.strftime("%Y-%m-%d %H:%M:%S")

        print(f"⏰ [{timestamp}] Бот работает")

        try:
            events = get_all_events()
        except Exception as e:
            logging.error(f"❌ Ошибка при получении ивентов из БД: {e}")
            await asyncio.sleep(60)
            continue

        for event in events:
            event_id, type_, days, date, time_, desc = event

            try:
                send = False
                message = ""

                if type_ == "weekly":
                    if days and weekday in days.split(",") and time_ == current_time:
                        message = f"🔁 <b>Ивент:</b> {desc}\n🕒 {time_}"
                        send = True

                elif type_ == "once":
                    if date == today and time_ == current_time:
                        message = f"📌 <b>Одноразовый ивент:</b> {desc}\n🕒 {time_}"
                        send = True

                elif type_ == "weekly_once":
                    if weekday in (days or "") and time_ == current_time:
                        message = f"🔂 <b>Еженедельный разовый ивент:</b> {desc}\n🕒 {time_}"
                        send = True

                elif type_ == "weekly_multiple":
                    if weekday in (days or "") and time_ == current_time:
                        message = f"🔂 <b>Будничный ивент:</b> {desc}\n🕒 {time_}"
                        send = True

                if send:
                    print(f"📨 [{timestamp}] Отправка уведомления: {message}")
                    await bot.send_message(group_id, message)

            except Exception as e:
                logging.error(f"❌ Ошибка при обработке ивента {event_id}: {e}")

        await asyncio.sleep(60)
