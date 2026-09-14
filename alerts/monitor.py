import asyncio
import logging

from alerts.state_store import StateStore
from alerts.states import Alert
from alerts.models import Thresholds, AlertData
from alerts.manager import check_alert
from monitor.system import cpu_check, ram_check
from telegram.notifier import send_alert

logger = logging.getLogger(__name__)

async def monitoring_loop(store: StateStore, bot, chat_id):
    cpu_thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75
    )
    ram_thresholds = Thresholds(
        warning=80,
        critical=95,
        recovery=80
    )

    while True:
        await monitoring_cpu_temperature(store, bot, chat_id, cpu_thresholds)
        await monitoring_ram_usage(store, bot, chat_id, ram_thresholds)
        await asyncio.sleep(5)


async def monitoring_cpu_temperature(store: StateStore, bot, chat_id, threshold: Thresholds):
    temperature = cpu_check().temperature
    if temperature is None:
        return None
    logger.info('Cpu monitor is begin')
    await monitoring_metrics(
        metric_name='cpu_temperature',
        display_name='CPU',
        value=temperature,
        unit='°C',
        threshold=threshold,
        store=store,
        bot=bot,
        chat_id=chat_id)

async def monitoring_ram_usage(store: StateStore, bot, chat_id, threshold: Thresholds):
    ram_usage_percent = ram_check().ram.usage
    if ram_usage_percent is None:
        return None
    logger.info('Ram monitor is begin')
    logger.info(f'Ram usage {ram_usage_percent}')
    await monitoring_metrics(
        metric_name='ram_thresholds',
        display_name='RAM',
        value=ram_usage_percent,
        unit='%'
        threshold=threshold,
        store=store,
        bot=bot,
        chat_id=chat_id
    )


async def monitoring_metrics(
        metric_name: str,
        display_name: str,
        value: float,
        unit: str,
        threshold: Thresholds,
        store: StateStore,
        bot,
        chat_id,
        ):
    previous_state = store.get(metric=metric_name)

    status = check_alert(
        value=value,
        previous_state=previous_state,
        threshold=threshold
    )

    store.set(metric_name, status.state)

    if status.alert != Alert.NO_ALERT:
        await send_alert(bot=bot, 
                         chat_id=chat_id, 
                         status={
                             display_name: AlertData(
                             status=status,
                             value=value,
                             unit=unit
                         )
                         }
                         )