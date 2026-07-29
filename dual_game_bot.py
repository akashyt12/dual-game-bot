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
from datetime import datetime
from pathlib import Path
from html import escape

sys.path.insert(0, str(Path(__file__).parent))
from JAI_CLUB_BOT import AccountChecker as JAIChecker, AutoBetEngine, GAME_CODES, make_levels, predict_bs as jai_predict_bs, predict_color as jai_predict_color
from game51_checker import Game51AccountChecker, predict_bs as game51_predict_bs, predict_color as game51_predict_color, result_to_bs, result_to_color
from bdgwin_checker import BDGWinAccountChecker, predict_bs as bdgwin_predict_bs, predict_color as bdgwin_predict_color

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
IMAGES_DIR = Path(__file__).parent / "images"

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
        [InlineKeyboardButton(text="?? JAI CLUB", callback_data="platform_jai")],
        [InlineKeyboardButton(text="?? 51GAME", callback_data="platform_51")],
        [InlineKeyboardButton(text="?? BDGWIN", callback_data="platform_bdgwin")],
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
            InlineKeyboardButton(text="? 30 SEC", callback_data="game51_30"),
            InlineKeyboardButton(text="?? 1 MIN", callback_data="game51_1m"),
        ],
        [
            InlineKeyboardButton(text="?? 3 MIN", callback_data="game51_3m"),
            InlineKeyboardButton(text="? 5 MIN", callback_data="game51_5m"),
        ],
        [InlineKeyboardButton(text="? BACK", callback_data="back_menu")]
    ])

