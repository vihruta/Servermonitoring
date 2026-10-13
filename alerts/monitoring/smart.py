import logging
import asyncio
from datetime import datetime, timezone

from monitor.smart import get_nvme_smartlog
from models import SmartMetrics
from config import SmartSettings

from alerts.models import SmartAlertData, MetricStatus

from alerts.state_store import SmartCounterStore, StateStore, AlertCooldownStore, SmartSnapshotStore
from alerts.states import Alert, State, SmartAlertReason
from alerts.manager import get_smart_state, check_state_transition, check_cooldown

from telegram.notifier import send_smart_alert


logger = logging.getLogger(__name__)


async def monitoring_smart_disk(
        store: StateStore, 
        settings: SmartSettings,
        smart_store: SmartSnapshotStore,
        smart_counter_store: SmartCounterStore,
        cooldown: AlertCooldownStore,
        bot,
        chat_id
):

    smart_disk_dict = await asyncio.to_thread(
        get_nvme_smartlog,
        smartlog_timeout=settings.timeout
    )

    if smart_disk_dict is None:
        return None
    
    for disk, metrics in smart_disk_dict.items():
        try:
            smart_store.update(
                disk=disk,
                metrics=metrics,
                checked_at=datetime.now(timezone.utc)
            )
            
            if metrics is None:
                continue

            await monitoring_smart_metrics(
                store=store,
                disk=disk,
                metrics=metrics,
                settings=settings,
                smart_store=smart_counter_store,
                cooldown=cooldown,
                bot=bot,
                chat_id=chat_id
            )
        except Exception:
            logger.exception(
                'SMART monitoring failed for disk %s',
                disk,
            )


async def monitoring_smart_metrics(
        store: StateStore,
        disk: str,
        metrics: SmartMetrics,
        settings: SmartSettings,
        smart_store: SmartCounterStore,
        cooldown: AlertCooldownStore,
        bot,
        chat_id
):

    metric_name = f'smart_{disk}'

    previous_state = store.get(metric=metric_name)

    current_state = get_smart_state(
        metrics=metrics,
        settings=settings
    )

    status = check_state_transition(
        current_state=current_state,
        previous_state=previous_state
    )

    status.alert = check_cooldown(
        status=status,
        metric_name=metric_name,
        cooldown_timer=cooldown,
        cooldown=settings.cooldown
    )

    media_errors_increase = smart_store.increase_check(
        metric=disk + ':media_errors',
        measure=metrics.media_errors
    )

    smart_store.initialize(
        metric=f'{disk}:media_errors',
        measure=metrics.media_errors
    )

    smart_store.initialize(
        metric=f'{disk}:num_err_log_entries',
        measure=metrics.num_err_log_entries
    )


    num_err_increased = smart_store.increase_check(
        metric=disk + ':num_err_log_entries',
        measure=metrics.num_err_log_entries
    )

        


    if status.alert != Alert.NO_ALERT:
        if status.alert == Alert.CRITICAL:

            logger.error(
                '%s - %s -> %s',
                metric_name,
                previous_state.name,
                current_state.name
            )

        reasons = get_reason(
            metrics=metrics,
            settings=settings,
            media_errors_increase=False,
            num_err_increased=False
        )

        await send_smart_alert(
            bot=bot,
            chat_id=chat_id,
            status={
                metric_name: SmartAlertData(
                    status=status,
                    metrics=metrics,
                    reasons=reasons
                )
            }
        )

        if current_state == State.OK:
            cooldown.remove(metric=metric_name)
        else:
            cooldown.start(metric=metric_name)

    store.set(
        metric=metric_name,
        state=current_state
    )

    event_reasons: list[SmartAlertReason] = []

    if media_errors_increase:
        event_reasons.append(SmartAlertReason.MEDIA_ERRORS_INCREASED)

    if num_err_increased:
        event_reasons.append(SmartAlertReason.ERROR_LOG_INCREASED)

    if event_reasons:
        await send_smart_alert(
            bot=bot,
            chat_id=chat_id,
            status={
                metric_name: SmartAlertData(
                    status=MetricStatus(
                        state=current_state,
                        alert=Alert.CRITICAL,
                    ),
                    metrics=metrics,
                    reasons=event_reasons,
                )
            },
        )
    smart_store.set(
        metric=f'{disk}:media_errors',
        measure=metrics.media_errors,
    )
    smart_store.set(
        metric=f'{disk}:num_err_log_entries',
        measure=metrics.num_err_log_entries,
    )


def get_reason(
        metrics: SmartMetrics,
        settings: SmartSettings,
        media_errors_increase,
        num_err_increased: bool,

) -> list[SmartAlertReason]:
    
    reasons = []
    if metrics.critical_warning != 0:
        reasons.append(SmartAlertReason.CRITICAL_WARNING)
    if media_errors_increase:
        reasons.append(SmartAlertReason.MEDIA_ERRORS_INCREASED)
    if num_err_increased:
        reasons.append(SmartAlertReason.ERROR_LOG_INCREASED)
    if metrics.available_spare < settings.available_spare_warning:
        reasons.append(SmartAlertReason.LOW_SPARE)
    if metrics.percent_used >= settings.percentage_used_warning:
        reasons.append(SmartAlertReason.HIGH_WEAR)

    return reasons
