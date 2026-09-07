import logging
import asyncio

from telegram.create_bot import bot, dp
from telegram.handlers import start_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s| %(levelname)s | %(name)s | %(message)s"
)

async def main():
    dp.include_router(start_router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

