from aiogram import Bot
from alerts.models import NumericAlertData, ContainerAlertData, HttpAlertData
from telegram.formatter import (format_numeric_alert, format_container_alert,
                                format_http_alert, format_network_alert)

async def send_alert(bot: Bot, chat_id: int, status: dict[str, NumericAlertData]):
    msg = format_numeric_alert(status)
    await bot.send_message(
        chat_id=chat_id,
        text=msg
    )

async def send_container_alert(bot: Bot, chat_id: int, status: dict[str, ContainerAlertData]):
    msg = format_container_alert(status)

    await bot.send_message(
        chat_id=chat_id,
        text=msg)


async def send_http_alert(
        bot: Bot,
        chat_id: int,
        status: dict[str, HttpAlertData]
):
    msg = format_http_alert(status)
    await bot.send_message(
        chat_id=chat_id,
        text=msg
    )

async def send_network_alert(
        bot: Bot,
        chat_id: int,
        problem_was_notified: bool,
        status: dict[str, HttpAlertData]
):
    msg = format_network_alert(
        status,
        problem_was_notified
    )
    await bot.send_message(
        chat_id=chat_id,
        text=msg
    )
    