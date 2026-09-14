import asyncio
import logging

from alerts.state_store import StateStore
from alerts.states import Alert
from alerts.models import Thresholds, NumericAlertData, ContainerAlertData
from alerts.manager import check_alert, check_container_alert
from monitor.system import cpu_check, ram_check, disk_check
from monitor.docker_monitor import get_containers_health
from telegram.notifier import send_alert, send_container_alert

logger = logging.getLogger(__name__)

async def monitoring_loop(store: StateStore, bot, chat_id):
    cpu_thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75
    )
    ram_thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=80
    )

    disk_thresholds = {
        'temperature_threshold' : Thresholds(
        warning=65,
        critical=75,
        recovery=55
    ),
        'usage_threshold' : Thresholds(
        warning=80,
        critical=90,
        recovery=75
    )
    }

    monitored_containers = {
        "immich_server",
        "immich_postgres",
        "immich_redis",
        "vaultwarden"
    }

    while True:
        try:
            await monitoring_cpu_temperature(store, bot, chat_id, cpu_thresholds)
        except Exception:
            logger.exception('CPU monitoring failed')
        try:
            await monitoring_ram_usage(store, bot, chat_id, ram_thresholds)
        except Exception:
            logger.exception('RAM monitoring failed')
        try:
            await monitoring_disk(store, bot, chat_id, disk_thresholds)
        except Exception:
            logger.exception('Disks monitoring failed')
        try:
            await monitoring_containers(store, bot, chat_id, monitored_containers)
        except Exception:
            logger.exception('Containers monitoring is failed')
        await asyncio.sleep(5)


async def monitoring_containers(store: StateStore, bot, chat_id, monitored_containers: set[str]):
    containers = get_containers_health()
    logger.info('Containers monitor is begin')

    for container_name in monitored_containers:
        container_info = containers.get(container_name)

        if container_info is None:
            await docker_monitoring_metrics(
                container_name=container_name,
                container_status='missing',
                container_health=None,
                store=store,
                bot=bot,
                chat_id=chat_id
            )
        else:
            await docker_monitoring_metrics(
                container_name=container_name,
                container_status=container_info.status,
                container_health=container_info.health,
                store=store,
                bot=bot,
                chat_id=chat_id
            )
        


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
        metric_name='ram_usage',
        display_name='RAM',
        value=ram_usage_percent,
        unit='%',
        threshold=threshold,
        store=store,
        bot=bot,
        chat_id=chat_id
    )

async def monitoring_disk(store: StateStore, bot, chat_id, threshold: dict[str, Thresholds]):
    disks_dict = disk_check()
    if disks_dict is None:
        return None
    logger.info('Disk monitor is begin')
    for disk_name, disk_info in disks_dict.items():
        
        if disk_info.temperature is not None:

            logger.info(f'DISK {disk_name} | temperature {disk_info.temperature}')
            await monitoring_metrics(
                metric_name='disk_temperature_' + disk_name,
                display_name='DISK ' + disk_name,
                value=disk_info.temperature,
                unit='°C',
                threshold=threshold['temperature_threshold'],
                store=store,
                bot=bot,
                chat_id=chat_id
            )

        for partition in disk_info.partitions:
            if partition.mountpoint != '/boot/efi':

                logger.info(f'Partition {partition} | usage {partition.usage_percent}')
                await monitoring_metrics(
                    metric_name='partition_usage_' + partition.partition,
                    display_name='Partition '+ partition.mountpoint,
                    value=partition.usage_percent,
                    unit='%',
                    threshold=threshold['usage_threshold'],
                    store=store,
                    bot=bot,
                    chat_id=chat_id
                )

async def docker_monitoring_metrics(
        container_name: str,
        container_status: str,
        container_health: str | None,
        store: StateStore,
        bot,
        chat_id):
    
    metric_name = f'docker_{container_name}'

    previous_state = store.get(metric=metric_name)

    status = check_container_alert(
        status=container_status,
        health=container_health,
        previous_state=previous_state
    )

    if status.alert != Alert.NO_ALERT:
        await send_container_alert(
            bot=bot,
            chat_id=chat_id,
            status = {
                container_name: ContainerAlertData(
                        status=status,
                        container_status=container_status,
                        container_health=container_health
                    )
                }
        )

    store.set(metric=metric_name, state=status.state)

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

    if status.alert != Alert.NO_ALERT:
        await send_alert( 
            bot=bot, 
            chat_id=chat_id, 
            status={
                    display_name: NumericAlertData(
                        status=status,
                        value=value,
                        unit=unit
                        )
                    }
                )
    store.set(metric_name, status.state)