#!/usr/bin/env python3
"""
DUAL GAME BOT - JAI CLUB + 51gamet
aiogram 3.30 with Colored Buttons + Images + Platform Selection
"""

import os
import sys
import json
import asyncio
import logging
import random
import time
from datetime import datetime
from pathlib import Path
from html import escape

sys.path.insert(0, str(Path(__file__).parent))
from JAI_CLUB_BOT import AccountChecker as JAIChecker, AutoBetEngine, GAME_CODES, make_levels, predict_bs as jai_predict_bs, predict_color as jai_predict_color
from game51_checker import Game51AccountChecker, predict_bs as game51_predict_bs, predict_color as game51_predict_color, result_to_bs, result_to_color

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InputMediaPhoto,
    InlineKeyboardButton, InlineKeyboardMarkup
)

BOT_TOKEN = os.environ.get(
    "BOT_TOKEN",
    "8488981885:AAHP6PO4d6wDFr-cLSL1-lRHV5j9y7dXLP4",
).strip()
CHANNEL_ID = "@JaiClubOfficial"
CHANNEL_URL = "https://t.me/JaiClubOfficial"
BASE_DIR = Path(__file__).resolve().parent
IMAGES_DIR = BASE_DIR / "images"

USERS_FILE = BASE_DIR / "users.json"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

user_states = {}
active_bots = {}
profit_messages = {}

def load_users():
    if USERS_FILE.exists():
        with open(USERS_FILE) as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def get_user(user_id):
    return load_users().get(str(user_id), {})

def update_user(user_id, data):
    users = load_users()
    users[str(user_id)] = data
    save_users(users)

# ============================================
# KEYBOARDS
# ============================================

def platform_select_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ðŸŽ° JAI CLUB", callback_data="platform_jai")],
        [InlineKeyboardButton(text="ðŸŽ¯ 51GAME", callback_data="platform_51")],
    ])

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="â–¶ï¸ START BOT", callback_data="start_bot"),
            InlineKeyboardButton(text="ðŸ“Š STATUS", callback_data="status"),
        ],
        [
            InlineKeyboardButton(text="ðŸ’° PROFIT", callback_data="profit"),
            InlineKeyboardButton(text="âš™ï¸ SETTINGS", callback_data="settings"),
        ],
        [
            InlineKeyboardButton(text="ðŸŽ¯ GAME", callback_data="game_select"),
            InlineKeyboardButton(text="ðŸ›‘ STOP", callback_data="stop_bot"),
        ],
        [
            InlineKeyboardButton(text="ðŸ”„ SWITCH", callback_data="switch_platform"),
            InlineKeyboardButton(text="â“ HELP", callback_data="help"),
        ],
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ðŸ”™ BACK", callback_data="back_menu")]
    ])

def game_menu_kb_jai():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="âš¡ 30 SEC", callback_data="game_30s"),
            InlineKeyboardButton(text="ðŸ”¥ 1 MIN", callback_data="game_1m"),
        ],
        [InlineKeyboardButton(text="ðŸ”™ BACK", callback_data="back_menu")]
    ])

def game_menu_kb_51():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="âš¡ 30 SEC", callback_data="game51_30"),
            InlineKeyboardButton(text="ðŸ”¥ 1 MIN", callback_data="game51_1m"),
        ],
        [
            InlineKeyboardButton(text="ðŸ’Ž 3 MIN", callback_data="game51_3m"),
            InlineKeyboardButton(text="â­ 5 MIN", callback_data="game51_5m"),
        ],
        [InlineKeyboardButton(text="ðŸ”™ BACK", callback_data="back_menu")]
    ])

def settings_kb(user_data):
    restart = "ON" if user_data.get("auto_restart", True) else "OFF"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"ðŸ”„ AUTO RESTART: {restart}", callback_data="toggle_restart")],
        [InlineKeyboardButton(text="ðŸ’° SET BET", callback_data="set_bet")],
        [InlineKeyboardButton(text="ðŸ“Š SET MULTIPLIER", callback_data="set_multiplier")],
        [InlineKeyboardButton(text="ðŸ”™ BACK", callback_data="back_menu")],
    ])

