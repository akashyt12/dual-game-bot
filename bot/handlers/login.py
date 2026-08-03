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

    # Always force fresh login
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
    await callback.answer("🔑 Fresh login required!", show_alert=False)


# ── STEP 1: Login ──
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

    # Step 2: Ask balance
    _user_states[user_id] = "set_amount"
    user = await get_user(user_id)
    platform = user.get("platform", "jai")
    pn = {"jai": "JAI CLUB", "bdgwin": "BDGWIN", "51": "51GAME"}.get(platform, "JAI CLUB")
    await message.answer(box("💰 STEP 2 - BALANCE",
        f"<b>{pn}</b>\n\nEnter your total balance:\n<code>5000</code>") + footer())


# ── STEP 2: Balance ──
async def handle_set_amount(message: Message, user_id: int, text: str):
    try:
        amount = max(100, int(text))
    except ValueError:
        await message.answer(box("❌ INVALID", "Enter a number. Min 100") + footer())
        return

    from bot.bot_instance import _active_bots
    if user_id not in _active_bots:
        _active_bots[user_id] = {}
    _active_bots[user_id]["start_balance"] = amount

    # Step 3: Ask target amount
    _user_states[user_id] = "set_target_amount"
    await message.answer(box("🎯 STEP 3 - TARGET",
        f"<b>Balance:</b> {amount}\n\n"
        f"Enter target profit in ₹:\n"
        f"<code>20</code> or <code>50</code> or <code>100</code>\n\n"
        f"<i>Bot stops when profit reaches this amount</i>") + footer())


# ── STEP 3: Target Amount ──
async def handle_set_target_amount(message: Message, user_id: int, text: str):
    try:
        target = max(1, float(text))
    except ValueError:
        await message.answer(box("❌ INVALID", "Enter a number. Min 1") + footer())
        return

    from bot.bot_instance import _active_bots
    if user_id not in _active_bots:
        _active_bots[user_id] = {}
    _active_bots[user_id]["target_amount"] = target

    # Done - start bot
    _user_states.pop(user_id, None)
    user = await get_user(user_id)
    platform = user.get("platform", "jai")
    pn = {"jai": "JAI CLUB", "bdgwin": "BDGWIN", "51": "51GAME"}.get(platform, "JAI CLUB")
    balance = _active_bots[user_id].get("start_balance", 0)

    await message.answer(box("✅ READY!",
        f"<b>{pn}</b>\n\n"
        f"💰 Balance: <code>{balance}</code>\n"
        f"🎯 Target: <code>₹{target}</code>\n\n"
        f"<b>3-Fund System:</b>\n"
        f"🟢 F1 LOW (0% risk)\n"
        f"🟡 F2 MED (10% risk)\n"
        f"🔴 F3 HIGH (50% risk)\n\n"
        f"Starting...") + footer(),
        reply_markup=main_menu_kb())

    import asyncio
    from bot.handlers.dashboard import start_betting
    asyncio.create_task(start_betting(user_id, message.chat.id, user))


# ── Settings handlers ──

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
    "set_target_amount": handle_set_target_amount,
    "set_bet": handle_set_bet,
    "set_mult": handle_set_mult,
    "set_target": handle_set_target,
    "set_delay": handle_set_delay,
    "set_confidence": handle_set_confidence,
    "set_stoploss": handle_set_stoploss,
}


@router.message(F.text)
async def catch_all_text(message: Message):
    user_id = message.from_user.id
    state = _user_states.get(user_id)
    if state and state in STATE_HANDLERS:
        text = (message.text or "").strip()
        if text.startswith("/"):
            return
        await STATE_HANDLERS[state](message, user_id, text)


def get_state(user_id: int):
    return _user_states.get(user_id)


def pop_state(user_id: int):
    _user_states.pop(user_id, None)
