from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendMessage

from alerts import state_store
from alerts.monitoring import smart
from alerts.state_store import (
    AlertCooldownStore,
    SmartCounterStore,
    SmartSnapshotStore,
    StateStore,
)
from alerts.states import Alert, State, SmartAlertReason
from config import SmartSettings
from models import SmartMetrics


DISK = '/dev/nvme0n1'
KEY = f'smart_{DISK}'


def metrics(**changes):
    values = {
        'critical_warning': 0,
        'available_spare': 100,
        'percent_used': 2,
        'media_errors': 5,
        'num_err_log_entries': 10,
    }
    values.update(changes)
    return SmartMetrics(**values)


@pytest.fixture
def scenario(monkeypatch):
    ctx = SimpleNamespace(
        now=0,
        sent=[],
        store=StateStore(),
        smart_store=SmartCounterStore(),
        cooldown=AlertCooldownStore(),
        settings=SmartSettings(
            available_spare_warning=10,
            percentage_used_warning=20,
        ),
    )

    monkeypatch.setattr(
        state_store.time,
        'monotonic',
        lambda: ctx.now,
    )

    async def fake_send(bot, chat_id, status):
        ctx.sent.extend(status.values())

    monkeypatch.setattr(
        smart,
        'send_smart_alert',
        fake_send,
    )

    async def run(data, disk=DISK):
        await smart.monitoring_smart_metrics(
            store=ctx.store,
            disk=disk,
            metrics=data,
            settings=ctx.settings,
            smart_store=ctx.smart_store,
            cooldown=ctx.cooldown,
            bot=None,
            chat_id=123,
        )

    ctx.run = run
    return ctx


@pytest.mark.asyncio
async def test_counter_baseline_growth_and_no_false_recovery(scenario):
    s = scenario

    await s.run(metrics())

    await s.run(metrics())
    assert s.sent == []

    await s.run(metrics(
        media_errors=6,
        num_err_log_entries=11,
    ))
    assert len(s.sent) == 1
    assert s.sent[0].status.alert == Alert.CRITICAL

    await s.run(metrics(
        media_errors=6,
        num_err_log_entries=11,
    ))

    assert len(s.sent) == 1
    assert s.sent[0].status.alert == Alert.CRITICAL

    assert set(s.sent[0].reasons) == {
        SmartAlertReason.MEDIA_ERRORS_INCREASED,
        SmartAlertReason.ERROR_LOG_INCREASED,
    }
    assert s.store.get(KEY) == State.OK

@pytest.mark.asyncio
async def test_media_errors_increase_sends_critical_once(scenario):
    s = scenario

    await s.run(metrics())
    assert s.sent == []

    await s.run(metrics(media_errors=6))

    assert len(s.sent) == 1
    assert s.sent[0].status.alert == Alert.CRITICAL
    assert s.sent[0].reasons == [SmartAlertReason.MEDIA_ERRORS_INCREASED]

    await s.run(metrics(media_errors=6))

    assert len(s.sent) == 1
    assert s.sent[0].status.alert == Alert.CRITICAL
    assert s.sent[0].reasons == [SmartAlertReason.MEDIA_ERRORS_INCREASED]


@pytest.mark.asyncio
async def test_smart_counters_are_independent_per_disk(scenario):
    s = scenario

    await s.run(metrics(media_errors = 5), disk='/dev/nvme0n1')
    await s.run(metrics(media_errors = 100), disk='/dev/nvme1n1')

    assert s.sent == []

    await s.run(metrics(media_errors = 5), disk='/dev/nvme0n1')
    await s.run(metrics(media_errors = 100), disk='/dev/nvme1n1')

    assert s.sent == []

    await s.run(metrics(media_errors = 6), disk='/dev/nvme0n1')

    assert len(s.sent) == 1
    assert s.sent[0].reasons == [
        SmartAlertReason.MEDIA_ERRORS_INCREASED
    ]

    await s.run(metrics(media_errors = 100), disk='/dev/nvme1n1')

    assert len(s.sent) == 1


