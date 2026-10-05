import asyncio
import logging

from alerts.state_store import StateStore, IncidentStore, AlertCooldownStore
from alerts.states import Alert
from alerts.models import ContainerAlertData
from alerts.manager import check_container_alert, check_cooldown

from monitor.docker_monitor import get_containers_health

from telegram.notifier import send_container_alert

logger = logging.getLogger(__name__)


async def monitoring_containers(
        store: StateStore, 
        incident: IncidentStore,
        cooldown_timer: AlertCooldownStore,
        bot, 
        chat_id, 
        monitored_containers: set[str],
        cooldown: float,
        docker_timeout: int
):
    
    containers = await asyncio.to_thread(
        get_containers_health,
        docker_timeout=docker_timeout
    )

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