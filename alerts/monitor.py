import asyncio
import logging
from config import (MONITORING_INTERVAL, 
                    CPU_TEMPERATURE_THRESHOLDS,
                    CPU_USAGE_THRESHOLD, 
                    RAM_THRESHOLDS, 
                    DISK_THRESHOLDS, 
                    MONITORED_CONTAINERS)

from alerts.state_store import StateStore, IncidentStore
from alerts.states import Alert
from alerts.models import Thresholds, NumericAlertData, ContainerAlertData
from alerts.manager import check_alert, check_container_alert
from monitor.system import cpu_check, ram_check, disk_check
from monitor.docker_monitor import get_containers_health
from telegram.notifier import send_alert, send_container_alert

logger = logging.getLogger(__name__)

async def monitoring_loop(store: StateStore,incident: IncidentStore, bot, chat_id):
    logger.info(
        'Monitoring interval is %s seconds',
        MONITORING_INTERVAL
        )
    
    while True:
        try:
            await monitoring_cpu(
                store, 
                bot, 
                chat_id, 
                CPU_TEMPERATURE_THRESHOLDS, 
                CPU_USAGE_THRESHOLD
                )
        except Exception:
            logger.exception('CPU monitoring failed')
        try:
            await monitoring_ram_usage(store, bot, chat_id, RAM_THRESHOLDS)
        except Exception:
            logger.exception('RAM monitoring failed')
        try:
            await monitoring_disk(store, bot, chat_id, DISK_THRESHOLDS)
        except Exception:
            logger.exception('Disks monitoring failed')
        try:
            await monitoring_containers(store,incident, bot, chat_id, MONITORED_CONTAINERS)
        except Exception:
            logger.exception('Containers monitoring is failed')
            
        await asyncio.sleep(MONITORING_INTERVAL)


async def monitoring_containers(
        store: StateStore, 
        incident: IncidentStore, 
        bot, 
        chat_id, 
        monitored_containers: set[str]
):
    
    containers = get_containers_health()

    logger.debug('Containers monitor is begin')
    if containers is None:
        logger.warning('Docker data is unavailable')
        return
    
    for container_name in monitored_containers:
        if container_name not in containers:
            container_status = 'missing'
            container_health = None
        else:
            container_info = containers.get(container_name)

            if container_info is None:
                logger.warning(
                    'Container %s data is missing',
                    container_name)
                continue

            container_status = container_info.status
            container_health = container_info.health

        await docker_monitoring_metrics(
            container_name=container_name,
            container_status=container_status,
            container_health=container_health,
            store=store,
            incident=incident,
            bot=bot,
            chat_id=chat_id
        )

        


async def monitoring_cpu(store: StateStore, 
                         bot, 
                         chat_id, 
                         cpu_temperature_threshold: Thresholds,
                         cpu_usage_thresholds: Thresholds):

    cpu_data = cpu_check()
    if cpu_data is not None:
        temperature = cpu_data.temperature
        usage = cpu_data.usage_percent

        if temperature is not None:
            logger.debug('Cpu monitor is begin')
            logger.debug(
                'CPU temperature is %s',
                temperature
                )
            
            await monitoring_metrics(
                metric_name='cpu_temperature',
                display_name='CPU temperature',
                value=temperature,
                unit='°C',
                threshold=cpu_temperature_threshold,
                store=store,
                bot=bot,
                chat_id=chat_id)

        if usage is not None:
            logger.debug(
                'CPU usage is %s',
                usage
                )

            await monitoring_metrics(
                metric_name='cpu_usage',
                display_name='CPU usage',
                value=usage,
                unit='%',
                threshold=cpu_usage_thresholds,
                store=store,
                bot=bot,
                chat_id=chat_id)

async def monitoring_ram_usage(
        store: StateStore,
        bot, chat_id,
        threshold: Thresholds
):
    ram_data = ram_check()

    if ram_data is not None and ram_data.ram.usage is not None:
            
            logger.debug('Ram monitor is begin')
            logger.debug(
                'Ram usage is %.1f%%',
                ram_data.ram.usage
                )
            
            await monitoring_metrics(
                metric_name='ram_usage',
                display_name='RAM',
                value=ram_data.ram.usage,
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
    logger.debug('Disk monitor is begin')
    for disk_name, disk_info in disks_dict.items():
        
        if disk_info.temperature is not None:

            logger.debug(
                'DISK %s temperature is %s °C',
                disk_name, 
                disk_info.temperature
                )
            
            await monitoring_metrics(
                metric_name='disk_temperature_' + disk_name,
                display_name='DISK ' + disk_name,
                value=disk_info.temperature,
                unit='°C',
                threshold=threshold['temperature'],
                store=store,
                bot=bot,
                chat_id=chat_id
            )

        for partition in disk_info.partitions:
            if partition.mountpoint != '/boot/efi':

                logger.debug('Partition %s usage is %.1f%%',
                             partition.mountpoint,
                             partition.usage_percent
                             )
                await monitoring_metrics(
                    metric_name='partition_usage_' + partition.partition,
                    display_name='Partition '+ partition.mountpoint,
                    value=partition.usage_percent,
                    unit='%',
                    threshold=threshold['usage'],
                    store=store,
                    bot=bot,
                    chat_id=chat_id
                )

async def docker_monitoring_metrics(
        container_name: str,
        container_status: str,
        container_health: str | None,
        store: StateStore,
        incident: IncidentStore,
        bot,
        chat_id):
    
    metric_name = f'docker_{container_name}'

    previous_state = store.get(metric=metric_name)

    status = check_container_alert(
        status=container_status,
        health=container_health,
        previous_state=previous_state
    )
    downtime = None
    if status.alert != Alert.NO_ALERT:
        if status.alert == Alert.CRITICAL:
            incident.start(metric=metric_name)
            logger.error(
                'Container %s: %s -> %s | docker_status=%s | health=%s',
                container_name,
                previous_state.name,
                status.state.name,
                container_status,
                container_health
            )
        if status.alert == Alert.RECOVERED:
            downtime = incident.get_downtime(metric_name)
            logger.info(
                'Container %s: %s -> %s | docker_status=%s | health=%s',
                container_name,
                previous_state.name,
                status.state.name,
                container_status,
                container_health
            )
            if downtime is not None:
                logger.info(
                    'Container %s recovered after %.1f seconds',
                    container_name,
                    downtime
                )

        await send_container_alert(
            bot=bot,
            chat_id=chat_id,
            status = {
                container_name: ContainerAlertData(
                        status=status,
                        container_status=container_status,
                        container_health=container_health,
                        downtime=downtime
                    )
                }
        )
        if status.alert == Alert.RECOVERED:
            incident.remove(metric=metric_name)

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
        if status.alert == Alert.CRITICAL:
            logger.error(
                '%s: %s -> %s | value=%.1f %s',
                display_name,
                previous_state.name,
                status.state.name,
                value,
                unit
            )
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