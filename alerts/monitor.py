import asyncio
import logging

from alerts.state_store import StateStore, IncidentStore, PendingStore, AlertCooldownStore
from alerts.states import Alert, State
from alerts.models import Thresholds, NumericAlertData, ContainerAlertData
from alerts.manager import check_alert, check_container_alert, check_cooldown
from monitor.system import cpu_check, ram_check, disk_check
from monitor.docker_monitor import get_containers_health
from telegram.notifier import send_alert, send_container_alert
from config import Settings

logger = logging.getLogger(__name__)

async def monitoring_loop(
        store: StateStore,
        cooldown: AlertCooldownStore,
        incident: IncidentStore, 
        pending_timer: PendingStore,
        bot, chat_id, 
        settings: Settings
    ):
    logger.info(
        'Monitoring interval is %s seconds',
        settings.monitoring.interval
        )
    
    while True:

        try:
            await monitoring_cpu(
                store, 
                cooldown,
                pending_timer,
                bot, 
                chat_id, 
                settings.thresholds.cpu.temperature, 
                settings.thresholds.cpu.usage
                )
        except Exception:
            logger.exception('CPU monitoring failed')

        try:
            await monitoring_ram_usage(store,
                                       pending_timer,
                                       cooldown,
                                       bot,
                                       chat_id,
                                       settings.thresholds.ram
                )
        except Exception:
            logger.exception('RAM monitoring failed')

        try:
            await monitoring_disk(store,
                                  pending_timer,
                                  cooldown,
                                  bot,
                                  chat_id, 
                                  settings.thresholds.disk.temperature, 
                                  settings.thresholds.disk.usage
                )
        except Exception:
            logger.exception('Disks monitoring failed')

        try:
            await monitoring_containers(store,
                                        incident,
                                        cooldown,
                                        bot,
                                        chat_id,
                                        settings.docker.monitored_containers,
                                        settings.docker.cooldown
                )
        except Exception:
            logger.exception('Containers monitoring is failed')

            
        await asyncio.sleep(settings.monitoring.interval)


async def monitoring_containers(
        store: StateStore, 
        incident: IncidentStore,
        cooldown_timer: AlertCooldownStore,
        bot, 
        chat_id, 
        monitored_containers: set[str],
        cooldown: float
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
            cooldown_timer=cooldown_timer,
            cooldown=cooldown,
            bot=bot,
            chat_id=chat_id
        )

        


async def monitoring_cpu(store: StateStore,
                         cooldown: AlertCooldownStore,
                         pending_timer: PendingStore, 
                         bot, 
                         chat_id, 
                         cpu_temperature_threshold: Thresholds,
                         cpu_usage_thresholds: Thresholds):

    cpu_data = cpu_check()
    if cpu_data is not None:
        temperature = cpu_data.temperature
        usage = cpu_data.usage_percent

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
            pending_timer=pending_timer,
            cooldown=cooldown,
            bot=bot,
            chat_id=chat_id)

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
            pending_timer=pending_timer,
            cooldown=cooldown,
            bot=bot,
            chat_id=chat_id)

async def monitoring_ram_usage(
        store: StateStore,
        pending_timer: PendingStore,
        cooldown: AlertCooldownStore,
        bot, chat_id,
        threshold: Thresholds
):
    ram_data = ram_check()

    if ram_data is not None:
            
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
                pending_timer=pending_timer,
                cooldown=cooldown,
                bot=bot,
                chat_id=chat_id
            )

async def monitoring_disk(store: StateStore,
                          pending_timer: PendingStore,
                          cooldown: AlertCooldownStore,
                          bot, 
                          chat_id, 
                          temperature_threshold: Thresholds, 
                          usage_threshold: Thresholds):
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
                threshold=temperature_threshold,
                store=store,
                pending_timer=pending_timer,
                cooldown=cooldown,
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
                    threshold=usage_threshold,
                    store=store,
                    pending_timer=pending_timer,
                    cooldown=cooldown,
                    bot=bot,
                    chat_id=chat_id
                )

async def docker_monitoring_metrics(
        container_name: str,
        container_status: str,
        container_health: str | None,
        store: StateStore,
        incident: IncidentStore,
        cooldown_timer: AlertCooldownStore,
        cooldown: float,
        bot,
        chat_id):
    
    metric_name = f'docker_{container_name}'

    previous_state = store.get(metric=metric_name)

    status = check_container_alert(
        status=container_status,
        health=container_health,
        previous_state=previous_state
    )

    status.alert = check_cooldown(
        status=status,
        metric_name=metric_name,
        cooldown_timer=cooldown_timer,
        cooldown=cooldown
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
            incident.remove(
                metric=metric_name
            )
            cooldown_timer.remove(
                metric=metric_name
            )
        elif status.alert in (Alert.CRITICAL, Alert.WARNING):
            cooldown_timer.start(
                metric=metric_name
            )

    store.set(metric=metric_name, state=status.state)

async def monitoring_metrics(
        metric_name: str,
        display_name: str,
        value: float,
        unit: str,
        threshold: Thresholds,
        store: StateStore,
        pending_timer: PendingStore,
        cooldown: AlertCooldownStore,
        bot,
        chat_id,
        ):
    
    previous_state = store.get(metric=metric_name)

    status = check_alert(
        value=value,
        previous_state=previous_state,
        threshold=threshold
    )

    if status.state == State.WARNING and previous_state is State.OK:
        pending_timer.start(
            metric=metric_name,
            state=status.state
        )
    else:
        pending_timer.remove(
            metric=metric_name
        )
    
    duration = pending_timer.get(
        metric=metric_name,
        state=status.state
    )
    if (status.state == State.WARNING and 
        duration is not None and 
        duration < threshold.warning_duration):
            status.alert = Alert.NO_ALERT
            status.state = previous_state

    status.alert = check_cooldown(
        status=status,
        metric_name=metric_name,
        cooldown_timer=cooldown,
        cooldown=threshold.cooldown
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
        
    if status.alert == Alert.RECOVERED:
        cooldown.remove(metric=metric_name)
    elif status.alert in (Alert.CRITICAL, Alert.WARNING):
        cooldown.start(metric=metric_name)

    store.set(metric_name, status.state)