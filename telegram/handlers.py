from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from monitor import system, docker_monitor
import logging

from telegram.formatter import format_cpu, format_ram, format_disk, format_status, format_temp
from telegram.filters import AllowedUserFilter
from config import allowed_users

start_router = Router()

start_router.message.filter(
    AllowedUserFilter(allowed_users)
)
logger = logging.getLogger(__name__)

@start_router.message(Command('cpu'))
async def cmd_cpu(message: Message):
    logger.info('CPU command request')
    cpu_data = system.cpu_check()
    msg = format_cpu(cpu_data=cpu_data)
    await message.answer(msg)

@start_router.message(Command('ram'))
async def cmd_ram(message: Message):
    logger.info('RAM command request')
    ram_data = system.ram_check()
    msg = format_ram(ram_data=ram_data)
    await message.answer(msg)

@start_router.message(Command('disk'))
async def cmd_disk(message: Message):
    logger.info('DISK command request')
    disk_data = system.disk_check()
    msg = format_disk(disk_data)
    await message.answer(msg)

@start_router.message(Command('status'))
async def cmd_status(message: Message):
    logger.info('Status command request')
    status_data = system.get_status()
    msg = format_status(status_data=status_data)
    await message.answer(msg)

@start_router.message(Command('temp'))
async def cmd_temp(message: Message):
    logger.info('Temperature command request')
    status_data = system.get_status()
    msg = format_temp(status_data=status_data)
    await message.answer(msg)

@start_router.message(Command('docker'))
async def cmd_docker(message: Message):
    logger.info('Docker command request')
    docker_data = docker_monitor.get_containers_health()
    msg = format_docker_data(docker_data=docker_data)
    await message.answer(msg)   