import asyncio
import os
import logging
from aiogram import Dispatcher
from aiogram.types import BotCommand
from dotenv import load_dotenv

from bot.bot_instance import bot
from bot.database import init_db
from bot.middlewares import ChannelCheckMiddleware
from bot.handlers import start, referral, platform, login, settings, dashboard, admin

load_dotenv()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


async def on_startup():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await _set_commands()
    logger.info("Bot started")


async def on_shutdown():
    logger.info("Bot shutting down")


async def _set_commands():
    commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="stop", description="Stop the bot"),
        BotCommand(command="admin", description="Admin panel"),
    ]
    await bot.set_my_commands(commands)


def setup_dispatcher() -> Dispatcher:
    dp = Dispatcher()

    dp.message.middleware(ChannelCheckMiddleware())
    dp.callback_query.middleware(ChannelCheckMiddleware())

    dp.include_routers(
        admin.router,
        start.router,
        referral.router,
        platform.router,
        login.router,
        settings.router,
        dashboard.router,
    )

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    return dp
