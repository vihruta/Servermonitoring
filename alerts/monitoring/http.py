import logging
import httpx

from alerts.state_store import StateStore, IncidentStore, AlertCooldownStore
from alerts.states import Alert, State
from alerts.models import HttpAlertData
from alerts.manager import check_cooldown, check_http_alert
from monitor.http_health import http_health

from telegram.notifier import send_http_alert
from config import HttpServicesSettings

logger = logging.getLogger(__name__)

async def http_monitoring(
    client: httpx.AsyncClient,
    store: StateStore,
    incident: IncidentStore,
    cooldown_timer: AlertCooldownStore,
    bot,
    chat_id,
    http_settings: HttpServicesSettings,

):
    http_health_list = await http_health(
        client=client,
        settings=http_settings
    )

    for service in http_health_list:
        try:
            await http_monitoring_metrics(
                service_name=service.service,
                result_code=service.result_code,
                error=service.error,
                is_failed=service.is_failed,
                failure_duration=http_settings.failure_duration,
                store=store,
                incident=incident,
                cooldown_timer=cooldown_timer,
                cooldown=http_settings.cooldown,
                bot=bot,
                chat_id=chat_id
            )
        except Exception:
            logger.exception('HTTP monitoring failed | APP %s', service.service)

async def http_monitoring_metrics(
        service_name: str,
        result_code: int | None,
        is_failed: bool,
        error: str | None,
        failure_duration: float,
        store: StateStore,
        incident: IncidentStore,
        cooldown_timer: AlertCooldownStore,
        cooldown: float,
        bot,
        chat_id
):
    metric_name = f'http_check_{service_name}'
    previous_state = store.get(metric=metric_name)

    status = check_http_alert(
        result_code=result_code,
        is_failed=is_failed,
        previous_state=previous_state
    )

    if status.state != State.OK:
        incident.start(metric=metric_name)
        duration = incident.get_downtime(metric=metric_name)
        if previous_state == State.OK:
            if duration is None or duration < failure_duration:
                return
            
    elif status.state == State.OK and previous_state == State.OK:
        incident.remove(metric=metric_name)
        return

    status.alert = check_cooldown(
        status=status,
        metric_name=metric_name,
        cooldown_timer=cooldown_timer,
        cooldown=cooldown
    )
    
    if status.alert == Alert.NO_ALERT:
        store.set(
            metric=metric_name,
            state=status.state
        )
        return
    
    duration = incident.get_downtime(metric=metric_name)

    if status.alert == Alert.CRITICAL:
        logger.error(
            'HTTP Error: Service: %s: %s -> %s | Error: %s',
            metric_name,
            previous_state.name,
            status.state.name,
            error
        )
    await send_http_alert(
        bot=bot,
        chat_id=chat_id,
        status={
            service_name: HttpAlertData(
                status=status,
                result_code=result_code,
                error=error,
                duration=duration
            )
        }
    )
    if status.alert == Alert.RECOVERED:
        if duration is not None:
            logger.info(
                'HTTP| Service: %s recovered. Duration: %f',
                metric_name,
                duration
            )
        incident.remove(metric=metric_name)
        cooldown_timer.remove(metric=metric_name)
    else:
        cooldown_timer.start(metric=metric_name)
    store.set(
            metric=metric_name,
            state=status.state
        )

        
