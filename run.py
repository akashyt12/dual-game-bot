#!/usr/bin/env python3
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv()

def main():
    from bot.main import setup_dispatcher
    dp = setup_dispatcher()
    from bot.bot_instance import bot
    from aiogram import Bot
    asyncio.run(dp.start_polling(bot))

if __name__ == "__main__":
    main()
