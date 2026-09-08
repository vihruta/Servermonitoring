import psutil
import json
import subprocess
import time
from models import CpuMetrics, LoadAverage, MemoryMetrics, RamMetrics, SwapMetrics, DiskMetrics, PartitionMetrics, SystemStatus
from monitor.docker_monitor import get_containers_health

cpu_therm = 'k10temp'

def get_status() -> SystemStatus:
    return SystemStatus(
        uptime=get_uptime(),
        cpu=cpu_check(),
        memory=ram_check(),
        disks=disk_check(),
        docker_containers=get_containers_health()
    )

def cpu_check() -> CpuMetrics:
    data = psutil.sensors_temperatures()
    cpu_temp = data[cpu_therm][0].current
    cpu_load = psutil.cpu_percent()
    load_1, load_5, load_15 = psutil.getloadavg()
    return CpuMetrics(
        temperature=cpu_temp,
        usage_percent=cpu_load,
        load_average=LoadAverage(
            min_1=load_1,
            min_5=load_5,
            min_15=load_15
        )
    )

def ram_check() -> MemoryMetrics:
    ram = psutil.virtual_memory()
    ram_swap = psutil.swap_memory()
    return MemoryMetrics(
        ram=RamMetrics(
            total=ram.total,
            available=ram.available,
            usage=ram.percent
        ),
        swap=SwapMetrics(
            total=ram_swap.total,
            used=ram_swap.used,
            free=ram_swap.free,
            usage=ram_swap.percent
        )
    )

def disk_check() -> dict[str, DiskMetrics]:

    disks = psutil.disk_partitions()

    disk_dict: dict[str, DiskMetrics] = {}

    for device in disks:

        disk = get_parent_block(device.device)

        if disk not in disk_dict:
            disk_dict[disk] = DiskMetrics(
                temperature=None,
                partitions=[]
            )

        memory_info = psutil.disk_usage(device.mountpoint)
        partition = PartitionMetrics(
            partition=device.device,
            mountpoint=device.mountpoint,
            total=memory_info.total,
            used=memory_info.used,
            free=memory_info.free,
            usage_percent=memory_info.percent
        )
        disk_dict[disk].partitions.append(partition)

    for disk, disk_data in disk_dict.items():
        disk_data.temperature = get_disk_temp(disk)

    return disk_dict


def get_disk_temp(drive_path: str) -> float | None:
    result = subprocess.run(
        ['sudo', 'smartctl', '-A', '-j', drive_path],
        capture_output=True,
        text=True)
    try:
        disk_data = json.loads(result.stdout)
        temperature = disk_data["temperature"]['current']
    except Exception:
        temperature = None
    return temperature

def get_parent_block(drive_path: str) -> str:
    result = subprocess.run(
        ['lsblk', '-no', 'pkname', str(drive_path)],
        capture_output=True,
        text=True
    )
    disk = "/dev/" + str(result.stdout.strip())
    return disk

def get_uptime():
    boot_time = psutil.boot_time()
    uptime_sec = time.time() - boot_time
    return uptime_sec
