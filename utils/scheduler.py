import asyncio
from datetime import datetime, timezone, timedelta
from database import get_all_events
import logging

# ⏳ Удаление сообщения через указанное время
async def delete_after_delay(bot, chat_id, message_id, delay=300):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
        print(f"🗑️ Сообщение {message_id} удалено")
    except Exception as e:
        logging.warning(f"⚠️ Не удалось удалить сообщение {message_id}: {e}")

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
                    msg = await bot.send_message(group_id, message)
                    # ⏱️ Удаление через 5 минут
                    asyncio.create_task(delete_after_delay(bot, group_id, msg.message_id, delay=600))
            except Exception as e:
                logging.error(f"❌ Ошибка при обработке ивента {event_id}: {e}")

        await asyncio.sleep(60)