def stop_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="âœ… YES STOP", callback_data="confirm_stop"),
            InlineKeyboardButton(text="âŒ NO RUKO", callback_data="cancel_stop"),
        ]
    ])

# ============================================
# /start COMMAND - Platform Selection
# ============================================

@dp.message(CommandStart())
async def start_command(message: Message):
    user_id = message.from_user.id
    name = escape(message.from_user.first_name or "User")

    text = f"""
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>   ðŸŽ° DUAL GAME AUTO BOT ðŸŽ°</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

ðŸ‘‹ Welcome, <b>{name}</b>!

<b>Choose Your Platform:</b>

ðŸŽ® <b>JAI CLUB</b> - WinGo 30S/1M
ðŸŽ¯ <b>51GAME</b> - WinGo 30S/1M/3M/5M

<b>Features:</b>
â€¢ ðŸ¤– Auto Prediction
â€¢ ðŸ’° Dual Bet System
â€¢ ðŸ“ˆ Level Staking
â€¢ ðŸ”„ Auto Restart
â€¢ ðŸ“Š Live Profit
â€¢ ðŸ–¼ï¸ Images & Updates

<i>Niche platform choose karo:</i>
"""
    await message.answer(text=text, reply_markup=platform_select_kb())
    update_user(user_id, {"name": name, "username": message.from_user.username, "logged_in": False})

# ============================================
# PLATFORM SELECTION
# ============================================

@dp.callback_query(F.data.startswith("platform_"))
async def handle_platform(callback: CallbackQuery):
    user_id = callback.from_user.id
    platform = callback.data.replace("platform_", "")
    user_data = get_user(user_id)
    user_data["platform"] = platform
    update_user(user_id, user_data)

    if platform == "jai":
        image_path = IMAGES_DIR / "jaiclub_logo.png"
        text = """
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>      ðŸŽ° JAI CLUB SELECTED</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

<b>Platform:</b> JAI Club / AR Lottery
<b>Games:</b> WinGo 30S, 1M
<b>API:</b> jaiclubapi.com

ðŸ” Login karne ke liye /login type karo.
"""
    else:
        image_path = IMAGES_DIR / "wingo_icon.png"
        text = """
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>      ðŸŽ¯ 51GAME SELECTED</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

<b>Platform:</b> 51gamet.com
<b>Games:</b> WinGo 30S, 1M, 3M, 5M
<b>API:</b> api51gameapi.com

ðŸ” Login karne ke liye /login type karo.
"""

    try:
        if image_path.exists():
            with open(image_path, "rb") as f:
                await callback.message.answer_photo(photo=f, caption=text, reply_markup=main_menu_kb())
            await callback.message.delete()
        else:
            await callback.message.edit_text(text=text, reply_markup=main_menu_kb())
    except Exception:
        await callback.message.edit_text(text=text, reply_markup=main_menu_kb())

    await callback.answer(f"âœ… {platform.upper()} selected!")

# ============================================
# /login COMMAND
# ============================================

@dp.message(Command("login"))
async def login_command(message: Message):
    user_id = message.from_user.id
    user_data = get_user(user_id)
    platform = user_data.get("platform", "jai")
    user_states[user_id] = "login"

    if platform == "jai":
        text = """
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>       ðŸ” JAI CLUB LOGIN</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

Apna <b>username</b> aur <b>password</b> daalo:

<code>username
password</code>

<i>Example:</i>
<code>919876543210
mypassword123</code>
"""
    else:
        text = """
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>       ðŸ” 51GAME LOGIN</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

Apna <b>phone number</b> aur <b>password</b> daalo:

<code>phone
password</code>

<i>Example:</i>
<code>712813131819
shiv1234</code>

<i>Note: 91 prefix auto add hoga</i>
"""
    await message.answer(text=text)