@pytest.mark.asyncio
async def test_smart_warning_repeats_at_cooldown(scenario):
    s = scenario
    s.settings.cooldown = 600

    await s.run(metrics(percent_used=20))

    assert len(s.sent) == 1
    assert s.sent[0].status.alert == Alert.WARNING

    s.now = 599
    await s.run(metrics(percent_used=20))

    assert len(s.sent) == 1

    s.now = 600
    await s.run(metrics(percent_used=20))

    assert len(s.sent) == 2
    assert s.sent[1].status.alert == Alert.WARNING

    s.now = 601
    await s.run(metrics(percent_used=20))

    assert len(s.sent) == 2


@pytest.mark.asyncio
async def test_smart_critical_bypasses_cooldown(scenario):
    s = scenario
    s.settings.cooldown = 600

    await s.run(metrics(percent_used=20))

    assert len(s.sent) == 1
    assert s.sent[0].status.alert == Alert.WARNING

    s.now = 1
    await s.run(metrics(percent_used=20, critical_warning=1))

    assert len(s.sent) == 2
    assert s.sent[1].status.alert == Alert.CRITICAL
    assert SmartAlertReason.CRITICAL_WARNING in s.sent[1].reasons


@pytest.mark.asyncio
async def test_smart_counter_growth_bypasses_cooldown(scenario):
    s = scenario
    s.settings.cooldown = 600

    await s.run(metrics(percent_used=20, media_errors=5))

    assert len(s.sent) == 1

    s.now = 1
    await s.run(metrics(percent_used=20, media_errors=6))

    assert len(s.sent) == 2
    assert s.sent[1].status.alert == Alert.CRITICAL
    assert s.sent[1].reasons == [
        SmartAlertReason.MEDIA_ERRORS_INCREASED,
    ]

@pytest.mark.asyncio
async def test_smart_recovery_sends_once_and_clears_cooldown(scenario):
    s = scenario

    await s.run(metrics(available_spare=5))

    assert len(s.sent) == 1
    assert s.sent[0].status.alert == Alert.WARNING

    s.now = 1
    await s.run(metrics(available_spare=100))

    assert len(s.sent) == 2
    assert s.sent[1].status.alert == Alert.RECOVERED
    assert s.store.get(KEY) == State.OK
    assert s.cooldown.check_end(
        metric=KEY,
        metric_cooldown=s.settings.cooldown,
    ) is True

    s.now = 2
    await s.run(metrics(available_spare=100))

    assert len(s.sent) == 2

@pytest.mark.asyncio
async def test_smart_counter_event_retries_after_send_failure(
    scenario,
    monkeypatch,
):
    s = scenario

    await s.run(metrics(media_errors=5))
    assert s.sent == []

    successful_send = smart.send_smart_alert

    async def failing_send(bot, chat_id, status):
        raise TelegramNetworkError(
            method=SendMessage(chat_id=chat_id, text='Test'),
            message='Network unavailable',
        )

    monkeypatch.setattr(smart, 'send_smart_alert', failing_send)

    with pytest.raises(TelegramNetworkError):
        await s.run(metrics(media_errors=6))

    assert s.sent == []


    assert s.smart_store.increase_check(
        metric=f'{DISK}:media_errors',
        measure=6,
    ) is True

    monkeypatch.setattr(smart, 'send_smart_alert', successful_send)

    await s.run(metrics(media_errors=6))

    assert len(s.sent) == 1
    assert s.sent[0].reasons == [
        SmartAlertReason.MEDIA_ERRORS_INCREASED,
    ]

    await s.run(metrics(media_errors=6))

    assert len(s.sent) == 1


