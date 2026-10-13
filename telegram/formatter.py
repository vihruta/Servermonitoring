from models import (CpuMetrics, MemoryMetrics, 
                    DiskMetrics, SystemStatus, 
                    DockerContainerMetrics, SmartMetricsSnapShot,
                    HttpServiceSnapShot)

from alerts.models import (NumericAlertData, ContainerAlertData, 
                           HttpAlertData, SmartAlertData)

from alerts.states import Alert, SmartAlertReason

from config import Settings


line_divider = '\n\n──────────────────\n\n'


def _alert_label(alert: Alert) -> str:
    labels = {
        Alert.NO_ALERT: 'без уведомления',
        Alert.WARNING: 'предупреждение',
        Alert.CRITICAL: 'критическое событие',
        Alert.RECOVERED: 'восстановление',
    }
    return labels[alert]

def bytes_to_gb(size_bytes):
    return round(size_bytes/1073741824, 2)

def format_help() -> str:
    return (
        '📋 Доступные команды\n\n'
        '/status — сводка состояния сервера\n'
        '/cpu — загрузка и температура процессора\n'
        '/ram — использование оперативной памяти и swap\n'
        '/disk — разделы, свободное место и SMART\n'
        '/temp — температуры\n'
        '/docker — состояние контейнеров\n'
        '/services — результаты HTTP-проверок сервисов\n'
        '/network — проверка доступности интернет-адреса\n'
        '/help — список команд'
    )

def format_cpu(cpu_data: CpuMetrics | None) -> str:
    if cpu_data is None:
        return '🖥 Процессор · CPU\n\nНе удалось получить данные процессора.'

    temperature = (
        f'{cpu_data.temperature:.1f} °C'
        if cpu_data.temperature is not None else 'недоступна'
    )
    return (
        '🖥 Процессор · CPU\n\n'
        f'Температура: {temperature}\n'
        f'Загрузка: {cpu_data.usage_percent:.1f}%\n\n'
        'Средняя нагрузка (load average)\n'
        f'1 мин: {cpu_data.load_average.min_1:.2f}\n'
        f'5 мин: {cpu_data.load_average.min_5:.2f}\n'
        f'15 мин: {cpu_data.load_average.min_15:.2f}'
    )

def format_ram(ram_data: MemoryMetrics | None) -> str:
    if ram_data is None:
        return '🧠 Память · RAM\n\nНе удалось получить данные ОЗУ.'

    return (
        '🧠 Память · RAM\n\n'
        f'Всего: {bytes_to_gb(ram_data.ram.total):.2f} GiB\n'
        f'Доступно: {bytes_to_gb(ram_data.ram.available):.2f} GiB\n'
        f'Использовано: {ram_data.ram.usage:.1f}%\n\n'
        'SWAP\n'
        f'Всего: {bytes_to_gb(ram_data.swap.total):.2f} GiB\n'
        f'Использовано: {bytes_to_gb(ram_data.swap.used):.2f} GiB'
        f' · {ram_data.swap.usage:.1f}%\n'
        f'Свободно: {bytes_to_gb(ram_data.swap.free):.2f} GiB'
    )



def format_disk(
    disk_data: dict[str, DiskMetrics] | None,
) -> str:
    sections = ['💾 Диски']

    if disk_data is None:
        sections.append('Не удалось получить информацию о разделах.')
    elif not disk_data:
        sections.append('Смонтированные разделы не найдены.')
    else:
        for disk, info in disk_data.items():
            lines = [f'Диск: {disk}']

            if info.temperature is None:
                lines.append('Температура: недоступна')
            else:
                lines.append(f'Температура: {info.temperature:.1f} °C')

            for partition in info.partitions:
                lines.append(
                    f'\nРаздел: {partition.partition}\n'
                    f'Точка монтирования: {partition.mountpoint}\n'
                    f'Всего: {bytes_to_gb(partition.total):.2f} GiB\n'
                    f'Использовано: {bytes_to_gb(partition.used):.2f} GiB'
                    f' | {partition.usage_percent:.1f}%\n'
                    f'Свободно: {bytes_to_gb(partition.free):.2f} GiB'
                )

            sections.append('\n'.join(lines))

    return '\n\n'.join(sections)

def format_smart(
    smart_data: dict[str, SmartMetricsSnapShot] | None,
    short: bool = False,
) -> str:
    sections = ['🔎 SMART']

    if not smart_data:
        sections.append('Данных SMART пока нет.')
        return '\n\n'.join(sections)

    for disk, snapshot in smart_data.items():
        metrics = snapshot.metrics

        if metrics is None:
            lines = [
                f'Устройство: {disk}',
                'Последняя проверка SMART не удалась.',
            ]
        elif short:
            lines = [
                f'{disk} — флаги: 0x{metrics.critical_warning:02X}, '
                f'резерв: {metrics.available_spare:g}%, '
                f'износ: {metrics.percent_used:g}%'
            ]
        else:
            lines = [f'Устройство: {disk}']

            if metrics.critical_warning == 0:
                lines.append('Предупреждения контроллера: нет')
            else:
                lines.append(
                    'Флаги предупреждений контроллера: '
                    f'0x{metrics.critical_warning:02X}'
                )

            lines.extend([
                f'Доступный резерв: {metrics.available_spare:g}%',
                f'Израсходованный ресурс: {metrics.percent_used:g}%',
                f'Ошибки целостности данных: {metrics.media_errors}',
                f'Записи в журнале ошибок: {metrics.num_err_log_entries}',
            ])

        lines.append(
            f'Проверено: {snapshot.checked_at:%d.%m.%Y %H:%M:%S %Z}'
        )
        sections.append('\n'.join(lines))

    return '\n\n'.join(sections)