# ============================================
# /stop COMMAND
# ============================================

@dp.message(Command("stop"))
async def stop_command(message: Message):
    user_id = message.from_user.id
    if user_id in active_bots:
        active_bots[user_id]["running"] = False
    text = """
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>      ðŸ›‘ BOT BAND!</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

Bot stop ho gaya.
Dubara /start se start karo.
"""
    await message.answer(text=text, reply_markup=main_menu_kb())

# ============================================
# TEXT MESSAGE HANDLER
# ============================================

@dp.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    text = message.text.strip()
    user_data = get_user(user_id)
    platform = user_data.get("platform", "jai")

    if state == "login":
        lines = text.split("\n")
        if len(lines) < 2:
            await message.answer("âŒ Format sahi se daalo!\n<code>username\npassword</code>")
            return

        username = lines[0].strip()
        password = lines[1].strip()

        user_data["login_user"] = username
        user_data["login_pass"] = password
        user_data["logged_in"] = True
        update_user(user_id, user_data)
        user_states[user_id] = "set_amount"

        platform_name = "JAI CLUB" if platform == "jai" else "51GAME"
        text = f"""
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>      ðŸ’° AMOUNT SET KARO</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

<b>Platform:</b> {platform_name}
Apna total balance daalo:
<i>Example:</i> <code>1000</code>, <code>5000</code>, <code>10000</code>

<i>Amount daalo:</i>
"""
        await message.answer(text=text)
        return

    if state == "set_amount":
        try:
            amount = max(100, int(text))
            user_data["start_balance"] = amount
            update_user(user_id, user_data)
            user_states.pop(user_id, None)

            platform_name = "JAI CLUB" if platform == "jai" else "51GAME"
            await message.answer(
                f"âœ… <b>Platform:</b> {platform_name}\nâœ… <b>Balance:</b> <code>â‚¹{amount}</code>\n\nðŸš€ Bot start ho raha hai...",
                reply_markup=main_menu_kb()
            )

            user_data = get_user(user_id)
            asyncio.create_task(run_betting(user_id, message.chat.id, user_data))
        except:
            await message.answer("âŒ Number daalo! Min â‚¹100")
        return

    if state == "set_bet":
        try:
            bet = max(2, int(text))
            user_data["total_bet"] = bet
            update_user(user_id, user_data)
            user_states.pop(user_id, None)
            await message.answer(f"âœ… Bet Set: â‚¹{bet}", reply_markup=main_menu_kb())
        except:
            await message.answer("âŒ Number daalo!")
        return

    if state == "set_mult":
        try:
            mult = max(1.5, float(text))
            user_data["multiplier"] = mult
            update_user(user_id, user_data)
            user_states.pop(user_id, None)
            await message.answer(f"âœ… Multiplier Set: {mult}x", reply_markup=main_menu_kb())
        except:
            await message.answer("âŒ Number daalo!")
        return

# ============================================
# CALLBACK QUERY HANDLER
# ============================================

