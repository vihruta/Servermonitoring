import psutil
import json
import subprocess
import time
import logging
import asyncio
logger = logging.getLogger(__name__)


from models import (CpuMetrics, LoadAverage, 
                    MemoryMetrics, RamMetrics, 
                    SwapMetrics, DiskMetrics, 
                    PartitionMetrics, SystemStatus)

from monitor.docker_monitor import get_containers_health
from config import Settings

cpu_therm = 'k10temp'

def get_status(settings: Settings) -> SystemStatus:
    return SystemStatus(
        uptime=get_uptime(),
        cpu=cpu_check(),
        memory=ram_check(),
        disks= disk_check(
            lsblk_timeout=settings.timeouts.lsblk,
            smartctl_timeout=settings.timeouts.smartctl
        ),
        docker_containers=get_containers_health(
            docker_timeout=settings.timeouts.docker
        )
    )

def cpu_check() -> CpuMetrics | None:
    try:
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
    except Exception:
        logger.exception('CPU check error')
        return None

    
def ram_check() -> MemoryMetrics | None:
    try:
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
    except Exception:
        logger.exception('RAM check error')
        return None

def disk_check(
        lsblk_timeout: float,
        smartctl_timeout: float
        ) -> dict[str, DiskMetrics] | None:
    
    try:
        disks = psutil.disk_partitions()

        disk_dict: dict[str, DiskMetrics] = {}

        for device in disks:

            disk = get_parent_block(
                device.device,
                lsblk_timeout=lsblk_timeout
                )

            if disk is None:
                continue

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
            disk_data.temperature = get_disk_temp(
                drive_path=disk,
                smartctl_timeout = smartctl_timeout
            )

        return disk_dict
    except Exception:
        logger.exception('Disk check error')
        return None


def get_disk_temp(
        drive_path: str,
        smartctl_timeout: float) -> float | None:
    try:
        result = subprocess.run(
            ['sudo', 'smartctl', '-A', '-j', drive_path],
            capture_output=True,
            text=True, timeout=smartctl_timeout)
        disk_data = json.loads(result.stdout)
        temperature = disk_data["temperature"]['current']
    except subprocess.TimeoutExpired as exception:
        logger.exception('Smartctl timeout %s', exception)
        temperature = None
    except Exception as exception:
        temperature = None
        logger.exception('Smartctl error %s', exception)
    return temperature

def get_parent_block(drive_path: str, lsblk_timeout: float) -> str | None:
    try:
        result = subprocess.run(
            ['lsblk', '-no', 'pkname', str(drive_path)],
            capture_output=True,
            text=True, timeout=lsblk_timeout
        )
        result.check_returncode()

        parent = result.stdout.strip()

        if not parent:
            return None
    
        disk = "/dev/" + parent
        return disk
    
    except subprocess.TimeoutExpired as exception:
        logger.exception('Timeout while get parent block from %s,%s | %s',
                         drive_path,
                         exception,
                         exception.stderr
                         )
        return None
    except subprocess.CalledProcessError as exception:
        logger.exception('lsblk error with disk %s| %s | %s',
                         drive_path,
                         exception,
                         exception.stderr)
        return None
    except FileNotFoundError:
        logger.exception('No lsblk in system')
        return None
    
def get_uptime():
    try:
        boot_time = psutil.boot_time()
        uptime_sec = time.time() - boot_time
        return uptime_sec
    except Exception:
        logger.exception('Get uptime error')
        return None
