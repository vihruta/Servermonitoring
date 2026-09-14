from aiogram import Bot
from alerts.models import NumericAlertData, ContainerAlertData
from telegram.formatter import format_numeric_alert, format_container_alert

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
    