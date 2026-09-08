import asyncio
import logging

from alerts.state_store import StateStore
from alerts.states import Alert
from alerts.manager import check_alert
from monitor.system import cpu_check
from telegram.notifier import send_alert

logger = logging.getLogger(__name__)

async def monitoring_loop(store: StateStore, bot, chat_id):
    while True:
        status = await monitoring_cpu_temperature(store, bot, chat_id)
        await asyncio.sleep(60)


async def monitoring_cpu_temperature(store: StateStore, bot, chat_id):
    temperature = cpu_check().temperature
    if temperature is not None:
        previous_state = store.get('cpu_temperature')
        logger.info(f'temp - {temperature} | previous state - {previous_state}')
        status = check_alert(
            temperature=temperature, 
            previous_state=previous_state
            )

        store.set(
            "cpu_temperature",
            status.state
            )
        if status.alert != Alert.NO_ALERT:
            await send_alert(bot=bot, chat_id=chat_id, status={'CPU': (status, temperature)})

    return status