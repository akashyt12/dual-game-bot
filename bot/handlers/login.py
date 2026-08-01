from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from bot.config import REQUIRED_POINTS
from bot.database import get_user, update_user
from bot.keyboards import box, footer, main_menu_kb

router = Router()
_user_states = {}


@router.message(F.text.startswith("/login"))
async def cmd_login(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if user.get("banned"):
        return
    pts = user.get("points", 0)
    if pts < REQUIRED_POINTS:
        from bot.keyboards import referral_only_kb
        await message.answer(box("💰 INSUFFICIENT POINTS",
            f"You need {REQUIRED_POINTS} points.\nGet referrals!") + footer(),
            reply_markup=referral_only_kb())
        return
    _user_states[user_id] = "login"
    platform = user.get("platform", "jai")
    titles = {"jai": "🔑 JAI CLUB LOGIN", "bdgwin": "💰 BDGWIN LOGIN", "51": "🔑 51GAME LOGIN"}
    bodies = {
        "jai": "Enter <b>username</b> and <b>password</b>:\n\n<code>username\npassword</code>",
        "bdgwin": "Enter <b>username</b> and <b>password</b>:\n\n<code>username\npassword</code>",
        "51": "Enter <b>phone</b> and <b>password</b>:\n\n<code>phone\npassword</code>",
    }
    await message.answer(box(titles.get(platform, "LOGIN"), bodies.get(platform, "")) + footer())


@router.callback_query(F.data == "start_bot")
async def cb_start_bot(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    if not user.get("logged_in"):
        _user_states[user_id] = "login"
        platform = user.get("platform", "jai")
        titles = {"jai": "🔑 JAI CLUB LOGIN", "bdgwin": "💰 BDGWIN LOGIN", "51": "🔑 51GAME LOGIN"}
        bodies = {
            "jai": "Enter <b>username</b> and <b>password</b>:\n\n<code>username\npassword</code>",
            "bdgwin": "Enter <b>username</b> and <b>password</b>:\n\n<code>username\npassword</code>",
            "51": "Enter <b>phone</b> and <b>password</b>:\n\n<code>phone\npassword</code>",
        }
        try:
            await callback.message.edit_text(
                box(titles.get(platform, "LOGIN"), bodies.get(platform, "")) + footer())
        except Exception:
            from bot.bot_instance import bot
            await bot.send_message(callback.message.chat.id,
                box(titles.get(platform, "LOGIN"), bodies.get(platform, "")) + footer())
        await callback.answer("🔑 Login first!", show_alert=False)
        return

    pts = user.get("points", 0)
    if pts < REQUIRED_POINTS:
        from bot.keyboards import referral_only_kb
        ref_link = f"t.me/predictor20lord_bot?start=REF_{user_id}"
        from bot.bot_instance import bot
        await bot.send_message(callback.message.chat.id,
            box("💰 NEED POINTS",
                f"<b>Points:</b> <code>{pts}</code> / <code>{REQUIRED_POINTS}</code>\n\n"
                f"Referral link:\n<code>{ref_link}</code>"),
            reply_markup=referral_only_kb())
        await callback.answer()
        return

    if not user.get("start_balance"):
        _user_states[user_id] = "set_amount"
        try:
            await callback.message.edit_text(
                box("💰 SET BALANCE", "Enter total balance:\n<code>5000</code>") + footer())
        except Exception:
            from bot.bot_instance import bot
            await bot.send_message(callback.message.chat.id,
                box("💰 SET BALANCE", "Enter total balance:\n<code>5000</code>") + footer())
        await callback.answer()
        return

    from bot.handlers.dashboard import start_betting
    await callback.answer("🚀 Starting!")
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    user = await get_user(user_id)
    await bot.send_message(callback.message.chat.id,
        box("✅ STARTED", "Bot running! /stop to stop.") + footer(),
        reply_markup=main_menu_kb())
    import asyncio
    asyncio.create_task(start_betting(user_id, callback.message.chat.id, user))


async def handle_login_state(message: Message, user_id: int, text: str):
    lines = text.split("\n")
    if len(lines) < 2:
        await message.answer(box("❌ FORMAT", "Send:\n<code>username\npassword</code>") + footer())
        return
    username = lines[0].strip()[:50]
    password = lines[1].strip()[:50]
    if not username or not password:
        await message.answer(box("❌ EMPTY", "Cannot be empty") + footer())
        return
    from bot.bot_instance import _active_bots
    if user_id not in _active_bots:
        _active_bots[user_id] = {}
    _active_bots[user_id]["login_user"] = username
    _active_bots[user_id]["login_pass"] = password
    await update_user(user_id, {"logged_in": 1, "login_user": username})
    _user_states[user_id] = "set_amount"
    user = await get_user(user_id)
    platform = user.get("platform", "jai")
    pn = {"jai": "JAI CLUB", "bdgwin": "BDGWIN", "51": "51GAME"}.get(platform, "JAI CLUB")
    await message.answer(box("💰 SET BALANCE", f"<b>{pn}</b>\nEnter balance:\n<code>5000</code>") + footer())


async def handle_set_amount(message: Message, user_id: int, text: str):
    try:
        amount = max(100, int(text))
    except ValueError:
        await message.answer(box("❌ INVALID", "Enter a number. Min 100") + footer())
        return
    await update_user(user_id, {"start_balance": amount})
    _user_states.pop(user_id, None)
    user = await get_user(user_id)
    platform = user.get("platform", "jai")
    pn = {"jai": "JAI CLUB", "bdgwin": "BDGWIN", "51": "51GAME"}.get(platform, "JAI CLUB")
    await message.answer(box("✅ READY", f"<b>{pn}</b> | Balance: {amount}\nStarting...") + footer(),
                         reply_markup=main_menu_kb())
    import asyncio
    from bot.handlers.dashboard import start_betting
    user = await get_user(user_id)
    asyncio.create_task(start_betting(user_id, message.chat.id, user))


async def handle_set_bet(message: Message, user_id: int, text: str):
    try:
        bet = max(2, int(text))
    except ValueError:
        await message.answer(box("❌ INVALID", "Enter a number. Min 2") + footer())
        return
    await update_user(user_id, {"total_bet": bet})
    _user_states.pop(user_id, None)
    await message.answer(box("✅ BET SET", f"<b>{bet}</b>") + footer(), reply_markup=main_menu_kb())


async def handle_set_mult(message: Message, user_id: int, text: str):
    try:
        mult = max(1.5, float(text))
    except ValueError:
        await message.answer(box("❌ INVALID", "Enter a number. Min 1.5") + footer())
        return
    await update_user(user_id, {"multiplier": mult})
    _user_states.pop(user_id, None)
    await message.answer(box("✅ MULTIPLIER SET", f"<b>{mult}x</b>") + footer(), reply_markup=main_menu_kb())


async def handle_set_target(message: Message, user_id: int, text: str):
    try:
        target = max(5, min(500, float(text)))
    except ValueError:
        await message.answer(box("❌ INVALID", "Enter 5-500") + footer())
        return
    await update_user(user_id, {"profit_target": target})
    _user_states.pop(user_id, None)
    await message.answer(box("✅ TARGET SET", f"<b>{target}%</b>") + footer(), reply_markup=main_menu_kb())


async def handle_set_delay(message: Message, user_id: int, text: str):
    try:
        delay = max(0.5, min(10.0, float(text)))
    except ValueError:
        await message.answer(box("❌ INVALID", "Enter 0.5-10.0") + footer())
        return
    await update_user(user_id, {"bet_delay": delay})
    _user_states.pop(user_id, None)
    await message.answer(box("✅ DELAY SET", f"<b>{delay}s</b>") + footer(), reply_markup=main_menu_kb())


async def handle_set_confidence(message: Message, user_id: int, text: str):
    try:
        conf = max(30, min(95, int(text)))
    except ValueError:
        await message.answer(box("❌ INVALID", "Enter 30-95") + footer())
        return
    await update_user(user_id, {"confidence": conf})
    _user_states.pop(user_id, None)
    await message.answer(box("✅ CONFIDENCE SET", f"<b>{conf}%</b>") + footer(), reply_markup=main_menu_kb())


async def handle_set_stoploss(message: Message, user_id: int, text: str):
    try:
        sl = max(0, min(50, float(text)))
    except ValueError:
        await message.answer(box("❌ INVALID", "Enter 0-50") + footer())
        return
    await update_user(user_id, {"stop_loss": sl})
    _user_states.pop(user_id, None)
    await message.answer(box("✅ STOP LOSS SET", f"<b>{sl}%</b>") + footer(), reply_markup=main_menu_kb())


STATE_HANDLERS = {
    "login": handle_login_state,
    "set_amount": handle_set_amount,
    "set_bet": handle_set_bet,
    "set_mult": handle_set_mult,
    "set_target": handle_set_target,
    "set_delay": handle_set_delay,
    "set_confidence": handle_set_confidence,
    "set_stoploss": handle_set_stoploss,
}


def get_state(user_id: int):
    return _user_states.get(user_id)


def pop_state(user_id: int):
    _user_states.pop(user_id, None)
