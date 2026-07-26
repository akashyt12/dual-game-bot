#!/usr/bin/env python3
"""PREDICTOR 2.0 - Dual Game Bot | Creator: Lord Senku | Play At Own Risk"""

import os, sys, json, asyncio, logging, random, time, threading
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
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile

BOT_TOKEN = "8641246132:AAEK0413rOwM4LYeHQJ0_dQ4gQ_ENncYbDc"
ADMIN_USERNAME = "lord_x_stylo"
BOT_VERSION = "Predictor 2.0"
CREATOR = "Lord Senku"
IMAGES_DIR = Path(__file__).parent / "images"
BASE_DIR = Path("/home/akash/mimo-test")
USERS_FILE = BASE_DIR / "users.json"
CHANNELS_FILE = BASE_DIR / "channels.json"
KEYS_FILE = BASE_DIR / "premium_keys.json"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

REFERRAL_POINTS = 50
REQUIRED_POINTS = 100

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

_user_lock = threading.Lock()
_user_states = {}
_active_bots = {}
_profit_messages = {}
_rate_limits = {}
_last_bot_msg = {}
_pending_referrals = {}

# ============================================
# STORAGE
# ============================================
def _load_json(path):
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return {}

def _save_json(path, data):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)

def get_user(user_id):
    with _user_lock:
        users = _load_json(USERS_FILE)
        return dict(users.get(str(user_id), {}))

def update_user(user_id, data):
    with _user_lock:
        users = _load_json(USERS_FILE)
        uid = str(user_id)
        if uid in users:
            users[uid].update(data)
        else:
            users[uid] = data
        _save_json(USERS_FILE, users)

def get_channels():
    with _user_lock:
        return _load_json(CHANNELS_FILE)

def save_channels(data):
    with _user_lock:
        _save_json(CHANNELS_FILE, data)

def get_keys():
    with _user_lock:
        return _load_json(KEYS_FILE)

def save_keys(data):
    with _user_lock:
        _save_json(KEYS_FILE, data)

def generate_key(hours):
    import hashlib
    raw = f"{time.time()}{random.randint(100000,999999)}{hours}"
    key = hashlib.md5(raw.encode()).hexdigest()[:12].upper()
    key = f"{key[:4]}-{key[4:8]}-{key[8:]}"
    keys = get_keys()
    keys[key] = {
        "hours": hours,
        "created_by": "admin",
        "created_at": time.time(),
        "used": False,
        "used_by": None,
        "activated_at": None,
        "expires_at": None
    }
    save_keys(keys)
    return key

def is_premium_active(user_data):
    prem = user_data.get("premium", {})
    if prem.get("active") and prem.get("end_time", 0) > time.time():
        return True
    return False

def is_admin(user):
    return (user.username or "").lower() == ADMIN_USERNAME

def has_joined_channels(user_id):
    if _is_admin_user(user_id):
        return True
    channels = get_channels()
    if not channels:
        return False
    all_checked = True
    for ch_id in channels.values():
        try:
            member = asyncio.get_event_loop().run_until_complete(
                bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            )
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            all_checked = False
    if not all_checked:
        return False
    return True

async def check_joined_async(user_id):
    if _is_admin_user(user_id):
        return True
    channels = get_channels()
    if not channels:
        return False
    all_checked = True
    for ch_id in channels.values():
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            all_checked = False
    if not all_checked:
        return False
    return True

def _is_admin_user(user_id):
    user_data = get_user(user_id)
    return user_data.get("is_admin", False)

def check_rate_limit(user_id, action, cooldown=1.0):
    key = f"{user_id}:{action}"
    now = time.time()
    last = _rate_limits.get(key, 0)
    if now - last < cooldown:
        return False
    _rate_limits[key] = now
    return True

async def send_or_edit(chat_id, user_id, text, reply_markup=None, parse_mode="HTML"):
    old_msg_id = _last_bot_msg.get(user_id)
    if old_msg_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=old_msg_id)
        except Exception:
            pass
    msg = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    _last_bot_msg[user_id] = msg.message_id
    return msg

async def send_section(chat_id, user_id, image_name, text, reply_markup=None):
    old_msg_id = _last_bot_msg.get(user_id)
    if old_msg_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=old_msg_id)
        except Exception:
            pass
    image = img(image_name)
    try:
        if image:
            msg = await bot.send_photo(chat_id=chat_id, photo=FSInputFile(image),
                caption=text, parse_mode="HTML", reply_markup=reply_markup)
        else:
            msg = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        msg = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode="HTML")
    _last_bot_msg[user_id] = msg.message_id
    return msg

def has_access(user_data):
    if user_data.get("is_admin"):
        return True
    if user_data.get("banned"):
        return False
    return True

def has_enough_points(user_data):
    if user_data.get("is_admin"):
        return True
    prem = user_data.get("premium", {})
    if prem.get("active") and prem.get("end_time", 0) > time.time():
        return True
    return user_data.get("points", 0) >= REQUIRED_POINTS

def points_finished(user_data):
    if user_data.get("is_admin"):
        return False
    return user_data.get("points", 0) <= 0

def deduct_point(user_id):
    user_data = get_user(user_id)
    if user_data.get("is_admin"):
        return 999999
    pts = user_data.get("points", 0)
    if pts > 0:
        user_data["points"] = pts - 1
        update_user(user_id, user_data)
    return user_data.get("points", 0)

def img(name):
    if not name:
        return None
    p = IMAGES_DIR / name
    return str(p) if p.exists() else None

def safe_str(val, max_len=200):
    return escape(str(val).strip()[:max_len])

def box(title, body):
    return f"{'='*24}\n  <b>{title}</b>\n{'='*24}\n\n{body}"

def footer():
    return f"\n\n<i>{BOT_VERSION} | Created by {CREATOR} | Play at own risk</i>"

def channels_join_kb():
    channels = get_channels()
    if not channels:
        return None
    buttons = []
    for name, ch_id in channels.items():
        link = f"https://t.me/{ch_id.replace('@','')}" if ch_id.startswith("@") else f"https://t.me/c/{str(ch_id).replace('-100','')}"
        buttons.append([InlineKeyboardButton(text=f"\U0001F4E2 Join {name}", url=link)])
    buttons.append([InlineKeyboardButton(text="\u2705 I Joined", callback_data="check_joined")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def referral_only_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001F4DD MY REFERRALS", callback_data="check_referrals")],
        [InlineKeyboardButton(text="\U0001F48E PREMIUM", callback_data="premium_info")],
        [InlineKeyboardButton(text="\U0001F464 USER INFO", callback_data="user_info")],
    ])

# ============================================
# KEYBOARDS
# ============================================
def platform_select_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001F3B0 JAI CLUB", callback_data="platform_jai")],
        [InlineKeyboardButton(text="\U0001F3AF 51GAME", callback_data="platform_51")],
    ])

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\u25B6 START", callback_data="start_bot"),
         InlineKeyboardButton(text="\U0001F4CA STATUS", callback_data="status")],
        [InlineKeyboardButton(text="\U0001F4B0 PROFIT", callback_data="profit"),
         InlineKeyboardButton(text="\u2699 SETTINGS", callback_data="settings")],
        [InlineKeyboardButton(text="\U0001F3AF GAME", callback_data="game_select"),
         InlineKeyboardButton(text="\U0001F6D1 STOP", callback_data="stop_bot")],
        [InlineKeyboardButton(text="\U0001F504 SWITCH", callback_data="switch_platform"),
         InlineKeyboardButton(text="\U0001F4DD REFER", callback_data="check_referrals")],
        [InlineKeyboardButton(text="\U0001F48E PREMIUM", callback_data="premium_info")],
        [InlineKeyboardButton(text="\U0001F464 USER INFO", callback_data="user_info")],
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="\u25C0 BACK", callback_data="back_menu")]])

def game_menu_kb_jai():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\u26A1 30 SEC", callback_data="game_30s"),
         InlineKeyboardButton(text="\U0001F525 1 MIN", callback_data="game_1m")],
        [InlineKeyboardButton(text="\u25C0 BACK", callback_data="back_menu")]
    ])

def game_menu_kb_51():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\u26A1 30 SEC", callback_data="game51_30"),
         InlineKeyboardButton(text="\U0001F525 1 MIN", callback_data="game51_1m")],
        [InlineKeyboardButton(text="\U0001F48E 3 MIN", callback_data="game51_3m"),
         InlineKeyboardButton(text="\u2B50 5 MIN", callback_data="game51_5m")],
        [InlineKeyboardButton(text="\u25C0 BACK", callback_data="back_menu")]
    ])