@pytest.mark.asyncio
async def test_smart_first_baseline_survives_send_failure(
    scenario,
    monkeypatch,
):
    s = scenario
    successful_send = smart.send_smart_alert

    async def failing_send(bot, chat_id, status):
        raise TelegramNetworkError(
            method=SendMessage(chat_id=chat_id, text='Test'),
            message='Network unavailable',
        )

    monkeypatch.setattr(smart, 'send_smart_alert', failing_send)

    with pytest.raises(TelegramNetworkError):
        await s.run(metrics(
            critical_warning=1,
            media_errors=5,
        ))

    monkeypatch.setattr(smart, 'send_smart_alert', successful_send)

    await s.run(metrics(
        critical_warning=1,
        media_errors=6,
    ))

    assert len(s.sent) == 2
    assert s.sent[0].reasons == [
        SmartAlertReason.CRITICAL_WARNING,
    ]
    assert s.sent[1].reasons == [
        SmartAlertReason.MEDIA_ERRORS_INCREASED,
    ]
    assert all(item.status.alert == Alert.CRITICAL for item in s.sent)


@pytest.mark.asyncio
async def test_smart_recovery_does_not_hide_counter_growth(scenario):
    s = scenario

    await s.run(metrics(
        critical_warning=1,
        media_errors=5,
    ))

    assert len(s.sent) == 1
    assert s.sent[0].status.alert == Alert.CRITICAL

    await s.run(metrics(
        critical_warning=0,
        media_errors=6,
    ))

    assert len(s.sent) == 3
    assert s.sent[1].status.alert == Alert.RECOVERED
    assert s.sent[2].status.alert == Alert.CRITICAL
    assert s.sent[2].reasons == [
        SmartAlertReason.MEDIA_ERRORS_INCREASED,
    ]
    assert s.store.get(KEY) == State.OK

    await s.run(metrics(media_errors=6))

    assert len(s.sent) == 3


@pytest.mark.asyncio
async def test_smart_monitoring_continues_after_disk_send_failure(
    scenario,
    monkeypatch,
):
    s = scenario
    second_disk = '/dev/nvme1n1'

    def fake_collector(smartlog_timeout):
        return {
            DISK: metrics(critical_warning=1),
            second_disk: metrics(available_spare=5),
        }

    monkeypatch.setattr(
        smart,
        'get_nvme_smartlog',
        fake_collector,
    )

    attempted_disks = []
    successful_send = smart.send_smart_alert

    async def fake_send(bot, chat_id, status):
        attempted_disks.extend(status.keys())

        if KEY in status:
            raise TelegramNetworkError(
                method=SendMessage(chat_id=chat_id, text='Test'),
                message='Network unavailable',
            )

        await successful_send(
            bot=bot,
            chat_id=chat_id,
            status=status,
        )

    monkeypatch.setattr(smart, 'send_smart_alert', fake_send)

    snapshots = SmartSnapshotStore()
    await smart.monitoring_smart_disk(
        smart_store=snapshots,
        store=s.store,
        settings=s.settings,
        smart_counter_store=s.smart_store,
        cooldown=s.cooldown,
        bot=None,
        chat_id=123,
    )

    assert attempted_disks == [KEY, f'smart_{second_disk}']
    assert len(s.sent) == 1
    assert s.sent[0].status.alert == Alert.WARNING
    assert s.sent[0].reasons == [SmartAlertReason.LOW_SPARE]
    assert s.store.get(KEY) == State.OK
    assert s.store.get(f'smart_{second_disk}') == State.WARNING
    assert snapshots.get(DISK).metrics.critical_warning == 1
    assert snapshots.get(second_disk).metrics.available_spare == 5


@pytest.mark.asyncio
async def test_smart_failed_measurement_is_saved_for_commands(scenario, monkeypatch):
    from datetime import datetime, timezone

    s = scenario
    snapshots = SmartSnapshotStore()
    old_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
    snapshots.update(DISK, metrics(), old_time)
    monkeypatch.setattr(smart, 'get_nvme_smartlog', lambda smartlog_timeout: {DISK: None})

    await smart.monitoring_smart_disk(
        store=s.store,
        settings=s.settings,
        smart_store=snapshots,
        smart_counter_store=s.smart_store,
        cooldown=s.cooldown,
        bot=None,
        chat_id=123,
    )

    snapshot = snapshots.get(DISK)
    assert snapshot is not None
    assert snapshot.metrics is None
    assert snapshot.checked_at > old_time
    assert s.sent == []
