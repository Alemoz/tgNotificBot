from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from database import get_all_events

scheduler = AsyncIOScheduler()

def schedule_event_notifications(bot, group_id):
    @scheduler.scheduled_job("cron", minute="*")  # проверка каждую минуту
    async def send_events():
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        weekday = now.strftime("%a").lower()
        current_time = now.strftime("%H:%M")

        for event in get_all_events():
            _, type_, days, date, time_, desc = event

            if type_ == "weekly":
                if weekday in days.split(",") and time_ == current_time:
                    await bot.send_message(group_id, f"🔁 <b>Ивент:</b> {desc}\n🕒 {time_}")
            elif type_ == "once":
                if date == today and time_ == current_time:
                    await bot.send_message(group_id, f"📌 <b>Одноразовый ивент:</b> {desc}\n🕒 {time_}")

    scheduler.start()
