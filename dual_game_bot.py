#!/usr/bin/env python3
"""
DUAL GAME BOT - JAI CLUB + 51GAME
aiogram 3.15+ with Clean UI, Images, Profit Target
"""

import os
import sys
import json
import asyncio
import logging
import random
import time
import urllib.request
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

BOT_TOKEN = "8488981885:AAHP6PO4d6wDFr-cLSL1-lRHV5j9y7dXLP4"
CHANNEL_ID = "@JaiClubOfficial"
CHANNEL_URL = "https://t.me/JaiClubOfficial"
IMAGES_DIR = Path("/home/akash/mimo-test/images")

BASE_DIR = Path("/home/akash/mimo-test")
USERS_FILE = BASE_DIR / "users.json"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

user_states = {}
active_bots = {}
profit_messages = {}

# ============================================
# IMAGE DOWNLOAD
# ============================================

IMAGE_URLS = {
    "profit.png": "https://t3.ftcdn.net/jpg/03/76/73/94/360_F_376739477_RzVTIqh9QmtkqBlIGD3HTOW7K3q3ZEuq.jpg",
    "wingo.png": "https://images.seeklogo.com/logo-png/42/1/wingo-logo-png_seeklogo-428333.png",
    "game51.png": "https://cdn.aptoide.com/imgs/5/6/5/56557ac7b64f397687e07dbbdc013e7b_icon.png",
    "jaiclub.png": "http://jaiclubgame.cc/wp-content/uploads/2026/04/Jai-Club-logo-with-golden-details-2.webp",
    "target.png": "https://omahacharts.com/wp-content/uploads/2018/12/target.png",
}

def download_images():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    for fname, url in IMAGE_URLS.items():
        fpath = IMAGES_DIR / fname
        if not fpath.exists():
            try:
                urllib.request.urlretrieve(url, str(fpath))
                logger.info(f"Downloaded: {fname}")
            except Exception as e:
                logger.warning(f"Failed to download {fname}: {e}")

download_images()

# ============================================
# HELPERS
# ============================================

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

def img(name):
    p = IMAGES_DIR / name
    return str(p) if p.exists() else None

def box(title, body):
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  <b>{title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{body}"
    )

# ============================================
# KEYBOARDS
# ============================================

def platform_select_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 JAI CLUB", callback_data="platform_jai")],
        [InlineKeyboardButton(text="🎯 51GAME", callback_data="platform_51")],
    ])

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="▶ START", callback_data="start_bot"),
            InlineKeyboardButton(text="📊 STATUS", callback_data="status"),
        ],
        [
            InlineKeyboardButton(text="💰 PROFIT", callback_data="profit"),
            InlineKeyboardButton(text="⚙ SETTINGS", callback_data="settings"),
        ],
        [
            InlineKeyboardButton(text="🎯 GAME", callback_data="game_select"),
            InlineKeyboardButton(text="🛑 STOP", callback_data="stop_bot"),
        ],
        [
            InlineKeyboardButton(text="🔄 SWITCH", callback_data="switch_platform"),
            InlineKeyboardButton(text="❓ HELP", callback_data="help"),
        ],
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")]
    ])

def game_menu_kb_jai():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ 30 SEC", callback_data="game_30s"),
            InlineKeyboardButton(text="🔥 1 MIN", callback_data="game_1m"),
        ],
        [InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")]
    ])

def game_menu_kb_51():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ 30 SEC", callback_data="game51_30"),
            InlineKeyboardButton(text="🔥 1 MIN", callback_data="game51_1m"),
        ],
        [
            InlineKeyboardButton(text="💎 3 MIN", callback_data="game51_3m"),
            InlineKeyboardButton(text="⭐ 5 MIN", callback_data="game51_5m"),
        ],
        [InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")]
    ])

def settings_kb(user_data):
    restart = "ON" if user_data.get("auto_restart", True) else "OFF"
    target = user_data.get("profit_target", 20)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔄 AUTO RESTART: {restart}", callback_data="toggle_restart")],
        [InlineKeyboardButton(text="💰 SET BET", callback_data="set_bet")],
        [InlineKeyboardButton(text="📈 SET MULTIPLIER", callback_data="set_multiplier")],
        [InlineKeyboardButton(text=f"🎯 PROFIT TARGET: {target}%", callback_data="set_target")],
        [InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")],
    ])

