from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from bot.config import ADMIN_ID, BOT_TOKEN
from bot.database import (get_user, update_user, get_all_users, get_stats,
                          add_premium_key, get_premium_keys, get_referral_count)
from bot.keyboards import admin_kb, main_menu_kb, box, footer
from bot.handlers.dashboard import _active_bots

router = Router()

ADMIN_IDS = [int(x.strip()) for x in str(ADMIN_ID).split(",") if x.strip().isdigit()]


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(F.text == "/admin")
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    users = await get_all_users()
    total = len(users)
    premium = sum(1 for u in users if u.get("premium") == 1)
    banned = sum(1 for u in users if u.get("banned") == 1)
    from bot.keyboards import admin_kb
    await message.answer(box("🛡 ADMIN",
        f"<b>Total:</b> <code>{total}</code>\n"
        f"<b>Premium:</b> <code>{premium}</code>\n"
        f"<b>Banned:</b> <code>{banned}</code>"), reply_markup=admin_kb())


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌")
        return
    users = await get_all_users()
    total = len(users)
    premium = sum(1 for u in users if u.get("premium") == 1)
    banned = sum(1 for u in users if u.get("banned") == 1)
    total_pts = sum(u.get("points", 0) for u in users)
    try:
        await callback.message.edit_text(box("📊 STATS",
            f"<b>Total:</b> <code>{total}</code>\n"
            f"<b>Premium:</b> <code>{premium}</code>\n"
            f"<b>Banned:</b> <code>{banned}</code>\n"
            f"<b>Total Points:</b> <code>{total_pts}</code>"), reply_markup=admin_kb())
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("admin_user:"))
async def cb_admin_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌")
        return
    uid = int(callback.data.split(":")[1])
    user = await get_user(uid)
    refs = await get_referral_count(uid)
    txt = box("👤 USER",
        f"<b>ID:</b> <code>{uid}</code>\n"
        f"<b>Name:</b> {user.get('name','N/A')}\n"
        f"<b>Username:</b> @{user.get('username','N/A')}\n"
        f"<b>Points:</b> <code>{user.get('points',0)}</code>\n"
        f"<b>Referrals:</b> <code>{refs}</code>\n"
        f"<b>Premium:</b> {'YES' if user.get('premium') else 'NO'}\n"
        f"<b>Banned:</b> {'YES' if user.get('banned') else 'NO'}")
    try:
        await callback.message.edit_text(txt, reply_markup=admin_kb())
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ban:"))
async def cb_admin_ban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌")
        return
    uid = int(callback.data.split(":")[1])
    user = await get_user(uid)
    new_val = 0 if user.get("banned") else 1
    await update_user(uid, {"banned": new_val})
    action = "BANNED" if new_val else "UNBANNED"
    await callback.answer(f"{action}!")
    if uid in _active_bots:
        _active_bots[uid]["running"] = False
    try:
        await callback.message.edit_text(box("🛡 ACTION", f"<b>User {uid} {action}</b>"), reply_markup=admin_kb())
    except Exception:
        pass
    from bot.bot_instance import bot
    try:
        await bot.send_message(uid, box("⚠ NOTICE", f"You have been {action.lower()} by admin."))
    except Exception:
        pass


@router.callback_query(F.data.startswith("admin_prem:"))
async def cb_admin_prem(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌")
        return
    uid = int(callback.data.split(":")[1])
    user = await get_user(uid)
    new_val = 1 if user.get("premium") else 0
    await update_user(uid, {"premium": new_val, "premium_days": 30})
    action = "PREMIUM ON" if new_val else "PREMIUM OFF"
    await callback.answer(f"{action}!")
    from bot.bot_instance import bot
    try:
        await bot.send_message(uid, box("💎 NOTICE", f"Premium {'activated' if new_val else 'deactivated'}."))
    except Exception:
        pass


@router.message(F.text.startswith("/genkey"))
async def cmd_genkey(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(box("❌ FORMAT", "/genkey <days> [username]"))
        return
    try:
        days = int(parts[1])
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer(box("❌ INVALID", "Days must be positive"))
        return
    username = parts[2].lstrip("@") if len(parts) > 2 else None
    import secrets
    key = f"PREM-{secrets.token_hex(4).upper()}-{secrets.token_hex(2).upper()}"
    await add_premium_key(key, days, username, message.from_user.id)
    extra = f"\n<b>For:</b> @{username}" if username else ""
    await message.answer(box("🔑 KEY CREATED", f"<code>{key}</code>\n<b>Duration:</b> {days} days{extra}"))


@router.message(F.text.startswith("/user"))
async def cmd_user_info(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Format: /user <user_id>")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("Invalid ID")
        return
    user = await get_user(uid)
    if not user:
        await message.answer("User not found")
        return
    refs = await get_referral_count(uid)
    await message.answer(box("👤 USER",
        f"<b>ID:</b> <code>{uid}</code>\n"
        f"<b>Name:</b> {user.get('name','N/A')}\n"
        f"<b>Username:</b> @{user.get('username','N/A')}\n"
        f"<b>Points:</b> <code>{user.get('points',0)}</code>\n"
        f"<b>Referrals:</b> <code>{refs}</code>\n"
        f"<b>Premium:</b> {'YES' if user.get('premium') else 'NO'}\n"
        f"<b>Banned:</b> {'YES' if user.get('banned') else 'NO'}"))


@router.message(F.text.startswith("/broadcast"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return
    text = message.text.replace("/broadcast", "", 1).strip()
    if not text:
        await message.answer("Format: /broadcast <message>")
        return
    users = await get_all_users()
    sent = 0
    failed = 0
    from bot.bot_instance import bot
    for user in users:
        try:
            await bot.send_message(user["user_id"], text)
            sent += 1
        except Exception:
            failed += 1
    await message.answer(box("📢 DONE", f"Sent: {sent} | Failed: {failed}"))


@router.message(F.text.startswith("/admin_addpoints"))
async def cmd_addpoints(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Format: /admin_addpoints <user_id> <points>")
        return
    try:
        uid = int(parts[1])
        pts = int(parts[2])
    except ValueError:
        await message.answer("Invalid format")
        return
    user = await get_user(uid)
    curr = user.get("points", 0)
    await update_user(uid, {"points": curr + pts})
    await message.answer(box("✅ DONE", f"Added {pts} to {uid}. Total: {curr + pts}"))
