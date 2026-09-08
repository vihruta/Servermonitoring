import logging
import asyncio

from telegram.create_bot import bot, dp
from telegram.handlers import start_router
from alerts.state_store import StateStore
from alerts.monitor import monitoring_loop
from config import alert_chat_id

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s| %(levelname)s | %(name)s | %(message)s"
)

async def main():
    store = StateStore()

    dp.include_router(start_router)

    asyncio.create_task(
        monitoring_loop(store, bot, chat_id=alert_chat_id)
    )

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

