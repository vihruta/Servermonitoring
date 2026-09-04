from monitor.system import cpu_check, ram_check, disk_check
import asyncio
from telegram.create_bot import bot, dp
from telegram.handlers import start_router

async def main():
    dp.include_router(start_router)
    await dp.start_polling(bot)

    # print('CPU')
    # cpu_check()

    # print("\nRAM")
    # ram_check()

    # print("\nDisks")
    # disk_check()


if __name__ == "__main__":
    asyncio.run(main())

