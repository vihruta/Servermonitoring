import asyncio
import logging
from alerts.state_store import StateStore, PendingStore, AlertCooldownStore
from alerts.states import Alert, State
from alerts.models import Thresholds, NumericAlertData
from alerts.manager import check_alert,check_cooldown

from monitor.system import cpu_check, ram_check, disk_check

from telegram.notifier import send_alert

logger = logging.getLogger(__name__)



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
        if temperature is not None:
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
                          usage_threshold: Thresholds,
                          lsblk_timeout: float,
                          smartctl_timeout: float):
    disks_dict = await asyncio.to_thread(
        disk_check,
        lsblk_timeout=lsblk_timeout,
        smartctl_timeout=smartctl_timeout
    )
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