@dp.callback_query()
async def handle_callbacks(callback: CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data
    user_data = get_user(user_id)
    platform = user_data.get("platform", "jai")

    if data == "back_menu":
        text = """
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>      ðŸ“‹ MAIN MENU</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

<i>Choose karo:</i>
"""
        await callback.message.edit_text(text=text, reply_markup=main_menu_kb())
        return

    if data == "switch_platform":
        text = """
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>      ðŸ”„ SWITCH PLATFORM</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

<i>Kaunsa platform?</i>
"""
        await callback.message.edit_text(text=text, reply_markup=platform_select_kb())
        return

    if data == "start_bot":
        if not user_data.get("logged_in"):
            await callback.answer("âŒ Pehle /login karo!", show_alert=True)
            return
        if not user_data.get("start_balance"):
            user_states[user_id] = "set_amount"
            await callback.message.edit_text(
                "<b>ðŸ’° AMOUNT SET KARO</b>\n\nBalance daalo:",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="â—€ï¸ BACK", callback_data="back_menu")]
                    ]
                ),
            )
            return

        await callback.answer("ðŸš€ Bot starting!")
        platform_name = "JAI CLUB" if platform == "jai" else "51GAME"
        text = f"""
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>    âœ… BOT START HO GAYA!</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

<b>Platform:</b> {platform_name}
ðŸ“Š Live updates aayenge!
ðŸ›‘ Rokne ke liye /stop
"""
        await callback.message.edit_text(text=text, reply_markup=main_menu_kb())
        asyncio.create_task(run_betting(user_id, callback.message.chat.id, user_data))
        return

    if data == "status":
        bot_data = active_bots.get(user_id, {})
        running = "ðŸŸ¢ Running" if bot_data.get("running") else "ðŸ”´ Stopped"
        level = bot_data.get("level", 0)
        max_levels = len(bot_data.get("levels", [])) if bot_data.get("levels") else 0
        platform_name = "JAI CLUB" if platform == "jai" else "51GAME"

        text = f"""
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>      ðŸ“Š BOT STATUS</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

<b>Platform:</b> {platform_name}
<b>Status:</b> {running}
<b>Balance:</b> <code>â‚¹{bot_data.get('balance', 0):.2f}</code>
<b>Profit:</b> <code>â‚¹{bot_data.get('profit', 0):.2f}</code>
<b>Level:</b> <code>{level}/{max_levels}</code>
"""
        await callback.message.edit_text(text=text, reply_markup=back_kb())
        return

    if data == "profit":
        bot_data = active_bots.get(user_id, {})
        start = bot_data.get("start_balance", 0)
        curr = bot_data.get("balance", 0)
        profit = curr - start
        pct = ((profit / start) * 100) if start > 0 else 0
        emoji = "ðŸ“ˆ" if profit >= 0 else "ðŸ“‰"
        sign = "+" if profit >= 0 else ""

        text = f"""
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>      ðŸ’° LIVE PROFIT</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

{emoji} <b>Net Profit:</b> <code>{sign}â‚¹{profit:.2f}</code>
ðŸ“Š <b>Profit %:</b> <code>{sign}{pct:.1f}%</code>

âœ… <b>Double Win:</b> <code>{bot_data.get('double_win', 0)}</code>
âŒ <b>Double Loss:</b> <code>{bot_data.get('double_loss', 0)}</code>
ðŸŽ¯ <b>Level:</b> <code>{bot_data.get('level', 0)}</code>
"""
        await callback.message.edit_text(text=text, reply_markup=back_kb())
        return

    if data == "game_select":
        if platform == "jai":
            text = """
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>      ðŸŽ® JAI CLUB GAMES</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

<i>Kaunsa game?</i>
"""
            await callback.message.edit_text(text=text, reply_markup=game_menu_kb_jai())
        else:
            text = """
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>      ðŸŽ® 51GAME GAMES</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

<i>Kaunsa game?</i>
"""
            await callback.message.edit_text(text=text, reply_markup=game_menu_kb_51())
        return

    if data in ["game_30s", "game_1m"]:
        game = "WinGo_30S" if data == "game_30s" else "WinGo_1M"
        user_data["game"] = game
        update_user(user_id, user_data)
        await callback.answer(f"âœ… Game: {game}")
        await callback.message.edit_text(f"âœ… <b>Game:</b> {game}", reply_markup=main_menu_kb())
        return

    if data.startswith("game51_"):
        game_map = {"game51_30": 30, "game51_1m": 1, "game51_3m": 2, "game51_5m": 3}
        type_id = game_map.get(data, 30)
        user_data["game51_type_id"] = type_id
        update_user(user_id, user_data)
        names = {30: "30 SEC", 1: "1 MIN", 2: "3 MIN", 3: "5 MIN"}
        await callback.answer(f"âœ… Game: {names.get(type_id, '30S')}")
        await callback.message.edit_text(f"âœ… <b>Game:</b> WinGo {names.get(type_id, '30S')}", reply_markup=main_menu_kb())
        return

    if data == "stop_bot":
        text = """
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>      ðŸ›‘ BAND KARO?</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

<i>Sure hai?</i>
"""
        await callback.message.edit_text(text=text, reply_markup=stop_confirm_kb())
        return

    if data == "confirm_stop":
        if user_id in active_bots:
            active_bots[user_id]["running"] = False
        await callback.answer("ðŸ›‘ Bot band!")
        text = """
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>    ðŸ”´ BOT BAND HO GAYA!</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

Dubara /start se start karo.
"""
        await callback.message.edit_text(text=text, reply_markup=main_menu_kb())
        return

    if data == "cancel_stop":
        await callback.answer("âœ… Bot chalu hai!")
        await callback.message.edit_text("âœ… Bot chalu hai!", reply_markup=main_menu_kb())
        return

    if data == "settings":
        text = """
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>      âš™ï¸ SETTINGS</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

<i>Badlo:</i>
"""
        await callback.message.edit_text(text=text, reply_markup=settings_kb(user_data))
        return

    if data == "toggle_restart":
        user_data["auto_restart"] = not user_data.get("auto_restart", True)
        update_user(user_id, user_data)
        status = "ON" if user_data["auto_restart"] else "OFF"
        await callback.answer(f"âœ… Auto Restart: {status}")
        await callback.message.edit_text(f"âœ… <b>Auto Restart:</b> {status}", reply_markup=settings_kb(user_data))
        return

    if data == "set_bet":
        user_states[user_id] = "set_bet"
        await callback.message.edit_text(
            "ðŸ’° <b>Bet amount daalo</b> (min 2):",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="â—€ï¸ BACK", callback_data="back_menu")]
                ]
            ),
        )
        return

    if data == "set_multiplier":
        user_states[user_id] = "set_mult"
        await callback.message.edit_text(
            "ðŸ“ˆ <b>Multiplier daalo</b> (1.5, 2, 3):",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="â—€ï¸ BACK", callback_data="back_menu")]
                ]
            ),
        )
        return

    if data == "help":
        text = """
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>       â“ HELP</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

<b>Commands:</b>
/start - Bot start & platform select
/login - Login
/status - Status
/stop - Bot band
/help - Ye help

<b>How it works:</b>
1ï¸âƒ£ Platform choose karo
2ï¸âƒ£ Login karo
3ï¸âƒ£ Bot start karo!
4ï¸âƒ£ Live profit dekho!

<b>Platforms:</b>
ðŸŽ® JAI CLUB - WinGo 30S/1M
ðŸŽ¯ 51GAME - WinGo 30S/1M/3M/5M
"""
        await callback.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="â—€ï¸ BACK", callback_data="back_menu")]
                ]
            ),
        )
        return

