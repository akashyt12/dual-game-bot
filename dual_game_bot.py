#!/usr/bin/env python3
"""DUAL GAME BOT - JAI CLUB + 51GAME | Admin + Keys + Referrals + Points"""

import os, sys, json, asyncio, logging, random, time, hashlib, threading
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

BOT_TOKEN = "8488981885:AAHP6PO4d6wDFr-cLSL1-lRHV5j9y7dXLP4"
ADMIN_USERNAME = "lord_x_stylo"
IMAGES_DIR = Path(__file__).parent / "images"
BASE_DIR = Path("/home/akash/mimo-test")
USERS_FILE = BASE_DIR / "users.json"
KEYS_FILE = BASE_DIR / "keys.json"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

MIN_REFERRALS = 3
REFERRAL_POINTS = 100
REQUIRED_POINTS = MIN_REFERRALS * REFERRAL_POINTS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

_user_lock = threading.Lock()
_user_states = {}
_active_bots = {}
_profit_messages = {}
_rate_limits = {}

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

def get_keys():
    with _user_lock:
        return _load_json(KEYS_FILE)

def save_keys(data):
    with _user_lock:
        _save_json(KEYS_FILE, data)

def is_admin(user):
    uname = (user.username or "").lower()
    return uname == ADMIN_USERNAME

def check_rate_limit(user_id, action, cooldown=1.0):
    key = f"{user_id}:{action}"
    now = time.time()
    last = _rate_limits.get(key, 0)
    if now - last < cooldown:
        return False
    _rate_limits[key] = now
    return True

def has_access(user_data):
    if user_data.get("is_admin"):
        return True
    if user_data.get("banned"):
        return False
    return user_data.get("access_key_valid", False)

def has_enough_points(user_data):
    if user_data.get("is_admin"):
        return True
    return user_data.get("points", 0) >= REQUIRED_POINTS

def deduct_point(user_id):
    user_data = get_user(user_id)
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
    s = str(val).strip()[:max_len]
    return escape(s)

def gen_key():
    parts = [f"{random.randint(0,65535):04X}" for _ in range(4)]
    return "KEY-" + "-".join(parts)

def box(title, body):
    return f"{'='*22}\n  <b>{title}</b>\n{'='*22}\n\n{body}"

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
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="\u25C0 BACK", callback_data="back_menu")]])

def back_only_kb():
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
        [InlineKeyboardButton(text="\U0001F511 GEN KEY", callback_data="admin_genkey")],
        [InlineKeyboardButton(text="\U0001F4CA STATS", callback_data="admin_stats"),
         InlineKeyboardButton(text="\U0001F4CB LIST KEYS", callback_data="admin_listkeys")],
        [InlineKeyboardButton(text="\U0001F464 ADD POINTS", callback_data="admin_addpts")],
    ])