def stop_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ YES STOP", callback_data="confirm_stop"),
            InlineKeyboardButton(text="❌ NO CANCEL", callback_data="cancel_stop"),
        ]
    ])

# ============================================
# /start COMMAND - Platform Selection
# ============================================

@dp.message(CommandStart())
async def start_command(message: Message):
    user_id = message.from_user.id
    name = escape(message.from_user.first_name or "User")

    text = box("🎰 DUAL GAME AUTO BOT", (
        f"👋 Welcome, <b>{name}</b>!\n\n"
        "Choose Your Platform:\n\n"
        "🎰 <b>JAI CLUB</b> — WinGo 30S / 1M\n"
        "🎯 <b>51GAME</b> — WinGo 30S / 1M / 3M / 5M\n\n"
        "━━━ <b>Features</b> ━━━\n"
        "🤖 Auto Prediction\n"
        "💰 Dual Bet System\n"
        "📈 Level Staking\n"
        "🔄 Auto Restart\n"
        "📊 Live Profit Updates\n"
        "🖼️ Images & Reports\n\n"
        "<i>Select a platform to continue:</i>"
    ))

    image = img("profit.png")
    try:
        if image:
            await message.answer_photo(photo=InputMediaPhoto(media=open(image, "rb")), caption=text, reply_markup=platform_select_kb())
        else:
            await message.answer(text=text, reply_markup=platform_select_kb())
    except Exception:
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
        image_file = "jaiclub.png"
        text = box("🎰 JAI CLUB SELECTED", (
            "<b>Platform:</b> JAI Club / AR Lottery\n"
            "<b>Games:</b> WinGo 30 Second, 1 Minute\n"
            "<b>API:</b> jaiclubapi.com\n"
            "<b>Server:</b> ar-lottery06.com\n\n"
            "📊 <b>Auto Prediction</b> + <b>Dual Bet System</b>\n"
            "🎯 <b>Level Staking</b> + <b>Profit Target</b>\n\n"
            "🔐 Type <b>/login</b> to authenticate\n"
            "💰 Then enter balance to start bot"
        ))
    else:
        image_file = "game51.png"
        text = box("🎯 51GAME SELECTED", (
            "<b>Platform:</b> 51gamet.com\n"
            "<b>Games:</b> WinGo 30S, 1M, 3M, 5M\n"
            "<b>API:</b> api51gameapi.com\n\n"
            "🔐 Type <b>/login</b> to authenticate"
        ))

    image = img(image_file)
    try:
        if image:
            photo = InputMediaPhoto(media=open(image, "rb"), caption=text)
            await callback.message.edit_media(media=photo, reply_markup=main_menu_kb())
        else:
            await callback.message.edit_text(text=text, reply_markup=main_menu_kb())
    except Exception:
        try:
            await callback.message.edit_text(text=text, reply_markup=main_menu_kb())
        except Exception:
            pass

    await callback.answer(f"✅ {platform.upper()} selected!", show_alert=False)

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
        title = "🔐 JAI CLUB LOGIN"
        body = (
            "Enter your <b>username</b> and <b>password</b>:\n\n"
            "<code>username\npassword</code>\n\n"
            "<i>Example:</i>\n"
            "<code>919876543210\nmypassword123</code>"
        )
    else:
        title = "🔐 51GAME LOGIN"
        body = (
            "Enter your <b>phone number</b> and <b>password</b>:\n\n"
            "<code>phone\npassword</code>\n\n"
            "<i>Example:</i>\n"
            "<code>712813131819\nshiv1234</code>\n\n"
            "<i>Note: 91 prefix is auto-added</i>"
        )

    await message.answer(text=box(title, body))

# ============================================
# /stop COMMAND
# ============================================

