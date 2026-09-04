from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from monitor import system

start_router = Router()

@start_router.message(Command('cpu'))
async def cmd_cpu(message: Message):
    cpu_data = system.cpu_check()
    await message.answer('Температура процессора:'+str(cpu_data["temperature"])+'℃'+
                         '\nЗагрузка процессора: '+str(cpu_data['load'])+
                         '\nЗагрузка процессора за 1,5,15 мин:'+str(cpu_data['load_average']))

@start_router.message(Command('ram'))
async def cmd_ram(message: Message):
    ram_data = system.ram_check()
    msg = f'''Всего памяти {ram_data["total"]}
            \nДоступно памяти {ram_data["available"]} 
            \n Занято - {ram_data["usage"]} %'''
    await message.answer(msg)

@start_router.message(Command('disk'))
async def cmd_disk(message: Message):
    disk_data = system.disk_check()
    msg = ''
    for disk, info in disk_data.items():
        msg += f'Диск: {disk}\nТемпуратура: {info["temperature"]} ℃\n'
        for partition in info['partitions']:
            msg += f'''Partition: {partition["partition"]}
                    Точка монтирования: {partition['mountpoint']}
                    Всего памяти: {partition['total']}
                    Использовано: {partition['used']}\n'''
    await message.answer(msg)
    