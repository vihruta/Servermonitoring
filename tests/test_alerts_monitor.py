import pytest
import asyncio
import threading
from pathlib import Path

from models import (CpuMetrics, LoadAverage, 
                    RamMetrics, MemoryMetrics,
                    SwapMetrics, DiskMetrics,
                    PartitionMetrics)
import alerts.monitor as monitor
import alerts.state_store as state_store
from alerts.models import Thresholds

from alerts.state_store import StateStore, IncidentStore, PendingStore, AlertCooldownStore
from alerts.states import State, Alert

from config import Settings, get_yaml_config

def test_monitoring_metrics(monkeypatch):
    sent_alerts = []

    async def fake_send_alert(bot, chat_id, status):
        sent_alerts.append(status)

    monkeypatch.setattr(
        monitor,
        "send_alert",
        fake_send_alert
        )

    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75,
        warning_duration=0,
        cooldown=60
    )

    async def run_scenario():
        values = [70, 86, 87, 96, 70]

        for value in values:
            await monitor.monitoring_metrics(
                metric_name='cpu_usage',
                display_name='CPU usage',
                value=value,
                unit='%',
                threshold=thresholds,
                store=store,
                pending_timer=pending_timer,
                cooldown=cooldown,
                bot=None,
                chat_id=123
            )

    asyncio.run(run_scenario())

    alerts = [
        item['CPU usage'].status.alert
        for item in sent_alerts
    ]

    assert alerts == [
        Alert.WARNING,
        Alert.CRITICAL,
        Alert.RECOVERED
    ]

    assert store.get('cpu_usage') == State.OK

def test_monitoring_metrics_timer(monkeypatch):
    sent_alerts = []
    current_time = 0

    async def fake_send_alert(bot, chat_id, status):
        sent_alerts.append([status, current_time])
    
    def fake_pending_timer_duration() -> float:
        return current_time
    
    monkeypatch.setattr(
        monitor,
        "send_alert",
        fake_send_alert
        )

    monkeypatch.setattr(
        state_store.time,
        "monotonic",
        fake_pending_timer_duration
    )

    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75,
        warning_duration=120
    )

    async def run_scenario():
        values = [70, 86, 86, 86]
        nonlocal current_time
        for value in values:
            await monitor.monitoring_metrics(
                metric_name='cpu_usage',
                display_name='CPU usage',
                value=value,
                unit='%',
                threshold=thresholds,
                store=store,
                pending_timer=pending_timer,
                cooldown=cooldown,
                bot=None,
                chat_id=123
            )
            current_time += 60

    asyncio.run(run_scenario())

    alerts = [

        [item[0]['CPU usage'].status.alert,
         item[1]]
        for item in sent_alerts
    ]

    assert alerts == [
        [Alert.WARNING, 180]
    ]

def test_monitoring_metrics_timer_crit_warn_crit(monkeypatch):
    sent_alerts = []
    current_time = 0

    async def fake_send_alert(bot, chat_id, status):
        sent_alerts.append([status, current_time])
    
    def fake_pending_timer_duration() -> float:
        return current_time
    
    monkeypatch.setattr(
        monitor,
        "send_alert",
        fake_send_alert
        )

    monkeypatch.setattr(
        state_store.time,
        "monotonic",
        fake_pending_timer_duration
    )

    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75,
        warning_duration=120
    )

    async def run_scenario():
        values = [96, 86, 96]
        nonlocal current_time
        for value in values:
            await monitor.monitoring_metrics(
                metric_name='cpu_usage',
                display_name='CPU usage',
                value=value,
                unit='%',
                threshold=thresholds,
                store=store,
                pending_timer=pending_timer,
                cooldown=cooldown,
                bot=None,
                chat_id=123
            )
            current_time += 60

    asyncio.run(run_scenario())

    alerts = [

        [item[0]['CPU usage'].status.alert,
         item[1]]
        for item in sent_alerts
    ]

    assert alerts == [
        [Alert.CRITICAL, 0],
        [Alert.CRITICAL, 120]
    ]