# ============================================
# RUN BETTING - JAI CLUB
# ============================================

async def run_betting_jai(user_id, chat_id, user_data):
    username = user_data.get("login_user", "")
    password = user_data.get("login_pass", "")
    game = user_data.get("game", "WinGo_30S")
    total_bet = user_data.get("total_bet", 2)
    multiplier = user_data.get("multiplier", 2.0)
    start_balance = user_data.get("start_balance", 500)

    msg = await bot.send_message(chat_id, "â³ <b>JAI CLUB</b> - Logging in...", reply_markup=main_menu_kb())
    profit_messages[user_id] = msg.message_id

    try:
        engine = AutoBetEngine(username, password, game, total_bet, multiplier, 55)
        engine.login()
        engine.checker.fetch_ar_token(game)
    except Exception as e:
        await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=f"âŒ Login failed: {e}")
        return

    engine.start_balance = start_balance
    engine.current_balance = start_balance
    engine.levels = make_levels(start_balance, total_bet, multiplier)

    bot_state = {
        "running": True, "start_balance": start_balance, "balance": start_balance,
        "profit": 0, "total_won": 0, "total_lost": 0, "wins": 0, "losses": 0,
        "double_win": 0, "double_loss": 0, "level": 0, "pending": None, "last_seen_period": None
    }
    active_bots[user_id] = bot_state
    await update_profit_msg(user_id, chat_id, bot_state, "RUNNING", "JAI CLUB")

    while bot_state["running"]:
        try:
            data = engine.fetch_draw_history(6)
            if not data:
                await asyncio.sleep(1)
                continue

            latest = str(data[0]["issueNumber"])
            nums = [int(x["number"]) for x in data[:6]]

            if bot_state["pending"]:
                pending = bot_state["pending"]
                if str(pending["period"]) == latest:
                    actual_num = nums[0]
                    actual_bs = "BIG" if actual_num >= 5 else "SMALL"
                    actual_color = "GREEN" if actual_num in {1,3,5,7,9} else "RED"
                    bs_match = pending["bs_prediction"] == actual_bs
                    color_match = pending["color_prediction"] == actual_color

                    if bs_match and color_match:
                        result = "DOUBLE WIN"
                        bot_state["double_win"] += 1
                        bot_state["wins"] += 1
                        bot_state["level"] = 0
                        bot_state["total_won"] += pending["total_bet"]
                    elif bs_match or color_match:
                        result = "BREAK EVEN"
                    else:
                        result = "DOUBLE LOSS"
                        bot_state["double_loss"] += 1
                        bot_state["losses"] += 1
                        bot_state["level"] += 1
                        bot_state["total_lost"] += pending["total_bet"]
                        if bot_state["level"] >= len(engine.levels):
                            bot_state["running"] = False
                            break

                    bot_state["pending"] = None
                    bot_state["profit"] = bot_state["total_won"] - bot_state["total_lost"]
                    bot_state["balance"] = bot_state["start_balance"] + bot_state["profit"]
                    await update_profit_msg(user_id, chat_id, bot_state, result, "JAI CLUB")
                await asyncio.sleep(1)
                continue

            if latest == bot_state["last_seen_period"]:
                await asyncio.sleep(1)
                continue
            bot_state["last_seen_period"] = latest

            pattern_bs = [("B" if n >= 5 else "S") for n in reversed(nums)]
            pattern_co = [("G" if n in {1,3,5,7,9} else "R") for n in reversed(nums)]
            bs_pred, _ = jai_predict_bs(pattern_bs)
            co_pred, _ = jai_predict_color(pattern_co)

            if bot_state["level"] >= len(engine.levels):
                bot_state["running"] = False
                break

            lv = engine.levels[bot_state["level"]]
            open_issue = engine.fetch_open_issue()
            if open_issue:
                try:
                    engine.place_dual_bet(open_issue, bs_pred, co_pred, lv["bs_bet"], lv["color_bet"])
                    bot_state["pending"] = {
                        "period": open_issue, "bs_prediction": bs_pred, "color_prediction": co_pred,
                        "total_bet": lv["total_bet"], "level": lv["level"]
                    }
                    await update_profit_msg(user_id, chat_id, bot_state, "WAITING", "JAI CLUB")
                except Exception as e:
                    logger.error(f"Bet failed: {e}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Betting error: {e}")
            await asyncio.sleep(3)

    if user_id in profit_messages:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=profit_messages[user_id],
                text=format_profit(bot_state, "STOPPED", "JAI CLUB"), reply_markup=main_menu_kb())
        except:
            pass