def game_menu_kb_bdgwin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="? 30 SEC", callback_data="bdgwin_30s"),
            InlineKeyboardButton(text="?? 1 MIN", callback_data="bdgwin_1m"),
        ],
        [
            InlineKeyboardButton(text="?? 3 MIN", callback_data="bdgwin_3m"),
            InlineKeyboardButton(text="? 5 MIN", callback_data="bdgwin_5m"),
        ],
        [
            InlineKeyboardButton(text="?? 10 MIN", callback_data="bdgwin_10m"),
        ],
        [InlineKeyboardButton(text="? BACK", callback_data="back_menu")]
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

    text = box("🎰 𝐃𝐔𝐀𝐋 𝐆𝐀𝐌𝐄 𝐀𝐔𝐓𝐎 𝐁𝐄𝐓", (
        f"👋 Wᴇʟᴄᴏᴍᴇ, <b>{name}</b>!\n\n"
        "Choose Your Platform:\n\n"
        "🎰 <b>𝗝𝗔𝗜 𝗖𝗟𝗨𝗕</b> — WinGo 30S / 1M\n"
        "🎯 <b>51𝗚𝗔𝗠𝗘</b> — WinGo 30S / 1M / 3M / 5M\n\n"
        "━━━ <b>Features</b> ━━━\n"
        "🤖 Auto Prediction\n"
        "💰 Dual Bet System\n"
        "📈 Level Staking\n"
        "🔄 Auto Restart\n"
        "📊 Live Profit Updates\n"
        "🖼️ Images & Reports\n\n"
        "<i>Select a platform to continue:</i>"
    ))

    image = img("profit.jpg")
    try:
        if image:
            await message.answer_photo(photo=open(image, "rb"), caption=text, reply_markup=platform_select_kb())
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
        image_file = "jaiclub.webp"
        text = box("🎰 𝗝𝗔𝗜 𝗖𝗟𝗨𝗕 SELECTED", (
            "<b>Platform:</b> JAI Club / AR Lottery\n"
            "<b>Games:</b> WinGo 30 Second, 1 Minute\n"
            "<b>API:</b> jaiclubapi.com\n"
            "<b>Server:</b> ar-lottery06.com\n\n"
            "📊 <b>Auto Prediction</b> + <b>Dual Bet System</b>\n"
            "🎯 <b>Level Staking</b> + <b>Profit Target</b>\n\n"
            "🔐 Type <b>/login</b> to authenticate\n"
            "💰 Then enter balance to start bot"
        ))
    elif platform == "bdgwin":
        image_file = None
        text = box("🔵 𝗕𝗗𝗚𝗪𝗜𝗡 SELECTED", (
            "<b>Platform:</b> bdgwin79.com\n"
            "<b>Games:</b> WinGo 30S, 1M, 3M, 5M, 10M\n"
            "<b>API:</b> api.bdg88zf.com\n"
            "<b>Server:</b> ar-lottery01.com\n\n"
            "📊 <b>Auto Prediction</b> + <b>Dual Bet System</b>\n"
            "🎯 <b>Level Staking</b> + <b>Profit Target</b>\n\n"
            "🔐 Type <b>/login</b> to authenticate\n"
            "💰 Then enter balance to start bot"
        ))
    else:
        image_file = None
        text = box("🎯 51𝗚𝗠𝗔𝗘 SELECTED", (
            "<b>Platform:</b> 51gamet.com\n"
            "<b>Games:</b> WinGo 30S, 1M, 3M, 5M\n"
            "<b>API:</b> api51gameapi.com\n\n"
            "🔐 Type <b>/login</b> to authenticate"
        ))

    image = img(image_file)
    try:
        await callback.message.delete()
    except Exception:
        pass
    try:
        if image:
            await callback.message.answer_photo(
                photo=open(image, "rb"),
                caption=text,
                reply_markup=main_menu_kb()
            )
        else:
            await callback.message.answer(text=text, reply_markup=main_menu_kb())
    except Exception:
        await callback.message.answer(text=text, reply_markup=main_menu_kb())

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
        title = "🔐 𝗝𝗔𝗜 𝗖𝗟𝗨𝗕 𝗟𝗢𝗚𝗜𝗡"
        body = (
            "𝖤𝗇𝗍𝖾𝗋 𝗒𝗈𝗎𝗋 <b>𝗎𝗌𝖾𝗋𝗇𝖺𝗆𝖾</b> 𝖺𝗇𝖽 <b>𝗉𝖺𝗌𝗌𝗐𝗈𝗋𝖽</b>:\n\n"
            "<code>username\npassword</code>\n\n"
            "<i>Example:</i>\n"
            "<code>919876543210\nmypassword123</code>"
        )
    elif platform == "bdgwin":
        title = "🔐 𝗕𝗗𝗚𝗪𝗜𝗡 𝗟𝗢𝗚𝗜𝗡"
        body = (
            "Enter your <b>phone number</b> and <b>password</b>:\n\n"
            "<code>phone\npassword</code>\n\n"
            "<i>Example:</i>\n"
            "<code>7441528680\nloveop902x</code>\n\n"
            "<i>Note: 91 prefix is auto-added</i>"
        )
    else:
        title = "🔐 51𝗚𝗔𝗠𝗘 𝗟𝗢𝗚𝗜𝗡"
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

        platform_name = "JAI CLUB" if platform == "jai" else ("BDGWIN" if platform == "bdgwin" else "51GAME")
        await message.answer(text=box("💰 SET BALANCE", (
            f"<b>Platform:</b> {platform_name}\n\n"
            "𝗘𝗻𝘁𝗲𝗿 𝘆𝗼𝘂𝗿 𝘁𝗼𝘁𝗮𝗹 𝗯𝗮𝗹𝗮𝗻𝗰𝗲:\n"
            "<i>Examples:</i> <code>1000</code>, <code>5000</code>, <code>10000</code>\n\n"
            "<i>S𝘦𝗍 𝗍𝗁𝖾 𝖺𝗆𝗈𝗎𝗇𝗍:</i>"
        )))
        return

    if state == "set_amount":
        try:
            amount = max(100, int(text))
            user_data["start_balance"] = amount
            update_user(user_id, user_data)
            user_states.pop(user_id, None)

            platform_name = "JAI CLUB" if platform == "jai" else ("BDGWIN" if platform == "bdgwin" else "51GAME")
            await message.answer(
                text=box("✅ READY TO START", (
                    f"<b>Platform:</b> {platform_name}\n"
                    f"<b>Balance:</b> <code>₹{amount}</code>\n\n"
                    "🚀 Bᴏᴛ ɪs ʀᴜɴɴɪɴɢ..."
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
            text=box("📋 𝗠𝗔𝗜𝗡 𝗠𝗘𝗡𝗨", "Cʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ:"),
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
            await callback.answer("❌ Lᴏɢɪɴ ғɪʀsᴛ! Send /login", show_alert=True)
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
            text=box("✅ 𝐁𝐎𝐓 𝐒𝐓𝐀𝐑𝐓𝐄𝐃", (
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
            text=box("📊 𝗕𝗢𝗧 𝗦𝗧𝗔𝗧𝗨𝗦", (
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

        image = img("profit.jpg")
        text = box("💰 𝗟𝗜𝗩𝗘 𝗣𝗥𝗢𝗙𝗜𝗧", (
            f"{emoji} <b>Net Profit:</b> <code>{sign}₹{profit:.2f}</code>\n"
            f"📊 <b>Profit %:</b> <code>{sign}{pct:.1f}%</code>\n"
            f"🎯 <b>Target:</b> <code>{target_status}</code>\n\n"
            f"✅ <b>Wins:</b> <code>{bot_data.get('double_win', 0)}</code>\n"
            f"❌ <b>Losses:</b> <code>{bot_data.get('double_loss', 0)}</code>\n"
            f"📊 <b>Level:</b> <code>{bot_data.get('level', 0)}</code>"
        ))

        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            if image:
                await callback.message.answer_photo(
                    photo=open(image, "rb"),
                    caption=text,
                    reply_markup=back_kb()
                )
            else:
                await callback.message.answer(text=text, reply_markup=back_kb())
        except Exception:
            await callback.message.answer(text=text, reply_markup=back_kb())
        return

    if data == "game_select":
        if platform == "jai":
            text = box("🎮 JAI CLUB GAMES", "Select game type:")
            kb = game_menu_kb_jai()
        elif platform == "bdgwin":
            text = box("🎮 BDGWIN GAMES", "Select game type:")
            kb = game_menu_kb_bdgwin()
        else:
            text = box("🎮 51GAME GAMES", "Select game type:")
            kb = game_menu_kb_51()

        try:
            await callback.message.edit_text(text=text, reply_markup=kb)
        except Exception:
            pass
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

    if data.startswith("bdgwin_"):
        bdgwin_game_map = {
            "bdgwin_30s": "WinGo_30S",
            "bdgwin_1m": "WinGo_1M",
            "bdgwin_3m": "WinGo_3M",
            "bdgwin_5m": "WinGo_5M",
            "bdgwin_10m": "WinGo_10M"
        }
        game = bdgwin_game_map.get(data, "WinGo_30S")
        user_data["bdgwin_game"] = game
        update_user(user_id, user_data)
        names = {"WinGo_30S": "30 SEC", "WinGo_1M": "1 MIN", "WinGo_3M": "3 MIN", "WinGo_5M": "5 MIN", "WinGo_10M": "10 MIN"}
        await callback.answer(f"✅ Game: WinGo {names.get(game, '30S')}", show_alert=False)
        await callback.message.edit_text(
            text=box("✅ GAME SELECTED", f"<b>Game:</b> WinGo {names.get(game, '30S')}"),
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
            text=box("⚙ 𝗦𝗘𝗧𝗧𝗜𝗡𝗚𝗦", "Adjust bot settings:"),
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
            text=box("💰 𝗦𝗘𝗧 𝗕𝗘𝗧 𝗔𝗠𝗢𝗨𝗡𝗧", "Enter bet amount (min: <code>2</code>):"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")]])
        )
        return

    if data == "set_multiplier":
        user_states[user_id] = "set_mult"
        await callback.message.edit_text(
            text=box("📈 𝗦𝗘𝗧 𝗠𝗨𝗟𝗧𝗜𝗣𝗟𝗜𝗘𝗥", "Enter multiplier (min: <code>1.5</code>):"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")]])
        )
        return

    if data == "set_target":
        user_states[user_id] = "set_target"
        await callback.message.edit_text(
            text=box("🎯 𝗦𝗘𝗧 𝗣𝗥𝗢𝗙𝗜𝗧 𝗧𝗔𝗥𝗚𝗘𝗧", "Enter target profit % (5 — 500):"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")]])
        )
        return

    if data == "help":
        await callback.message.edit_text(
            text=box("❓ 𝗛𝗘𝗟𝗣", (
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
                            target_text = box("🎉🎉🎉 TARGET REACHED! 🎉🎉🎉", (
                                f"🎯 <b>Target:</b> <code>{profit_target}%</code> ✅\n"
                                f"💰 <b>Profit:</b> <code>+₹{bot_state['profit']:.2f}</code>\n"
                                f"📈 <b>Profit %:</b> <code>+{pct:.1f}%</code>\n\n"
                                "Congratulations! Keep going or stop with /stop"
                            ))
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
                            target_text = box("🎉🎉🎉 TARGET REACHED! 🎉🎉🎉", (
                                f"🎯 <b>Target:</b> <code>{profit_target}%</code> ✅\n"
                                f"💰 <b>Profit:</b> <code>+₹{bot_state['profit']:.2f}</code>\n"
                                f"📈 <b>Profit %:</b> <code>+{pct:.1f}%</code>\n\n"
                                "Congratulations! Keep going or stop with /stop"
                            ))
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
# RUN BETTING - BDGWIN
# ============================================

async def run_betting_bdgwin(user_id, chat_id, user_data):
    username = user_data.get("login_user", "")
    password = user_data.get("login_pass", "")
    game = user_data.get("bdgwin_game", "WinGo_30S")
    total_bet = user_data.get("total_bet", 2)
    multiplier = user_data.get("multiplier", 2.0)
    start_balance = user_data.get("start_balance", 1000)

    game_names = {
        "WinGo_30S": "30 SEC", "WinGo_1M": "1 MIN", "WinGo_3M": "3 MIN",
        "WinGo_5M": "5 MIN", "WinGo_10M": "10 MIN"
    }
    game_name = game_names.get(game, "30S")

    bot_state = {
        "running": True, "wins": 0, "losses": 0, "break_even": 0,
        "double_win": 0, "double_loss": 0, "level": 0,
        "total_won": 0, "total_lost": 0, "profit": 0,
        "start_balance": start_balance, "current_balance": start_balance,
        "pending": None, "history": [], "game": game, "game_name": game_name
    }

    try:
        checker = BDGWinAccountChecker(username, password)
        if not checker.perform_login():
            await message.answer(text=box("❌ LOGIN FAILED", f"Error: {checker.message}"))
            return
        
        checker.fetch_user_info()
        ud = checker.user_info
        balance = None
        for key in ("amount", "balance", "money", "coin", "points"):
            if key in ud:
                try:
                    bal = float(ud[key])
                    if bal > 0:
                        balance = bal
                        break
                except:
                    pass
        
        if balance is not None and balance > 0:
            bot_state["start_balance"] = balance
            bot_state["current_balance"] = balance
            start_balance = balance

        try:
            checker.fetch_ar_token(game)
        except:
            pass

        levels = make_levels(start_balance, total_bet, multiplier)
        current_level = 0

        profit_msg = await bot.send_message(
            chat_id=chat_id,
            text=format_profit(bot_state, "RUNNING", f"BDGWIN {game_name}"),
            reply_markup=main_menu_kb()
        )
        profit_messages[user_id] = profit_msg.message_id

        last_seen = None

        while bot_state["running"] and user_id in active_bots:
            try:
                draw_urls = ["https://draw.ar-lottery06.com", checker.lottery_draw_base_url]
                issues = []
                for base in draw_urls:
                    try:
                        url = f"{base}/WinGo/{game}/GetHistoryIssuePage.json?pageSize=6&ts={int(time.time()*1000)}"
                        resp = requests.get(url, timeout=6, verify=False, headers={"User-Agent": "Mozilla/5.0"})
                        data = resp.json()
                        if data.get("code") == 0:
                            issues = data["data"]["list"]
                            issues.sort(key=lambda x: x["issueNumber"], reverse=True)
                            break
                    except:
                        continue

                if not issues:
                    await asyncio.sleep(1)
                    continue

                latest = str(issues[0]["issueNumber"])
                if latest == last_seen:
                    await asyncio.sleep(1)
                    continue

                last_seen = latest
                nums = [int(x["number"]) for x in issues[:6]]
                actual_num = nums[0]

                if bot_state["pending"]:
                    pending = bot_state["pending"]
                    if str(pending["period"]) == str(latest):
                        actual_bs = "BIG" if actual_num >= 5 else "SMALL"
                        actual_color = "GREEN" if actual_num in GREEN_NUMS else "RED"
                        bs_hit = pending["bs_pred"] == actual_bs
                        color_hit = pending["color_pred"] == actual_color

                        if bs_hit and color_hit:
                            result = "DOUBLE WIN"
                            bot_state["double_win"] += 1
                            current_level = 0
                            bot_state["wins"] += 1
                        elif bs_hit or color_hit:
                            result = "BREAK EVEN"
                            bot_state["break_even"] += 1
                        else:
                            result = "DOUBLE LOSS"
                            bot_state["double_loss"] += 1
                            current_level += 1
                            bot_state["losses"] += 1
                            if current_level >= len(levels):
                                bot_state["running"] = False

                        bot_state["level"] = current_level
                        bot_state["pending"] = None

                        try:
                            checker.fetch_user_info()
                            ud2 = checker.user_info
                            for key in ("amount", "balance", "money", "coin", "points"):
                                if key in ud2:
                                    try:
                                        bot_state["current_balance"] = float(ud2[key])
                                        break
                                    except:
                                        pass
                            bot_state["profit"] = bot_state["current_balance"] - start_balance
                        except:
                            pass

                        await update_profit_msg(user_id, chat_id, bot_state, result, f"BDGWIN {game_name}")
                        await asyncio.sleep(1)
                        continue

                pattern_bs = [("B" if n >= 5 else "S") for n in reversed(nums)]
                pattern_co = [("G" if n in GREEN_NUMS else "R") for n in reversed(nums)]
                bs_pred, _ = bdgwin_predict_bs(pattern_bs)
                co_pred, _ = bdgwin_predict_color(pattern_co)

                if current_level < len(levels):
                    lv = levels[current_level]
                    bs_content = f"BigSmall_{bs_pred.capitalize()}"
                    co_content = f"Color_{co_pred.capitalize()}"

                    # Calculate next issue
                    prefix = latest[:-3]
                    num = int(latest[-3:]) + 1
                    next_issue = f"{prefix}{num:03d}"

                    try:
                        checker.place_wingo_bet(next_issue, lv["bs_bet"], 1, bs_content, game)
                        checker.place_wingo_bet(next_issue, lv["color_bet"], 1, co_content, game)
                        
                        bot_state["pending"] = {
                            "period": next_issue, "bs_pred": bs_pred, "color_pred": co_pred,
                            "bs_bet": lv["bs_bet"], "color_bet": lv["color_bet"]
                        }
                    except Exception as e:
                        if "settled" not in str(e).lower():
                            logger.error(f"BDGWin bet error: {e}")

                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"BDGWin loop error: {e}")
                await asyncio.sleep(3)

    except Exception as e:
        logger.error(f"BDGWin betting error: {e}")
        await bot.send_message(chat_id=chat_id, text=box("❌ ERROR", str(e)))

    if user_id in active_bots:
        del active_bots[user_id]
    if user_id in profit_messages:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=profit_messages[user_id],
                text=format_profit(bot_state, "STOPPED", f"BDGWIN {game_name}"), reply_markup=main_menu_kb())
        except:
            pass

# ============================================
# RUN BETTING - ROUTER
# ============================================

async def run_betting(user_id, chat_id, user_data):
    platform = user_data.get("platform", "jai")
    if platform == "51":
        await run_betting_51(user_id, chat_id, user_data)
    elif platform == "bdgwin":
        await run_betting_bdgwin(user_id, chat_id, user_data)
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
        s_emoji, s_text = "🟢", "𝗥𝘂𝗻𝗻𝗶𝗻𝗴"
    elif status == "WAITING":
        s_emoji, s_text = "⏳", "𝗪𝗮𝗶𝘁𝗶𝗻𝗴"
    elif status == "STOPPED":
        s_emoji, s_text = "🔴", "𝗦𝘁𝗼𝗽𝗽𝗲𝗱"
    elif "WIN" in status:
        s_emoji, s_text = "🏆", status
    elif "LOSS" in status:
        s_emoji, s_text = "💔", status
    else:
        s_emoji, s_text = "⚡", status

    p_emoji = "📈" if profit >= 0 else "📉"
    sign = "+" if profit >= 0 else ""
    target_indicator = f"✅ {target}%" if pct >= target else f"⏳ {target}%"

    return box(f"💰 {platform} 𝗣𝗥𝗢𝗙𝗜𝗧", (
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

