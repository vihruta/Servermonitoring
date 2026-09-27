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
        ("disks", "дисков", "RAM"),
        ("docker_containers", "контейнеров", "CPU"),
    ],
)

def test_format_status_with_unavailable_section(
    full_status,
    field,
    error_text,
    available_text
):
    partial_status = full_status.model_copy(
        update={field: None}
    )

    message = format_status(partial_status)

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