def enter_key_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001F511 ENTER ACCESS KEY", callback_data="enter_key")]
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

    if ref_code and ref_code != user_id and not user_data.get("referred_by"):
        referrer_data = get_user(ref_code)
        referrer_data.setdefault("referrals", [])
        if user_id not in referrer_data["referrals"]:
            referrer_data["referrals"].append(user_id)
            referrer_data["points"] = referrer_data.get("points", 0) + REFERRAL_POINTS
            update_user(ref_code, referrer_data)
            try:
                await bot.send_message(ref_code, box("\U0001F389 NEW REFERRAL!",
                    f"User <b>{name}</b> joined via your link!\n\n"
                    f"<b>+{REFERRAL_POINTS} points</b> added!\n"
                    f"Total referrals: <code>{len(referrer_data['referrals'])}</code>\n"
                    f"Total points: <code>{referrer_data.get('points', 0)}</code>"
                ))
            except Exception:
                pass

    if is_admin(message.from_user):
        user_data["is_admin"] = True
        user_data["access_key_valid"] = True
        user_data["points"] = 999999
        user_data["name"] = name
        user_data["username"] = username
        update_user(user_id, user_data)
        await message.answer(box("\U0001F451 ADMIN PANEL",
            f"Welcome Admin <b>{name}</b>!\n\n"
            "You have full access.\n"
            "Use /admin for admin panel."
        ), reply_markup=admin_kb())
        return

    user_data["name"] = name
    user_data["username"] = username
    update_user(user_id, user_data)

    if user_data.get("banned"):
        await message.answer(box("\U0001F6AB ACCESS DENIED", "You are banned from this bot."))
        return

    if not user_data.get("access_key_valid"):
        await message.answer(box("\U0001F511 ACCESS KEY REQUIRED",
            f"Welcome <b>{name}</b>!\n\n"
            "You need a valid access key to use this bot.\n\n"
            "Get a key from the admin or a referrer.\n"
            "Click below to enter your key:"
        ), reply_markup=enter_key_kb())
        return

    if not has_enough_points(user_data):
        pts = user_data.get("points", 0)
        refs = len(user_data.get("referrals", []))
        ref_link = f"t.me/predictfinalbot?start=REF_{user_id}"
        await message.answer(box("\U0001F4B0 NOT ENOUGH POINTS",
            f"Welcome <b>{name}</b>!\n\n"
            f"<b>Points:</b> <code>{pts}</code> / <code>{REQUIRED_POINTS}</code>\n"
            f"<b>Referrals:</b> <code>{refs}</code> / <code>{MIN_REFERRALS}</code>\n\n"
            f"Share your referral link to earn points:\n"
            f"<code>{ref_link}</code>\n\n"
            f"<i>Each referral = {REFERRAL_POINTS} points</i>\n"
            f"<i>Need {REQUIRED_POINTS} points ({MIN_REFERRALS} referrals) to start</i>"
        ), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="\U0001F511 ENTER KEY", callback_data="enter_key")],
            [InlineKeyboardButton(text="\U0001F4DD MY REFERRALS", callback_data="check_referrals")],
        ]))
        return

    image = img("profit.jpg")
    text = box("\U0001F3B0 DUAL GAME AUTO BOT",
        f"Welcome <b>{name}</b>!\n\n"
        f"<b>Points:</b> <code>{user_data.get('points', 0)}</code>\n\n"
        "Choose Your Platform:\n\n"
        "\U0001F3B0 <b>JAI CLUB</b> - WinGo 30S / 1M\n"
        "\U0001F3AF <b>51GAME</b> - WinGo 30S / 1M / 3M / 5M\n\n"
        "Features:\n"
        "- Auto Prediction\n"
        "- Dual Bet System\n"
        "- Level Staking\n"
        "- Profit Target\n\n"
        "<i>Select a platform:</i>"
    )
    try:
        if image:
            await bot.send_photo(chat_id=message.chat.id, photo=FSInputFile(image),
                caption=text, parse_mode="HTML", reply_markup=platform_select_kb())
        else:
            await message.answer(text=text, reply_markup=platform_select_kb())
    except Exception as e:
        logger.error(f"start photo error: {e}")
        await message.answer(text=text, reply_markup=platform_select_kb())

# ============================================
# /admin COMMAND
# ============================================
@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not is_admin(message.from_user):
        await message.answer(box("\U0001F6AB DENIED", "Admin only."))
        return
    users = _load_json(USERS_FILE)
    total_users = len(users)
    active = sum(1 for uid in _active_bots if _active_bots[uid].get("running"))
    total_pts = sum(u.get("points", 0) for u in users.values())
    await message.answer(box("\U0001F451 ADMIN PANEL",
        f"<b>Total Users:</b> <code>{total_users}</code>\n"
        f"<b>Active Bots:</b> <code>{active}</code>\n"
        f"<b>Total Points:</b> <code>{total_pts}</code>"
    ), reply_markup=admin_kb())

@dp.message(Command("genkey"))
async def genkey_command(message: Message):
    if not is_admin(message.from_user):
        return
    parts = (message.text or "").split()
    count = 1
    if len(parts) > 1:
        try:
            count = max(1, min(50, int(parts[1])))
        except ValueError:
            pass
    keys = get_keys()
    new_keys = []
    for _ in range(count):
        k = gen_key()
        keys[k] = {"used": False, "created_by": message.from_user.id, "created_at": datetime.now().isoformat()}
        new_keys.append(k)
    save_keys(keys)
    key_list = "\n".join(f"<code>{k}</code>" for k in new_keys)
    await message.answer(box(f"\U0001F511 {count} KEYS GENERATED",
        f"{key_list}\n\n<i>Share these keys with users</i>"
    ))

