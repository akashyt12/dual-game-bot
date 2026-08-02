from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from html import escape
from bot.config import BOT_VERSION, REFERRAL_POINTS, REQUIRED_POINTS, IMAGES_DIR
from bot.database import (get_user, update_user, upsert_user, get_channels,
                          get_referral_count, was_referred, get_referrer, add_referral,
                          update_stats, is_admin, get_user_count)
from bot.keyboards import (channels_join_kb, main_menu_kb, referral_only_kb,
                           platform_select_kb, box, footer)

router = Router()


def img(name):
    if not name:
        return None
    p = IMAGES_DIR / name
    return str(p) if p.exists() else None


def safe(val, mx=50):
    return escape(str(val).strip()[:mx])


@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    args = (message.text or "").split()
    ref_code = None
    if len(args) > 1 and args[1].startswith("REF_"):
        try:
            ref_code = int(args[1].replace("REF_", ""))
        except ValueError:
            pass

    user = await get_user(user_id)
    name = safe(message.from_user.first_name or "User")
    username = message.from_user.username or ""

    if await is_admin(user_id):
        await upsert_user(user_id, {"is_admin": 1, "name": name, "username": username})
        await message.answer(
            box(f"👑 ADMIN - {BOT_VERSION}",
                f"Welcome Admin <b>{name}</b>!\n\nFull access granted."),
            reply_markup=admin_kb())
        return

    if user.get("banned"):
        await message.answer(box("🚫 BANNED", "You are banned.\nContact admin.") + footer())
        return

    await upsert_user(user_id, {"name": name, "username": username})

    # Fresh login: always clear old login state
    await update_user(user_id, {
        "logged_in": 0,
        "login_user": "",
        "start_balance": 0,
    })

    if ref_code and ref_code != user_id and not await was_referred(user_id):
        from bot.handlers.referral import pending_referrals
        pending_referrals[user_id] = ref_code

    channels = await get_channels()
    if channels and not user.get("verified_channels"):
        await message.answer(
            box("📢 JOIN CHANNELS",
                f"Welcome <b>{name}</b>!\n\nJoin our channels to use the bot."),
            reply_markup=channels_join_kb(channels))
        return

    pts = user.get("points", 0)
    if pts < REQUIRED_POINTS and not await is_admin(user_id):
        ref_link = f"t.me/predictor20lord_bot?start=REF_{user_id}"
        refs = await get_referral_count(user_id)
        await message.answer(
            box(f"💰 NEED {REQUIRED_POINTS} POINTS",
                f"Welcome <b>{name}</b>!\n\n"
                f"<b>Your Points:</b> <code>{pts}</code> / <code>{REQUIRED_POINTS}</code>\n"
                f"<b>Referrals:</b> <code>{refs}</code>\n\n"
                f"Share your referral link:\n<code>{ref_link}</code>\n\n"
                f"<i>Each referral = {REFERRAL_POINTS} points</i>"),
            reply_markup=referral_only_kb())
        return

    await send_main_menu(message.chat.id, user_id, name, pts)


async def send_main_menu(chat_id, user_id, name, pts):
    image = img("main_menu.png")
    text = box(f"🎮 {BOT_VERSION}",
        f"Welcome <b>{name}</b>!\n\n"
        f"<b>Points:</b> <code>{pts}</code>\n\n"
        "Choose an option:") + footer()
    try:
        if image:
            from aiogram.types import FSInputFile as FI
            from bot.bot_instance import bot
            await bot.send_photo(chat_id=chat_id, photo=FI(image),
                caption=text, parse_mode="HTML", reply_markup=main_menu_kb())
        else:
            from bot.bot_instance import bot
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=main_menu_kb())
    except Exception:
        from bot.bot_instance import bot
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=main_menu_kb())


