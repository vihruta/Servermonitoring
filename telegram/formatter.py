from models import CpuMetrics, MemoryMetrics, DiskMetrics, SystemStatus, DockerContainerMetrics
from alerts.models import MetricStatus


line_divider = '__________________________________\n'

def bytes_to_gb(size_bytes):
    return round(size_bytes/1073741824, 2)

def format_cpu(cpu_data: CpuMetrics) -> str:
    msg = (f'CPU\nТемпература процессора: {cpu_data.temperature}℃\n'
    f'Загрузка процессора: {cpu_data.usage_percent}%\n'
    f'Загрузка процессора за 1мин: {cpu_data.load_average.min_1:.2f} \n'
    f'Загрузка процессора за 5мин: {cpu_data.load_average.min_5:.2f} \n'
    f'Загрузка процессора за 15мин: {cpu_data.load_average.min_15:.2f} \n')
    
    return msg

def format_ram(ram_data: MemoryMetrics) -> str:
    msg = (f'RAM\nВсего памяти {bytes_to_gb(ram_data.ram.total)} GB\n'
           f'Доступно памяти {bytes_to_gb(ram_data.ram.available)} GB\n'
           f'Используется - {ram_data.ram.usage}%\n'
           f'SWAP\nSwap всего: {bytes_to_gb(ram_data.swap.total)} GB\n'
           f'Swap использовано: {bytes_to_gb(ram_data.swap.used)} GB | {ram_data.swap.usage} %\n'
           f'Swap свободно: {bytes_to_gb(ram_data.swap.free)} GB\n')
    return msg

def format_disk(disk_data: dict[str, DiskMetrics]) -> str:
    msg = 'DISKS\n'
    for disk, info in disk_data.items():
        msg += f'Диск: {disk}\nТемпература: {info.temperature} ℃\n'
        for partition in info.partitions:
            msg += (f'Partition: {partition.partition}\n'
                    f'Точка монтирования: {partition.mountpoint}\n'
                    f'Всего памяти: {bytes_to_gb(partition.total)} GB\n'
                    f'Использовано: {bytes_to_gb(partition.used)} GB | {round(partition.usage_percent, 2)} %\n'
                    f'Свободно: {bytes_to_gb(partition.free)} GB| {round(100 - partition.usage_percent,2)} %\n\n')
        msg += '\n'
    return msg

def format_status(status_data: SystemStatus) -> str:
    msg = ''
    uptime = format_time(status_data.uptime)
    msg += (f'Аптайм системы: \n{uptime["days"]} дней {uptime["hours"]} часов '
           f'{uptime["minutes"]} минут {uptime['seconds']} секунд\n')
    msg += line_divider
    msg += format_cpu(status_data.cpu)
    msg += line_divider
    msg += format_ram(status_data.memory)
    msg += line_divider
    msg += format_disk(status_data.disks)
    msg += line_divider
    msg += format_docker_data(status_data.docker_containers)
    return msg

def format_time(uptime):
    hours, remainder = divmod(int(uptime), 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)
    return {
        "days" : days,
        "hours" : hours,
        "minutes" : minutes,
        "seconds" : seconds
    }

def format_temp(status_data):
    msg = ''
    msg += f'CPU: {status_data['cpu']['temperature']}℃\n\nDISKS:\n'
    for disk, info in status_data['disks'].items():
        msg += f'Диск {disk} - {info['temperature']}℃\n'
    return msg

def format_docker_data(docker_data: dict[str, DockerContainerMetrics]):
    msg = 'DOCKER\n'
    for name, info in docker_data.items():
        msg += (f'Контейнер: {name}\n'
                f'Статус: {info.status}\n'
                f'Health: {info.health}\n'
                f'OOM killed: {info.oom_killed}\n'
                f'Exit code: {info.exit_code}\n')

        if info.error:
            msg += f'Ошибка: {info.error}\n'
        msg += '\n'
    return msg 

def format_alert(
        data: dict[str, tuple[MetricStatus, float]]
        ) -> str:
    msg = 'ALERT\n'
    for device, (status, temperature) in data.items():
        msg += (f'{device}\n'
                f'Alert: {status.alert.name}\n'
                f'Температура: {temperature}')
    return msg

    