import logging
import asyncio
from pathlib import Path
from telegram.create_bot import create_bot
from telegram.handlers import start_router
from alerts.state_store import StateStore, IncidentStore
from alerts.monitor import monitoring_loop
from telegram.filters import AllowedUserFilter

from config import get_settings

async def main():
    base_path = Path(__file__).resolve().parent
    settings = get_settings(base_path)

    logging.basicConfig(
        level=settings.logger.level,
        format=settings.logger.format
    )

    logger = logging.getLogger(__name__)

    logger.info('ServerMonitor is starting')
    store = StateStore()
    incident = IncidentStore()
    bot, dp = create_bot(settings.telegram.token)

    start_router.message.filter(
        AllowedUserFilter(settings.telegram.allowed_users)
    )

    dp.include_router(start_router)

    asyncio.create_task(
        monitoring_loop(store,incident, bot, 
                        chat_id=settings.telegram.alert_chat_id, 
                        settings=settings
        )
    )

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