@router.callback_query(F.data == "check_joined")
async def cb_check_joined(callback: CallbackQuery):
    user_id = callback.from_user.id
    if await is_admin(user_id):
        await callback.answer("Admin bypass!", show_alert=False)
        return

    channels = await get_channels()
    all_ok = True
    for ch in channels:
        ch_id = ch["channel_id"]
        if ch_id.startswith("https://t.me/+"):
            continue
        try:
            from bot.bot_instance import bot
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ("left", "kicked"):
                all_ok = False
                break
        except Exception:
            all_ok = False
            break

    if not all_ok:
        await callback.answer("❌ Not joined all channels! Join then verify.", show_alert=True)
        return

    await update_user(user_id, {"verified_channels": 1})
    from bot.handlers.referral import pending_referrals
    if user_id in pending_referrals:
        ref_code = pending_referrals.pop(user_id)
        if ref_code != user_id and not await was_referred(user_id):
            ok = await add_referral(ref_code, user_id)
            if ok:
                from bot.config import REFERRAL_POINTS
                ref_user = await get_user(ref_code)
                new_pts = ref_user.get("points", 0) + REFERRAL_POINTS
                await update_user(ref_code, {"points": new_pts})
                try:
                    from bot.bot_instance import bot
                    await bot.send_message(ref_code,
                        box("🎉 NEW REFERRAL!",
                            f"User <b>{safe(callback.from_user.first_name)}</b> joined!\n\n"
                            f"<b>+{REFERRAL_POINTS} points</b> added!"))
                except Exception:
                    pass

    user = await get_user(user_id)
    pts = user.get("points", 0)
    name = user.get("name", safe(callback.from_user.first_name or "User"))
    ref_link = f"t.me/predictor20lord_bot?start=REF_{user_id}"
    refs = await get_referral_count(user_id)

    if pts < REQUIRED_POINTS:
        await callback.message.edit_text(
            box(f"💰 NEED {REQUIRED_POINTS} POINTS",
                f"Welcome <b>{name}</b>!\n\n"
                f"<b>Your Points:</b> <code>{pts}</code> / <code>{REQUIRED_POINTS}</code>\n"
                f"<b>Referrals:</b> <code>{refs}</code>\n\n"
                f"Share your referral link:\n<code>{ref_link}</code>\n\n"
                f"<i>Each referral = {REFERRAL_POINTS} points</i>"),
            reply_markup=referral_only_kb())
        await callback.answer("✅ Verified!", show_alert=False)
        return

    await callback.message.edit_text(
        box(f"✅ VERIFIED!", f"Welcome <b>{name}</b>!\n\nAll channels joined!") + footer(),
        reply_markup=main_menu_kb())
    await callback.answer("✅ Verified!", show_alert=False)


@router.message(Command("stop"))
async def cmd_stop(message: Message):
    from bot.handlers.dashboard import _active_bots
    user_id = message.from_user.id
    if user_id in _active_bots:
        _active_bots[user_id]["running"] = False
        await message.answer(box("🛑 STOPPING", "Bot stopping..."))
    else:
        await message.answer(box("ℹ NOT RUNNING", "No active session.\nUse /start to begin."))


@router.callback_query(F.data == "back_menu")
async def cb_back_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    pts = user.get("points", 0)
    name = user.get("name", "User")
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    image = img("main_menu.png")
    text = box(f"📋 MENU",
        f"Welcome <b>{name}</b>!\n\n<b>Points:</b> <code>{pts}</code>\n\nChoose:") + footer()
    try:
        if image:
            await bot.send_photo(chat_id=callback.message.chat.id, photo=FSInputFile(image),
                caption=text, parse_mode="HTML", reply_markup=main_menu_kb())
        else:
            await bot.send_message(chat_id=callback.message.chat.id, text=text, reply_markup=main_menu_kb())
    except Exception:
        await bot.send_message(chat_id=callback.message.chat.id, text=text, reply_markup=main_menu_kb())
    await callback.answer()


def admin_kb():
    from bot.keyboards import admin_kb as _admin_kb
    return _admin_kb()
