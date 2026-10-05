import logging
import httpx
from aiogram.exceptions import TelegramNetworkError

from alerts.state_store import  AlertCooldownStore, NetworkAccidentStore
from alerts.states import Alert, State
from alerts.models import HttpAlertData, MetricStatus

from monitor.network import network_check

from telegram.notifier import send_network_alert
from config import InternetSettings

logger = logging.getLogger(__name__)


async def network_monitoring_metrics(
    client: httpx.AsyncClient,
    network_incident: NetworkAccidentStore,
    network_settings: InternetSettings,
    cooldown: AlertCooldownStore,
    bot,
    chat_id,
):
    metric_name = "network_internet"
    status = await network_check(
        client=client,
        service_settings=network_settings,
    )

    if status.is_failed:
        network_incident.recovered_at = None
        network_incident.start()
        duration = network_incident.get_duration()

        if duration is None or duration < network_settings.failure_duration:
            return

        network_incident.confirm()

        if network_incident.notified and not cooldown.check(
            metric=metric_name,
            metric_cooldown=network_settings.cooldown,
        ):
            return

        metric_status = MetricStatus(
            alert=Alert.CRITICAL,
            state=State.CRITICAL,
        )

        try:
            await send_network_alert(
                bot=bot,
                chat_id=chat_id,
                problem_was_notified=network_incident.notified,
                status={
                    "Network": HttpAlertData(
                        status=metric_status,
                        result_code=status.result_code,
                        error=status.error,
                        duration=duration,
                    )
                },
            )
        except TelegramNetworkError:
            logger.exception("Cant send message about network error")
        else:
            network_incident.notify()
            cooldown.start(metric=metric_name)

        return

    if not network_incident.confirmed:
        network_incident.reset()
        cooldown.remove(metric=metric_name)
        return

    if network_incident.started_at is None:
        return

    network_incident.recover()
    duration = network_incident.get_duration()

    metric_status = MetricStatus(
        alert=Alert.RECOVERED,
        state=State.OK,
    )

    try:
        await send_network_alert(
            bot=bot,
            chat_id=chat_id,
            problem_was_notified=network_incident.notified,
            status={
                "Network": HttpAlertData(
                    status=metric_status,
                    result_code=status.result_code,
                    error=status.error,
                    duration=duration,
                )
            },
        )
    except TelegramNetworkError:
        logger.exception("Cant send message about network recovery")
    else:
        network_incident.reset()
        cooldown.remove(metric=metric_name)