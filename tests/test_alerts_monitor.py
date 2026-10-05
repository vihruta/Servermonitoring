import pytest
import asyncio
import threading
import httpx
from pathlib import Path
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendMessage

from models import (CpuMetrics, LoadAverage, 
                    RamMetrics, MemoryMetrics,
                    SwapMetrics, DiskMetrics,
                    PartitionMetrics, HttpMetrics)
import alerts.monitor as monitor
from alerts.monitoring import containers as container_monitor
from alerts.monitoring import hardware as hardware_monitor
from alerts.monitoring import http as http_monitor
from alerts.monitoring import network as network_monitor
import alerts.state_store as state_store
from alerts.models import Thresholds

from alerts.state_store import StateStore, IncidentStore, PendingStore, AlertCooldownStore, NetworkAccidentStore
from alerts.states import State, Alert

from config import (Settings, get_yaml_config, 
                    HttpServiceSettings, HttpServicesSettings,
                    InternetSettings)

def test_monitoring_metrics(monkeypatch: pytest.MonkeyPatch):
    sent_alerts = []

    async def fake_send_alert(bot, chat_id, status):
        sent_alerts.append(status)

    monkeypatch.setattr(
        hardware_monitor,
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
            await hardware_monitor.monitoring_metrics(
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

def test_monitoring_metrics_timer(monkeypatch: pytest.MonkeyPatch):
    sent_alerts = []
    current_time = 0

    async def fake_send_alert(bot, chat_id, status):
        sent_alerts.append([status, current_time])
    
    def fake_pending_timer_duration() -> float:
        return current_time
    
    monkeypatch.setattr(
        hardware_monitor,
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
            await hardware_monitor.monitoring_metrics(
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

def test_monitoring_metrics_timer_crit_warn_crit(monkeypatch: pytest.MonkeyPatch):
    sent_alerts = []
    current_time = 0

    async def fake_send_alert(bot, chat_id, status):
        sent_alerts.append([status, current_time])
    
    def fake_pending_timer_duration() -> float:
        return current_time
    
    monkeypatch.setattr(
        hardware_monitor,
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
            await hardware_monitor.monitoring_metrics(
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

def test_short_warning_sends_no_alerts(monkeypatch: pytest.MonkeyPatch):
    sent_alerts = []
    current_time = 0

    async def fake_send_alert(bot, chat_id, status):
        sent_alerts.append([status, current_time])
    
    def fake_pending_timer_duration() -> float:
        return current_time
    
    monkeypatch.setattr(
        hardware_monitor,
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
            await hardware_monitor.monitoring_metrics(
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


def test_warning_timer_restarts_after_normalization(monkeypatch: pytest.MonkeyPatch):
    sent_alerts = []
    current_time = 0

    async def fake_send_alert(bot, chat_id, status):
        sent_alerts.append([status, current_time])
    
    def fake_pending_timer_duration() -> float:
        return current_time
    
    monkeypatch.setattr(
        hardware_monitor,
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
            await hardware_monitor.monitoring_metrics(
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
async def test_numeric_cooldown_restarts_after_repeat(monkeypatch: pytest.MonkeyPatch):
    sent_alerts = []
    current_time = 0.0

    def fake_monotonic():
        return current_time

    async def fake_send_alert(bot, chat_id, status):
        sent_alerts.append(
            (status["CPU usage"].status.alert, current_time)
        )

    monkeypatch.setattr(state_store.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(hardware_monitor, "send_alert", fake_send_alert)

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

        await hardware_monitor.monitoring_metrics(
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
async def test_critical_interrupts_pending_warning(monkeypatch: pytest.MonkeyPatch):
    sent_alerts = []
    current_time = 0.0

    def fake_monotonic():
        return current_time

    async def fake_send_alert(bot, chat_id, status):
        sent_alerts.append(
            (status["CPU usage"].status.alert, current_time)
        )

    monkeypatch.setattr(state_store.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(hardware_monitor, "send_alert", fake_send_alert)

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

        await hardware_monitor.monitoring_metrics(
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
async def test_monitoring_cpu_no_cpu_data(monkeypatch: pytest.MonkeyPatch):
    metrics = []

    def fake_cpu_check():
        return None
    
    async def fake_monitoring_metrics(**kwargs):
        metrics.append(kwargs)

    monkeypatch.setattr(
        hardware_monitor,
        'cpu_check',
        fake_cpu_check
    )

    monkeypatch.setattr(
        hardware_monitor,
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

    await hardware_monitor.monitoring_cpu(
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
async def test_monitoring_cpu(monkeypatch: pytest.MonkeyPatch):

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
        
    monkeypatch.setattr(hardware_monitor,'cpu_check', fake_cpu_check)
    monkeypatch.setattr(hardware_monitor, 'monitoring_metrics', fake_monitoring_metrics)


    store = StateStore()
    pending_timer = PendingStore()
    cooldown = AlertCooldownStore()
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75,
        warning_duration=120
    )

    await hardware_monitor.monitoring_cpu(
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
async def test_monitoring_ram(monkeypatch: pytest.MonkeyPatch):

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
        hardware_monitor,
        'ram_check',
        fake_ram_check
        )
    
    monkeypatch.setattr(
        hardware_monitor,
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

    await hardware_monitor.monitoring_ram_usage(
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
async def test_monitoring_ram_unavailable(monkeypatch: pytest.MonkeyPatch):
    metrics = []

    def fake_ram_check():
        return None

    def fake_monitoring_metrics(**kwargs):
        metrics.append(kwargs)

    monkeypatch.setattr(
        hardware_monitor,
        'ram_check',
        fake_ram_check
        )

    monkeypatch.setattr(
        hardware_monitor,
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

    await hardware_monitor.monitoring_ram_usage(
        store=store,
        pending_timer=pending_timer,
        cooldown=cooldown,
        bot=None,
        chat_id=123,
        threshold=thresholds
    )

    assert metrics == []


@pytest.mark.asyncio
async def test_monitoring_disks(monkeypatch: pytest.MonkeyPatch):
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
        hardware_monitor,
        'disk_check',
        fake_disk_check
    )

    monkeypatch.setattr(
        hardware_monitor,
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


    await hardware_monitor.monitoring_disk(
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
async def test_monitoring_disks_temperature_unavailable(monkeypatch: pytest.MonkeyPatch):
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
        hardware_monitor,
        'disk_check',
        fake_disk_check
    )

    monkeypatch.setattr(
        hardware_monitor,
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


    await hardware_monitor.monitoring_disk(
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
async def test_monitoring_disks_efi_is_not_checking(monkeypatch: pytest.MonkeyPatch):
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
        hardware_monitor,
        'disk_check',
        fake_disk_check
    )

    monkeypatch.setattr(
        hardware_monitor,
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


    await hardware_monitor.monitoring_disk(
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
async def test_monitoring_disks_unavailable(monkeypatch: pytest.MonkeyPatch):
    metrics = []

    def fake_disk_check(**kwargs):
        return None

    async def fake_monitoring_metrics(**kwargs):
        metrics.append(kwargs)

    monkeypatch.setattr(
        hardware_monitor,
        'disk_check',
        fake_disk_check
    )

    monkeypatch.setattr(
        hardware_monitor,
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


    await hardware_monitor.monitoring_disk(
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
async def test_docker_monitoring_container_unavailable(monkeypatch: pytest.MonkeyPatch):
    sent_alerts = []

    def fake_get_conatiners_health(**kwargs):
        return None

    async def fake_send_container_alert(bot, chat_id, status):
        sent_alerts.append(status)

    monkeypatch.setattr(
        container_monitor,
        'get_containers_health',
        fake_get_conatiners_health
    )

    monkeypatch.setattr(
        container_monitor,
        'send_container_alert',
        fake_send_container_alert
    )

    monitored_containers = {'abc', 'bcd', 'edf'}
    store = StateStore()
    incident = IncidentStore()
    cooldown_timer = AlertCooldownStore()

    await container_monitor.monitoring_containers(
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
async def test_docker_monitoring_container_is_missing(monkeypatch: pytest.MonkeyPatch):
    sent_alerts = []

    def fake_get_conatiners_health(**kwargs):
        return {}

    async def fake_send_container_alert(bot, chat_id, status):
        sent_alerts.append(status)

    monkeypatch.setattr(
        container_monitor,
        'get_containers_health',
        fake_get_conatiners_health
    )

    monkeypatch.setattr(
        container_monitor,
        'send_container_alert',
        fake_send_container_alert
    )

    monitored_containers = {'abc'}
    store = StateStore()
    incident = IncidentStore()
    cooldown_timer = AlertCooldownStore()

    await container_monitor.monitoring_containers(
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
async def test_docker_container_get_no_info(monkeypatch: pytest.MonkeyPatch):
    sent_alerts = []

    def fake_get_conatiners_health(**kwargs):
        return {'abc': None}

    async def fake_send_container_alert(bot, chat_id, status):
        sent_alerts.append(status)

    monkeypatch.setattr(
        container_monitor,
        'get_containers_health',
        fake_get_conatiners_health
    )

    monkeypatch.setattr(
        container_monitor,
        'send_container_alert',
        fake_send_container_alert
    )

    monitored_containers = {'abc'}
    store = StateStore()
    incident = IncidentStore()
    cooldown_timer = AlertCooldownStore()

    await container_monitor.monitoring_containers(
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
async def test_docker_container_lifecycle(monkeypatch: pytest.MonkeyPatch):
    sent_alerts = []
    async def fake_send_container_alert(
        bot,
        chat_id,
        status,
    ):
        sent_alerts.append(status)

    monkeypatch.setattr(
        container_monitor,
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
        await container_monitor.docker_monitoring_metrics(
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
async def test_docker_monitoring_cooldown(monkeypatch: pytest.MonkeyPatch):
    sent_alerts = []
    current_time = 0
    async def fake_send_container_alert(
        bot,
        chat_id,
        status,
    ):
        sent_alerts.append([status, current_time])

    monkeypatch.setattr(
        container_monitor,
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
        await container_monitor.docker_monitoring_metrics(
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

def test_pending_store_preserves_start_time(monkeypatch: pytest.MonkeyPatch):
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
async def test_monitoring_disk_not_block_event_loop(monkeypatch: pytest.MonkeyPatch):
    loop = asyncio.get_running_loop()

    started = asyncio.Event()
    realese = threading.Event()

    def fake_disk_check(*args, **kwargs):
        loop.call_soon_threadsafe(started.set)
        realese.wait(timeout=5)
        return {}

    monkeypatch.setattr(hardware_monitor, 'disk_check', fake_disk_check)

    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75
    )

    task = asyncio.create_task(
        hardware_monitor.monitoring_disk(
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
async def test_monitoring_loop_can_be_cancelled(monkeypatch: pytest.MonkeyPatch):
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
            cooldown_timer=AlertCooldownStore(),
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


@pytest.mark.asyncio
async def test_http_rapid_rejection(monkeypatch):
    current_time = 0
    sent_alert = 0

    async def fake_handler(request: httpx.Request) -> httpx.Response:
        nonlocal current_time
        if current_time == 0:
            raise httpx.TimeoutException(
                message='Connection error',
                request=request
            )
        else:
            code = 200

        return httpx.Response(status_code=code)
    
    fake_transport = httpx.MockTransport(handler=fake_handler)

    def fake_monotonic():
        return current_time

    monkeypatch.setattr(
        state_store.time,
        "monotonic",
        fake_monotonic
    )

    def fake_send_http_alert(
            bot,
            chat_id,
            status
        ):
        nonlocal sent_alert
        sent_alert += 1

    monkeypatch.setattr(
        http_monitor,
        "send_http_alert",
        fake_send_http_alert
    )

    first_service = 'test_app'
    first_settings = HttpServiceSettings(
        url='https://test_app.com',
        timeout=10,
        expected_status={200}
    )

    settings = HttpServicesSettings(
        interval = 1,
        failure_duration= 120,
        monitored={
                first_service: first_settings
            }
    )
    store = StateStore()
    incident = IncidentStore()
    cooldown_timer = AlertCooldownStore()

    async with httpx.AsyncClient(transport=fake_transport) as client:
        await http_monitor.http_monitoring(
            client=client,
            store=store,
            incident=incident,
            cooldown_timer=cooldown_timer,
            bot=None,
            chat_id=123,
            http_settings=settings
        )
        current_time = 60
        await http_monitor.http_monitoring(
            client=client,
            store=store,
            incident=incident,
            cooldown_timer=cooldown_timer,
            bot=None,
            chat_id=123,
            http_settings=settings
        )

    assert sent_alert == 0
    assert incident.get(metric=f'http_check_{first_service}') is None
    assert store.get(metric=f'http_check_{first_service}') == State.OK


@pytest.mark.asyncio
async def test_http_return_border_error(monkeypatch):
    current_time = 0
    sent_alert = []

    async def fake_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException(
            message='Connection error',
            request=request
        )

    
    fake_transport = httpx.MockTransport(handler=fake_handler)

    def fake_monotonic():
        return current_time

    monkeypatch.setattr(
        state_store.time,
        "monotonic",
        fake_monotonic
    )

    async def fake_send_http_alert(
            bot,
            chat_id,
            status
        ):
        sent_alert.append(status)

    monkeypatch.setattr(
        http_monitor,
        "send_http_alert",
        fake_send_http_alert
    )

    first_service = 'test_app'
    first_settings = HttpServiceSettings(
        url='https://test_app.com',
        timeout=10,
        expected_status={200}
    )

    settings = HttpServicesSettings(
        interval = 1,
        failure_duration= 120,
        monitored={
                first_service: first_settings
            }
    )
    store = StateStore()
    incident = IncidentStore()
    cooldown_timer = AlertCooldownStore()

    async with httpx.AsyncClient(transport=fake_transport) as client:
        await http_monitor.http_monitoring(
            client=client,
            store=store,
            incident=incident,
            cooldown_timer=cooldown_timer,
            bot=None,
            chat_id=123,
            http_settings=settings
        )
        current_time = 119
        assert store.get(metric=f'http_check_{first_service}') == State.OK
        await http_monitor.http_monitoring(
            client=client,
            store=store,
            incident=incident,
            cooldown_timer=cooldown_timer,
            bot=None,
            chat_id=123,
            http_settings=settings
        )

        assert store.get(metric=f'http_check_{first_service}') == State.OK
        assert sent_alert == []
        current_time = 120
        await http_monitor.http_monitoring(
            client=client,
            store=store,
            incident=incident,
            cooldown_timer=cooldown_timer,
            bot=None,
            chat_id=123,
            http_settings=settings
        )

    assert store.get(metric=f'http_check_{first_service}') == State.CRITICAL
    assert len(sent_alert) == 1
    assert sent_alert[0][first_service].status.alert == Alert.CRITICAL
    assert incident.get(metric=f'http_check_{first_service}') == 0


@pytest.mark.asyncio
async def test_http_failure_timer_restarts_after_short_recovery(monkeypatch):
    current_time = 0
    sent_alert = []

    async def fake_handler(request: httpx.Request) -> httpx.Response:
        nonlocal current_time
        if current_time == 60:
            return httpx.Response(status_code=200)
        
        raise httpx.TimeoutException(
            message='Connection error',
            request=request
        )

    
    fake_transport = httpx.MockTransport(handler=fake_handler)

    def fake_monotonic():
        return current_time

    monkeypatch.setattr(
        state_store.time,
        "monotonic",
        fake_monotonic
    )

    async def fake_send_http_alert(
            bot,
            chat_id,
            status
        ):
        sent_alert.append(status)

    monkeypatch.setattr(
        http_monitor,
        "send_http_alert",
        fake_send_http_alert
    )

    service = 'test_app'
    setting = HttpServiceSettings(
        url='https://test_app.com',
        timeout=10,
        expected_status={200}
    )

    settings = HttpServicesSettings(
        interval = 1,
        failure_duration= 120,
        monitored={
                service: setting
        }
    )

    store = StateStore()
    incident = IncidentStore()
    cooldown_timer = AlertCooldownStore()

    async with httpx.AsyncClient(transport=fake_transport) as client:
        for _ in range(8):
            await http_monitor.http_monitoring(
                client=client,
                store=store,
                incident=incident,
                cooldown_timer=cooldown_timer,
                bot=None,
                chat_id=123,
                http_settings=settings
            )
            if current_time < 210:
                assert sent_alert == []
            current_time += 30

    assert store.get(metric=f'http_check_{service}') == State.CRITICAL
    assert len(sent_alert) == 1
    assert sent_alert[0][service].status.alert == Alert.CRITICAL
    assert incident.get(metric=f'http_check_{service}') == 90


@pytest.mark.asyncio
async def test_http_recovery_reports_downtime(monkeypatch):
    current_time = 0
    sent_alerts = []

    def fake_handler(request: httpx.Request) -> httpx.Response:
        if current_time == 180:
            return httpx.Response(status_code=200)

        raise httpx.ReadTimeout("Timeout", request=request)

    def fake_monotonic():
        return current_time

    async def fake_send_http_alert(bot, chat_id, status):
        sent_alerts.append(status)

    monkeypatch.setattr(
        state_store.time, "monotonic", fake_monotonic
    )
    monkeypatch.setattr(
        http_monitor, "send_http_alert", fake_send_http_alert
    )

    service = "test_app"
    metric_name = f"http_check_{service}"

    settings = HttpServicesSettings(
        interval=60,
        failure_duration=120,
        cooldown=600,
        monitored={
            service: HttpServiceSettings(
                url="https://test.example",
                timeout=10,
                expected_status={200},
            )
        },
    )

    store = StateStore()
    incident = IncidentStore()
    cooldown_timer = AlertCooldownStore()

    transport = httpx.MockTransport(fake_handler)

    async with httpx.AsyncClient(transport=transport) as client:
        for timestamp in (0, 120, 180):
            current_time = timestamp

            await http_monitor.http_monitoring(
                client=client,
                store=store,
                incident=incident,
                cooldown_timer=cooldown_timer,
                bot=None,
                chat_id=123,
                http_settings=settings,
            )

            if timestamp == 0:
                assert sent_alerts == []
                assert store.get(metric_name) == State.OK
                assert incident.get(metric_name) == 0

            elif timestamp == 120:
                assert len(sent_alerts) == 1
                assert (
                    sent_alerts[0][service].status.alert
                    == Alert.CRITICAL
                )
                assert store.get(metric_name) == State.CRITICAL

    assert [
        message[service].status.alert
        for message in sent_alerts
    ] == [Alert.CRITICAL, Alert.RECOVERED]

    recovery = sent_alerts[1][service]
    assert recovery.result_code == 200
    assert recovery.error is None
    assert recovery.duration == 180

    assert store.get(metric_name) == State.OK
    assert incident.get(metric_name) is None
    assert cooldown_timer.check(metric_name, settings.cooldown)


@pytest.mark.asyncio
async def test_network_short_failure_is_reset(monkeypatch):
    is_failed = True
    current_time = 0.0

    async def fake_network_check(
            client,
            service_settings
    ):
        return HttpMetrics(
            service='Internet',
            result_code=None if is_failed else 200,
            is_failed=is_failed,
            error="Timeout error" if is_failed else None,
            duration_seconds=0.1,
        )

    monkeypatch.setattr(
        network_monitor,
        'network_check',
        fake_network_check
    )

    def fake_monotonic():
        return current_time


    monkeypatch.setattr(
        state_store.time, "monotonic", fake_monotonic
    )
    network_incident = NetworkAccidentStore()
    cooldown = AlertCooldownStore()
    network_settings = InternetSettings(
        url='http://example.com',
        timeout=120,
        expected_status={200},
        interval=60,
        failure_duration=120,
        cooldown=60
    )

    async with httpx.AsyncClient() as client:
        await network_monitor.network_monitoring_metrics(
            client=client,
            network_incident=network_incident,
            network_settings=network_settings,
            cooldown=cooldown,
            bot=None,
            chat_id=123
        )

        assert network_incident.started_at == 0
        assert network_incident.confirmed is False

        current_time = 60
        is_failed = False

        await network_monitor.network_monitoring_metrics(
            client=client,
            network_incident=network_incident,
            network_settings=network_settings,
            cooldown=cooldown,
            bot=None,
            chat_id=123
        )

        assert network_incident.started_at is None
        assert network_incident.confirmed is False
        assert network_incident.notified is False


@pytest.mark.asyncio
async def test_network_failure_is_confirmed_at_threshold(monkeypatch):
    is_failed = True
    current_time = 0.0
    sent_alerts = []

    async def fake_send_network_alert(
            bot,
            chat_id,
            problem_was_notified,
            status):
        sent_alerts.append(status)

    monkeypatch.setattr(
        network_monitor,
        "send_network_alert",
        fake_send_network_alert,
    )
    async def fake_network_check(
            client,
            service_settings
    ):
        return HttpMetrics(
            service='Internet',
            result_code=None,
            is_failed=True,
            error="Timeout error",
            duration_seconds=0.1,
        )

    monkeypatch.setattr(
        network_monitor,
        'network_check',
        fake_network_check
    )

    def fake_monotonic():
        return current_time


    monkeypatch.setattr(
        state_store.time, "monotonic", fake_monotonic
    )
    network_incident = NetworkAccidentStore()
    cooldown = AlertCooldownStore()
    network_settings = InternetSettings(
        url='http://example.com',
        timeout=120,
        expected_status={200},
        interval=60,
        failure_duration=120,
        cooldown=60
    )

    async with httpx.AsyncClient() as client:
        await network_monitor.network_monitoring_metrics(
            client=client,
            network_incident=network_incident,
            network_settings=network_settings,
            cooldown=cooldown,
            bot=None,
            chat_id=123
        )

        assert network_incident.started_at == 0.0
        assert network_incident.confirmed is False
        assert network_incident.notified is False

        current_time = 119

        await network_monitor.network_monitoring_metrics(
            client=client,
            network_incident=network_incident,
            network_settings=network_settings,
            cooldown=cooldown,
            bot=None,
            chat_id=123
        )

        assert network_incident.started_at == 0.0
        assert network_incident.confirmed is False
        assert network_incident.notified is False

        current_time = 120
        await network_monitor.network_monitoring_metrics(
            client=client,
            network_incident=network_incident,
            network_settings=network_settings,
            cooldown=cooldown,
            bot=None,
            chat_id=123
        )

        assert network_incident.started_at == 0.0
        assert network_incident.confirmed is True
        assert network_incident.notified is True
        assert len(sent_alerts) == 1


@pytest.mark.asyncio
async def test_network_recovery_retry_preserves_downtime(monkeypatch):
    current_time = 0.0
    delivered = []
    recovery_attempts = []

    def fake_monotonic():
        return current_time

    async def fake_network_check(client, service_settings):
        is_failed = current_time < 180

        return HttpMetrics(
            service="internet",
            result_code=None if is_failed else 200,
            is_failed=is_failed,
            error="Timeout error" if is_failed else None,
            duration_seconds=0.1,
        )

    async def fake_send_network_alert(
        bot,
        chat_id,
        status,
        problem_was_notified,
    ):
        alert = status["Network"]

        if alert.status.alert == Alert.RECOVERED:
            recovery_attempts.append(
                (current_time, alert.duration, problem_was_notified)
            )

            if current_time == 180:
                raise TelegramNetworkError(
                    method=SendMessage(chat_id=chat_id, text="Test"),
                    message="Network unavailable",
                )

        delivered.append(alert)

    monkeypatch.setattr(
        state_store.time, "monotonic", fake_monotonic
    )
    monkeypatch.setattr(
        network_monitor, "network_check", fake_network_check
    )
    monkeypatch.setattr(
        network_monitor, "send_network_alert", fake_send_network_alert
    )

    incident = NetworkAccidentStore()
    cooldown = AlertCooldownStore()
    settings = InternetSettings(
        url="https://example.com",
        timeout=10,
        expected_status={200},
        interval=60,
        failure_duration=120,
        cooldown=600,
    )

    async with httpx.AsyncClient() as client:
        async def run_check():
            await network_monitor.network_monitoring_metrics(
                client=client,
                network_incident=incident,
                network_settings=settings,
                cooldown=cooldown,
                bot=None,
                chat_id=123,
            )

        await run_check()
        assert delivered == []

        current_time = 120.0
        await run_check()

        assert len(delivered) == 1
        assert delivered[0].status.alert == Alert.CRITICAL
        assert incident.notified is True

        current_time = 180.0
        await run_check()

        assert len(delivered) == 1
        assert incident.started_at == 0.0
        assert incident.recovered_at == 180.0
        assert incident.confirmed is True
        assert incident.notified is True
        assert incident.get_duration() == 180.0

        current_time = 240.0
        await run_check()

        assert recovery_attempts == [
            (180.0, 180.0, True),
            (240.0, 180.0, True),
        ]
        assert len(delivered) == 2
        assert delivered[1].status.alert == Alert.RECOVERED
        assert delivered[1].duration == 180.0

        assert incident.started_at is None
        assert incident.recovered_at is None
        assert incident.confirmed is False
        assert incident.notified is False


@pytest.mark.asyncio
async def test_network_recovery_after_delivered_alert(monkeypatch):
    current_time = 0.0
    sent_alerts = []

    def fake_monotonic():
        return current_time

    async def fake_network_check(client, service_settings):
        is_failed = current_time < 180

        return HttpMetrics(
            service="internet",
            result_code=None if is_failed else 200,
            is_failed=is_failed,
            error="Timeout error" if is_failed else None,
            duration_seconds=0.1,
        )

    async def fake_send_network_alert(
        bot,
        chat_id,
        status,
        problem_was_notified,
    ):
        sent_alerts.append(
            (current_time, status["Network"], problem_was_notified)
        )

    monkeypatch.setattr(
        state_store.time, "monotonic", fake_monotonic
    )
    monkeypatch.setattr(
        network_monitor, "network_check", fake_network_check
    )
    monkeypatch.setattr(
        network_monitor, "send_network_alert", fake_send_network_alert
    )

    incident = NetworkAccidentStore()
    cooldown = AlertCooldownStore()
    settings = InternetSettings(
        url="https://example.com",
        timeout=10,
        expected_status={200},
        interval=60,
        failure_duration=120,
        cooldown=600,
    )

    async with httpx.AsyncClient() as client:
        async def run_check():
            await network_monitor.network_monitoring_metrics(
                client=client,
                network_incident=incident,
                network_settings=settings,
                cooldown=cooldown,
                bot=None,
                chat_id=123,
            )

        await run_check()

        assert sent_alerts == []
        assert incident.started_at == 0.0
        assert incident.confirmed is False
        assert incident.notified is False

        current_time = 120.0
        await run_check()

        assert len(sent_alerts) == 1
        timestamp, alert, was_notified = sent_alerts[0]

        assert timestamp == 120.0
        assert alert.status.alert == Alert.CRITICAL
        assert alert.status.state == State.CRITICAL
        assert alert.duration == 120.0
        assert was_notified is False
        assert incident.confirmed is True
        assert incident.notified is True

        current_time = 180.0
        await run_check()

        assert len(sent_alerts) == 2
        timestamp, recovery, was_notified = sent_alerts[1]

        assert timestamp == 180.0
        assert recovery.status.alert == Alert.RECOVERED
        assert recovery.status.state == State.OK
        assert recovery.result_code == 200
        assert recovery.error is None
        assert recovery.duration == 180.0
        assert was_notified is True

        assert incident.started_at is None
        assert incident.recovered_at is None
        assert incident.confirmed is False
        assert incident.notified is False

        current_time = 240.0
        await run_check()

        assert len(sent_alerts) == 2


@pytest.mark.asyncio
async def test_network_alert_repeats_after_cooldown(monkeypatch):
    current_time = 0.0
    sent_at = []
    sent_alerts = []

    def fake_monotonic():
        return current_time

    async def fake_network_check(client, service_settings):
        return HttpMetrics(
            service="internet",
            result_code=None,
            is_failed=True,
            error="Timeout error",
            duration_seconds=0.1,
        )

    async def fake_send_network_alert(
        bot,
        chat_id,
        status,
        problem_was_notified,
    ):
        sent_at.append(current_time)
        sent_alerts.append(status["Network"])

    monkeypatch.setattr(
        state_store.time, "monotonic", fake_monotonic
    )
    monkeypatch.setattr(
        network_monitor, "network_check", fake_network_check
    )
    monkeypatch.setattr(
        network_monitor, "send_network_alert", fake_send_network_alert
    )

    incident = NetworkAccidentStore()
    cooldown = AlertCooldownStore()
    settings = InternetSettings(
        url="https://example.com",
        timeout=10,
        expected_status={200},
        interval=60,
        failure_duration=120,
        cooldown=600,
    )

    async with httpx.AsyncClient() as client:
        for timestamp, expected_count in (
            (0, 0),
            (120, 1),
            (719, 1),
            (720, 2),
            (721, 2),
        ):
            current_time = timestamp

            await network_monitor.network_monitoring_metrics(
                client=client,
                network_incident=incident,
                network_settings=settings,
                cooldown=cooldown,
                bot=None,
                chat_id=123,
            )

            assert len(sent_at) == expected_count

    assert sent_at == [120, 720]
    assert [alert.status.alert for alert in sent_alerts] == [
        Alert.CRITICAL,
        Alert.CRITICAL,
    ]

    assert incident.started_at == 0
    assert incident.confirmed is True
    assert incident.notified is True