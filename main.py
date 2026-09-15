import logging
import asyncio

from telegram.create_bot import bot, dp
from telegram.handlers import start_router
from alerts.state_store import StateStore, IncidentStore
from alerts.monitor import monitoring_loop
from config import alert_chat_id, LOGGING_FORMAT, LOGGING_LEVEL

logging.basicConfig(
    level=LOGGING_LEVEL,
    format=LOGGING_FORMAT
)
logger = logging.getLogger(__name__)


async def main():
    logger.info('ServerMonitor is starting')
    store = StateStore()
    incident = IncidentStore()

    dp.include_router(start_router)

    asyncio.create_task(
        monitoring_loop(store,incident, bot, chat_id=alert_chat_id)
    )

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