def settings_kb(user_data):
    restart = "ON" if user_data.get("auto_restart", True) else "OFF"
    target = user_data.get("profit_target", 20)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"\U0001F504 RESTART: {restart}", callback_data="toggle_restart")],
        [InlineKeyboardButton(text="\U0001F4B0 SET BET", callback_data="set_bet")],
        [InlineKeyboardButton(text="\U0001F4C8 SET MULTIPLIER", callback_data="set_multiplier")],
        [InlineKeyboardButton(text=f"\U0001F3AF TARGET: {target}%", callback_data="set_target")],
        [InlineKeyboardButton(text="\u25C0 BACK", callback_data="back_menu")],
    ])

def stop_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\u2705 YES STOP", callback_data="confirm_stop"),
         InlineKeyboardButton(text="\u274C NO", callback_data="cancel_stop")]
    ])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001F4CA STATS", callback_data="admin_stats")],
        [InlineKeyboardButton(text="\U0001F4E2 ADD CHANNEL", callback_data="admin_addch")],
        [InlineKeyboardButton(text="\U0001F5D1 DEL CHANNEL", callback_data="admin_delch")],
        [InlineKeyboardButton(text="\U0001F916 BOT AS CHANNEL ADMIN", callback_data="admin_promote_bot")],
        [InlineKeyboardButton(text="\U0001F464 ADD POINTS", callback_data="admin_addpts")],
        [InlineKeyboardButton(text="\U0001F6AB BAN USER", callback_data="admin_ban")],
        [InlineKeyboardButton(text="\u2705 UNBAN USER", callback_data="admin_unban")],
        [InlineKeyboardButton(text="\U0001F3AE PLAY BOT", callback_data="admin_play")],
    ])

# ============================================
# /start COMMAND
# ============================================
@dp.message(CommandStart())
async def start_command(message: Message):
    user_id = message.from_user.id
    if not check_rate_limit(user_id, "start", 2):
        return

    args = (message.text or "").split()
    ref_code = None
    if len(args) > 1 and args[1].startswith("REF_"):
        try:
            ref_code = int(args[1].replace("REF_", ""))
        except ValueError:
            pass

    user_data = get_user(user_id)
    name = safe_str(message.from_user.first_name or "User", 50)
    username = message.from_user.username or ""

    if is_admin(message.from_user):
        user_data["is_admin"] = True
        user_data["points"] = 999999
        user_data["name"] = name
        user_data["username"] = username
        update_user(user_id, user_data)
        await message.answer(box(f"\U0001F451 ADMIN - {BOT_VERSION}",
            f"Welcome Admin <b>{name}</b>!\n\n"
            f"Full access granted.\n"
            f"Use /admin for panel or just /start to play."
        ) + footer(), reply_markup=admin_kb())
        return

    if user_data.get("banned"):
        await message.answer(box("\U0001F6AB BANNED",
            "You are banned from this bot.\nContact admin.") + footer())
        return

    user_data["name"] = name
    user_data["username"] = username
    update_user(user_id, user_data)

    channels = get_channels()
    if not channels:
        await message.answer(box(f"\U0001F4E2 CHANNELS NOT SET",
            f"Welcome <b>{name}</b>!\n\n"
            "No channels configured yet.\n"
            "Ask admin to add channels first."
        ) + footer())
        return

    if ref_code and ref_code != user_id and not user_data.get("referred_by"):
        _pending_referrals[user_id] = ref_code

    joined = await check_joined_async(user_id)
    if not joined:
        kb = channels_join_kb()
        await message.answer(box(f"\U0001F4E2 JOIN CHANNELS FIRST",
            f"Welcome <b>{name}</b>!\n\n"
            "You must join our channels to use this bot.\n\n"
            "1. Click each channel button below\n"
            "2. Join the channel\n"
            "3. Come back and click <b>\u2705 I HAVE JOINED</b>\n\n"
            "<i>Referral credit also requires channel verification.</i>"
        ) + footer(), reply_markup=kb)
        return

    if not has_enough_points(user_data) and not user_data.get("is_admin"):
        pts = user_data.get("points", 0)
        refs = len(user_data.get("referrals", []))
        ref_link = f"t.me/predictor20lord_bot?start=REF_{user_id}"
        await message.answer(box(f"\U0001F4B0 NEED {REQUIRED_POINTS} POINTS",
            f"Welcome <b>{name}</b>!\n\n"
            f"<b>Your Points:</b> <code>{pts}</code> / <code>{REQUIRED_POINTS}</code>\n"
            f"<b>Referrals:</b> <code>{refs}</code>\n\n"
            f"Share your referral link:\n<code>{ref_link}</code>\n\n"
            f"<i>Each referral = {REFERRAL_POINTS} points</i>\n"
            f"<i>Need {REQUIRED_POINTS} points to access bot</i>"
        ) + footer(), reply_markup=referral_only_kb(user_id))
        return

    pts = user_data.get("points", 0)
    image = img("main_menu.png")
    text = box(f"\U0001F3B0 {BOT_VERSION}",
        f"Welcome <b>{name}</b>!\n\n"
        f"<b>Points:</b> <code>{pts}</code>\n\n"
        "Choose an option:"
    ) + footer()
    try:
        if image:
            await bot.send_photo(chat_id=message.chat.id, photo=FSInputFile(image),
                caption=text, parse_mode="HTML", reply_markup=main_menu_kb())
        else:
            await message.answer(text=text, reply_markup=main_menu_kb())
    except Exception as e:
        logger.error(f"start error: {e}")
        await message.answer(text=text, reply_markup=platform_select_kb())

# ============================================
# CHECK JOINED CALLBACK
# ============================================
@dp.callback_query(F.data == "check_joined")
async def check_joined_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    if is_admin(callback.from_user):
        await callback.answer("Admin bypass!", show_alert=False)
        return

    joined = await check_joined_async(user_id)
    if not joined:
        await callback.answer("\u274C Not yet! Join ALL channels first, then click I HAVE JOINED.", show_alert=True)
        return

    if user_id in _pending_referrals:
        ref_code = _pending_referrals.pop(user_id)
        user_data = get_user(user_id)
        if not user_data.get("referred_by") and ref_code != user_id:
            user_data["referred_by"] = ref_code
            update_user(user_id, user_data)
            referrer_data = get_user(ref_code)
            referrer_data.setdefault("referrals", [])
            if user_id not in referrer_data["referrals"]:
                referrer_data["referrals"].append(user_id)
                referrer_data["points"] = referrer_data.get("points", 0) + REFERRAL_POINTS
                update_user(ref_code, referrer_data)
                try:
                    await bot.send_message(ref_code, box("\U0001F389 NEW REFERRAL!",
                        f"User <b>{safe_str(callback.from_user.first_name or 'User', 50)}</b> joined via your link!\n\n"
                        f"<b>+{REFERRAL_POINTS} points</b> added!\n"
                        f"Total referrals: <code>{len(referrer_data['referrals'])}</code>\n"
                        f"Total points: <code>{referrer_data.get('points', 0)}</code>"
                    ) + footer())
                except Exception:
                    pass

    user_data = get_user(user_id)
    if not has_enough_points(user_data):
        pts = user_data.get("points", 0)
        ref_link = f"t.me/predictor20lord_bot?start=REF_{user_id}"
        try:
            await callback.message.edit_text(
                text=box(f"\U0001F4B0 NEED {REQUIRED_POINTS} POINTS",
                    f"Welcome <b>{safe_str(callback.from_user.first_name or 'User', 50)}</b>!\n\n"
                    f"<b>Your Points:</b> <code>{pts}</code> / <code>{REQUIRED_POINTS}</code>\n\n"
                    f"Share referral link:\n<code>{ref_link}</code>\n\n"
                    f"<i>Each referral = {REFERRAL_POINTS} points</i>"
                ) + footer(), reply_markup=referral_only_kb(user_id))
        except Exception:
            pass
        await callback.answer()
        return
    name = safe_str(callback.from_user.first_name or "User", 50)
    pts = user_data.get("points", 0)
    image = img("main_menu.png")
    text = box(f"\U0001F3B0 {BOT_VERSION}",
        f"Welcome <b>{name}</b>!\n"
        f"<b>Points:</b> <code>{pts}</code>\n\n"
        "Choose an option:"
    ) + footer()
    try:
        if image:
            await callback.message.delete()
            await bot.send_photo(chat_id=callback.message.chat.id, photo=FSInputFile(image),
                caption=text, parse_mode="HTML", reply_markup=main_menu_kb())
        else:
            await callback.message.edit_text(text=text, reply_markup=main_menu_kb())
    except Exception:
        try:
            await callback.message.edit_text(text=text, reply_markup=main_menu_kb())
        except Exception:
            pass
    await callback.answer("Verified!", show_alert=False)