def format_status(status_data: SystemStatus, settings: Settings) -> str:
    if status_data.uptime is not None:
        uptime = format_time(status_data.uptime)
        overview = (
            '📊 Состояние сервера\n\n'
            f'Время работы: {uptime["days"]} д {uptime["hours"]} ч '
            f'{uptime["minutes"]} мин {uptime["seconds"]} с'
        )
    else:
        overview = '📊 Состояние сервера\n\nНе удалось получить данные аптайма.'

    network_data = None
    if status_data.http_services is not None:
        network_data = status_data.http_services.get('Internet')

    return line_divider.join([
        overview,
        format_cpu(status_data.cpu),
        format_ram(status_data.memory),
        format_disk(status_data.disks),
        format_smart(smart_data=status_data.smart, short=True),
        format_docker_data(status_data.docker_containers),
        format_service_data_short(status_data.http_services, settings),
        format_network_data(network_data),
    ])
    
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

def format_temp(status_data: SystemStatus) -> str:
    sections = ['🌡 Температуры']
    if status_data.cpu is not None:
        temperature = status_data.cpu.temperature
        sections.append(
            f'CPU: {temperature:.1f} °C'
            if temperature is not None else 'CPU: температура недоступна'
        )
    else:
        sections.append('Не удалось получить температуру процессора.')

    if status_data.disks is not None:
        lines = ['Диски']
        for disk, info in status_data.disks.items():
            temperature_text = (
                f'{(info.temperature):.1f} °C'
                if info.temperature is not None else 'температура недоступна'
            )
            lines.append(f'{disk}: {temperature_text}')
        sections.append('\n'.join(lines))
    else:
        sections.append('Не удалось получить температуры дисков.')
    return '\n\n'.join(sections)

def format_docker_data(
    docker_data: dict[str, DockerContainerMetrics | None] | None,
) -> str:
    sections = ['📦 Docker']
    if docker_data is not None:
        for name, info in docker_data.items():
            lines = [f'Контейнер: {name}']
            if info is not None:
                if info.oom_killed is None:
                    oom = 'нет данных'
                elif info.oom_killed:
                    oom = 'да'
                else:
                    oom = 'нет'
                lines.extend([
                    f'Статус: {info.status}',
                    f'Health: {info.health if info.health is not None else "нет данных"}',
                    f'Завершён из-за нехватки памяти (OOM): {oom}',
                    f'Код выхода: {info.exit_code if info.exit_code is not None else "нет данных"}',
                ])
                if info.error:
                    lines.append(f'Ошибка: {info.error}')
            else:
                lines.append('При получении информации о контейнере возникла ошибка')
            sections.append('\n'.join(lines))
    else:
        sections.append('Не удалось получить данные контейнеров.')
    return '\n\n'.join(sections)


def format_numeric_alert(data: dict[str, NumericAlertData]) -> str:
    sections = ['🔔 Показатели сервера']
    for device, alert_data in data.items():
        sections.append(
            f'{device}\n'
            f'Уведомление: {_alert_label(alert_data.status.alert)}\n'
            f'Значение: {alert_data.value:g} {alert_data.unit}'
        )
    return '\n\n'.join(sections)


def format_container_alert(data: dict[str, ContainerAlertData]) -> str:
    sections = ['🔔 Контейнеры']
    for container, alert_data in data.items():
        lines = [
            container,
            f'Уведомление: {_alert_label(alert_data.status.alert)}',
            f'Статус: {alert_data.container_status}',
        ]
        if alert_data.container_health is not None:
            lines.append(f'Health: {alert_data.container_health}')
        if alert_data.downtime is not None:
            lines.append(f'Длительность инцидента: {format_duration(alert_data.downtime)}')
        sections.append('\n'.join(lines))
    return '\n\n'.join(sections)

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

def format_http_alert(data: dict[str, HttpAlertData]) -> str:
    sections = ['🔔 HTTP-сервисы']
    for service, alert_data in data.items():
        lines = [service, f'Уведомление: {_alert_label(alert_data.status.alert)}']
        if alert_data.result_code is not None:
            lines.append(f'HTTP: {alert_data.result_code}')
        if alert_data.error is not None:
            lines.append(f'Причина: {alert_data.error}')
        if alert_data.duration is not None:
            lines.append(f'Длительность: {alert_data.duration:.1f} с')
        sections.append('\n'.join(lines))
    return '\n\n'.join(sections)

