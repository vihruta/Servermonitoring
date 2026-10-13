import pytest

from models import (CpuMetrics, MemoryMetrics,
                    DiskMetrics, SystemStatus,
                    DockerContainerMetrics, LoadAverage,
                    RamMetrics, SwapMetrics,
                    PartitionMetrics)

from telegram.formatter import format_status, format_docker_data

@pytest.fixture
def full_status() -> SystemStatus:
    return SystemStatus(
        uptime=90061,
        cpu=CpuMetrics(
            temperature=55,
            usage_percent=21,
            load_average=LoadAverage(
                min_1=0.5,
                min_5=0.7,
                min_15=1.0,
            ),
        ),
        memory=MemoryMetrics(
            ram=RamMetrics(
                total=16_000_000_000,
                available=8_000_000_000,
                usage=50,
            ),
            swap=SwapMetrics(
                total=4_000_000_000,
                used=1_000_000_000,
                free=3_000_000_000,
                usage=25,
            ),
        ),
        disks={
            "/dev/sda": DiskMetrics(
                temperature=42,
                partitions=[
                    PartitionMetrics(
                        partition="/dev/sda1",
                        mountpoint="/",
                        total=1_000_000_000,
                        used=400_000_000,
                        free=600_000_000,
                        usage_percent=40,
                    )
                ],
            )
        },
        docker_containers={
            "vaultwarden": DockerContainerMetrics(
                status="running",
                oom_killed=False,
                exit_code=0,
                error=None,
                health="healthy",
            )
        },
    )


@pytest.mark.parametrize(
    "field, error_text, available_text",
    [
        ("uptime", "аптайма", "CPU"),
        ("cpu", "процессора", "RAM"),
        ("memory", "озу", "CPU"),
        ("disks", "разделах", "RAM"),
        ("docker_containers", "контейнеров", "CPU"),
    ],
)

def test_format_status_with_unavailable_section(
    full_status,
    app_settings,
    field,
    error_text,
    available_text
):
    partial_status = full_status.model_copy(
        update={field: None}
    )

    message = format_status(partial_status, app_settings)

    assert isinstance(message, str)
    assert error_text in message.lower()
    assert available_text in message

def test_format_docker():
    container_name_none = 'vaultwarden'
    container_name_good = 'immich'
    error_str = f'Контейнер: {container_name_none}\nПри получении информации о контейнере возникла ошибка'
    containers = {
        container_name_none: None,
        container_name_good :
            DockerContainerMetrics(
                status='abc',
                oom_killed=False,
                exit_code=0,
                error=None,
                health=None
            )
    }

    message = format_docker_data(docker_data=containers)

    assert isinstance(message, str)
    assert error_str in message
    assert container_name_good in message

def test_status_shows_full_partitions_and_short_smart(full_status, app_settings):
    from datetime import datetime, timezone
    from models import SmartMetrics, SmartMetricsSnapShot

    full_status.smart = {
        '/dev/nvme0n1': SmartMetricsSnapShot(
            metrics=SmartMetrics(critical_warning=0, available_spare=100,
                                 percent_used=2, media_errors=7, num_err_log_entries=9),
            checked_at=datetime(2026, 10, 13, tzinfo=timezone.utc),
        )
    }
    message = format_status(full_status, app_settings)
    assert '/dev/sda1' in message
    assert 'Точка монтирования: /' in message
    assert '/dev/nvme0n1' in message
    assert 'износ: 2%' in message
    assert 'Ошибки целостности данных' not in message


def test_http_summary_excludes_internet_and_counts_missing_services(app_settings):
    from datetime import datetime, timezone
    from config import HttpServiceSettings
    from alerts.state_store import HttpSnapshotStore
    from models import HttpMetrics
    from telegram.formatter import format_service_data_short, format_service_data

    app_settings.http_services.monitored = {
        name: HttpServiceSettings(url=f'https://{name}.example.com', expected_status={200})
        for name in ('good', 'bad', 'missing')
    }
    snapshots = HttpSnapshotStore()
    for name, failed in (('good', False), ('bad', True), ('Internet', False)):
        snapshots.update(name, HttpMetrics(service=name, result_code=503 if failed else 200,
                                          is_failed=failed, error='Unexpected HTTP status' if failed else None,
                                          duration_seconds=0.1), datetime.now(timezone.utc))
    message = format_service_data_short(snapshots.snapshots, app_settings)
    assert '1 из 3' in message
    assert 'Без данных: 1' in message
    full = format_service_data(snapshots.snapshots, app_settings)
    assert 'missing\nДанных пока нет' in full
    assert 'Internet' not in full


def test_docker_format_includes_error_reason():
    data = DockerContainerMetrics(status='unknown', oom_killed=None,
                                  exit_code=None, health=None, error='Docker unavailable')
    assert 'Docker unavailable' in format_docker_data({'app': data})