# ============================================
# ADMIN COMMANDS
# ============================================
@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not is_admin(message.from_user):
        await message.answer(box("\U0001F6AB DENIED", "Admin only.") + footer())
        return
    users = _load_json(USERS_FILE)
    total_users = len(users)
    active = sum(1 for uid in _active_bots if _active_bots[uid].get("running"))
    total_pts = sum(u.get("points", 0) for u in users.values())
    channels = get_channels()
    ch_list = "\n".join(f"- {n}: <code>{c}</code>" for n, c in channels.items()) if channels else "None"
    await message.answer(box(f"\U0001F451 ADMIN - {BOT_VERSION}",
        f"<b>Users:</b> <code>{total_users}</code>\n"
        f"<b>Active Bots:</b> <code>{active}</code>\n"
        f"<b>Total Points:</b> <code>{total_pts}</code>\n\n"
        f"<b>Channels:</b>\n{ch_list}"
    ) + footer(), reply_markup=admin_kb())

@dp.message(Command("addchannel"))
async def addchannel_command(message: Message):
    if not is_admin(message.from_user):
        return
    parts = (message.text or "").split("\n")
    if len(parts) < 2:
        await message.answer(
            box("\U0001F4E2 ADD CHANNEL", 
                "Usage:\n<code>/addchannel\nChannel Name\n@channel_username</code>\n\n"
                "Example:\n<code>/addchannel\nMy Channel\n@mychannel</code>"
            ) + footer())
        return
    ch_name = parts[1].strip()
    ch_id = parts[2].strip() if len(parts) > 2 else parts[1].strip()
    channels = get_channels()
    channels[ch_name] = ch_id
    save_channels(channels)
    await message.answer(box("\u2705 CHANNEL ADDED",
        f"<b>{ch_name}</b>: <code>{ch_id}</code>\n\n"
        f"Total channels: <code>{len(channels)}</code>"
    ) + footer(), reply_markup=admin_kb())