@dp.message(Command("listkeys"))
async def listkeys_command(message: Message):
    if not is_admin(message.from_user):
        return
    keys = get_keys()
    unused = [k for k, v in keys.items() if not v.get("used")]
    used = [k for k, v in keys.items() if v.get("used")]
    text = f"<b>Unused Keys:</b> <code>{len(unused)}</code>\n"
    if unused[:10]:
        text += "\n".join(f"<code>{k}</code>" for k in unused[:10])
    if len(unused) > 10:
        text += f"\n... and {len(unused)-10} more"
    text += f"\n\n<b>Used Keys:</b> <code>{len(used)}</code>"
    await message.answer(box("\U0001F4CB KEY LIST", text))

@dp.message(Command("stats"))
async def stats_command(message: Message):
    if not is_admin(message.from_user):
        return
    users = _load_json(USERS_FILE)
    total = len(users)
    active = sum(1 for uid in _active_bots if _active_bots[uid].get("running"))
    total_pts = sum(u.get("points", 0) for u in users.values())
    total_refs = sum(len(u.get("referrals", [])) for u in users.values())
    keys = get_keys()
    unused_keys = sum(1 for v in keys.values() if not v.get("used"))
    await message.answer(box("\U0001F4CA STATS",
        f"<b>Users:</b> <code>{total}</code>\n"
        f"<b>Active Bots:</b> <code>{active}</code>\n"
        f"<b>Total Points:</b> <code>{total_pts}</code>\n"
        f"<b>Total Referrals:</b> <code>{total_refs}</code>\n"
        f"<b>Unused Keys:</b> <code>{unused_keys}</code>"
    ))

@dp.message(Command("approve"))
async def approve_command(message: Message):
    if not is_admin(message.from_user):
        return
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("Usage: /approve user_id points")
        return
    try:
        uid = int(parts[1])
        pts = int(parts[2])
    except ValueError:
        await message.answer("Invalid format. Usage: /approve user_id points")
        return
    user_data = get_user(uid)
    user_data["access_key_valid"] = True
    user_data["points"] = user_data.get("points", 0) + pts
    update_user(uid, user_data)
    await message.answer(box("\u2705 APPROVED", f"User <code>{uid}</code> approved with <code>{pts}</code> points"))
    try:
        await bot.send_message(uid, box("\u2705 APPROVED!",
            f"You have been approved by admin!\n"
            f"<b>Points:</b> <code>{user_data['points']}</code>\n\n"
            "Send /start to continue."
        ))
    except Exception:
        pass

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
    await message.answer(box("\u2705 DONE", f"Added <code>{amt}</code> points to <code>{uid}</code>\nTotal: <code>{user_data['points']}</code>"))

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
    await message.answer(box("\U0001F6AB BANNED", f"User <code>{uid}</code> banned."))

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
    await message.answer(box("\u2705 UNBANNED", f"User <code>{uid}</code> unbanned."))

@dp.message(Command("stop"))
async def stop_command(message: Message):
    user_id = message.from_user.id
    if user_id in _active_bots:
        _active_bots[user_id]["running"] = False
    await message.answer(box("\U0001F6D1 BOT STOPPED", "Bot stopped.\nUse /start to restart."), reply_markup=main_menu_kb())

# ============================================
# /refer COMMAND
# ============================================
@dp.message(Command("refer"))
async def refer_command(message: Message):
    user_id = message.from_user.id
    user_data = get_user(user_id)
    ref_link = f"t.me/predictfinalbot?start=REF_{user_id}"
    refs = len(user_data.get("referrals", []))
    pts = user_data.get("points", 0)
    await message.answer(box("\U0001F4DD YOUR REFERRALS",
        f"<b>Referral Link:</b>\n<code>{ref_link}</code>\n\n"
        f"<b>Referrals:</b> <code>{refs}</code>\n"
        f"<b>Points:</b> <code>{pts}</code>\n\n"
        f"<i>Each referral = {REFERRAL_POINTS} points</i>\n"
        f"<i>Need {REQUIRED_POINTS} points ({MIN_REFERRALS} referrals) to use bot</i>"
    ))

# ============================================
# /points COMMAND
# ============================================
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
    ))

