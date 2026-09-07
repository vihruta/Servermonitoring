line_divider = '__________________________________\n'

def format_bytes(size_bytes):
    return round(size_bytes/1073741824, 2)

def format_cpu(cpu_data) -> str:
    load_1, load_5, load_15 = cpu_data["load_average"]
    msg = (f'CPU\nТемпература процессора: {cpu_data["temperature"]}℃\n'
    f'Загрузка процессора: {cpu_data['load']}\n'
    f'Загрузка процессора за 1,5,15 мин: {load_1:.2f} / {load_5:.2f} / {load_15:.2f}\n')
    return msg

def format_ram(ram_data) -> str:
    msg = (f'RAM\nВсего памяти {format_bytes(ram_data["total"])} GB\n'
           f'Доступно памяти {format_bytes(ram_data["available"])} GB\n'
           f'Занято - {ram_data["usage"]}%\n'
           f'SWAP\nSwap всего: {format_bytes(ram_data['swap_total'])} GB\n'
           f'Swap использовано: {format_bytes(ram_data['swap_used'])} GB | {format_bytes(ram_data['swap_usage'])} %\n'
           f'Swap свободно: {format_bytes(ram_data['swap_free'])} GB\n')
    return msg

def format_disk(disk_data) -> str:
    msg = 'DISKS\n'
    for disk, info in disk_data.items():
        msg += f'Диск: {disk}\nТемпература: {info["temperature"]} ℃\n'
        for partition in info['partitions']:
            msg += (f'Partition: {partition["partition"]}\n'
                    f'Точка монтирования: {partition['mountpoint']}\n'
                    f'Всего памяти: {format_bytes(partition['total'])} GB\n'
                    f'Использовано: {format_bytes(partition['used'])} GB | {round(partition['usage_percent'], 2)} %\n'
                    f'Свободно: {format_bytes(partition['free'])} GB| {round(100 - partition['usage_percent'],2)} %\n\n')
        msg += '\n'
    return msg

def format_status(status_data) -> str:
    msg = ''
    uptime = format_time(status_data["uptime"])
    msg += (f'Аптайм системы: \n{uptime["days"]} дней {uptime["hours"]} часов '
           f'{uptime["minutes"]} минут {uptime['seconds']} секунд\n')
    msg += line_divider
    msg += format_cpu(status_data['cpu'])
    msg += line_divider
    msg += format_ram(status_data['ram'])
    msg += line_divider
    msg += format_disk(status_data['disks'])
    return msg

def format_time(uptime):
    hours, remaider = divmod(int(uptime), 3600)
    minutes, seconds = divmod(remaider, 60)
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