def format_network_alert(
        data: dict[str, HttpAlertData],
        problem_was_notified: bool
) -> str:
    msg = '🔔 Доступность сети\n\n'

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

        msg += f'Уведомление: {_alert_label(alert_data.status.alert)}\n\n'

    return msg


def format_smart_alert(data: dict[str, SmartAlertData]) -> str:
    messages = []

    for disk, alert_data in data.items():
        alert = alert_data.status.alert
        metrics = alert_data.metrics

        if alert == Alert.NO_ALERT:
            continue

        if alert == Alert.RECOVERED:
            lines = [
                '✅ SMART: восстановление',
                f'Устройство: {disk}',
                'Ранее выявленная проблема состояния больше не наблюдается.',
            ]
        else:
            title = (
                '🚨 SMART: критическое уведомление'
                if alert == Alert.CRITICAL
                else '⚠️ SMART: предупреждение'
            )
            lines = [title, f'Устройство: {disk}']

            for reason in alert_data.reasons:
                if reason == SmartAlertReason.CRITICAL_WARNING:
                    lines.append(
                        '• Предупреждение контроллера: '
                        f'0x{metrics.critical_warning:02X}'
                    )
                elif reason == SmartAlertReason.LOW_SPARE:
                    lines.append(
                        '• Мало резервной памяти: '
                        f'{metrics.available_spare:g}%'
                    )
                elif reason == SmartAlertReason.HIGH_WEAR:
                    lines.append(
                        '• Высокий износ: '
                        f'{metrics.percent_used:g}% расчётного ресурса'
                    )
                elif reason == SmartAlertReason.MEDIA_ERRORS_INCREASED:
                    lines.append(
                        '• Вырос счётчик ошибок целостности данных. '
                        f'Текущее значение: {metrics.media_errors}'
                    )
                elif reason == SmartAlertReason.ERROR_LOG_INCREASED:
                    lines.append(
                        '• Вырос счётчик записей в журнале ошибок. '
                        f'Текущее значение: {metrics.num_err_log_entries}'
                    )

        messages.append('\n'.join(lines))

    return '\n\n'.join(messages)

def format_service_data(
    http_data: dict[str, HttpServiceSnapShot],
    settings: Settings,
) -> str:
    messages = ['🌐 Сервисы']

    for service in settings.http_services.monitored:
        data = http_data.get(service)

        if data is None:
            messages.append(f'{service}\nДанных пока нет')
            continue

        lines = [service]

        if not data.metrics.is_failed:
            lines.append('Последняя проверка: успешна')
        else:
            lines.append('Последняя проверка: неуспешна')
            if data.metrics.error is not None:
                lines.append(f'Причина: {data.metrics.error}')

        if data.metrics.result_code is not None:
            lines.append(f'HTTP: {data.metrics.result_code}')

        lines.append(
            f'Длительность проверки: '
            f'{data.metrics.duration_seconds * 1000:.0f} мс'
        )
        lines.append(
            f'Проверено: {data.checked_at:%d.%m.%Y %H:%M:%S %Z}'
        )

        if data.last_success_at is not None:
            lines.append(
                f'Последний успех: '
                f'{data.last_success_at:%d.%m.%Y %H:%M:%S %Z}'
            )
        else:
            lines.append('Успешных проверок пока не было')

        messages.append('\n'.join(lines))

    return '\n\n'.join(messages)


def format_service_data_short(
    http_data: dict[str, HttpServiceSnapShot] | None,
    settings: Settings,
) -> str:
    total = len(settings.http_services.monitored)

    if total == 0:
        return '🌐 HTTP-сервисы\n\nСервисы не настроены'

    if http_data is None:
        return '🌐 HTTP-сервисы\n\nДанных пока нет'

    successful = 0
    no_data = 0

    for service in settings.http_services.monitored:
        data = http_data.get(service)

        if data is None:
            no_data += 1
        elif not data.metrics.is_failed:
            successful += 1

    msg = f'🌐 HTTP-сервисы\n\nУспешных проверок: {successful} из {total}'

    if no_data:
        msg += f'\nБез данных: {no_data}'

    return msg

def format_network_data(
    network_data: HttpServiceSnapShot | None,
) -> str:
    if network_data is None:
        return '🌐 Проверочный интернет-адрес\n\nДанных пока нет'

    metrics = network_data.metrics

    if metrics.is_failed:
        lines = ['🌐 Проверочный интернет-адрес', '', 'Последняя проверка: неуспешна']
    else:
        lines = ['🌐 Проверочный интернет-адрес', '', 'Последняя проверка: адрес доступен']

    if metrics.result_code is not None:
        lines.append(f'HTTP: {metrics.result_code}')

    if metrics.error is not None:
        lines.append(f'Причина: {metrics.error}')

    lines.append(
        f'Проверено: {network_data.checked_at:%d.%m.%Y %H:%M:%S %Z}'
    )

    return '\n'.join(lines)