@dp.message(Command("delchannel"))
async def delchannel_command(message: Message):
    if not is_admin(message.from_user):
        return
    channels = get_channels()
    if not channels:
        await message.answer("No channels to delete.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        ch_list = "\n".join(f"- {n}: <code>{c}</code>" for n, c in channels.items())
        await message.answer(box("\U0001F5D1 DELETE CHANNEL",
            f"Usage: <code>/delchannel Channel Name</code>\n\nCurrent channels:\n{ch_list}"
        ) + footer())
        return
    ch_name = parts[1].strip()
    if ch_name in channels:
        del channels[ch_name]
        save_channels(channels)
        await message.answer(box("\u2705 DELETED", f"Channel '{ch_name}' removed.") + footer(), reply_markup=admin_kb())
    else:
        await message.answer(f"Channel '{ch_name}' not found.")

@dp.message(Command("listchannels"))
async def listchannels_command(message: Message):
    if not is_admin(message.from_user):
        return
    channels = get_channels()
    if not channels:
        await message.answer("No channels configured.")
        return
    ch_list = "\n".join(f"- <b>{n}</b>: <code>{c}</code>" for n, c in channels.items())
    await message.answer(box("\U0001F4E2 CHANNELS", ch_list) + footer())

@dp.message(Command("setpremium"))
async def setpremium_command(message: Message):
    if not is_admin(message.from_user):
        return
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer(
            box("\U0001F48E SET PREMIUM",
                "Usage:\n<code>/setpremium user_id days</code>\n\n"
                "Days: 1, 2, 3, 7, 30\n\n"
                "Example:\n<code>/setpremium 123456789 7</code>"
            ) + footer())
        return
    try:
        uid = int(parts[1])
        days = int(parts[2])
    except ValueError:
        await message.answer("Invalid user_id or days.")
        return
    user_data = get_user(uid)
    if not user_data:
        await message.answer(f"User <code>{uid}</code> not found.")
        return
    start_time = time.time()
    end_time = start_time + (days * 86400)
    user_data["premium"] = {
        "active": True,
        "start_time": start_time,
        "end_time": end_time,
        "days": days
    }
    update_user(uid, user_data)
    from datetime import datetime
    end_dt = datetime.fromtimestamp(end_time).strftime("%d %b %Y %I:%M %p")
    await message.answer(box("\U0001F48E PREMIUM ACTIVATED",
        f"<b>User:</b> <code>{uid}</code>\n"
        f"<b>Duration:</b> {days} days\n"
        f"<b>Expires:</b> {end_dt}"
    ) + footer())
    try:
        await bot.send_message(uid, box("\U0001F48E PREMIUM ACTIVATED!",
            f"Your premium access is now active!\n\n"
            f"<b>Duration:</b> {days} days\n"
            f"<b>Expires:</b> {end_dt}\n\n"
            "Enjoy full bot access!"
        ) + footer())
    except Exception:
        pass

@dp.message(Command("delpremium"))
async def delpremium_command(message: Message):
    if not is_admin(message.from_user):
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Usage: <code>/delpremium user_id</code>")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("Invalid user_id.")
        return
    user_data = get_user(uid)
    if not user_data:
        await message.answer(f"User <code>{uid}</code> not found.")
        return
    user_data["premium"] = {"active": False}
    update_user(uid, user_data)
    await message.answer(box("\U0001F5D1 PREMIUM REMOVED", f"User <code>{uid}</code> premium removed.") + footer())

@dp.message(Command("genkey"))
async def genkey_command(message: Message):
    if not is_admin(message.from_user):
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(
            box("\U0001F511 GENERATE KEY",
                "Usage:\n<code>/genkey hours</code>\n\n"
                "Examples:\n"
                "<code>/genkey 1</code> - 1 hour key\n"
                "<code>/genkey 24</code> - 1 day key\n"
                "<code>/genkey 168</code> - 7 day key\n"
                "<code>/genkey 720</code> - 30 day key"
            ) + footer())
        return
    try:
        hours = int(parts[1])
        if hours <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Invalid hours. Must be a positive number.")
        return
    key = generate_key(hours)
    if hours >= 24:
        dur = f"{hours // 24} day(s)"
    else:
        dur = f"{hours} hour(s)"
    await message.answer(box("\U0001F511 KEY GENERATED",
        f"<b>Key:</b> <code>{key}</code>\n"
        f"<b>Duration:</b> {dur}\n\n"
        f"Share this key with user to activate premium."
    ) + footer())

@dp.message(Command("keys"))
async def keys_command(message: Message):
    if not is_admin(message.from_user):
        return
    keys = get_keys()
    if not keys:
        await message.answer("No keys generated yet.")
        return
    active = []
    used = []
    for k, v in keys.items():
        if v.get("used"):
            used.append(k)
        else:
            active.append(k)
    txt = box("\U0001F511 ALL KEYS",
        f"<b>Active:</b> <code>{len(active)}</code>\n"
        f"<b>Used:</b> <code>{len(used)}</code>\n\n"
    )
    if active:
        txt += "<b>Active Keys:</b>\n"
        for k in active[:10]:
            hrs = keys[k].get("hours", 0)
            if hrs >= 24:
                dur = f"{hrs // 24}d"
            else:
                dur = f"{hrs}h"
            txt += f"<code>{k}</code> ({dur})\n"
    if used:
        txt += "\n<b>Used Keys:</b>\n"
        for k in used[:10]:
            uid = keys[k].get("used_by", "?")
            txt += f"<code>{k}</code> → <code>{uid}</code>\n"
    await message.answer(txt + footer())

@dp.message(Command("delkey"))
async def delkey_command(message: Message):
    if not is_admin(message.from_user):
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Usage: <code>/delkey KEY</code>\nExample: <code>/delkey ABC1-2345-6789</code>")
        return
    key = parts[1].strip().upper()
    keys = get_keys()
    if key in keys:
        del keys[key]
        save_keys(keys)
        await message.answer(box("\u2705 KEY DELETED", f"Key <code>{key}</code> deleted.") + footer())
    else:
        await message.answer(f"Key <code>{key}</code> not found.")

@dp.message(Command("activate"))
async def activate_command(message: Message):
    user_id = message.from_user.id
    user_data = get_user(user_id)
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(
            box("\U0001F511 ACTIVATE PREMIUM",
                "Enter your premium key:\n\n"
                "<code>/activate XXXX-XXXX-XXXX</code>\n\n"
                "Get key from admin to activate premium."
            ) + footer())
        return
    key = parts[1].strip().upper()
    keys = get_keys()
    if key not in keys:
        await message.answer(box("\u274C INVALID KEY", "This key does not exist.") + footer())
        return
    key_data = keys[key]
    if key_data.get("used"):
        await message.answer(box("\u274C KEY USED", "This key has already been used.") + footer())
        return
    hours = key_data.get("hours", 1)
    start_time = time.time()
    end_time = start_time + (hours * 3600)
    user_data["premium"] = {
        "active": True,
        "start_time": start_time,
        "end_time": end_time,
        "key": key,
        "hours": hours
    }
    update_user(user_id, user_data)
    keys[key]["used"] = True
    keys[key]["used_by"] = user_id
    keys[key]["activated_at"] = start_time
    keys[key]["expires_at"] = end_time
    save_keys(keys)
    if hours >= 24:
        dur = f"{hours // 24} day(s)"
    else:
        dur = f"{hours} hour(s)"
    from datetime import datetime
    end_dt = datetime.fromtimestamp(end_time).strftime("%d %b %Y %I:%M %p")
    await message.answer(box("\u2705 PREMIUM ACTIVATED!",
        f"<b>Duration:</b> {dur}\n"
        f"<b>Expires:</b> {end_dt}\n\n"
        "Enjoy full bot access!"
    ) + footer())

@dp.message(Command("stats"))
async def stats_command(message: Message):
    if not is_admin(message.from_user):
        return
    users = _load_json(USERS_FILE)
    total = len(users)
    active = sum(1 for uid in _active_bots if _active_bots[uid].get("running"))
    total_pts = sum(u.get("points", 0) for u in users.values())
    total_refs = sum(len(u.get("referrals", [])) for u in users.values())
    await message.answer(box("\U0001F4CA STATS",
        f"<b>Users:</b> <code>{total}</code>\n"
        f"<b>Active:</b> <code>{active}</code>\n"
        f"<b>Points:</b> <code>{total_pts}</code>\n"
        f"<b>Referrals:</b> <code>{total_refs}</code>"
    ) + footer())

@dp.message(Command("addpoints"))
async def addpoints_command(message: Message):
    if not is_admin(message.from_user):
        return
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("Usage: /addpoints user_id amount")
        return
    try:
        uid = int(parts[1])
        amt = int(parts[2])
    except ValueError:
        await message.answer("Invalid format.")
        return
    user_data = get_user(uid)
    user_data["points"] = user_data.get("points", 0) + amt
    update_user(uid, user_data)
    await message.answer(box("\u2705 DONE", f"Added <code>{amt}</code> to <code>{uid}</code>\nTotal: <code>{user_data['points']}</code>") + footer())
    try:
        await bot.send_message(uid, box("\U0001F4B0 POINTS ADDED!", f"Admin added <b>{amt}</b> points.\nTotal: <code>{user_data['points']}</code>") + footer())
    except Exception:
        pass

@dp.message(Command("ban"))
async def ban_command(message: Message):
    if not is_admin(message.from_user):
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        return
    try:
        uid = int(parts[1])
    except ValueError:
        return
    user_data = get_user(uid)
    user_data["banned"] = True
    update_user(uid, user_data)
    if uid in _active_bots:
        _active_bots[uid]["running"] = False
    await message.answer(box("\U0001F6AB BANNED", f"User <code>{uid}</code> banned.") + footer())

@dp.message(Command("unban"))
async def unban_command(message: Message):
    if not is_admin(message.from_user):
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        return
    try:
        uid = int(parts[1])
    except ValueError:
        return
    user_data = get_user(uid)
    user_data["banned"] = False
    update_user(uid, user_data)
    await message.answer(box("\u2705 UNBANNED", f"User <code>{uid}</code> unbanned.") + footer())

@dp.message(Command("refer"))
async def refer_command(message: Message):
    user_id = message.from_user.id
    user_data = get_user(user_id)
    ref_link = f"t.me/predictor20lord_bot?start=REF_{user_id}"
    refs = len(user_data.get("referrals", []))
    pts = user_data.get("points", 0)
    await message.answer(box("\U0001F4DD REFERRALS",
        f"<b>Your Link:</b>\n<code>{ref_link}</code>\n\n"
        f"<b>Referrals:</b> <code>{refs}</code>\n"
        f"<b>Points:</b> <code>{pts}</code> / <code>{REQUIRED_POINTS}</code>\n\n"
        f"<i>Each referral = {REFERRAL_POINTS} points</i>\n"
        f"<i>Need {REQUIRED_POINTS} points to use bot</i>"
    ) + footer())

@dp.message(Command("points"))
async def points_command(message: Message):
    user_id = message.from_user.id
    user_data = get_user(user_id)
    pts = user_data.get("points", 0)
    refs = len(user_data.get("referrals", []))
    active = "Running" if _active_bots.get(user_id, {}).get("running") else "Stopped"
    await message.answer(box("\U0001F4B0 YOUR POINTS",
        f"<b>Points:</b> <code>{pts}</code>\n"
        f"<b>Referrals:</b> <code>{refs}</code>\n"
        f"<b>Status:</b> {active}\n\n"
        f"<i>1 point = 1 minute play time</i>"
    ) + footer())

@dp.message(Command("login"))
async def login_command(message: Message):
    user_id = message.from_user.id
    if not check_rate_limit(user_id, "login", 2):
        return
    user_data = get_user(user_id)
    if points_finished(user_data):
        await message.answer(box("\U0001F4B0 NO POINTS", "You have 0 points.\nGet referrals to earn more!") + footer(),
            reply_markup=referral_only_kb(user_id))
        return
    if not has_enough_points(user_data) and not user_data.get("is_admin"):
        await message.answer(box("\U0001F4B0 INSUFFICIENT POINTS",
            f"You need {REQUIRED_POINTS} points.\nGet referrals!") + footer(),
            reply_markup=referral_only_kb(user_id))
        return
    platform = user_data.get("platform", "jai")
    _user_states[user_id] = "login"
    if platform == "jai":
        title = "\U0001F511 JAI CLUB LOGIN"
        body = "Enter <b>username</b> and <b>password</b>:\n\n<code>username\npassword</code>"
    else:
        title = "\U0001F511 51GAME LOGIN"
        body = "Enter <b>phone</b> and <b>password</b>:\n\n<code>phone\npassword</code>"
    await message.answer(text=box(title, body) + footer())

@dp.message(Command("stop"))
async def stop_command(message: Message):
    user_id = message.from_user.id
    if user_id in _active_bots:
        _active_bots[user_id]["running"] = False
    await message.answer(box("\U0001F6D1 STOPPED", "Bot stopped.\nUse /start to restart.") + footer(), reply_markup=main_menu_kb())

# ============================================
# CALLBACK QUERY HANDLER
# ============================================
@dp.callback_query()
async def handle_callbacks(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not check_rate_limit(user_id, "callback", 0.3):
        await callback.answer("Wait...", show_alert=False)
        return
    data = callback.data
    user_data = get_user(user_id)
    admin = is_admin(callback.from_user)

    # ---- CHECK REFERRALS ----
    if data == "check_referrals":
        ref_link = f"t.me/predictor20lord_bot?start=REF_{user_id}"
        refs = len(user_data.get("referrals", []))
        pts = user_data.get("points", 0)
        txt = box("\U0001F4DD REFERRALS",
            f"<b>Your Link:</b>\n<code>{ref_link}</code>\n\n"
            f"<b>Referrals:</b> <code>{refs}</code>\n"
            f"<b>Points:</b> <code>{pts}</code> / <code>{REQUIRED_POINTS}</code>\n\n"
            f"<i>Share to earn {REFERRAL_POINTS} pts per referral</i>"
        ) + footer()
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_section(callback.message.chat.id, user_id, "referrals.png", txt, reply_markup=back_kb())
        await callback.answer()
        return

    # ---- USER INFO ----
    if data == "user_info":
        uid_str = str(user_id)
        short_id = hashlib_md5(uid_str.encode())[:8].upper()
        refs = len(user_data.get("referrals", []))
        pts = user_data.get("points", 0)
        uname = user_data.get("username", "N/A")
        name = user_data.get("name", "N/A")
        total_won = 0
        total_lost = 0
        if user_id in _active_bots:
            total_won = _active_bots[user_id].get("total_won", 0)
            total_lost = _active_bots[user_id].get("total_lost", 0)
        prem = user_data.get("premium", {})
        if prem.get("active") and prem.get("end_time", 0) > time.time():
            from datetime import datetime
            end_dt = datetime.fromtimestamp(prem["end_time"]).strftime("%d %b %Y")
            prem_status = f"\u2705 Active (expires {end_dt})"
        else:
            prem_status = "\u274C Not active"
        txt = box("\U0001F464 USER INFO",
            f"<b>Name:</b> {name}\n"
            f"<b>Username:</b> @{uname}\n"
            f"<b>Unique ID:</b> <code>{short_id}</code>\n"
            f"<b>User ID:</b> <code>{user_id}</code>\n\n"
            f"<b>Points:</b> <code>{pts}</code>\n"
            f"<b>Referrals:</b> <code>{refs}</code>\n"
            f"<b>Premium:</b> {prem_status}\n\n"
            f"<b>Total Won:</b> <code>{total_won:.2f}</code>\n"
            f"<b>Total Lost:</b> <code>{total_lost:.2f}</code>"
        ) + footer()
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_or_edit(callback.message.chat.id, user_id, txt, reply_markup=back_kb())
        await callback.answer()
        return

    if data == "premium_info":
        prem = user_data.get("premium", {})
        is_premium = prem.get("active", False)
        if is_premium:
            end_time = prem.get("end_time", 0)
            from datetime import datetime
            end_dt = datetime.fromtimestamp(end_time).strftime("%d %b %Y %I:%M %p") if end_time else "N/A"
            remaining = end_time - time.time()
            if remaining > 86400:
                rem_str = f"{int(remaining // 86400)}d {int((remaining % 86400) // 3600)}h"
            elif remaining > 3600:
                rem_str = f"{int(remaining // 3600)}h {int((remaining % 3600) // 60)}m"
            else:
                rem_str = f"{int(remaining // 60)}m"
            txt = box("\U0001F48E PREMIUM ACTIVE",
                f"<b>Status:</b> \u2705 Active\n"
                f"<b>Expires:</b> {end_dt}\n"
                f"<b>Remaining:</b> {rem_str}\n\n"
                "You have full access to bot features!"
            ) + footer()
        else:
            admin_user = await bot.get_me()
            admin_username = ADMIN_USERNAME
            txt = box("\U0001F48E PREMIUM ACCESS",
                "Get unlimited bot access with Premium!\n\n"
                "<b>Pricing:</b>\n"
                "\U0001F538 <b>1 Day</b> - \u20B9100\n"
                "\U0001F538 <b>2 Days</b> - \u20B9199\n"
                "\U0001F538 <b>3 Days</b> - \u20B9249\n"
                "\U0001F538 <b>7 Days</b> - \u20B9599\n"
                "\U0001F538 <b>1 Month</b> - \u20B9999\n\n"
                f"DM @{admin_username} to purchase!"
            ) + footer()
        try:
            await callback.message.delete()
        except Exception:
            pass
        prem_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"\U0001F4AC DM @{ADMIN_USERNAME}", url=f"https://t.me/{ADMIN_USERNAME}")],
            [InlineKeyboardButton(text="\u25C0 BACK", callback_data="back_menu")],
        ])
        await send_or_edit(callback.message.chat.id, user_id, txt, reply_markup=prem_kb)
        await callback.answer()
        return

    # ---- ADMIN CALLBACKS ----
    if data == "admin_stats":
        if not admin:
            await callback.answer("Admin only!", show_alert=True)
            return
        users = _load_json(USERS_FILE)
        total_pts = sum(u.get("points", 0) for u in users.values())
        total_refs = sum(len(u.get("referrals", [])) for u in users.values())
        channels = get_channels()
        ch_count = len(channels)
        try:
            await callback.message.edit_text(
                text=box("\U0001F4CA STATS",
                    f"<b>Users:</b> <code>{len(users)}</code>\n"
                    f"<b>Active:</b> <code>{sum(1 for u in _active_bots.values() if u.get('running'))}</code>\n"
                    f"<b>Points:</b> <code>{total_pts}</code>\n"
                    f"<b>Referrals:</b> <code>{total_refs}</code>\n"
                    f"<b>Channels:</b> <code>{ch_count}</code>"
                ) + footer(), reply_markup=admin_kb())
        except Exception:
            pass
        await callback.answer()
        return

    if data == "admin_addch":
        if not admin:
            return
        _user_states[user_id] = "admin_addch"
        try:
            await callback.message.edit_text(
                text=box("\U0001F4E2 ADD CHANNEL",
                    "Send channel info:\n\n<code>channel_name\n@channel_username</code>\n\n"
                    "Example:\n<code>JaiClub\n@JaiClubOfficial</code>"
                ) + footer(), reply_markup=back_kb())
        except Exception:
            await callback.message.answer(
                text=box("\U0001F4E2 ADD CHANNEL",
                    "Send:\n<code>name\n@username</code>"
                ) + footer(), reply_markup=back_kb())
        await callback.answer()
        return

    if data == "admin_delch":
        if not admin:
            return
        channels = get_channels()
        if not channels:
            await callback.answer("No channels!", show_alert=True)
            return
        buttons = [[InlineKeyboardButton(text=f"\U0001F5D1 {n}", callback_data=f"delch_{n}")] for n in channels]
        buttons.append([InlineKeyboardButton(text="\u25C0 BACK", callback_data="admin_panel")])
        try:
            await callback.message.edit_text(
                text=box("\U0001F5D1 DELETE CHANNEL", "Select channel to delete:"),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        except Exception:
            pass
        await callback.answer()
        return

    if data.startswith("delch_"):
        if not admin:
            return
        ch_name = data.replace("delch_", "")
        channels = get_channels()
        if ch_name in channels:
            del channels[ch_name]
            save_channels(channels)
            await callback.answer(f"Deleted {ch_name}!")
            try:
                await callback.message.edit_text(
                    text=box("\u2705 DELETED", f"Channel '{ch_name}' removed.") + footer(),
                    reply_markup=admin_kb())
            except Exception:
                pass
        else:
            await callback.answer("Not found!", show_alert=True)
        return

    if data == "admin_promote_bot":
        if not admin:
            return
        channels = get_channels()
        if not channels:
            await callback.answer("No channels! Add channels first.", show_alert=True)
            return
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        ch_list = "\n".join(f"- <b>{n}</b>: <code>{c}</code>" for n, c in channels.items())
        text = box("\U0001F916 BOT AS CHANNEL ADMIN",
            "To verify user joins, bot must be <b>admin</b> in channel.\n\n"
            f"<b>Steps:</b>\n"
            "1. Open your channel in Telegram\n"
            "2. Go to channel settings (click channel name)\n"
            "3. Click <b>Administrators</b>\n"
            "4. Click <b>Add Admin</b>\n"
            f"5. Search: <code>@{bot_username}</code>\n"
            "6. Give <b>Read Messages</b> permission\n"
            "7. Save\n\n"
            f"<b>Your Channels:</b>\n{ch_list}\n\n"
            f"<i>Bot username:</i> <code>@{bot_username}</code>"
        ) + footer()
        try:
            await callback.message.edit_text(text=text, reply_markup=admin_kb())
        except Exception:
            pass
        await callback.answer()
        return

    if data == "admin_addpts":
        if not admin:
            return
        _user_states[user_id] = "admin_addpts"
        try:
            await callback.message.edit_text(
                text=box("\U0001F464 ADD POINTS", "Send:\n<code>user_id amount</code>\n\nExample: <code>123456 500</code>"),
                reply_markup=back_kb())
        except Exception:
            pass
        await callback.answer()
        return

    if data == "admin_ban":
        if not admin:
            return
        _user_states[user_id] = "admin_ban"
        try:
            await callback.message.edit_text(
                text=box("\U0001F6AB BAN USER", "Send:\n<code>user_id</code>"),
                reply_markup=back_kb())
        except Exception:
            pass
        await callback.answer()
        return

    if data == "admin_unban":
        if not admin:
            return
        _user_states[user_id] = "admin_unban"
        try:
            await callback.message.edit_text(
                text=box("\u2705 UNBAN USER", "Send:\n<code>user_id</code>"),
                reply_markup=back_kb())
        except Exception:
            pass
        await callback.answer()
        return

    if data == "admin_play":
        if not admin:
            return
        user_data["platform"] = "jai"
        update_user(user_id, user_data)
        try:
            await callback.message.edit_text(
                text=box(f"\U0001F3B0 {BOT_VERSION}", "Select platform:") + footer(),
                reply_markup=platform_select_kb())
        except Exception:
            await callback.message.answer(
                text=box(f"\U0001F3B0 {BOT_VERSION}", "Select platform:") + footer(),
                reply_markup=platform_select_kb())
        await callback.answer()
        return

    if data == "admin_panel":
        if not admin:
            return
        users = _load_json(USERS_FILE)
        try:
            await callback.message.edit_text(
                text=box(f"\U0001F451 ADMIN - {BOT_VERSION}",
                    f"<b>Users:</b> <code>{len(users)}</code>\n"
                    f"<b>Active:</b> <code>{sum(1 for u in _active_bots.values() if u.get('running'))}</code>"
                ) + footer(), reply_markup=admin_kb())
        except Exception:
            pass
        await callback.answer()
        return

    if data == "admin_play":
        if not admin:
            return
        user_data["platform"] = "jai"
        update_user(user_id, user_data)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_section(callback.message.chat.id, user_id, "games.jpg",
            box(f"\U0001F3B0 {BOT_VERSION}", "Select platform:") + footer(),
            reply_markup=platform_select_kb())
        await callback.answer()
        return

    # ---- POINT CHECK (only block at 0) ----
    if not admin and points_finished(user_data):
        if user_id in _active_bots:
            _active_bots[user_id]["running"] = False
        try:
            await callback.message.delete()
        except Exception:
            pass
        ref_link = f"t.me/predictor20lord_bot?start=REF_{user_id}"
        await send_section(callback.message.chat.id, user_id, "referrals.png",
            text=box("\U0001F4B0 NO POINTS LEFT",
                "Your points are finished!\n\n"
                "Get referrals to earn more points.\n\n"
                f"<b>Your Link:</b>\n<code>{ref_link}</code>\n\n"
                f"<i>Each referral = {REFERRAL_POINTS} points</i>"
            ) + footer(), reply_markup=referral_only_kb(user_id))
        await callback.answer()
        return

    platform = user_data.get("platform", "jai")

    if data == "back_menu":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_section(callback.message.chat.id, user_id, "main_menu.png",
            box("\U0001F4CB MAIN MENU", "Choose an option:") + footer(), reply_markup=main_menu_kb())
        await callback.answer()
        return

    if data == "switch_platform":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_section(callback.message.chat.id, user_id, "switch.jpg",
            box("\U0001F504 SWITCH", "Select platform:") + footer(), reply_markup=platform_select_kb())
        await callback.answer()
        return

    if data.startswith("platform_"):
        p = data.replace("platform_", "")
        user_data["platform"] = p
        update_user(user_id, user_data)
        if p == "jai":
            img_f = "jaiclub.webp"
            text = box("\U0001F3B0 JAI CLUB SELECTED",
                "<b>WinGo 30S / 1M</b>\n\n"
                "Type <b>/login</b> to authenticate\n"
                "Then enter balance to start"
            ) + footer()
        else:
            img_f = "game51.png"
            text = box("\U0001F3AF 51GAME SELECTED",
                "<b>WinGo 30S / 1M / 3M / 5M</b>\n\n"
                "Type <b>/login</b> to authenticate\n"
                "Then enter balance to start"
            ) + footer()
        image = img(img_f)
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            if image:
                await bot.send_photo(chat_id=callback.message.chat.id, photo=FSInputFile(image),
                    caption=text, parse_mode="HTML", reply_markup=main_menu_kb())
            else:
                await callback.message.answer(text=text, reply_markup=main_menu_kb())
        except Exception:
            await callback.message.answer(text=text, reply_markup=main_menu_kb())
        await callback.answer(f"{p.upper()} selected!")
        return

    if data == "start_bot":
        if not user_data.get("logged_in"):
            await callback.answer("\U0001F511 Login first! /login", show_alert=True)
            return
        if not user_data.get("start_balance"):
            _user_states[user_id] = "set_amount"
            try:
                await callback.message.edit_text(
                    text=box("\U0001F4B0 SET BALANCE", "Enter total balance:\n<code>5000</code>") + footer(),
                    reply_markup=back_kb())
            except Exception:
                try:
                    await callback.message.delete()
                except Exception:
                    pass
                await send_or_edit(callback.message.chat.id, user_id,
                    box("\U0001F4B0 SET BALANCE", "Enter total balance:\n<code>5000</code>") + footer(),
                    reply_markup=back_kb())
            await callback.answer()
            return
        if user_id in _active_bots and _active_bots[user_id].get("running"):
            await callback.answer("\U0001F6D1 Already running!", show_alert=True)
            return
        await callback.answer("\U0001F680 Starting!")
        pn = "JAI CLUB" if platform == "jai" else "51GAME"
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_section(callback.message.chat.id, user_id, "main_menu.png",
            box("\u2705 STARTED", f"<b>{pn}</b>\n\n/send /stop to stop") + footer(), reply_markup=main_menu_kb())
        asyncio.create_task(run_betting(user_id, callback.message.chat.id, user_data))
        return

    if data == "status":
        bd = _active_bots.get(user_id, {})
        st = "Running" if bd.get("running") else "Stopped"
        pn = "JAI CLUB" if platform == "jai" else "51GAME"
        pts = user_data.get("points", 0)
        txt = box("\U0001F4CA STATUS",
            f"<b>Platform:</b> {pn}\n<b>Status:</b> {st}\n"
            f"<b>Balance:</b> <code>{bd.get('balance',0):.2f}</code>\n"
            f"<b>Profit:</b> <code>{bd.get('profit',0):.2f}</code>\n"
            f"<b>Level:</b> <code>{bd.get('level',0)}</code>\n"
            f"<b>Points:</b> <code>{pts}</code>"
        ) + footer()
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_section(callback.message.chat.id, user_id, "status.jpg", txt, reply_markup=back_kb())
        await callback.answer()
        return

    if data == "profit":
        bd = _active_bots.get(user_id, {})
        start = bd.get("start_balance", 0)
        curr = bd.get("balance", 0)
        profit = curr - start
        pct = ((profit / start) * 100) if start > 0 else 0
        target = user_data.get("profit_target", 20)
        tgt = "REACHED!" if pct >= target else f"{target}%"
        image = img("profit.jpg")
        txt = box("\U0001F4B0 PROFIT",
            f"<b>Profit:</b> <code>{profit:.2f}</code>\n"
            f"<b>%:</b> <code>{pct:.1f}%</code>\n"
            f"<b>Target:</b> <code>{tgt}</code>\n\n"
            f"<b>Wins:</b> <code>{bd.get('double_win',0)}</code> | "
            f"<b>Losses:</b> <code>{bd.get('double_loss',0)}</code>\n"
            f"<b>Level:</b> <code>{bd.get('level',0)}</code>"
        ) + footer()
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            if image:
                await bot.send_photo(chat_id=callback.message.chat.id, photo=FSInputFile(image),
                    caption=txt, parse_mode="HTML", reply_markup=back_kb())
            else:
                await callback.message.answer(text=txt, reply_markup=back_kb())
        except Exception:
            await callback.message.answer(text=txt, reply_markup=back_kb())
        await callback.answer()
        return

    if data == "game_select":
        if platform == "jai":
            kb = game_menu_kb_jai()
        else:
            kb = game_menu_kb_51()
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_section(callback.message.chat.id, user_id, "games.jpg",
            box("\U0001F3AE GAMES", "Select game type:") + footer(), reply_markup=kb)
        await callback.answer()
        return

    if data in ["game_30s", "game_1m"]:
        game = "WinGo_30S" if data == "game_30s" else "WinGo_1M"
        user_data["game"] = game
        update_user(user_id, user_data)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_section(callback.message.chat.id, user_id, "main_menu.png",
            box("\u2705 GAME SET", f"<b>{game}</b>") + footer(), reply_markup=main_menu_kb())
        await callback.answer(f"Game: {game}")
        return

    if data.startswith("game51_"):
        gm = {"game51_30": 30, "game51_1m": 1, "game51_3m": 2, "game51_5m": 3}
        tid = gm.get(data, 30)
        user_data["game51_type_id"] = tid
        update_user(user_id, user_data)
        nm = {30: "30 SEC", 1: "1 MIN", 2: "3 MIN", 3: "5 MIN"}
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_section(callback.message.chat.id, user_id, "main_menu.png",
            box("\u2705 GAME SET", f"<b>WinGo {nm.get(tid,'30S')}</b>") + footer(), reply_markup=main_menu_kb())
        await callback.answer(f"WinGo {nm.get(tid,'30S')}")
        return

    if data == "stop_bot":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_section(callback.message.chat.id, user_id, "stop.png",
            box("\U0001F6D1 STOP?", "Confirm:") + footer(), reply_markup=stop_confirm_kb())
        await callback.answer()
        return

    if data == "confirm_stop":
        if user_id in _active_bots:
            _active_bots[user_id]["running"] = False
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_section(callback.message.chat.id, user_id, "main_menu.png",
            box("\U0001F6D1 STOPPED", "Use /start to restart.") + footer(), reply_markup=main_menu_kb())
        await callback.answer("\U0001F6D1 Stopped!")
        return

    if data == "cancel_stop":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_section(callback.message.chat.id, user_id, "main_menu.png",
            box("\u2705 RUNNING", "Bot continues.") + footer(), reply_markup=main_menu_kb())
        await callback.answer("Still running!")
        return

    if data == "settings":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_section(callback.message.chat.id, user_id, "settings.png",
            box("\u2699 SETTINGS", "Adjust:") + footer(), reply_markup=settings_kb(user_data))
        await callback.answer()
        return

    if data == "toggle_restart":
        user_data["auto_restart"] = not user_data.get("auto_restart", True)
        update_user(user_id, user_data)
        st = "ON" if user_data["auto_restart"] else "OFF"
        try:
            await callback.message.edit_text(text=box("\u2699 SETTINGS", f"<b>Restart:</b> {st}") + footer(), reply_markup=settings_kb(user_data))
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await send_section(callback.message.chat.id, user_id, "settings.png",
                box("\u2699 SETTINGS", f"<b>Restart:</b> {st}") + footer(), reply_markup=settings_kb(user_data))
        await callback.answer(f"Restart: {st}")
        return

    if data == "set_bet":
        _user_states[user_id] = "set_bet"
        try:
            await callback.message.edit_text(text=box("\U0001F4B0 SET BET", "Enter bet (min 2):") + footer(), reply_markup=back_kb())
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await send_or_edit(callback.message.chat.id, user_id, box("\U0001F4B0 SET BET", "Enter bet (min 2):") + footer(), reply_markup=back_kb())
        await callback.answer()
        return

    if data == "set_multiplier":
        _user_states[user_id] = "set_mult"
        try:
            await callback.message.edit_text(text=box("\U0001F4C8 SET MULTIPLIER", "Enter multiplier (min 1.5):") + footer(), reply_markup=back_kb())
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await send_or_edit(callback.message.chat.id, user_id, box("\U0001F4C8 SET MULTIPLIER", "Enter multiplier (min 1.5):") + footer(), reply_markup=back_kb())
        await callback.answer()
        return

    if data == "set_target":
        _user_states[user_id] = "set_target"
        try:
            await callback.message.edit_text(text=box("\U0001F3AF SET TARGET", "Enter target % (5-500):") + footer(), reply_markup=back_kb())
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await send_or_edit(callback.message.chat.id, user_id, box("\U0001F3AF SET TARGET", "Enter target % (5-500):") + footer(), reply_markup=back_kb())
        await callback.answer()
        return

# ============================================
# TEXT MESSAGE HANDLER
# ============================================
@dp.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id
    state = _user_states.get(user_id)
    text = (message.text or "").strip()
    user_data = get_user(user_id)
    admin = is_admin(message.from_user)

    if not admin and not user_data.get("banned"):
        channels = get_channels()
        if channels:
            joined = await check_joined_async(user_id)
            if not joined:
                kb = channels_join_kb()
                await message.answer(box(f"\U0001F4E2 JOIN CHANNELS FIRST",
                    f"Welcome <b>{safe_str(message.from_user.first_name or 'User', 50)}</b>!\n\n"
                    "You must join our channels to use this bot.\n\n"
                    "1. Click each channel button below\n"
                    "2. Join the channel\n"
                    "3. Come back and click <b>\u2705 I HAVE JOINED</b>\n\n"
                    "<i>Referral credit also requires channel verification.</i>"
                ) + footer(), reply_markup=kb)
                return

    # ---- ADMIN STATES ----
    if admin:
        if state == "admin_addch":
            _user_states.pop(user_id, None)
            lines = text.split("\n")
            if len(lines) < 2:
                await send_or_edit(message.chat.id, user_id, "Format:\n<code>name\n@username</code>")
                return
            ch_name = lines[0].strip()
            ch_id = lines[1].strip()
            channels = get_channels()
            channels[ch_name] = ch_id
            save_channels(channels)
            await send_or_edit(message.chat.id, user_id, box("\u2705 CHANNEL ADDED", f"<b>{ch_name}</b>: <code>{ch_id}</code>") + footer(), reply_markup=admin_kb())
            return

        if state == "admin_addpts":
            _user_states.pop(user_id, None)
            parts = text.split()
            if len(parts) >= 2:
                try:
                    uid = int(parts[0])
                    amt = int(parts[1])
                    ud = get_user(uid)
                    ud["points"] = ud.get("points", 0) + amt
                    update_user(uid, ud)
                    await send_or_edit(message.chat.id, user_id, box("\u2705 DONE", f"Added {amt} to <code>{uid}</code>\nTotal: {ud['points']}") + footer())
                except (ValueError, IndexError):
                    await send_or_edit(message.chat.id, user_id, "Format: user_id amount")
            return

        if state == "admin_ban":
            _user_states.pop(user_id, None)
            try:
                uid = int(text)
                ud = get_user(uid)
                ud["banned"] = True
                update_user(uid, ud)
                if uid in _active_bots:
                    _active_bots[uid]["running"] = False
                await send_or_edit(message.chat.id, user_id, box("\U0001F6AB BANNED", f"User <code>{uid}</code> banned.") + footer())
            except ValueError:
                await send_or_edit(message.chat.id, user_id, "Send user_id number")
            return

        if state == "admin_unban":
            _user_states.pop(user_id, None)
            try:
                uid = int(text)
                ud = get_user(uid)
                ud["banned"] = False
                update_user(uid, ud)
                await send_or_edit(message.chat.id, user_id, box("\u2705 UNBANNED", f"User <code>{uid}</code> unbanned.") + footer())
            except ValueError:
                await send_or_edit(message.chat.id, user_id, "Send user_id number")
            return

    # ---- LOGIN STATE ----
    if state == "login":
        if points_finished(user_data) and not admin:
            _user_states.pop(user_id, None)
            await send_or_edit(message.chat.id, user_id, box("\U0001F4B0 NO POINTS", "Get referrals!") + footer(), reply_markup=referral_only_kb(user_id))
            return
        lines = text.split("\n")
        if len(lines) < 2:
            await send_or_edit(message.chat.id, user_id, box("\u274C FORMAT", "Send:\n<code>username\npassword</code>") + footer())
            return
        username = lines[0].strip()[:50]
        password = lines[1].strip()[:50]
        if not username or not password:
            await send_or_edit(message.chat.id, user_id, box("\u274C EMPTY", "Cannot be empty") + footer())
            return
        user_data["login_user"] = username
        user_data["login_pass"] = password
        user_data["logged_in"] = True
        update_user(user_id, user_data)
        _user_states[user_id] = "set_amount"
        platform = user_data.get("platform", "jai")
        pn = "JAI CLUB" if platform == "jai" else "51GAME"
        await send_or_edit(message.chat.id, user_id, text=box("\U0001F4B0 SET BALANCE", f"<b>{pn}</b>\nEnter balance:\n<code>5000</code>") + footer())
        return

    if state == "set_amount":
        try:
            amount = max(100, int(text))
        except ValueError:
            await send_or_edit(message.chat.id, user_id, box("\u274C INVALID", "Enter a number. Min 100") + footer())
            return
        user_data["start_balance"] = amount
        update_user(user_id, user_data)
        _user_states.pop(user_id, None)
        platform = user_data.get("platform", "jai")
        pn = "JAI CLUB" if platform == "jai" else "51GAME"
        await send_or_edit(message.chat.id, user_id, text=box("\u2705 READY", f"<b>{pn}</b> | Balance: {amount}\nStarting...") + footer(), reply_markup=main_menu_kb())
        user_data = get_user(user_id)
        asyncio.create_task(run_betting(user_id, message.chat.id, user_data))
        return

    if state == "set_bet":
        try:
            bet = max(2, int(text))
        except ValueError:
            await send_or_edit(message.chat.id, user_id, box("\u274C INVALID", "Enter a number. Min 2") + footer())
            return
        user_data["total_bet"] = bet
        update_user(user_id, user_data)
        _user_states.pop(user_id, None)
        await send_or_edit(message.chat.id, user_id, text=box("\u2705 BET SET", f"<b>{bet}</b>") + footer(), reply_markup=main_menu_kb())
        return

    if state == "set_mult":
        try:
            mult = max(1.5, float(text))
        except ValueError:
            await send_or_edit(message.chat.id, user_id, box("\u274C INVALID", "Enter a number. Min 1.5") + footer())
            return
        user_data["multiplier"] = mult
        update_user(user_id, user_data)
        _user_states.pop(user_id, None)
        await send_or_edit(message.chat.id, user_id, text=box("\u2705 MULTIPLIER SET", f"<b>{mult}x</b>") + footer(), reply_markup=main_menu_kb())
        return

    if state == "set_target":
        try:
            target = max(5, min(500, float(text)))
        except ValueError:
            await send_or_edit(message.chat.id, user_id, box("\u274C INVALID", "Enter 5-500") + footer())
            return
        user_data["profit_target"] = target
        update_user(user_id, user_data)
        _user_states.pop(user_id, None)
        await send_or_edit(message.chat.id, user_id, text=box("\u2705 TARGET SET", f"<b>{target}%</b>") + footer(), reply_markup=main_menu_kb())
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
    admin = user_data.get("is_admin", False)

    msg = await bot.send_message(chat_id, box("\u23F3 JAI CLUB", "Logging in...") + footer(), reply_markup=main_menu_kb())
    _profit_messages[user_id] = msg.message_id

    try:
        engine = AutoBetEngine(username, password, game, total_bet, multiplier, 55)
        engine.checker.lottery_api_base_url = "https://h5.ar-lottery06.com"
        engine.checker.lottery_draw_base_url = "https://draw.ar-lottery06.com"
        engine.login()
        engine.checker.fetch_ar_token(game)
    except Exception as e:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=box("\u274C FAILED", safe_str(e, 100)) + footer())
        except Exception:
            pass
        return

    engine.start_balance = start_balance
    engine.current_balance = start_balance
    engine.levels = make_levels(start_balance, total_bet, multiplier)

    bot_state = {
        "running": True, "start_balance": start_balance, "balance": start_balance,
        "profit": 0, "total_won": 0, "total_lost": 0, "wins": 0, "losses": 0,
        "double_win": 0, "double_loss": 0, "level": 0, "pending": None, "last_seen_period": None,
        "target_hit": False, "profit_target": profit_target, "start_time": time.time()
    }
    _active_bots[user_id] = bot_state
    await update_profit_msg(user_id, chat_id, bot_state, "RUNNING", "JAI CLUB")

    while bot_state["running"]:
        try:
            if not admin:
                ud = get_user(user_id)
                if points_finished(ud):
                    bot_state["running"] = False
                    try:
                        await bot.send_message(chat_id, box("\U0001F4B0 POINTS OVER", "No points left!\nGet referrals to continue.") + footer(),
                            reply_markup=referral_only_kb(user_id))
                    except Exception:
                        pass
                    break

                elapsed = time.time() - bot_state["start_time"]
                if elapsed >= 60:
                    bot_state["start_time"] = time.time()
                    remaining = deduct_point(user_id)
                    if remaining <= 0:
                        bot_state["running"] = False
                        try:
                            await bot.send_message(chat_id, box("\U0001F4B0 POINTS OVER", "No points left!") + footer(),
                                reply_markup=referral_only_kb(user_id))
                        except Exception:
                            pass
                        break

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
                    pct = ((bot_state["profit"] / bot_state["start_balance"]) * 100) if bot_state["start_balance"] > 0 else 0
                    if pct >= profit_target and not bot_state["target_hit"]:
                        bot_state["target_hit"] = True
                        try:
                            await bot.send_message(chat_id, box("\U0001F389 TARGET!",
                                f"<b>Profit:</b> +{bot_state['profit']:.2f} ({pct:.1f}%)") + footer())
                        except Exception:
                            pass
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
            logger.error(f"JAI error: {e}")
            await asyncio.sleep(3)

    if user_id in _profit_messages:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=_profit_messages[user_id],
                text=format_profit(bot_state, "STOPPED", "JAI CLUB") + footer(), reply_markup=main_menu_kb())
        except Exception:
            pass

