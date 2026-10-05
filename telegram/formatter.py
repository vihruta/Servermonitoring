from models import CpuMetrics, MemoryMetrics, DiskMetrics, SystemStatus, DockerContainerMetrics
from alerts.models import MetricStatus, NumericAlertData, ContainerAlertData, HttpAlertData
from alerts.states import Alert



line_divider = '__________________________________\n'

def bytes_to_gb(size_bytes):
    return round(size_bytes/1073741824, 2)

def format_cpu(cpu_data: CpuMetrics | None) -> str:
    if cpu_data is not None:
        msg = (f'CPU\nТемпература процессора: {cpu_data.temperature}℃\n'
        f'Загрузка процессора: {cpu_data.usage_percent}%\n'
        f'Загрузка процессора за 1мин: {cpu_data.load_average.min_1:.2f} \n'
        f'Загрузка процессора за 5мин: {cpu_data.load_average.min_5:.2f} \n'
        f'Загрузка процессора за 15мин: {cpu_data.load_average.min_15:.2f} \n')
    else:
        msg = 'При попытке получения состояния процессора возникла ошибка\n'
    
    return msg

def format_ram(ram_data: MemoryMetrics | None) -> str:
    if ram_data is not None:
        msg = (f'RAM\nВсего памяти {bytes_to_gb(ram_data.ram.total)} GB\n'
            f'Доступно памяти {bytes_to_gb(ram_data.ram.available)} GB\n'
            f'Используется - {ram_data.ram.usage}%\n'
            f'SWAP\nSwap всего: {bytes_to_gb(ram_data.swap.total)} GB\n'
            f'Swap использовано: {bytes_to_gb(ram_data.swap.used)} GB | {ram_data.swap.usage} %\n'
            f'Swap свободно: {bytes_to_gb(ram_data.swap.free)} GB\n')
    else:
        msg = 'При попытке получения состояния ОЗУ возникла ошибка\n'
    return msg

def format_disk(disk_data: dict[str, DiskMetrics] | None) -> str:
    if disk_data is not None:
        msg = 'DISKS\n'
        for disk, info in disk_data.items():
            msg += f'Диск: {disk}\nТемпература: {info.temperature} ℃\n'
            for partition in info.partitions:
                msg += (f'Partition: {partition.partition}\n'
                        f'Точка монтирования: {partition.mountpoint}\n'
                        f'Всего памяти: {bytes_to_gb(partition.total)} GB\n'
                        f'Использовано: {bytes_to_gb(partition.used)} GB | {round(partition.usage_percent, 2)} %\n'
                        f'Свободно: {bytes_to_gb(partition.free)} GB | {round(100 - partition.usage_percent,2)} %\n\n')
            msg += '\n'
    else:
        msg = 'При попытке получения состояния дисков возникла ошибка'
    return msg

def format_status(status_data: SystemStatus) -> str:
    msg = ''
    if status_data.uptime is not None:
        uptime = format_time(status_data.uptime)
        msg += (f'Аптайм системы: \n{uptime["days"]} дней {uptime["hours"]} часов '
            f'{uptime["minutes"]} минут {uptime['seconds']} секунд\n')
    else:
        msg += 'При получении аптайма возникла ошибка'
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

def format_temp(status_data: SystemStatus):
    msg = ''
    if status_data.cpu is not None:
        msg += f'CPU: {status_data.cpu.temperature}℃\n\nDISKS:\n'
    else:
        msg += 'При получении температуры ЦП возникла ошибка\n'
    if status_data.disks is not None:
        for disk, info in status_data.disks.items():
            msg += f'Диск {disk} - {info.temperature}℃\n'
    else:
        msg += 'При получении температуры дисков возникла ошибка\n'
    return msg

def format_docker_data(docker_data: dict[str, DockerContainerMetrics | None] | None):
    msg = 'DOCKER\n'
    if docker_data is not None:
        for name, info in docker_data.items():
            msg += (f'Контейнер: {name}\n')
            if info is not None:
                msg += (f'Статус: {info.status}\n'
                        f'Health: {info.health}\n'
                        f'OOM killed: {info.oom_killed}\n'
                        f'Exit code: {info.exit_code}\n')
                
                if info.error is not None:
                    msg += f'Ошибка: {info.error}\n'
                msg += '\n'
                
            else:
                msg += 'При получении информации о контейнере возникла ошибка\n'
    else:
        msg += 'При получении данных контейнеров возникла ошибка\n'
    return msg 


def format_numeric_alert(
        data: dict[str, NumericAlertData]
        ) -> str:
    msg = 'ALERT\n'

    for device, alert_data in data.items():
        msg += (f'{device}\n'
                f'Alert: {alert_data.status.alert.name}\n'
                f'Значение: {alert_data.value} {alert_data.unit}')
    return msg


def format_container_alert(
        data: dict[str, ContainerAlertData]
) -> str:
    msg = 'ALERT\n'

    for container, alert_data in data.items():
        msg += (f'{container}\n'
                f'Alert: {alert_data.status.alert.name}\n'
                f'Статус: {alert_data.container_status}\n')
        if alert_data.container_health is not None:
            msg += f'Health: {alert_data.container_health}\n'
        if alert_data.downtime is not None:
            msg+= 'Инцидент продлился: '
            msg += format_duration(seconds=alert_data.downtime)

    return msg

def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    msg = ''

    if hours:
        msg += f'{hours} часов '
    if minutes:
        msg += f'{minutes} минут '
    msg += f'{seconds} секунд'

    return msg

def format_http_alert(
        data: dict[str, HttpAlertData]) -> str:
    msg = 'ALERT\n'

    for service, alert_data in data.items():
        msg += (f'{service}\n'
                f'Alert: {alert_data.status.alert.name}\n')
        if alert_data.result_code is not None:
            msg += f'Status code: {alert_data.result_code}\n'
        if alert_data.error is not None:
            msg += f'Error: {alert_data.error}\n'
        if alert_data.duration is not None:
            msg += f'Duration: {alert_data.duration:.1f} sec\n'

    return msg

def format_network_alert(
        data: dict[str, HttpAlertData],
        problem_was_notified: bool
) -> str:
    msg = 'ALERT\n'

    for  alert_data in data.values():
        if alert_data.status.alert == Alert.RECOVERED:
            if problem_was_notified:
                msg += 'Доступ к проверочному адресу восстановлен\n'
            else:
                msg += (
                    'Зафиксирован сбой доступности проверочного адреса.\n'
                    'К моменту отправки сообщения доступ уже восстановлен.\n'
                )
        else:
            msg += 'Проверочный адрес недоступен\n'
        if alert_data.duration is not None:
            label = (
                'Длительность сбоя'
                if alert_data.status.alert == Alert.RECOVERED
                else 'Сбой продолжается'
            )
            msg += f'{label}: {alert_data.duration:.1f} сек\n'

        msg += f'Alert: {alert_data.status.alert.name}\n'

    return msg