@dp.message(Command("stop"))
async def stop_command(message: Message):
    user_id = message.from_user.id
    if user_id in active_bots:
        active_bots[user_id]["running"] = False

    await message.answer(
        text=box("🛑 BOT STOPPED", "Bot has been stopped.\nUse <b>/start</b> to restart."),
        reply_markup=main_menu_kb()
    )

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
            await message.answer(box("❌ FORMAT ERROR", "Send credentials in this format:\n<code>username\npassword</code>"))
            return

        username = lines[0].strip()
        password = lines[1].strip()

        user_data["login_user"] = username
        user_data["login_pass"] = password
        user_data["logged_in"] = True
        update_user(user_id, user_data)
        user_states[user_id] = "set_amount"

        platform_name = "JAI CLUB" if platform == "jai" else "51GAME"
        await message.answer(text=box("💰 SET BALANCE", (
            f"<b>Platform:</b> {platform_name}\n\n"
            "Enter your total balance:\n"
            "<i>Examples:</i> <code>1000</code>, <code>5000</code>, <code>10000</code>\n\n"
            "<i>Send the amount:</i>"
        )))
        return

    if state == "set_amount":
        try:
            amount = max(100, int(text))
            user_data["start_balance"] = amount
            update_user(user_id, user_data)
            user_states.pop(user_id, None)

            platform_name = "JAI CLUB" if platform == "jai" else "51GAME"
            await message.answer(
                text=box("✅ READY TO START", (
                    f"<b>Platform:</b> {platform_name}\n"
                    f"<b>Balance:</b> <code>₹{amount}</code>\n\n"
                    "🚀 Bot is starting..."
                )),
                reply_markup=main_menu_kb()
            )

            user_data = get_user(user_id)
            asyncio.create_task(run_betting(user_id, message.chat.id, user_data))
        except ValueError:
            await message.answer(box("❌ INVALID AMOUNT", "Enter a valid number.\nMinimum: <code>₹100</code>"))
        return

    if state == "set_bet":
        try:
            bet = max(2, int(text))
            user_data["total_bet"] = bet
            update_user(user_id, user_data)
            user_states.pop(user_id, None)
            await message.answer(
                text=box("✅ BET UPDATED", f"<b>Bet Amount:</b> <code>₹{bet}</code>"),
                reply_markup=main_menu_kb()
            )
        except ValueError:
            await message.answer(box("❌ INVALID", "Enter a valid number.\nMinimum: <code>2</code>"))
        return

    if state == "set_mult":
        try:
            mult = max(1.5, float(text))
            user_data["multiplier"] = mult
            update_user(user_id, user_data)
            user_states.pop(user_id, None)
            await message.answer(
                text=box("✅ MULTIPLIER UPDATED", f"<b>Multiplier:</b> <code>{mult}x</code>"),
                reply_markup=main_menu_kb()
            )
        except ValueError:
            await message.answer(box("❌ INVALID", "Enter a valid number.\nMinimum: <code>1.5</code>"))
        return

    if state == "set_target":
        try:
            target = max(5, min(500, float(text)))
            user_data["profit_target"] = target
            update_user(user_id, user_data)
            user_states.pop(user_id, None)
            await message.answer(
                text=box("✅ TARGET UPDATED", f"<b>Profit Target:</b> <code>{target}%</code>"),
                reply_markup=main_menu_kb()
            )
        except ValueError:
            await message.answer(box("❌ INVALID", "Enter a valid percentage.\nRange: <code>5</code> — <code>500</code>"))
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
        await callback.message.edit_text(
            text=box("📋 MAIN MENU", "Choose an option:"),
            reply_markup=main_menu_kb()
        )
        return

    if data == "switch_platform":
        await callback.message.edit_text(
            text=box("🔄 SWITCH PLATFORM", "Select a platform:"),
            reply_markup=platform_select_kb()
        )
        return

    if data == "start_bot":
        if not user_data.get("logged_in"):
            await callback.answer("❌ Login first! Send /login", show_alert=True)
            return
        if not user_data.get("start_balance"):
            user_states[user_id] = "set_amount"
            await callback.message.edit_text(
                text=box("💰 SET BALANCE", "Enter your total balance:\n<i>Example:</i> <code>5000</code>"),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")]])
            )
            return

        await callback.answer("🚀 Starting bot!", show_alert=False)
        platform_name = "JAI CLUB" if platform == "jai" else "51GAME"
        await callback.message.edit_text(
            text=box("✅ BOT STARTED", (
                f"<b>Platform:</b> {platform_name}\n\n"
                "📊 Live updates incoming!\n"
                "🛑 Send <b>/stop</b> to stop"
            )),
            reply_markup=main_menu_kb()
        )
        asyncio.create_task(run_betting(user_id, callback.message.chat.id, user_data))
        return

    if data == "status":
        bot_data = active_bots.get(user_id, {})
        running = "🟢 Running" if bot_data.get("running") else "🔴 Stopped"
        level = bot_data.get("level", 0)
        max_levels = len(bot_data.get("levels", [])) if bot_data.get("levels") else 0
        platform_name = "JAI CLUB" if platform == "jai" else "51GAME"

        await callback.message.edit_text(
            text=box("📊 BOT STATUS", (
                f"<b>Platform:</b> {platform_name}\n"
                f"<b>Status:</b> {running}\n"
                f"<b>Balance:</b> <code>₹{bot_data.get('balance', 0):.2f}</code>\n"
                f"<b>Profit:</b> <code>₹{bot_data.get('profit', 0):.2f}</code>\n"
                f"<b>Level:</b> <code>{level}/{max_levels}</code>"
            )),
            reply_markup=back_kb()
        )
        return

    if data == "profit":
        bot_data = active_bots.get(user_id, {})
        start = bot_data.get("start_balance", 0)
        curr = bot_data.get("balance", 0)
        profit = curr - start
        pct = ((profit / start) * 100) if start > 0 else 0
        emoji = "📈" if profit >= 0 else "📉"
        sign = "+" if profit >= 0 else ""

        target = user_data.get("profit_target", 20)
        target_status = "✅ REACHED!" if pct >= target else f"Target: {target}%"

        image = img("profit.png")
        text = box("💰 LIVE PROFIT", (
            f"{emoji} <b>Net Profit:</b> <code>{sign}₹{profit:.2f}</code>\n"
            f"📊 <b>Profit %:</b> <code>{sign}{pct:.1f}%</code>\n"
            f"🎯 <b>Target:</b> <code>{target_status}</code>\n\n"
            f"✅ <b>Wins:</b> <code>{bot_data.get('double_win', 0)}</code>\n"
            f"❌ <b>Losses:</b> <code>{bot_data.get('double_loss', 0)}</code>\n"
            f"📊 <b>Level:</b> <code>{bot_data.get('level', 0)}</code>"
        ))

        try:
            if image:
                photo = InputMediaPhoto(media=open(image, "rb"), caption=text)
                await callback.message.edit_media(media=photo, reply_markup=back_kb())
            else:
                await callback.message.edit_text(text=text, reply_markup=back_kb())
        except Exception:
            try:
                await callback.message.edit_text(text=text, reply_markup=back_kb())
            except Exception:
                pass
        return

    if data == "game_select":
        if platform == "jai":
            image = img("wingo.png")
            text = box("🎮 JAI CLUB GAMES", "Select game type:")
            kb = game_menu_kb_jai()
        else:
            image = img("wingo.png")
            text = box("🎮 51GAME GAMES", "Select game type:")
            kb = game_menu_kb_51()

        try:
            if image:
                photo = InputMediaPhoto(media=open(image, "rb"), caption=text)
                await callback.message.edit_media(media=photo, reply_markup=kb)
            else:
                await callback.message.edit_text(text=text, reply_markup=kb)
        except Exception:
            await callback.message.edit_text(text=text, reply_markup=kb)
        return

    if data in ["game_30s", "game_1m"]:
        game = "WinGo_30S" if data == "game_30s" else "WinGo_1M"
        user_data["game"] = game
        update_user(user_id, user_data)
        await callback.answer(f"✅ Game: {game}", show_alert=False)
        await callback.message.edit_text(
            text=box("✅ GAME SELECTED", f"<b>Game:</b> {game}"),
            reply_markup=main_menu_kb()
        )
        return

    if data.startswith("game51_"):
        game_map = {"game51_30": 30, "game51_1m": 1, "game51_3m": 2, "game51_5m": 3}
        type_id = game_map.get(data, 30)
        user_data["game51_type_id"] = type_id
        update_user(user_id, user_data)
        names = {30: "30 SEC", 1: "1 MIN", 2: "3 MIN", 3: "5 MIN"}
        await callback.answer(f"✅ Game: WinGo {names.get(type_id, '30S')}", show_alert=False)
        await callback.message.edit_text(
            text=box("✅ GAME SELECTED", f"<b>Game:</b> WinGo {names.get(type_id, '30S')}"),
            reply_markup=main_menu_kb()
        )
        return

    if data == "stop_bot":
        await callback.message.edit_text(
            text=box("🛑 STOP BOT?", "Are you sure you want to stop?"),
            reply_markup=stop_confirm_kb()
        )
        return

    if data == "confirm_stop":
        if user_id in active_bots:
            active_bots[user_id]["running"] = False
        await callback.answer("🛑 Bot stopped!", show_alert=True)
        await callback.message.edit_text(
            text=box("🛑 BOT STOPPED", "Bot has been stopped.\nUse <b>/start</b> to restart."),
            reply_markup=main_menu_kb()
        )
        return

    if data == "cancel_stop":
        await callback.answer("✅ Bot is still running!", show_alert=False)
        await callback.message.edit_text(
            text=box("✅ BOT RUNNING", "Bot continues to run."),
            reply_markup=main_menu_kb()
        )
        return

    if data == "settings":
        await callback.message.edit_text(
            text=box("⚙ SETTINGS", "Adjust bot settings:"),
            reply_markup=settings_kb(user_data)
        )
        return

    if data == "toggle_restart":
        user_data["auto_restart"] = not user_data.get("auto_restart", True)
        update_user(user_id, user_data)
        status = "ON" if user_data["auto_restart"] else "OFF"
        await callback.answer(f"✅ Auto Restart: {status}", show_alert=False)
        await callback.message.edit_text(
            text=box("⚙ SETTINGS", f"<b>Auto Restart:</b> {status}"),
            reply_markup=settings_kb(user_data)
        )
        return

    if data == "set_bet":
        user_states[user_id] = "set_bet"
        await callback.message.edit_text(
            text=box("💰 SET BET AMOUNT", "Enter bet amount (min: <code>2</code>):"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")]])
        )
        return

    if data == "set_multiplier":
        user_states[user_id] = "set_mult"
        await callback.message.edit_text(
            text=box("📈 SET MULTIPLIER", "Enter multiplier (min: <code>1.5</code>):"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")]])
        )
        return

    if data == "set_target":
        user_states[user_id] = "set_target"
        await callback.message.edit_text(
            text=box("🎯 SET PROFIT TARGET", "Enter target profit % (5 — 500):"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")]])
        )
        return

    if data == "help":
        await callback.message.edit_text(
            text=box("❓ HELP", (
                "<b>Commands:</b>\n"
                "/start — Start bot & select platform\n"
                "/login — Login with credentials\n"
                "/status — Check bot status\n"
                "/stop — Stop bot\n"
                "/help — Show this help\n\n"
                "<b>How it works:</b>\n"
                "1️⃣ Choose platform\n"
                "2️⃣ Login with credentials\n"
                "3️⃣ Set balance & start!\n"
                "4️⃣ Watch live profit updates!\n\n"
                "<b>Platforms:</b>\n"
                "🎰 JAI CLUB — WinGo 30S/1M\n"
                "🎯 51GAME — WinGo 30S/1M/3M/5M\n\n"
                "<b>Profit Target:</b>\n"
                "Set a target % in Settings.\n"
                "Bot will celebrate when reached! 🎉"
            )),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")]])
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
    profit_target = user_data.get("profit_target", 20)

    msg = await bot.send_message(chat_id, box("⏳ JAI CLUB", "Logging in..."), reply_markup=main_menu_kb())
    profit_messages[user_id] = msg.message_id

    try:
        engine = AutoBetEngine(username, password, game, total_bet, multiplier, 55)
        engine.checker.lottery_api_base_url = "https://h5.ar-lottery06.com"
        engine.checker.lottery_draw_base_url = "https://draw.ar-lottery06.com"
        engine.login()
        engine.checker.fetch_ar_token(game)
    except Exception as e:
        await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=box("❌ LOGIN FAILED", str(e)))
        return

    engine.start_balance = start_balance
    engine.current_balance = start_balance
    engine.levels = make_levels(start_balance, total_bet, multiplier)

    logger.info(f"JAI CLUB engine ready: game={game} balance={start_balance} levels={len(engine.levels)} draw_url={engine.checker.lottery_draw_base_url}")

    bot_state = {
        "running": True, "start_balance": start_balance, "balance": start_balance,
        "profit": 0, "total_won": 0, "total_lost": 0, "wins": 0, "losses": 0,
        "double_win": 0, "double_loss": 0, "level": 0, "pending": None, "last_seen_period": None,
        "target_hit": False, "profit_target": profit_target
    }
    active_bots[user_id] = bot_state
    await update_profit_msg(user_id, chat_id, bot_state, "RUNNING", "JAI CLUB")

    while bot_state["running"]:
        try:
            data = engine.fetch_draw_history(6)
            if not data:
                logger.warning("No draw history returned, retrying...")
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

                    # Check profit target
                    pct = ((bot_state["profit"] / bot_state["start_balance"]) * 100) if bot_state["start_balance"] > 0 else 0
                    if pct >= profit_target and not bot_state["target_hit"]:
                        bot_state["target_hit"] = True
                        try:
                            target_img = img("target.png")
                            target_text = box("🎉🎉🎉 TARGET REACHED! 🎉🎉🎉", (
                                f"🎯 <b>Target:</b> <code>{profit_target}%</code> ✅\n"
                                f"💰 <b>Profit:</b> <code>+₹{bot_state['profit']:.2f}</code>\n"
                                f"📈 <b>Profit %:</b> <code>+{pct:.1f}%</code>\n\n"
                                "Congratulations! Keep going or stop with /stop"
                            ))
                            if target_img:
                                with open(target_img, "rb") as tf:
                                    await bot.send_photo(chat_id, photo=tf, caption=target_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                        [InlineKeyboardButton(text="🛑 STOP BOT", callback_data="confirm_stop")],
                                        [InlineKeyboardButton(text="▶ CONTINUE", callback_data="back_menu")]
                                    ]))
                            else:
                                await bot.send_message(chat_id, target_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text="🛑 STOP BOT", callback_data="confirm_stop")],
                                    [InlineKeyboardButton(text="▶ CONTINUE", callback_data="back_menu")]
                                ]))
                        except Exception as e:
                            logger.error(f"Target celebration error: {e}")

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
                    logger.info(f"Bet placed: issue={open_issue} bs={bs_pred} color={co_pred} L{lv['level']}")
                    await update_profit_msg(user_id, chat_id, bot_state, "WAITING", "JAI CLUB")
                except Exception as e:
                    logger.error(f"Bet failed on {open_issue}: {e}")
            else:
                logger.warning("No open issue found, skipping round")
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
    profit_target = user_data.get("profit_target", 20)

    msg = await bot.send_message(chat_id, box("⏳ 51GAME", "Logging in..."), reply_markup=main_menu_kb())
    profit_messages[user_id] = msg.message_id

    checker = Game51AccountChecker(username, password)
    try:
        if not checker.perform_login():
            await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
                text=box("❌ LOGIN FAILED", checker.message))
            return
    except Exception as e:
        await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
            text=box("❌ LOGIN FAILED", str(e)))
        return

    balance = checker.get_balance()
    if balance <= 0:
        balance = start_balance

    game_names = {30: "30 SEC", 1: "1 MIN", 2: "3 MIN", 3: "5 MIN"}
    game_name = game_names.get(type_id, "30 SEC")

    bot_state = {
        "running": True, "start_balance": balance, "balance": balance,
        "profit": 0, "total_won": 0, "total_lost": 0, "wins": 0, "losses": 0,
        "double_win": 0, "double_loss": 0, "level": 0, "pending": None, "last_seen_period": None,
        "target_hit": False, "profit_target": profit_target
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

                    # Check profit target
                    pct = ((bot_state["profit"] / bot_state["start_balance"]) * 100) if bot_state["start_balance"] > 0 else 0
                    if pct >= profit_target and not bot_state["target_hit"]:
                        bot_state["target_hit"] = True
                        try:
                            target_img = img("target.png")
                            target_text = box("🎉🎉🎉 TARGET REACHED! 🎉🎉🎉", (
                                f"🎯 <b>Target:</b> <code>{profit_target}%</code> ✅\n"
                                f"💰 <b>Profit:</b> <code>+₹{bot_state['profit']:.2f}</code>\n"
                                f"📈 <b>Profit %:</b> <code>+{pct:.1f}%</code>\n\n"
                                "Congratulations! Keep going or stop with /stop"
                            ))
                            if target_img:
                                with open(target_img, "rb") as tf:
                                    await bot.send_photo(chat_id, photo=tf, caption=target_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                        [InlineKeyboardButton(text="🛑 STOP BOT", callback_data="confirm_stop")],
                                        [InlineKeyboardButton(text="▶ CONTINUE", callback_data="back_menu")]
                                    ]))
                            else:
                                await bot.send_message(chat_id, target_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text="🛑 STOP BOT", callback_data="confirm_stop")],
                                    [InlineKeyboardButton(text="▶ CONTINUE", callback_data="back_menu")]
                                ]))
                        except Exception as e:
                            logger.error(f"Target celebration error: {e}")

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
    target = bot_state.get("profit_target", 20)

    if status == "RUNNING":
        s_emoji, s_text = "🟢", "Running"
    elif status == "WAITING":
        s_emoji, s_text = "⏳", "Waiting"
    elif status == "STOPPED":
        s_emoji, s_text = "🔴", "Stopped"
    elif "WIN" in status:
        s_emoji, s_text = "🏆", status
    elif "LOSS" in status:
        s_emoji, s_text = "💔", status
    else:
        s_emoji, s_text = "⚡", status

    p_emoji = "📈" if profit >= 0 else "📉"
    sign = "+" if profit >= 0 else ""
    target_indicator = f"✅ {target}%" if pct >= target else f"⏳ {target}%"

    return box(f"💰 {platform} PROFIT", (
        f"{s_emoji} <b>Status:</b> {s_text}\n\n"
        f"{p_emoji} <b>Net Profit:</b> <code>{sign}₹{profit:.2f}</code>\n"
        f"📊 <b>Profit %:</b> <code>{sign}{pct:.1f}%</code>\n"
        f"🎯 <b>Target:</b> <code>{target_indicator}</code>\n\n"
        f"✅ <b>Wins:</b> <code>{bot_state.get('wins', 0)}</code>  |  ❌ <b>Losses:</b> <code>{bot_state.get('losses', 0)}</code>\n"
        f"🏆 <b>Double Win:</b> <code>{bot_state.get('double_win', 0)}</code>  |  💔 <b>Double Loss:</b> <code>{bot_state.get('double_loss', 0)}</code>\n\n"
        f"📊 <b>Level:</b> <code>{bot_state.get('level', 0)}</code>\n"
        f"💰 <b>Won:</b> <code>₹{bot_state.get('total_won', 0):.2f}</code>  |  🪙 <b>Lost:</b> <code>₹{bot_state.get('total_lost', 0):.2f}</code>\n\n"
        f"🕐 <i>{datetime.now().strftime('%H:%M:%S')}</i>"
    ))

# ============================================
# BOT START
# ============================================

async def main():
    print("🤖 DUAL GAME BOT STARTED!")
    print("   🎮 JAI CLUB + 🎯 51GAME")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