# ============================================
# RUN BETTING - 51GAME (Game51 login + JAI retry)
# ============================================
async def run_betting_51(user_id, chat_id, user_data):
    username = user_data.get("login_user", "")
    password = user_data.get("login_pass", "")
    type_id = user_data.get("game51_type_id", 30)
    total_bet = user_data.get("total_bet", 2)
    start_balance = user_data.get("start_balance", 500)
    profit_target = user_data.get("profit_target", 20)
    admin = user_data.get("is_admin", False)

    game_code_map = {30: "WinGo_30S", 1: "WinGo_1M", 2: "WinGo_3M", 3: "WinGo_5M"}
    game_code = game_code_map.get(type_id, "WinGo_30S")
    display_names = {30: "30 SEC", 1: "1 MIN", 2: "3 MIN", 3: "5 MIN"}
    game_name = display_names.get(type_id, "30 SEC")

    msg = await bot.send_message(chat_id, box("\u23F3 51GAME", "Logging in...") + footer(), reply_markup=main_menu_kb())
    _profit_messages[user_id] = msg.message_id

    checker = Game51AccountChecker(username, password)
    try:
        if not checker.perform_login():
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
                    text=box("\u274C FAILED", safe_str(checker.message, 100)) + footer())
            except Exception:
                pass
            return
    except Exception as e:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
                text=box("\u274C FAILED", safe_str(e, 100)) + footer())
        except Exception:
            pass
        return

    balance = checker.get_balance()
    if balance <= 0:
        balance = start_balance
    levels = make_levels(balance, total_bet, 2.0)

    jai_checker = JAIChecker(username, password)
    try:
        jai_checker.perform_login()
    except Exception:
        pass

    bot_state = {
        "running": True, "start_balance": balance, "balance": balance,
        "profit": 0, "total_won": 0, "total_lost": 0, "wins": 0, "losses": 0,
        "double_win": 0, "double_loss": 0, "level": 0, "pending": None, "last_seen_period": None,
        "target_hit": False, "profit_target": profit_target, "start_time": time.time()
    }
    _active_bots[user_id] = bot_state
    await update_profit_msg(user_id, chat_id, bot_state, "RUNNING", f"51GAME {game_name}")

    while bot_state["running"]:
        try:
            if not admin:
                ud = get_user(user_id)
                if points_finished(ud):
                    bot_state["running"] = False
                    try:
                        await bot.send_message(chat_id, box("\U0001F4B0 POINTS OVER", "No points!") + footer(),
                            reply_markup=referral_only_kb(user_id))
                    except Exception:
                        pass
                    break
                elapsed = time.time() - bot_state["start_time"]
                if elapsed >= 60:
                    bot_state["start_time"] = time.time()
                    remaining = deduct_point(user_id)
                    if remaining <= 0:
                        bot_state["running"] = False
                        try:
                            await bot.send_message(chat_id, box("\U0001F4B0 POINTS OVER", "No points!") + footer(),
                                reply_markup=referral_only_kb(user_id))
                        except Exception:
                            pass
                        break

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
                    pct = ((bot_state["profit"] / bot_state["start_balance"]) * 100) if bot_state["start_balance"] > 0 else 0
                    if pct >= profit_target and not bot_state["target_hit"]:
                        bot_state["target_hit"] = True
                        try:
                            await bot.send_message(chat_id, box("\U0001F389 TARGET!",
                                f"<b>Profit:</b> +{bot_state['profit']:.2f} ({pct:.1f}%)") + footer())
                        except Exception:
                            pass
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
                    bs_data = results.get("bs", {})
                    color_data = results.get("color", {})
                    bs_ok = "error" not in bs_data and bs_data.get("code", -1) == 0
                    color_ok = "error" not in color_data and color_data.get("code", -1) == 0
                    if bs_ok or color_ok:
                        bot_state["pending"] = {
                            "period": open_issue, "bs_prediction": bs_pred, "color_prediction": co_pred,
                            "total_bet": lv["total_bet"], "level": lv["level"]
                        }
                        await update_profit_msg(user_id, chat_id, bot_state, "WAITING", f"51GAME {game_name}")
                    else:
                        logger.error(f"51GAME Bet rejected: bs={bs_data} color={color_data}")
                except Exception as e:
                    logger.error(f"51GAME Bet failed: {e}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"51GAME error: {e}")
            await asyncio.sleep(3)

    if user_id in _profit_messages:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=_profit_messages[user_id],
                text=format_profit(bot_state, "STOPPED", f"51GAME {game_name}") + footer(), reply_markup=main_menu_kb())
        except Exception:
            pass

