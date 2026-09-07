import psutil
import json
import subprocess
import time
from docker_monitor import get_containers_health

cpu_therm = 'k10temp'

def get_status() -> dict:
    cpu_data = cpu_check()
    ram_data = ram_check()
    disk_data = disk_check()
    uptime = get_uptime()
    docker = get_containers_health()
    return {
        "cpu": cpu_data,
        "ram": ram_data,
        "disks": disk_data,
        "uptime": uptime,
        "docker": docker
    }

def cpu_check() -> dict:
    data = psutil.sensors_temperatures()
    cpu_temp = data[cpu_therm][0].current
    cpu_load = psutil.cpu_percent()
    cpu_avg_load = psutil.getloadavg()
    return {
        "temperature": cpu_temp,
        "load": cpu_load, 
        "load_average": cpu_avg_load
    }

def ram_check() -> dict:
    ram = psutil.virtual_memory()
    ram_swap = psutil.swap_memory()
    return {
        "total": ram.total,
        "available": ram.available,
        "usage": ram.percent,
        "swap_total": ram_swap.total,
        "swap_used": ram_swap.used,
        "swap_free": ram_swap.free,
        "swap_usage": ram_swap.percent
    }

def disk_check() -> dict:

    disks = psutil.disk_partitions()

    disk_dict = {}

    for device in disks:

        disk = get_parent_block(device.device)

        disk_dict.setdefault(disk, {
            "temperature": None,
            "partitions": []
        })

        memory_info = psutil.disk_usage(device.mountpoint)
        disk_dict[disk]["partitions"].append({
            "partition": device.device,
            "mountpoint": device.mountpoint,
            "total": memory_info.total,
            "used": memory_info.used,
            "free": memory_info.free,
            "usage_percent": memory_info.percent
        })

    for disk in disk_dict:
        temperature = get_disk_temp(disk)
        disk_dict[disk]['temperature'] = temperature

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