# ============================================
# RUN BETTING - 51GAME
# ============================================

async def run_betting_51(user_id, chat_id, user_data):
    username = user_data.get("login_user", "")
    password = user_data.get("login_pass", "")
    type_id = user_data.get("game51_type_id", 30)
    total_bet = user_data.get("total_bet", 2)
    start_balance = user_data.get("start_balance", 500)

    msg = await bot.send_message(chat_id, "â³ <b>51GAME</b> - Logging in...", reply_markup=main_menu_kb())
    profit_messages[user_id] = msg.message_id

    checker = Game51AccountChecker(username, password)
    try:
        if not checker.perform_login():
            await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
                text=f"âŒ Login failed: {checker.message}")
            return
    except Exception as e:
        await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
            text=f"âŒ Login failed: {e}")
        return

    balance = checker.get_balance()
    if balance <= 0:
        balance = start_balance

    game_names = {30: "30 SEC", 1: "1 MIN", 2: "3 MIN", 3: "5 MIN"}
    game_name = game_names.get(type_id, "30 SEC")

    bot_state = {
        "running": True, "start_balance": balance, "balance": balance,
        "profit": 0, "total_won": 0, "total_lost": 0, "wins": 0, "losses": 0,
        "double_win": 0, "double_loss": 0, "level": 0, "pending": None, "last_seen_period": None
    }
    active_bots[user_id] = bot_state
    await update_profit_msg(user_id, chat_id, bot_state, "RUNNING", f"51GAME {game_name}")

    levels = make_levels(balance, total_bet, 2.0)

    while bot_state["running"]:
        try:
            history = checker.fetch_draw_history(type_id, 6)
            if not history:
                await asyncio.sleep(1)
                continue

            latest = str(history[0].get("issueNumber", ""))
            nums = [int(h.get("number", 0)) for h in history[:6]]

            if bot_state["pending"]:
                pending = bot_state["pending"]
                if str(pending["period"]) == latest:
                    actual_num = nums[0]
                    actual_bs = result_to_bs(actual_num)
                    actual_color = result_to_color(actual_num)
                    bs_match = pending["bs_prediction"] == actual_bs
                    color_match = pending["color_prediction"] == actual_color

                    if bs_match and color_match:
                        result = "DOUBLE WIN"
                        bot_state["double_win"] += 1
                        bot_state["wins"] += 1
                        bot_state["level"] = 0
                        bot_state["total_won"] += pending["total_bet"]
                    elif bs_match or color_match:
                        result = "BREAK EVEN"
                    else:
                        result = "DOUBLE LOSS"
                        bot_state["double_loss"] += 1
                        bot_state["losses"] += 1
                        bot_state["level"] += 1
                        bot_state["total_lost"] += pending["total_bet"]
                        if bot_state["level"] >= len(levels):
                            bot_state["running"] = False
                            break

                    bot_state["pending"] = None
                    bot_state["profit"] = bot_state["total_won"] - bot_state["total_lost"]
                    bot_state["balance"] = bot_state["start_balance"] + bot_state["profit"]
                    await update_profit_msg(user_id, chat_id, bot_state, result, f"51GAME {game_name}")
                await asyncio.sleep(1)
                continue

            if latest == bot_state["last_seen_period"]:
                await asyncio.sleep(1)
                continue
            bot_state["last_seen_period"] = latest

            pattern_bs = [("B" if n >= 5 else "S") for n in reversed(nums)]
            pattern_co = [("G" if n in {1,3,5,7,9} else "R") for n in reversed(nums)]
            bs_pred, _ = game51_predict_bs(pattern_bs)
            co_pred, _ = game51_predict_color(pattern_co)

            if bot_state["level"] >= len(levels):
                bot_state["running"] = False
                break

            lv = levels[bot_state["level"]]
            open_issue = checker.fetch_open_issue(type_id)
            if open_issue:
                try:
                    bs_content = f"BigSmall_{bs_pred.capitalize()}"
                    color_content = f"Color_{co_pred.capitalize()}"
                    results = checker.place_dual_bet(open_issue, type_id, lv["bs_bet"], lv["color_bet"], bs_content, color_content)
                    bs_ok = "error" not in results.get("bs", {})
                    color_ok = "error" not in results.get("color", {})
                    if bs_ok or color_ok:
                        bot_state["pending"] = {
                            "period": open_issue, "bs_prediction": bs_pred, "color_prediction": co_pred,
                            "total_bet": lv["total_bet"], "level": lv["level"]
                        }
                        await update_profit_msg(user_id, chat_id, bot_state, "WAITING", f"51GAME {game_name}")
                    else:
                        logger.error(f"51GAME Both bets failed: {results}")
                except Exception as e:
                    logger.error(f"51GAME Bet failed: {e}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"51GAME error: {e}")
            await asyncio.sleep(3)

    if user_id in profit_messages:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=profit_messages[user_id],
                text=format_profit(bot_state, "STOPPED", f"51GAME {game_name}"), reply_markup=main_menu_kb())
        except:
            pass

