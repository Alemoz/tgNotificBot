import asyncio
import os
import threading
import socket

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from aiogram.client.default import DefaultBotProperties

from handlers import admin
from utils.scheduler import schedule_event_notifications

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("CHANNEL_ID", "0"))  # добавлен дефолт
PORT = int(os.getenv("PORT", 10000))  # Render по умолчанию ожидает порт 10000


def dummy_server():
    """
    Фиктивный сервер, чтобы Render не завершал Web Service из-за "отсутствия открытого порта".
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", PORT))
            s.listen(1)
            while True:
                conn, _ = s.accept()
                conn.close()
        except OSError as e:
            print(f"Dummy server error: {e}")


async def main():
    # Запускаем фиктивный сервер в отдельном потоке
    threading.Thread(target=dummy_server, daemon=True).start()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin.router)

    # Планировщик уведомлений
    asyncio.create_task(schedule_event_notifications(bot, GROUP_CHAT_ID))

    # Отключаем вебхуки и запускаем long polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
