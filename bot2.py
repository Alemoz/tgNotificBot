import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from aiogram.client.default import DefaultBotProperties

from handlers import admin
from utils.scheduler import schedule_event_notifications

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("CHANNEL_ID", "0"))


async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    if not BOT_TOKEN or GROUP_CHAT_ID == 0:
        raise RuntimeError("❌ BOT_TOKEN или CHANNEL_ID не установлены!")
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin.router)

    asyncio.create_task(schedule_event_notifications(bot, GROUP_CHAT_ID))

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
