from aiogram import Bot
from telegram.formatter import format_alert

async def send_alert(bot: Bot, chat_id: int, status: dict):
    msg = format_alert(status)
    await bot.send_message(
        chat_id=chat_id,
        text=msg
    )