# ============================================
# ROUTER + PROFIT
# ============================================
async def run_betting(user_id, chat_id, user_data):
    platform = user_data.get("platform", "jai")
    if platform == "51":
        await run_betting_51(user_id, chat_id, user_data)
    else:
        await run_betting_jai(user_id, chat_id, user_data)

async def update_profit_msg(user_id, chat_id, bot_state, status="RUNNING", platform="JAI CLUB"):
    msg_id = _profit_messages.get(user_id)
    if not msg_id:
        return
    text = format_profit(bot_state, status, platform) + footer()
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, reply_markup=main_menu_kb())
    except Exception as e:
        if "not modified" not in str(e) and "not found" not in str(e):
            logger.error(f"Edit profit error: {e}")

def format_profit(bot_state, status="RUNNING", platform="JAI CLUB"):
    profit = bot_state.get("profit", 0)
    start = bot_state.get("start_balance", 0)
    pct = ((profit / start) * 100) if start > 0 else 0
    target = bot_state.get("profit_target", 20)
    s_map = {"RUNNING": "Running", "WAITING": "Waiting", "STOPPED": "Stopped"}
    s_text = s_map.get(status, status)
    sign = "+" if profit >= 0 else ""
    tgt = f"{target}% OK" if pct >= target else f"{target}%"
    return box(f"\U0001F4B0 {platform}", (
        f"<b>Status:</b> {s_text}\n\n"
        f"<b>Profit:</b> <code>{sign}{profit:.2f}</code>\n"
        f"<b>%:</b> <code>{sign}{pct:.1f}%</code>\n"
        f"<b>Target:</b> <code>{tgt}</code>\n\n"
        f"<b>Wins:</b> <code>{bot_state.get('wins',0)}</code> | "
        f"<b>Losses:</b> <code>{bot_state.get('losses',0)}</code>\n"
        f"<b>DW:</b> <code>{bot_state.get('double_win',0)}</code> | "
        f"<b>DL:</b> <code>{bot_state.get('double_loss',0)}</code>\n"
        f"<b>Level:</b> <code>{bot_state.get('level',0)}</code>\n\n"
        f"<i>{datetime.now().strftime('%H:%M:%S')}</i>"
    ))

def hashlib_md5(data):
    import hashlib as hl
    return hl.md5(data).hexdigest()

# ============================================
# BOT START
# ============================================
async def main():
    print(f"{BOT_VERSION} - DUAL GAME BOT STARTED!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
