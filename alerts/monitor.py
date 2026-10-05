import asyncio
import logging
import httpx

from alerts.state_store import (StateStore, IncidentStore, 
                                PendingStore, AlertCooldownStore, 
                                NetworkAccidentStore)

from monitor.http_health import http_health
from alerts.monitoring.hardware import monitoring_cpu, monitoring_ram_usage, monitoring_disk
from alerts.monitoring.containers import monitoring_containers
from alerts.monitoring.http import http_monitoring
from alerts.monitoring.network import network_monitoring_metrics

from config import Settings, HttpServicesSettings, InternetSettings

logger = logging.getLogger(__name__)


async def http_monitoring_loop(
    client: httpx.AsyncClient,
    store: StateStore,
    incident: IncidentStore,
    cooldown_timer: AlertCooldownStore,
    bot,
    chat_id,
    http_settings: HttpServicesSettings,
):
    logger.info(
        'Http Mmonitoring interval is %s seconds',
        http_settings.interval
    )
    while True:

        try:
            await http_monitoring(
                client=client,
                store=store,
                incident=incident,
                cooldown_timer=cooldown_timer,
                bot=bot,
                chat_id=chat_id,
                http_settings=http_settings
            )
        except Exception:
            logger.exception('HTTP monitoring if failed')

        await asyncio.sleep(http_settings.interval)


async def monitoring_loop(
        store: StateStore,
        cooldown_timer: AlertCooldownStore,
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
                cooldown_timer,
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
                                       cooldown_timer,
                                       bot,
                                       chat_id,
                                       settings.thresholds.ram
                )
        except Exception:
            logger.exception('RAM monitoring failed')

        try:
            await monitoring_disk(store,
                                  pending_timer,
                                  cooldown_timer,
                                  bot,
                                  chat_id, 
                                  settings.thresholds.disk.temperature, 
                                  settings.thresholds.disk.usage,
                                  lsblk_timeout=settings.timeouts.lsblk,
                                  smartctl_timeout=settings.timeouts.smartctl
                )
        except Exception:
            logger.exception('Disks monitoring failed')

        try:
            await monitoring_containers(store,
                                        incident,
                                        cooldown_timer,
                                        bot,
                                        chat_id,
                                        settings.docker.monitored_containers,
                                        settings.docker.cooldown,
                                        settings.timeouts.docker
                )
        except Exception:
            logger.exception('Containers monitoring is failed')

            
        await asyncio.sleep(settings.monitoring.interval)


        
async def network_monitoring_loop(
        client: httpx.AsyncClient,
        network_incident: NetworkAccidentStore,
        network_settings: InternetSettings,
        cooldown: AlertCooldownStore,
        bot,
        chat_id
):
    logger.info(
        'Network monitoring interval is %s seconds',
        network_settings.interval
    )
    while True:
        try:
            await network_monitoring_metrics(
            client=client,
            network_incident=network_incident,
            network_settings=network_settings,
            cooldown=cooldown,
            bot=bot,
            chat_id=chat_id,
            )
        except Exception:
            logger.exception('Error while network monitoring')

        await asyncio.sleep(network_settings.interval)