# ============================================
# /login COMMAND
# ============================================
@dp.message(Command("login"))
async def login_command(message: Message):
    user_id = message.from_user.id
    if not check_rate_limit(user_id, "login", 2):
        return
    user_data = get_user(user_id)
    if not has_access(user_data) or not has_enough_points(user_data):
        await message.answer(box("\U0001F6AB ACCESS DENIED", "You need a valid key and enough points."))
        return
    platform = user_data.get("platform", "jai")
    _user_states[user_id] = "login"
    if platform == "jai":
        title = "\U0001F511 JAI CLUB LOGIN"
        body = "Enter <b>username</b> and <b>password</b>:\n\n<code>username\npassword</code>"
    else:
        title = "\U0001F511 51GAME LOGIN"
        body = "Enter <b>phone</b> and <b>password</b>:\n\n<code>phone\npassword</code>"
    await message.answer(text=box(title, body))

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

    # ---- ENTER KEY ----
    if data == "enter_key":
        _user_states[user_id] = "enter_key"
        try:
            await callback.message.edit_text(
                text=box("\U0001F511 ENTER ACCESS KEY",
                    "Type your access key:\n\n<code>KEY-XXXX-XXXX</code>"
                ), reply_markup=back_only_kb())
        except Exception:
            await callback.message.answer(
                text=box("\U0001F511 ENTER ACCESS KEY",
                    "Type your access key:\n\n<code>KEY-XXXX-XXXX</code>"
                ), reply_markup=back_only_kb())
        await callback.answer()
        return

    # ---- CHECK REFERRALS ----
    if data == "check_referrals":
        user_data = get_user(user_id)
        ref_link = f"t.me/predictfinalbot?start=REF_{user_id}"
        refs = len(user_data.get("referrals", []))
        pts = user_data.get("points", 0)
        try:
            await callback.message.edit_text(
                text=box("\U0001F4DD REFERRALS",
                    f"<b>Your Link:</b>\n<code>{ref_link}</code>\n\n"
                    f"<b>Referrals:</b> <code>{refs}</code> / <code>{MIN_REFERRALS}</code>\n"
                    f"<b>Points:</b> <code>{pts}</code> / <code>{REQUIRED_POINTS}</code>\n\n"
                    f"<i>Share link to earn {REFERRAL_POINTS} pts per referral</i>"
                ), reply_markup=back_kb())
        except Exception:
            await callback.message.answer(
                text=box("\U0001F4DD REFERRALS",
                    f"<b>Your Link:</b>\n<code>{ref_link}</code>\n\n"
                    f"<b>Referrals:</b> <code>{refs}</code>\n"
                    f"<b>Points:</b> <code>{pts}</code>"
                ), reply_markup=back_kb())
        await callback.answer()
        return

    # ---- ADMIN CALLBACKS ----
    if data == "admin_panel":
        if not is_admin(callback.from_user):
            await callback.answer("Admin only!", show_alert=True)
            return
        users = _load_json(USERS_FILE)
        await callback.message.edit_text(
            text=box("\U0001F451 ADMIN PANEL",
                f"<b>Users:</b> <code>{len(users)}</code>\n"
                f"<b>Active:</b> <code>{sum(1 for u in _active_bots.values() if u.get('running'))}</code>"
            ), reply_markup=admin_kb())
        await callback.answer()
        return

    if data == "admin_genkey":
        if not is_admin(callback.from_user):
            await callback.answer("Admin only!", show_alert=True)
            return
        _user_states[user_id] = "genkey"
        try:
            await callback.message.edit_text(
                text=box("\U0001F511 GENERATE KEYS", "How many keys to generate?\n(1-50)"),
                reply_markup=back_only_kb())
        except Exception:
            await callback.message.answer(
                text=box("\U0001F511 GENERATE KEYS", "How many keys to generate?\n(1-50)"),
                reply_markup=back_only_kb())
        await callback.answer()
        return

    if data == "admin_stats":
        if not is_admin(callback.from_user):
            return
        users = _load_json(USERS_FILE)
        total_pts = sum(u.get("points", 0) for u in users.values())
        total_refs = sum(len(u.get("referrals", [])) for u in users.values())
        keys = get_keys()
        unused = sum(1 for v in keys.values() if not v.get("used"))
        try:
            await callback.message.edit_text(
                text=box("\U0001F4CA STATS",
                    f"<b>Users:</b> <code>{len(users)}</code>\n"
                    f"<b>Points:</b> <code>{total_pts}</code>\n"
                    f"<b>Referrals:</b> <code>{total_refs}</code>\n"
                    f"<b>Keys:</b> <code>{unused}</code> unused"
                ), reply_markup=admin_kb())
        except Exception:
            pass
        await callback.answer()
        return

    if data == "admin_listkeys":
        if not is_admin(callback.from_user):
            return
        keys = get_keys()
        unused = [k for k, v in keys.items() if not v.get("used")]
        text = "\n".join(f"<code>{k}</code>" for k in unused[:15])
        if len(unused) > 15:
            text += f"\n... +{len(unused)-15} more"
        if not text:
            text = "No unused keys."
        try:
            await callback.message.edit_text(
                text=box("\U0001F4CB KEYS", text), reply_markup=admin_kb())
        except Exception:
            pass
        await callback.answer()
        return

    if data == "admin_addpts":
        if not is_admin(callback.from_user):
            return
        _user_states[user_id] = "admin_addpts"
        try:
            await callback.message.edit_text(
                text=box("\U0001F464 ADD POINTS", "Send: user_id amount\n\nExample: <code>123456 500</code>"),
                reply_markup=back_only_kb())
        except Exception:
            await callback.message.answer(
                text=box("\U0001F464 ADD POINTS", "Send: user_id amount"),
                reply_markup=back_only_kb())
        await callback.answer()
        return

    # ---- ACCESS CHECK ----
    if not has_access(user_data):
        await callback.answer("\U0001F511 Enter access key first!", show_alert=True)
        return

    if not has_enough_points(user_data):
        await callback.answer(f"\U0001F4B0 Need {REQUIRED_POINTS} points! Get referrals.", show_alert=True)
        return

    platform = user_data.get("platform", "jai")

    if data == "back_menu":
        try:
            await callback.message.edit_text(text=box("\U0001F4CB MAIN MENU", "Choose an option:"), reply_markup=main_menu_kb())
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text=box("\U0001F4CB MAIN MENU", "Choose an option:"), reply_markup=main_menu_kb())
        await callback.answer()
        return

    if data == "switch_platform":
        try:
            await callback.message.edit_text(text=box("\U0001F504 SWITCH", "Select platform:"), reply_markup=platform_select_kb())
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text=box("\U0001F504 SWITCH", "Select platform:"), reply_markup=platform_select_kb())
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
            )
        else:
            img_f = "game_icon.png"
            text = box("\U0001F3AF 51GAME SELECTED",
                "<b>WinGo 30S / 1M / 3M / 5M</b>\n\n"
                "Type <b>/login</b> to authenticate\n"
                "Then enter balance to start"
            )
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
            await callback.answer("\U0001F511 Login first! Send /login", show_alert=True)
            return
        if not user_data.get("start_balance"):
            _user_states[user_id] = "set_amount"
            try:
                await callback.message.edit_text(
                    text=box("\U0001F4B0 SET BALANCE", "Enter total balance:\n<code>5000</code>"),
                    reply_markup=back_only_kb())
            except Exception:
                await callback.message.answer(
                    text=box("\U0001F4B0 SET BALANCE", "Enter total balance:\n<code>5000</code>"),
                    reply_markup=back_only_kb())
            await callback.answer()
            return
        if user_id in _active_bots and _active_bots[user_id].get("running"):
            await callback.answer("\U0001F6D1 Bot already running!", show_alert=True)
            return
        await callback.answer("\U0001F680 Starting!")
        pn = "JAI CLUB" if platform == "jai" else "51GAME"
        try:
            await callback.message.edit_text(
                text=box("\u2705 BOT STARTED", f"<b>Platform:</b> {pn}\n\nSend <b>/stop</b> to stop"),
                reply_markup=main_menu_kb())
        except Exception:
            await callback.message.answer(
                text=box("\u2705 BOT STARTED", f"<b>Platform:</b> {pn}\n\nSend <b>/stop</b> to stop"),
                reply_markup=main_menu_kb())
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
            f"<b>Points:</b> <code>{pts}</code>")
        try:
            await callback.message.edit_text(text=txt, reply_markup=back_kb())
        except Exception:
            await callback.message.answer(text=txt, reply_markup=back_kb())
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
            f"<b>Level:</b> <code>{bd.get('level',0)}</code>")
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
            txt = box("\U0001F3AE GAMES", "Select game type:")
            kb = game_menu_kb_jai()
        else:
            txt = box("\U0001F3AE GAMES", "Select game type:")
            kb = game_menu_kb_51()
        try:
            await callback.message.edit_text(text=txt, reply_markup=kb)
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text=txt, reply_markup=kb)
        await callback.answer()
        return

    if data in ["game_30s", "game_1m"]:
        game = "WinGo_30S" if data == "game_30s" else "WinGo_1M"
        user_data["game"] = game
        update_user(user_id, user_data)
        try:
            await callback.message.edit_text(text=box("\u2705 GAME SET", f"<b>{game}</b>"), reply_markup=main_menu_kb())
        except Exception:
            await callback.message.answer(text=box("\u2705 GAME SET", f"<b>{game}</b>"), reply_markup=main_menu_kb())
        await callback.answer(f"Game: {game}")
        return

    if data.startswith("game51_"):
        gm = {"game51_30": 30, "game51_1m": 1, "game51_3m": 2, "game51_5m": 3}
        tid = gm.get(data, 30)
        user_data["game51_type_id"] = tid
        update_user(user_id, user_data)
        nm = {30: "30 SEC", 1: "1 MIN", 2: "3 MIN", 3: "5 MIN"}
        try:
            await callback.message.edit_text(text=box("\u2705 GAME SET", f"<b>WinGo {nm.get(tid,'30S')}</b>"), reply_markup=main_menu_kb())
        except Exception:
            await callback.message.answer(text=box("\u2705 GAME SET", f"<b>WinGo {nm.get(tid,'30S')}</b>"), reply_markup=main_menu_kb())
        await callback.answer(f"WinGo {nm.get(tid,'30S')}")
        return

    if data == "stop_bot":
        try:
            await callback.message.edit_text(text=box("\U0001F6D1 STOP?", "Confirm stop:"), reply_markup=stop_confirm_kb())
        except Exception:
            await callback.message.answer(text=box("\U0001F6D1 STOP?", "Confirm stop:"), reply_markup=stop_confirm_kb())
        await callback.answer()
        return

    if data == "confirm_stop":
        if user_id in _active_bots:
            _active_bots[user_id]["running"] = False
        try:
            await callback.message.edit_text(text=box("\U0001F6D1 STOPPED", "Use /start to restart."), reply_markup=main_menu_kb())
        except Exception:
            await callback.message.answer(text=box("\U0001F6D1 STOPPED", "Use /start to restart."), reply_markup=main_menu_kb())
        await callback.answer("\U0001F6D1 Stopped!")
        return

    if data == "cancel_stop":
        try:
            await callback.message.edit_text(text=box("\u2705 RUNNING", "Bot continues."), reply_markup=main_menu_kb())
        except Exception:
            await callback.message.answer(text=box("\u2705 RUNNING", "Bot continues."), reply_markup=main_menu_kb())
        await callback.answer("Still running!")
        return

    if data == "settings":
        try:
            await callback.message.edit_text(text=box("\u2699 SETTINGS", "Adjust settings:"), reply_markup=settings_kb(user_data))
        except Exception:
            await callback.message.answer(text=box("\u2699 SETTINGS", "Adjust settings:"), reply_markup=settings_kb(user_data))
        await callback.answer()
        return

    if data == "toggle_restart":
        user_data["auto_restart"] = not user_data.get("auto_restart", True)
        update_user(user_id, user_data)
        st = "ON" if user_data["auto_restart"] else "OFF"
        try:
            await callback.message.edit_text(text=box("\u2699 SETTINGS", f"<b>Restart:</b> {st}"), reply_markup=settings_kb(user_data))
        except Exception:
            pass
        await callback.answer(f"Restart: {st}")
        return

    if data == "set_bet":
        _user_states[user_id] = "set_bet"
        try:
            await callback.message.edit_text(text=box("\U0001F4B0 SET BET", "Enter bet amount (min 2):"), reply_markup=back_only_kb())
        except Exception:
            await callback.message.answer(text=box("\U0001F4B0 SET BET", "Enter bet amount (min 2):"), reply_markup=back_only_kb())
        await callback.answer()
        return

    if data == "set_multiplier":
        _user_states[user_id] = "set_mult"
        try:
            await callback.message.edit_text(text=box("\U0001F4C8 SET MULTIPLIER", "Enter multiplier (min 1.5):"), reply_markup=back_only_kb())
        except Exception:
            await callback.message.answer(text=box("\U0001F4C8 SET MULTIPLIER", "Enter multiplier (min 1.5):"), reply_markup=back_only_kb())
        await callback.answer()
        return

    if data == "set_target":
        _user_states[user_id] = "set_target"
        try:
            await callback.message.edit_text(text=box("\U0001F3AF SET TARGET", "Enter target % (5-500):"), reply_markup=back_only_kb())
        except Exception:
            await callback.message.answer(text=box("\U0001F3AF SET TARGET", "Enter target % (5-500):"), reply_markup=back_only_kb())
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

    # ---- ADMIN STATES ----
    if is_admin(message.from_user):
        if state == "genkey":
            _user_states.pop(user_id, None)
            try:
                count = max(1, min(50, int(text)))
            except ValueError:
                count = 1
            keys = get_keys()
            new_keys = []
            for _ in range(count):
                k = gen_key()
                keys[k] = {"used": False, "created_by": user_id, "created_at": datetime.now().isoformat()}
                new_keys.append(k)
            save_keys(keys)
            key_list = "\n".join(f"<code>{k}</code>" for k in new_keys)
            await message.answer(box(f"\U0001F511 {count} KEYS", f"{key_list}"))
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
                    await message.answer(box("\u2705 DONE", f"Added {amt} to <code>{uid}</code>\nTotal: {ud['points']}"))
                except (ValueError, IndexError):
                    await message.answer("Format: user_id amount")
            return

    # ---- ENTER KEY STATE ----
    if state == "enter_key":
        _user_states.pop(user_id, None)
        key = text.strip().upper()
        keys = get_keys()
        if key in keys and not keys[key].get("used"):
            keys[key]["used"] = True
            keys[key]["used_by"] = user_id
            save_keys(keys)
            user_data["access_key_valid"] = True
            user_data["access_key"] = key
            update_user(user_id, user_data)
            await message.answer(box("\u2705 KEY ACCEPTED!",
                "Access granted!\n\nNow set your balance to start.\nUse /start to continue."
            ))
        else:
            await message.answer(box("\u274C INVALID KEY", "Key not found or already used.\nTry again or contact admin."))
        return

    # ---- LOGIN STATE ----
    if state == "login":
        if not has_access(user_data) or not has_enough_points(user_data):
            await message.answer(box("\U0001F6AB DENIED", "Need valid key and points."))
            return
        lines = text.split("\n")
        if len(lines) < 2:
            await message.answer(box("\u274C FORMAT", "Send:\n<code>username\npassword</code>"))
            return
        username = lines[0].strip()[:50]
        password = lines[1].strip()[:50]
        if not username or not password:
            await message.answer(box("\u274C EMPTY", "Username/password cannot be empty"))
            return
        user_data["login_user"] = username
        user_data["login_pass"] = password
        user_data["logged_in"] = True
        update_user(user_id, user_data)
        _user_states[user_id] = "set_amount"
        platform = user_data.get("platform", "jai")
        pn = "JAI CLUB" if platform == "jai" else "51GAME"
        await message.answer(text=box("\U0001F4B0 SET BALANCE",
            f"<b>{pn}</b>\n\nEnter balance:\n<code>5000</code>"))
        return

    if state == "set_amount":
        try:
            amount = max(100, int(text))
        except ValueError:
            await message.answer(box("\u274C INVALID", "Enter a number. Min 100"))
            return
        user_data["start_balance"] = amount
        update_user(user_id, user_data)
        _user_states.pop(user_id, None)
        platform = user_data.get("platform", "jai")
        pn = "JAI CLUB" if platform == "jai" else "51GAME"
        await message.answer(text=box("\u2705 READY", f"<b>{pn}</b> | Balance: {amount}\nStarting..."), reply_markup=main_menu_kb())
        user_data = get_user(user_id)
        asyncio.create_task(run_betting(user_id, message.chat.id, user_data))
        return

    if state == "set_bet":
        try:
            bet = max(2, int(text))
        except ValueError:
            await message.answer(box("\u274C INVALID", "Enter a number. Min 2"))
            return
        user_data["total_bet"] = bet
        update_user(user_id, user_data)
        _user_states.pop(user_id, None)
        await message.answer(text=box("\u2705 BET SET", f"<b>{bet}</b>"), reply_markup=main_menu_kb())
        return

    if state == "set_mult":
        try:
            mult = max(1.5, float(text))
        except ValueError:
            await message.answer(box("\u274C INVALID", "Enter a number. Min 1.5"))
            return
        user_data["multiplier"] = mult
        update_user(user_id, user_data)
        _user_states.pop(user_id, None)
        await message.answer(text=box("\u2705 MULTIPLIER SET", f"<b>{mult}x</b>"), reply_markup=main_menu_kb())
        return

    if state == "set_target":
        try:
            target = max(5, min(500, float(text)))
        except ValueError:
            await message.answer(box("\u274C INVALID", "Enter 5-500"))
            return
        user_data["profit_target"] = target
        update_user(user_id, user_data)
        _user_states.pop(user_id, None)
        await message.answer(text=box("\u2705 TARGET SET", f"<b>{target}%</b>"), reply_markup=main_menu_kb())
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

    msg = await bot.send_message(chat_id, box("\u23F3 JAI CLUB", "Logging in..."), reply_markup=main_menu_kb())
    _profit_messages[user_id] = msg.message_id

    try:
        engine = AutoBetEngine(username, password, game, total_bet, multiplier, 55)
        engine.checker.lottery_api_base_url = "https://h5.ar-lottery06.com"
        engine.checker.lottery_draw_base_url = "https://draw.ar-lottery06.com"
        engine.login()
        engine.checker.fetch_ar_token(game)
    except Exception as e:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=box("\u274C FAILED", safe_str(e, 100)))
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
            ud = get_user(user_id)
            if not ud.get("is_admin") and ud.get("points", 0) <= 0 and not ud.get("banned"):
                bot_state["running"] = False
                try:
                    await bot.send_message(chat_id, box("\U0001F4B0 POINTS OVER", "No points left! Get referrals to earn more."))
                except Exception:
                    pass
                break

            elapsed = time.time() - bot_state["start_time"]
            if elapsed >= 60:
                bot_state["start_time"] = time.time()
                if not ud.get("is_admin"):
                    remaining = deduct_point(user_id)
                    if remaining <= 0:
                        bot_state["running"] = False
                        try:
                            await bot.send_message(chat_id, box("\U0001F4B0 POINTS OVER", "No points left!"))
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
                            await bot.send_message(chat_id, box("\U0001F389 TARGET REACHED!",
                                f"<b>Target:</b> {profit_target}%\n<b>Profit:</b> +{bot_state['profit']:.2f}"))
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
                text=format_profit(bot_state, "STOPPED", "JAI CLUB"), reply_markup=main_menu_kb())
        except Exception:
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

    msg = await bot.send_message(chat_id, box("\u23F3 51GAME", "Logging in..."), reply_markup=main_menu_kb())
    _profit_messages[user_id] = msg.message_id

    checker = Game51AccountChecker(username, password)
    try:
        if not checker.perform_login():
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
                    text=box("\u274C FAILED", safe_str(checker.message, 100)))
            except Exception:
                pass
            return
    except Exception as e:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
                text=box("\u274C FAILED", safe_str(e, 100)))
        except Exception:
            pass
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
        "target_hit": False, "profit_target": profit_target, "start_time": time.time()
    }
    _active_bots[user_id] = bot_state
    levels = make_levels(balance, total_bet, 2.0)
    await update_profit_msg(user_id, chat_id, bot_state, "RUNNING", f"51GAME {game_name}")

    while bot_state["running"]:
        try:
            ud = get_user(user_id)
            if not ud.get("is_admin") and ud.get("points", 0) <= 0 and not ud.get("banned"):
                bot_state["running"] = False
                try:
                    await bot.send_message(chat_id, box("\U0001F4B0 POINTS OVER", "No points left!"))
                except Exception:
                    pass
                break

            elapsed = time.time() - bot_state["start_time"]
            if elapsed >= 60:
                bot_state["start_time"] = time.time()
                if not ud.get("is_admin"):
                    remaining = deduct_point(user_id)
                    if remaining <= 0:
                        bot_state["running"] = False
                        try:
                            await bot.send_message(chat_id, box("\U0001F4B0 POINTS OVER", "No points left!"))
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
                                f"<b>Profit:</b> +{bot_state['profit']:.2f} ({pct:.1f}%)"))
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
                    bs_ok = "error" not in results.get("bs", {})
                    color_ok = "error" not in results.get("color", {})
                    if bs_ok or color_ok:
                        bot_state["pending"] = {
                            "period": open_issue, "bs_prediction": bs_pred, "color_prediction": co_pred,
                            "total_bet": lv["total_bet"], "level": lv["level"]
                        }
                        await update_profit_msg(user_id, chat_id, bot_state, "WAITING", f"51GAME {game_name}")
                except Exception as e:
                    logger.error(f"51GAME Bet failed: {e}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"51GAME error: {e}")
            await asyncio.sleep(3)

    if user_id in _profit_messages:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=_profit_messages[user_id],
                text=format_profit(bot_state, "STOPPED", f"51GAME {game_name}"), reply_markup=main_menu_kb())
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
    text = format_profit(bot_state, status, platform)
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

# ============================================
# BOT START
# ============================================
async def main():
    print("DUAL GAME BOT STARTED!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