def test_short_warning_sends_no_alerts(monkeypatch):
    sent_alerts = []
    current_time = 0

    async def fake_send_alert(bot, chat_id, status):
        sent_alerts.append([status, current_time])
    
    def fake_pending_timer_duration() -> float:
        return current_time
    
    monkeypatch.setattr(
        monitor,
        "send_alert",
        fake_send_alert
        )

    monkeypatch.setattr(
        state_store.time,
        "monotonic",
        fake_pending_timer_duration
    )

    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75,
        warning_duration=120
    )

    async def run_scenario():
        values = [70, 86, 86, 70, 86, 83, 90]
        nonlocal current_time
        for value in values:
            await monitor.monitoring_metrics(
                metric_name='cpu_usage',
                display_name='CPU usage',
                value=value,
                unit='%',
                threshold=thresholds,
                store=store,
                pending_timer=pending_timer,
                cooldown=cooldown,
                bot=None,
                chat_id=123
            )
            current_time += 60

    asyncio.run(run_scenario())

    alerts = [

        [item[0]['CPU usage'].status.alert,
         item[1]]
        for item in sent_alerts
    ]

    assert len(alerts) == 0


def test_warning_timer_restarts_after_normalization(monkeypatch):
    sent_alerts = []
    current_time = 0

    async def fake_send_alert(bot, chat_id, status):
        sent_alerts.append([status, current_time])
    
    def fake_pending_timer_duration() -> float:
        return current_time
    
    monkeypatch.setattr(
        monitor,
        "send_alert",
        fake_send_alert
        )

    monkeypatch.setattr(
        state_store.time,
        "monotonic",
        fake_pending_timer_duration
    )

    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75,
        warning_duration=120
    )

    async def run_scenario():
        values = [70, 86, 86, 70, 86, 85, 90]
        nonlocal current_time
        for value in values:
            await monitor.monitoring_metrics(
                metric_name='cpu_usage',
                display_name='CPU usage',
                value=value,
                unit='%',
                threshold=thresholds,
                store=store,
                pending_timer=pending_timer,
                cooldown=cooldown,
                bot=None,
                chat_id=123
            )
            current_time += 60

    asyncio.run(run_scenario())

    alerts = [

        [item[0]['CPU usage'].status.alert,
         item[1]]
        for item in sent_alerts
    ]

    assert alerts == [
        [Alert.WARNING, 360]
    ]

@pytest.mark.asyncio
async def test_numeric_cooldown_restarts_after_repeat(monkeypatch):
    sent_alerts = []
    current_time = 0.0

    def fake_monotonic():
        return current_time

    async def fake_send_alert(bot, chat_id, status):
        sent_alerts.append(
            (status["CPU usage"].status.alert, current_time)
        )

    monkeypatch.setattr(state_store.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(monitor, "send_alert", fake_send_alert)

    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75,
        warning_duration=0,
        cooldown=120,
    )

    for moment in [0, 119, 120, 121, 239, 240]:
        current_time = moment

        await monitor.monitoring_metrics(
            metric_name="cpu_usage",
            display_name="CPU usage",
            value=90,
            unit="%",
            threshold=thresholds,
            store=store,
            pending_timer=pending_timer,
            cooldown=cooldown,
            bot=None,
            chat_id=123,
        )

    assert sent_alerts == [
        (Alert.WARNING, 0),
        (Alert.WARNING, 120),
        (Alert.WARNING, 240),
    ]
    assert store.get("cpu_usage") == State.WARNING

@pytest.mark.asyncio
async def test_critical_interrupts_pending_warning(monkeypatch):
    sent_alerts = []
    current_time = 0.0

    def fake_monotonic():
        return current_time

    async def fake_send_alert(bot, chat_id, status):
        sent_alerts.append(
            (status["CPU usage"].status.alert, current_time)
        )

    monkeypatch.setattr(state_store.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(monitor, "send_alert", fake_send_alert)

    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75,
        warning_duration=120,
        cooldown=300,
    )

    for moment, value in [(0, 86), (60, 96)]:
        current_time = moment

        await monitor.monitoring_metrics(
            metric_name="cpu_usage",
            display_name="CPU usage",
            value=value,
            unit="%",
            threshold=thresholds,
            store=store,
            pending_timer=pending_timer,
            cooldown=cooldown,
            bot=None,
            chat_id=123,
        )

        if moment == 0:
            assert sent_alerts == []
            assert store.get("cpu_usage") == State.OK

    assert sent_alerts == [(Alert.CRITICAL, 60)]
    assert store.get("cpu_usage") == State.CRITICAL
    assert pending_timer.get("cpu_usage", State.WARNING) is None


