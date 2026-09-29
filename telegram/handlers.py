from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from monitor import system, docker_monitor
import logging
import asyncio

from config import Settings
from telegram.formatter import (format_cpu, format_ram, 
                                format_disk, format_status, 
                                format_temp, format_docker_data)

start_router = Router()

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
async def cmd_disk(message: Message, settings: Settings):
    logger.info('DISK command request')
    disk_data = await asyncio.to_thread(
        system.disk_check,
        lsblk_timeout=settings.timeouts.lsblk,
        smartctl_timeout=settings.timeouts.smartctl
    )
    msg = format_disk(disk_data)
    await message.answer(msg)

@start_router.message(Command('status'))
async def cmd_status(message: Message, settings: Settings):
    logger.info('Status command request')
    status_data = await asyncio.to_thread( 
        system.get_status,
        settings=settings
    )
    msg = format_status(status_data=status_data)
    await message.answer(msg)

@start_router.message(Command('temp'))
async def cmd_temp(message: Message, settings: Settings):
    logger.info('Temperature command request')
    status_data = await asyncio.to_thread(
        system.get_status,
        settings=settings
    )
    msg = format_temp(status_data=status_data)
    await message.answer(msg)

@start_router.message(Command('docker'))
async def cmd_docker(message: Message, settings: Settings):
    logger.info('Docker command request')
    docker_data = await asyncio.to_thread(
        docker_monitor.get_containers_health,
        docker_timeout=settings.timeouts.docker
    )
    msg = format_docker_data(docker_data=docker_data)
    await message.answer(msg)   