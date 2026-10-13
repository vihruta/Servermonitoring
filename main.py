import logging
import asyncio
import httpx
from pathlib import Path
from aiogram.exceptions import TelegramNetworkError


from telegram.create_bot import create_bot, setup_commands
from telegram.handlers import start_router
from telegram.filters import AllowedUserFilter

from alerts.state_store import (AlertCooldownStore, StateStore, 
                                IncidentStore, PendingStore, 
                                NetworkAccidentStore, SmartCounterStore,
                                HttpSnapshotStore, SmartSnapshotStore)
from alerts.monitor import monitoring_loop, http_monitoring_loop, network_monitoring_loop, smart_monitoring_loop

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

    cooldown_timer = AlertCooldownStore()
    store = StateStore()
    incident = IncidentStore()
    pending_timer = PendingStore()
    network_incident = NetworkAccidentStore()
    smart_store = SmartSnapshotStore()
    smart_counter_store = SmartCounterStore()
    http_store = HttpSnapshotStore()

    bot, dp = create_bot(settings.telegram.token)
    
    try:
        await setup_commands(bot)
    except TelegramNetworkError:
        logger.exception('Command dont update')

    start_router.message.filter(
        AllowedUserFilter(settings.telegram.allowed_users)
    )
    
    dp.include_router(start_router)

    async with httpx.AsyncClient() as client:
        monitoring_task = asyncio.create_task(
            monitoring_loop(store,
                            cooldown_timer,
                            incident,
                            pending_timer, 
                            bot, 
                            chat_id=settings.telegram.alert_chat_id, 
                            settings=settings
            )
        )
        http_task = asyncio.create_task(
            http_monitoring_loop(
                client=client,
                store=store,
                http_store=http_store,
                incident=incident,
                cooldown_timer=cooldown_timer,
                bot=bot,
                chat_id=settings.telegram.alert_chat_id,
                http_settings=settings.http_services,

            )
        )
        network_task = asyncio.create_task(
            network_monitoring_loop(
                client=client,
                http_store=http_store,
                network_incident=network_incident,
                network_settings=settings.internet,
                cooldown=cooldown_timer,
                bot=bot,
                chat_id=settings.telegram.alert_chat_id
            )
        )
        smart_task = asyncio.create_task(
            smart_monitoring_loop(
                store=store,
                settings=settings.smart,
                smart_store=smart_store,
                smart_counter_store=smart_counter_store,
                cooldown=cooldown_timer,
                bot=bot,
                chat_id=settings.telegram.alert_chat_id

            )
        )
        try:
            await dp.start_polling(
                bot,
                settings=settings,
                http_store=http_store,
                smart_store=smart_store,
            )

        finally:
            monitoring_task.cancel()
            http_task.cancel()
            network_task.cancel()
            smart_task.cancel()
            
            await asyncio.gather(
                monitoring_task,
                http_task,
                network_task,
                smart_task,
                return_exceptions=True
            )

if __name__ == "__main__":
    asyncio.run(main())