@pytest.mark.asyncio
async def test_monitoring_cpu_no_cpu_data(monkeypatch):
    metrics = []

    def fake_cpu_check():
        return None
    
    async def fake_monitoring_metrics(**kwargs):
        metrics.append(kwargs)

    monkeypatch.setattr(
        monitor,
        'cpu_check',
        fake_cpu_check
    )

    monkeypatch.setattr(
        monitor,
        'monitoring_metrics',
        fake_monitoring_metrics
    )
    
    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75,
        warning_duration=120
    )

    await monitor.monitoring_cpu(
        store=store,
        pending_timer=pending_timer,
        cooldown=cooldown,
        bot=None,
        chat_id=123,
        cpu_temperature_threshold=thresholds,
        cpu_usage_thresholds=thresholds
    )

    assert metrics == []


@pytest.mark.asyncio
async def test_monitoring_cpu(monkeypatch):

    calls = {
        'cpu_check': 0,
        'monitoring_metrics': 0
    }

    metrics = []

    def fake_cpu_check():
        calls['cpu_check'] += 1
        return CpuMetrics(
                    temperature=55,
                    usage_percent=92.5,
                    load_average=LoadAverage(
                        min_1=0.5,
                        min_5=0.7,
                        min_15=1.6
                    )
        )

    async def fake_monitoring_metrics(
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
        calls['monitoring_metrics'] += 1
        metrics.append((metric_name, value, unit))
        
    monkeypatch.setattr(monitor,'cpu_check', fake_cpu_check)
    monkeypatch.setattr(monitor, 'monitoring_metrics', fake_monitoring_metrics)


    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75,
        warning_duration=120
    )

    await monitor.monitoring_cpu(
        store=store,
        pending_timer=pending_timer,
        cooldown=cooldown,
        bot=None,
        chat_id=123,
        cpu_temperature_threshold=thresholds,
        cpu_usage_thresholds=thresholds
    )

    assert calls['cpu_check'] == 1
    assert calls['monitoring_metrics'] == 2

    assert ('cpu_temperature', 55, "°C") in metrics
    assert ('cpu_usage', 92.5, "%") in metrics


@pytest.mark.asyncio
async def test_monitoring_ram(monkeypatch):

    metrics = []

    def fake_ram_check():
        return MemoryMetrics(
            ram=RamMetrics(
                total=1073741824,
                available=2073741824,
                usage=91.0),
            swap=SwapMetrics(
                total=1073741824,
                used=1073741824,
                free=1073741824,
                usage=50.0
                )
            )

    async def fake_monitoring_metrics(
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
        metrics.append((metric_name, value, unit))

    monkeypatch.setattr(
        monitor,
        'ram_check',
        fake_ram_check
        )
    
    monkeypatch.setattr(
        monitor,
        'monitoring_metrics',
        fake_monitoring_metrics
        )

    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75,
        warning_duration=120
    )

    await monitor.monitoring_ram_usage(
        store=store,
        pending_timer=pending_timer,
        cooldown=cooldown,
        bot=None, 
        chat_id=None, 
        threshold=thresholds
    )

    assert ('ram_usage', 91.0, '%') in metrics
    assert len(metrics) == 1


