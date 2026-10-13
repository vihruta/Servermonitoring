from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

def create_bot(token: str):
    bot = Bot(token=token)
    dp = Dispatcher()
    return bot, dp

async def setup_commands(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command='status', description='Сводка состояния сервера'),
        BotCommand(command='cpu', description='Загрузка и температура процессора'),
        BotCommand(command='ram', description='Оперативная память и swap'),
        BotCommand(command='disk', description='Диски и SMART'),
        BotCommand(command='temp', description='Температуры'),
        BotCommand(command='docker', description='Состояние контейнеров'),
        BotCommand(command='services', description='HTTP-проверки сервисов'),
        BotCommand(command='network', description='Доступность интернет-адреса'),
        BotCommand(command='help', description='Справка по командам'),
    ])
