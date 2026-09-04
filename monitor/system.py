import psutil
import json
from psutil._common import bytes2human
import subprocess

cpu_therm = 'k10temp'

def cpu_check():
    data = psutil.sensors_temperatures()
    cpu_temp = data[cpu_therm][0].current
    cpu_load = psutil.cpu_percent()
    cpu_avg_load = psutil.getloadavg()
    return {
        "temperature": cpu_temp,
        "load": cpu_load, 
        "load_average": cpu_avg_load
    }

def ram_check():
    ram = psutil.virtual_memory()
    print('Total ram', bytes2human(ram.total))
    print('Available ram', bytes2human(ram.available))
    print('Ram usage:', ram.percent, "%")
    return {
        "total": ram.total,
        "available": ram.available,
        "usage": ram.percent
    }

def disk_check():

    disks = psutil.disk_partitions()

    disk_dict = {}

    for device in disks:

        disk = device.device[:-1]

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
        })

    for disk in disk_dict:
        temperature = get_disk_temp(disk)
        disk_dict[disk]['temperature'] = temperature

    for disk, info in disk_dict.items():
        print("Disk:", disk)
        print("Temperature:", info["temperature"])

        for partition in info["partitions"]:
            print("\nPartition:", partition["partition"])
            print("Mountpoint:", partition["mountpoint"])
            print("Total:", bytes2human(partition["total"]))
            print("Used:", bytes2human(partition["used"]))

        print()

    return disk_dict


def get_disk_temp(drive_path):
    result = subprocess.run(
        ['sudo', 'smartctl', '-A', '-j', drive_path],
        capture_output=True,
        text=True)

    disk_data = json.loads(result.stdout)
    temperature = disk_data["temperature"]['current']
    return temperature