@pytest.mark.asyncio
async def test_monitoring_ram_unavailable(monkeypatch):
    metrics = []

    def fake_ram_check():
        return None

    def fake_monitoring_metrics(**kwargs):
        metrics.append(kwargs)

    monkeypatch.setattr(
        monitor,
        'ram_check',
        fake_ram_check
        )

    monkeypatch.setattr(
        monitor,
        'monitoring_metrics',
        fake_monitoring_metrics
    )

    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75,
        warning_duration=120
    )

    await monitor.monitoring_ram_usage(
        store=store,
        pending_timer=pending_timer,
        cooldown=cooldown,
        bot=None,
        chat_id=123,
        threshold=thresholds
    )

    assert metrics == []


@pytest.mark.asyncio
async def test_monitoring_disks(monkeypatch):
    metrics = []

    calls = {
        'disk_check': 0,
        'monitoring_metrics': 0
    }

    def fake_disk_check(**kwargs):
        calls['disk_check'] += 1
        return {'sdb': DiskMetrics(
            temperature=52,
            partitions=[PartitionMetrics(
                    partition='sdb1',
                    mountpoint='/',
                    total=15,
                    used=10,
                    free=5,
                    usage_percent=55.0
                )]
            )
        }

    async def fake_monitoring_metrics(
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
        calls['monitoring_metrics'] += 1
        metrics.append((metric_name, value, unit))

    monkeypatch.setattr(
        monitor,
        'disk_check',
        fake_disk_check
    )

    monkeypatch.setattr(
        monitor,
        'monitoring_metrics',
        fake_monitoring_metrics
    )

    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = {
        'temperature': Thresholds(
            warning=85,
            critical=95,
            recovery=75,
            warning_duration=120
            ),
        'usage': Thresholds(
            warning=85,
            critical=95,
            recovery=75,
            warning_duration=120
        )
    }


    await monitor.monitoring_disk(
        store=store,
        pending_timer=pending_timer,
        cooldown=cooldown,
        bot=None,
        chat_id=123,
        temperature_threshold=thresholds['temperature'],
        usage_threshold=thresholds['usage'],
        lsblk_timeout=10,
        smartctl_timeout=10
    )

    assert calls['disk_check'] == 1
    assert calls['monitoring_metrics'] == 2

    assert ('disk_temperature_sdb', 52, '°C') in metrics
    assert('partition_usage_sdb1', 55.0, '%') in metrics



@pytest.mark.asyncio
async def test_monitoring_disks_temperature_unavailable(monkeypatch):
    metrics = []

    calls = {
        'disk_check': 0,
        'monitoring_metrics': 0
    }

    def fake_disk_check(**kwargs):
        calls['disk_check'] += 1
        return {'sdb': DiskMetrics(
            temperature=None,
            partitions=[PartitionMetrics(
                    partition='sdb1',
                    mountpoint='/',
                    total=15,
                    used=10,
                    free=5,
                    usage_percent=55.0
                )]
            )
        }

    async def fake_monitoring_metrics(
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
        calls['monitoring_metrics'] += 1
        metrics.append((metric_name, value, unit))

    monkeypatch.setattr(
        monitor,
        'disk_check',
        fake_disk_check
    )

    monkeypatch.setattr(
        monitor,
        'monitoring_metrics',
        fake_monitoring_metrics
    )

    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = {
        'temperature': Thresholds(
            warning=85,
            critical=95,
            recovery=75,
            warning_duration=120
            ),
        'usage': Thresholds(
            warning=85,
            critical=95,
            recovery=75,
            warning_duration=120
        )
    }


    await monitor.monitoring_disk(
        store=store,
        pending_timer=pending_timer,
        cooldown=cooldown,
        bot=None,
        chat_id=123,
        temperature_threshold=thresholds['temperature'],
        usage_threshold=thresholds['usage'],
        lsblk_timeout=10,
        smartctl_timeout=10
    )

    assert calls['disk_check'] == 1
    assert calls['monitoring_metrics'] == 1

    assert('partition_usage_sdb1', 55, '%') in metrics


@pytest.mark.asyncio
async def test_monitoring_disks_efi_is_not_checking(monkeypatch):
    metrics = []

    calls = {
        'disk_check': 0,
        'monitoring_metrics': 0
    }

    def fake_disk_check(**kwargs):
        calls['disk_check'] += 1
        return {'sdb': DiskMetrics(
            temperature=52,
            partitions=[PartitionMetrics(
                    partition='sdb1',
                    mountpoint='/boot/efi',
                    total=15,
                    used=10,
                    free=5,
                    usage_percent=52.0
                )]
            )
        }

    async def fake_monitoring_metrics(
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
        calls['monitoring_metrics'] += 1
        metrics.append((metric_name, value, unit))

    monkeypatch.setattr(
        monitor,
        'disk_check',
        fake_disk_check
    )

    monkeypatch.setattr(
        monitor,
        'monitoring_metrics',
        fake_monitoring_metrics
    )

    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = {
        'temperature': Thresholds(
            warning=85,
            critical=95,
            recovery=75,
            warning_duration=120
            ),
        'usage': Thresholds(
            warning=85,
            critical=95,
            recovery=75,
            warning_duration=120
        )
    }


    await monitor.monitoring_disk(
        store=store,
        pending_timer=pending_timer,
        cooldown=cooldown,
        bot=None,
        chat_id=123,
        temperature_threshold=thresholds['temperature'],
        usage_threshold=thresholds['usage'],
        lsblk_timeout=10,
        smartctl_timeout=10
    )

    assert calls['disk_check'] == 1
    assert calls['monitoring_metrics'] == 1

    assert ('disk_temperature_sdb', 52, '°C') in metrics
    assert('partition_usage_sdb1', 52, '%') not in metrics
    assert len(metrics) == 1


@pytest.mark.asyncio
async def test_monitoring_disks_unavailable(monkeypatch):
    metrics = []

    def fake_disk_check(**kwargs):
        return None

    async def fake_monitoring_metrics(**kwargs):
        metrics.append(kwargs)

    monkeypatch.setattr(
        monitor,
        'disk_check',
        fake_disk_check
    )

    monkeypatch.setattr(
        monitor,
        'monitoring_metrics',
        fake_monitoring_metrics
    )

    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = {
        'temperature': Thresholds(
            warning=85,
            critical=95,
            recovery=75,
            warning_duration=120
            ),
        'usage': Thresholds(
            warning=85,
            critical=95,
            recovery=75,
            warning_duration=120
        )
    }


    await monitor.monitoring_disk(
        store=store,
        pending_timer=pending_timer,
        cooldown=cooldown,
        bot=None,
        chat_id=123,
        temperature_threshold=thresholds['temperature'],
        usage_threshold=thresholds['usage'],
        lsblk_timeout=10,
        smartctl_timeout=10
    )

    assert metrics == []


@pytest.mark.asyncio
async def test_docker_monitoring_container_unavailable(monkeypatch):
    sent_alerts = []

    def fake_get_conatiners_health(**kwargs):
        return None

    async def fake_send_container_alert(bot, chat_id, status):
        sent_alerts.append(status)

    monkeypatch.setattr(
        monitor,
        'get_containers_health',
        fake_get_conatiners_health
    )

    monkeypatch.setattr(
        monitor,
        'send_container_alert',
        fake_send_container_alert
    )

    monitored_containers = ('abc', 'bcd', 'edf')
    store = StateStore()
    incident = IncidentStore()
    cooldown_timer = AlertCooldownStore()

    await monitor.monitoring_containers(
        store=store,
        incident=incident,
        cooldown_timer=cooldown_timer,
        bot=None,
        chat_id=123,
        monitored_containers=monitored_containers,
        cooldown=0,
        docker_timeout=10
    )

    assert sent_alerts == []

@pytest.mark.asyncio
async def test_docker_monitoring_container_is_missing(monkeypatch):
    sent_alerts = []

    def fake_get_conatiners_health(**kwargs):
        return {}

    async def fake_send_container_alert(bot, chat_id, status):
        sent_alerts.append(status)

    monkeypatch.setattr(
        monitor,
        'get_containers_health',
        fake_get_conatiners_health
    )

    monkeypatch.setattr(
        monitor,
        'send_container_alert',
        fake_send_container_alert
    )

    monitored_containers = {'abc'}
    store = StateStore()
    incident = IncidentStore()
    cooldown_timer = AlertCooldownStore()

    await monitor.monitoring_containers(
        store=store,
        incident=incident,
        cooldown_timer=cooldown_timer,
        bot=None,
        chat_id=123,
        monitored_containers=monitored_containers,
        cooldown=0,
        docker_timeout=10
    )

    assert sent_alerts[0]['abc'].status.alert == Alert.CRITICAL

@pytest.mark.asyncio
async def test_docker_container_get_no_info(monkeypatch):
    sent_alerts = []

    def fake_get_conatiners_health(**kwargs):
        return {'abc': None}

    async def fake_send_container_alert(bot, chat_id, status):
        sent_alerts.append(status)

    monkeypatch.setattr(
        monitor,
        'get_containers_health',
        fake_get_conatiners_health
    )

    monkeypatch.setattr(
        monitor,
        'send_container_alert',
        fake_send_container_alert
    )

    monitored_containers = {'abc'}
    store = StateStore()
    incident = IncidentStore()
    cooldown_timer = AlertCooldownStore()

    await monitor.monitoring_containers(
        store=store,
        incident=incident,
        cooldown_timer=cooldown_timer,
        bot=None,
        chat_id=123,
        monitored_containers=monitored_containers,
        cooldown=0,
        docker_timeout=10
    )

    assert sent_alerts == []


@pytest.mark.asyncio
async def test_docker_container_lifecycle(monkeypatch):
    sent_alerts = []
    async def fake_send_container_alert(
        bot,
        chat_id,
        status,
    ):
        sent_alerts.append(status)

    monkeypatch.setattr(
        monitor,
        "send_container_alert",
        fake_send_container_alert,
    )

    store = StateStore()
    incident = IncidentStore()
    cooldown_timer = AlertCooldownStore()

    container_statuses = [
        "running",
        "exited",
        "running",
    ]

    for container_status in container_statuses:
        await monitor.docker_monitoring_metrics(
            container_name="vaultwarden",
            container_status=container_status,
            container_health=None,
            store=store,
            incident=incident,
            cooldown_timer=cooldown_timer,
            cooldown=0,
            bot=None,
            chat_id=123,
        )

    assert len(sent_alerts) == 2

    alerts = [
        item["vaultwarden"]
        for item in sent_alerts
    ]

    assert alerts[0].status.alert == Alert.CRITICAL
    assert alerts[0].container_status == "exited"
    assert alerts[0].downtime is None

    assert alerts[1].status.alert == Alert.RECOVERED
    assert alerts[1].container_status == "running"
    assert alerts[1].downtime is not None

    assert store.get("docker_vaultwarden") == State.OK
    assert (
        incident.get_downtime("docker_vaultwarden")
        is None
    )


@pytest.mark.asyncio
async def test_docker_monitoring_cooldown(monkeypatch):
    sent_alerts = []
    current_time = 0

    async def fake_send_container_alert(
        bot,
        chat_id,
        status,
    ):
        sent_alerts.append([status, current_time])

    monkeypatch.setattr(
        monitor,
        "send_container_alert",
        fake_send_container_alert,
    )
    
    def fake_monotonic():
        return current_time

    monkeypatch.setattr(
        state_store.time,
        "monotonic",
        fake_monotonic
    )

    store = StateStore()
    incident = IncidentStore()
    cooldown_timer = AlertCooldownStore()

    container_statuses = [
        "running",
        "exited",
        "exited",
        "exited",
        "running",
    ]
    cooldown = 70

    for container_status in container_statuses:
        await monitor.docker_monitoring_metrics(
            container_name="vaultwarden",
            container_status=container_status,
            container_health=None,
            store=store,
            cooldown_timer= cooldown_timer,
            cooldown = cooldown,
            incident=incident,
            bot=None,
            chat_id=123,
        )
        current_time += 60

    assert len(sent_alerts) == 3

    alerts = [
        (item[0]["vaultwarden"], item[1])
        for item in sent_alerts
    ]

    assert alerts[0][0].status.alert == Alert.CRITICAL
    assert alerts[0][0].container_status == "exited"
    assert alerts[0][0].downtime is None
    assert alerts[0][1] == 60

    assert alerts[1][0].status.alert == Alert.CRITICAL
    assert alerts[1][0].container_status == "exited"
    assert alerts[1][0].downtime is None
    assert alerts[1][1] == 180

    assert alerts[2][0].status.alert == Alert.RECOVERED
    assert alerts[2][0].container_status == "running"
    assert alerts[2][0].downtime is not None
    assert alerts[2][1] == 240
    
    assert store.get("docker_vaultwarden") == State.OK

    recovery = sent_alerts[-1][0]["vaultwarden"]
    assert recovery.downtime == 180

def test_pending_store_preserves_start_time(monkeypatch):
    current_time = 100.0

    def fake_monotonic():
        return current_time

    monkeypatch.setattr(
        state_store.time,
        "monotonic",
        fake_monotonic
    )
    store = state_store.PendingStore()
    store.start(
        metric='cpu',
        state=State.WARNING)
    
    current_time = 130.0

    store.start(
        metric='cpu',
        state=State.WARNING)

    current_time = 150.0
    store.start(
        metric='cpu',
        state=State.WARNING)

    duration = store.get(metric='cpu', state=State.WARNING)
    
    assert duration == 50


def test_pending_store_remove_metric():
    store = state_store.PendingStore()

    store.start(
        metric='cpu',
        state=State.WARNING
    )

    assert store.get(metric='cpu', state=State.WARNING) is not None

    store.remove(metric='cpu')

    assert store.get(metric='cpu', state=State.WARNING) is None

@pytest.mark.asyncio
async def test_monitoring_disk_not_block_event_loop(monkeypatch):
    loop = asyncio.get_running_loop()

    started = asyncio.Event()
    realese = threading.Event()

    def fake_disk_check(*args, **kwargs):
        loop.call_soon_threadsafe(started.set)
        realese.wait(timeout=5)
        return {}

    monkeypatch.setattr(monitor, 'disk_check', fake_disk_check)

    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75
    )

    task = asyncio.create_task(
        monitor.monitoring_disk(
            store=StateStore(),
            pending_timer=PendingStore(),
            cooldown=AlertCooldownStore(),
            bot=None,
            chat_id=123,
            temperature_threshold=thresholds,
            usage_threshold=thresholds,
            lsblk_timeout=5,
            smartctl_timeout=10,
        )
    )

    try:
        await asyncio.wait_for(started.wait(), timeout=2)

        assert not task.done()

    finally:
        realese.set()
        await asyncio.wait_for(task, timeout=2)


@pytest.mark.asyncio
async def test_monitoring_loop_can_be_cancelled(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]

    import yaml

    data = yaml.safe_load(
        (project_root / "config.example.yaml").read_text(
            encoding="utf-8"
        )
    )
    data["telegram"] = {
        "token": "test-token",
        "allowed_users": [123],
        "alert_chat_id": 123,
    }
    settings = Settings.model_validate(data)

    cycle_finished = asyncio.Event()

    async def fake_monitoring(*args, **kwargs):
        pass

    async def fake_monitoring_containers(*args, **kwargs):
        cycle_finished.set()

    monkeypatch.setattr(monitor, "monitoring_cpu", fake_monitoring)
    monkeypatch.setattr(monitor, "monitoring_ram_usage", fake_monitoring)
    monkeypatch.setattr(monitor, "monitoring_disk", fake_monitoring)
    monkeypatch.setattr(
        monitor,
        "monitoring_containers",
        fake_monitoring_containers,
    )

    task = asyncio.create_task(
        monitor.monitoring_loop(
            store=StateStore(),
            cooldown=AlertCooldownStore(),
            incident=IncidentStore(),
            pending_timer=PendingStore(),
            bot=None,
            chat_id=123,
            settings=settings,
        )
    )

    try:
        await asyncio.wait_for(cycle_finished.wait(), timeout=2)

        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)

        assert task.cancelled()
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)