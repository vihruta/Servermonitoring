import pytest
import asyncio

from models import (CpuMetrics, LoadAverage, 
                    RamMetrics, MemoryMetrics,
                    SwapMetrics, DiskMetrics,
                    PartitionMetrics)
import alerts.monitor as monitor
from alerts.models import Thresholds
from alerts.state_store import StateStore, IncidentStore
from alerts.states import State, Alert


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
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75
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
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75
    )

    await monitor.monitoring_cpu(
        store=store,
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
        bot,
        chat_id,
        ):
        calls['monitoring_metrics'] += 1
        metrics.append((metric_name, value, unit))
        
    monkeypatch.setattr(monitor,'cpu_check', fake_cpu_check)
    monkeypatch.setattr(monitor, 'monitoring_metrics', fake_monitoring_metrics)


    store = StateStore()
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75
    )

    await monitor.monitoring_cpu(
        store=store,
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
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75
    )

    await monitor.monitoring_ram_usage(
        store=store, 
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
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75
    )

    await monitor.monitoring_ram_usage(
        store=store,
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

    def fake_disk_check():
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
    thresholds = {
        'temperature': Thresholds(
            warning=85,
            critical=95,
            recovery=75
            ),
        'usage': Thresholds(
            warning=85,
            critical=95,
            recovery=75
        )
    }


    await monitor.monitoring_disk(
        store=store,
        bot=None,
        chat_id=123,
        temperature_threshold=thresholds['temperature'],
        usage_threshold=thresholds['usage']
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

    def fake_disk_check():
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
    thresholds = {
        'temperature': Thresholds(
            warning=85,
            critical=95,
            recovery=75
            ),
        'usage': Thresholds(
            warning=85,
            critical=95,
            recovery=75
        )
    }


    await monitor.monitoring_disk(
        store=store,
        bot=None,
        chat_id=123,
        temperature_threshold=thresholds['temperature'],
        usage_threshold=thresholds['usage']
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

    def fake_disk_check():
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
    thresholds = {
        'temperature': Thresholds(
            warning=85,
            critical=95,
            recovery=75
            ),
        'usage': Thresholds(
            warning=85,
            critical=95,
            recovery=75
        )
    }


    await monitor.monitoring_disk(
        store=store,
        bot=None,
        chat_id=123,
        temperature_threshold=thresholds['temperature'],
        usage_threshold=thresholds['usage']
    )

    assert calls['disk_check'] == 1
    assert calls['monitoring_metrics'] == 1

    assert ('disk_temperature_sdb', 52, '°C') in metrics
    assert('partition_usage_sdb1', 52, '%') not in metrics
    assert len(metrics) == 1


@pytest.mark.asyncio
async def test_monitoring_disks_unavailable(monkeypatch):
    metrics = []

    def fake_disk_check():
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
    thresholds = {
        'temperature': Thresholds(
            warning=85,
            critical=95,
            recovery=75
            ),
        'usage': Thresholds(
            warning=85,
            critical=95,
            recovery=75
        )
    }


    await monitor.monitoring_disk(
        store=store,
        bot=None,
        chat_id=123,
        temperature_threshold=thresholds['temperature'],
        usage_threshold=thresholds['usage']
    )

    assert metrics == []


@pytest.mark.asyncio
async def test_docker_monitoring_container_unavailable(monkeypatch):
    sent_alerts = []

    def fake_get_conatiners_health():
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

    await monitor.monitoring_containers(
        store=store,
        incident=incident,
        bot=None,
        chat_id=123,
        monitored_containers=monitored_containers
    )

    assert sent_alerts == []

@pytest.mark.asyncio
async def test_docker_monitoring_container_is_missing(monkeypatch):
    sent_alerts = []

    def fake_get_conatiners_health():
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

    await monitor.monitoring_containers(
        store=store,
        incident=incident,
        bot=None,
        chat_id=123,
        monitored_containers=monitored_containers
    )

    assert sent_alerts[0]['abc'].status.alert == Alert.CRITICAL

@pytest.mark.asyncio
async def test_docker_container_get_no_info(monkeypatch):
    sent_alerts = []

    def fake_get_conatiners_health():
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

    await monitor.monitoring_containers(
        store=store,
        incident=incident,
        bot=None,
        chat_id=123,
        monitored_containers=monitored_containers
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

    container_statuses = [
        "running",
        "exited",
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