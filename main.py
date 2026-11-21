import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import BOT_TOKEN
from database.db import init_db
from handlers import setup_routers
from utils.logger import setup_logging

async def main():
    setup_logging()
    await init_db()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    setup_routers(dp)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