# ============================================
# RUN BETTING - ROUTER
# ============================================

async def run_betting(user_id, chat_id, user_data):
    platform = user_data.get("platform", "jai")
    if platform == "51":
        await run_betting_51(user_id, chat_id, user_data)
    else:
        await run_betting_jai(user_id, chat_id, user_data)

# ============================================
# UPDATE PROFIT MESSAGE
# ============================================

async def update_profit_msg(user_id, chat_id, bot_state, status="RUNNING", platform="JAI CLUB"):
    msg_id = profit_messages.get(user_id)
    if not msg_id:
        return
    text = format_profit(bot_state, status, platform)
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, reply_markup=main_menu_kb())
    except Exception as e:
        if "message is not modified" not in str(e):
            logger.error(f"Edit profit msg error: {e}")

def format_profit(bot_state, status="RUNNING", platform="JAI CLUB"):
    profit = bot_state.get("profit", 0)
    start = bot_state.get("start_balance", 0)
    pct = ((profit / start) * 100) if start > 0 else 0

    if status == "RUNNING":
        s_emoji, s_text = "ðŸŸ¢", "Running"
    elif status == "WAITING":
        s_emoji, s_text = "â³", "Waiting"
    elif status == "STOPPED":
        s_emoji, s_text = "ðŸ”´", "Stopped"
    elif "WIN" in status:
        s_emoji, s_text = "ðŸ†", status
    elif "LOSS" in status:
        s_emoji, s_text = "ðŸ’”", status
    else:
        s_emoji, s_text = "âš¡", status

    p_emoji = "ðŸ“ˆ" if profit >= 0 else "ðŸ“‰"
    sign = "+" if profit >= 0 else ""

    return f"""
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>
<b>  ðŸ’° {platform} PROFIT</b>
<b>â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”</b>

{s_emoji} <b>Status:</b> {s_text}

{p_emoji} <b>Net Profit:</b> <code>{sign}â‚¹{profit:.2f}</code>
ðŸ“Š <b>Profit %:</b> <code>{sign}{pct:.1f}%</code>

âœ… <b>Wins:</b> <code>{bot_state.get('wins', 0)}</code> | âŒ <b>Losses:</b> <code>{bot_state.get('losses', 0)}</code>
ðŸ† <b>Double Win:</b> <code>{bot_state.get('double_win', 0)}</code> | ðŸ’” <b>Double Loss:</b> <code>{bot_state.get('double_loss', 0)}</code>

ðŸŽ¯ <b>Level:</b> <code>{bot_state.get('level', 0)}</code>
ðŸ’° <b>Won:</b> <code>â‚¹{bot_state.get('total_won', 0):.2f}</code> | ðŸ’¸ <b>Lost:</b> <code>â‚¹{bot_state.get('total_lost', 0):.2f}</code>

ðŸ•’ <i>{datetime.now().strftime('%H:%M:%S')}</i>
"""

# ============================================
# BOT START
# ============================================

async def main():
    print("ðŸ¤– DUAL GAME BOT STARTED!")
    print("   ðŸŽ® JAI CLUB + ðŸŽ¯ 51GAME")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
