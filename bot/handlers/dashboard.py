import asyncio
import time
from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.config import REQUIRED_POINTS, IMAGES_DIR
from bot.database import (get_user, update_user, get_stats, update_stats, add_history)
from bot.keyboards import (main_menu_kb, referral_only_kb, stop_confirm_kb,
                           settings_kb, box, footer)

router = Router()
_active_bots = {}
_profit_messages = {}

# ═══════════════════════════════════════════════════════════════
#  3-FUND LEVEL SYSTEM
#  Fund 1 = LOW risk (0%)   → small profit, safe
#  Fund 2 = MED risk (10%)  → medium profit
#  Fund 3 = HIGH risk (50%) → big profit, aggressive
# ═══════════════════════════════════════════════════════════════

FUND_LEVELS = [
    # (level, fund1_bet, fund2_bet, fund3_bet)
    (1,   1,   1,   1),
    (2,   3,   3,   3),
    (3,   7,   8,   6),
    (4,  17,  20,  15),
    (5,  45,  40,  35),
    (6,  85,  80,  70),
    (7, 190, 170, 155),
    (8, 400, 370, 330),
    (9, 850, 780, 700),
    (10,1800,1650,1500),
]


def img(name):
    p = IMAGES_DIR / name
    return str(p) if p.exists() else None


def format_profit(state, status="RUNNING", platform="JAI CLUB"):
    profit = state.get("profit", 0)
    start = state.get("start_balance", 0)
    target_amt = state.get("target_amount", 0)
    sign = "+" if profit >= 0 else ""
    levels_info = state.get("levels", [1, 1, 1])

    return box(f"💰 {platform}",
        f"<b>Status:</b> {status}\n\n"
        f"<b>Profit:</b> <code>{sign}{profit:.2f}</code>\n"
        f"<b>Target:</b> <code>{target_amt}</code> | "
        f"<b>{'✅ DONE' if profit >= target_amt and target_amt > 0 else '⏳ Running'}</code>\n\n"
        f"━━━ <b>FUND LEVELS</b> ━━━\n"
        f"🟢 <b>F1 LOW:</b>  Lv.<code>{levels_info[0]}</code> | "
        f"Bet: <code>{_get_fund_bet(levels_info[0], 1)}</code>\n"
        f"🟡 <b>F2 MED:</b>  Lv.<code>{levels_info[1]}</code> | "
        f"Bet: <code>{_get_fund_bet(levels_info[1], 2)}</code>\n"
        f"🔴 <b>F3 HIGH:</b> Lv.<code>{levels_info[2]}</code> | "
        f"Bet: <code>{_get_fund_bet(levels_info[2], 3)}</code>\n\n"
        f"<b>Won:</b> <code>{state.get('total_won',0):.2f}</code> | "
        f"<b>Lost:</b> <code>{state.get('total_lost',0):.2f}</code>\n"
        f"<b>Rounds:</b> <code>{state.get('rounds',0)}</code>\n\n"
        f"<i>{time.strftime('%H:%M:%S')}</i>")


def _get_fund_bet(level, fund_num):
    idx = min(level - 1, len(FUND_LEVELS) - 1)
    if idx < 0:
        idx = 0
    row = FUND_LEVELS[idx]
    return row[fund_num]


def _make_3fund_levels(balance):
    return [
        {"level": 1, "f1": 1, "f2": 1, "f3": 1},
        {"level": 2, "f1": 3, "f2": 3, "f3": 3},
        {"level": 3, "f1": 7, "f2": 8, "f3": 6},
        {"level": 4, "f1": 17, "f2": 20, "f3": 15},
        {"level": 5, "f1": 45, "f2": 40, "f3": 35},
        {"level": 6, "f1": 85, "f2": 80, "f3": 70},
        {"level": 7, "f1": 190, "f2": 170, "f3": 155},
        {"level": 8, "f1": 400, "f2": 370, "f3": 330},
        {"level": 9, "f1": 850, "f2": 780, "f3": 700},
        {"level": 10, "f1": 1800, "f2": 1650, "f3": 1500},
    ]


# ═══════════════════════════════════════════════════════════════
#  CALLBACKS
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "stop_bot")
async def cb_stop_bot(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    await bot.send_message(callback.message.chat.id,
        box("🛑 STOP?", "Confirm:") + footer(), reply_markup=stop_confirm_kb())
    await callback.answer()


@router.callback_query(F.data == "confirm_stop")
async def cb_confirm_stop(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in _active_bots:
        _active_bots[user_id]["running"] = False
    _active_bots.pop(user_id, None)
    _profit_messages.pop(user_id, None)
    await update_user(user_id, {"logged_in": 0, "login_user": "", "start_balance": 0})
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    await bot.send_message(callback.message.chat.id,
        box("🛑 STOPPED", "All data cleared.\nUse /start for fresh login.") + footer(),
        reply_markup=main_menu_kb())
    await callback.answer("🛑 Stopped!")


@router.callback_query(F.data == "cancel_stop")
async def cb_cancel_stop(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    await bot.send_message(callback.message.chat.id,
        box("✅ RUNNING", "Bot continues.") + footer(), reply_markup=main_menu_kb())
    await callback.answer("Still running!")


@router.callback_query(F.data == "status")
async def cb_status(callback: CallbackQuery):
    user_id = callback.from_user.id
    bd = _active_bots.get(user_id, {})
    user = await get_user(user_id)
    platform = user.get("platform", "jai")
    pn = {"jai": "JAI CLUB", "bdgwin": "BDGWIN", "51": "51GAME"}.get(platform, "JAI CLUB")
    st = "Running" if bd.get("running") else "Stopped"
    pts = user.get("points", 0)
    lvls = bd.get("levels", [1, 1, 1])
    target_amt = bd.get("target_amount", 0)
    profit = bd.get("profit", 0)
    txt = box("📊 STATUS",
        f"<b>Platform:</b> {pn}\n<b>Status:</b> {st}\n"
        f"<b>Balance:</b> <code>{bd.get('start_balance',0)}</code>\n"
        f"<b>Profit:</b> <code>{profit:.2f}</code>\n"
        f"<b>Target:</b> <code>{target_amt}</code>\n\n"
        f"🟢 F1: Lv.<code>{lvls[0]}</code> | "
        f"🟡 F2: Lv.<code>{lvls[1]}</code> | "
        f"🔴 F3: Lv.<code>{lvls[2]}</code>\n\n"
        f"<b>Points:</b> <code>{pts}</code>") + footer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    await bot.send_message(callback.message.chat.id, txt, reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "profit")
async def cb_profit(callback: CallbackQuery):
    user_id = callback.from_user.id
    bd = _active_bots.get(user_id, {})
    start = bd.get("start_balance", 0)
    profit = bd.get("profit", 0)
    target_amt = bd.get("target_amount", 0)
    user = await get_user(user_id)
    lvls = bd.get("levels", [1, 1, 1])
    txt = box("💰 PROFIT",
        f"<b>Profit:</b> <code>{profit:.2f}</code>\n"
        f"<b>Target:</b> <code>{target_amt}</code> | "
        f"<b>{'✅ DONE' if profit >= target_amt and target_amt > 0 else '⏳'}</code>\n\n"
        f"🟢 F1 Lv.<code>{lvls[0]}</code> Bet:<code>{_get_fund_bet(lvls[0],1)}</code>\n"
        f"🟡 F2 Lv.<code>{lvls[1]}</code> Bet:<code>{_get_fund_bet(lvls[1],2)}</code>\n"
        f"🔴 F3 Lv.<code>{lvls[2]}</code> Bet:<code>{_get_fund_bet(lvls[2],3)}</code>\n\n"
        f"<b>Rounds:</b> <code>{bd.get('rounds',0)}</code>") + footer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    await bot.send_message(callback.message.chat.id, txt, reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "user_info")
async def cb_user_info(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    import hashlib
    short_id = hashlib.md5(str(user_id).encode()).hexdigest()[:8].upper()
    pts = user.get("points", 0)
    from bot.database import get_referral_count
    refs = await get_referral_count(user_id)
    platform = user.get("platform", "jai")
    stats = await get_stats(user_id, platform)
    txt = box("👤 USER INFO",
        f"<b>Name:</b> {user.get('name', 'N/A')}\n"
        f"<b>Username:</b> @{user.get('username', 'N/A')}\n"
        f"<b>Unique ID:</b> <code>{short_id}</code>\n"
        f"<b>User ID:</b> <code>{user_id}</code>\n\n"
        f"<b>Points:</b> <code>{pts}</code>\n"
        f"<b>Referrals:</b> <code>{refs}</code>\n"
        f"<b>Platform:</b> {platform}\n\n"
        f"<b>Total Won:</b> <code>{stats.get('total_won',0):.2f}</code>\n"
        f"<b>Total Lost:</b> <code>{stats.get('total_lost',0):.2f}</code>") + footer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    from bot.keyboards import back_kb
    await bot.send_message(callback.message.chat.id, txt, reply_markup=back_kb())
    await callback.answer()


@router.callback_query(F.data == "premium_info")
async def cb_premium(callback: CallbackQuery):
    txt = box("💎 PREMIUM ACCESS",
        "Get unlimited bot access with Premium!\n\n"
        "<b>Plans:</b>\n"
        "🔶 <b>1 Day</b> - ₹199\n"
        "🔶 <b>3 Days</b> - ₹499\n"
        "🔶 <b>7 Days</b> - ₹999\n"
        "🔶 <b>30 Days</b> - ₹1999\n\n"
        "DM @lord_x_stylo to purchase!") + footer()
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 DM Admin", url="https://t.me/lord_x_stylo")],
        [InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")],
    ])
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    await bot.send_message(callback.message.chat.id, txt, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ═══════════════════════════════════════════════════════════════
#  MAIN BETTING ENGINE - 3 FUND DUAL BET
# ═══════════════════════════════════════════════════════════════

async def start_betting(user_id, chat_id, user_data):
    from bot.bot_instance import _active_bots as ab, bot

    session = ab.get(user_id, {})
    platform = user_data.get("platform", "jai")
    username = session.get("login_user", "")
    password = session.get("login_pass", "")
    start_balance = session.get("start_balance", 0)
    target_amount = session.get("target_amount", 0)

    game = user_data.get("game", "WinGo_30S")

    if not username or not password or not start_balance:
        await bot.send_message(chat_id,
            box("❌ NO LOGIN DATA", "Use /start to login fresh.") + footer())
        return

    pn = {"jai": "JAI CLUB", "bdgwin": "BDGWIN", "51": "51GAME"}.get(platform, "JAI CLUB")

    msg = await bot.send_message(chat_id,
        box("⏳ LOGGING IN...", f"<b>{pn}</b>\nBalance: {start_balance}\nTarget: ₹{target_amount}") + footer(),
        reply_markup=main_menu_kb())
    _profit_messages[user_id] = msg.message_id

    try:
        if platform == "bdgwin":
            from bot.services.checker_bdgwin import BDGWinAccountChecker
            checker = BDGWinAccountChecker(username, password)
            if not checker.perform_login():
                await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
                    text=box("❌ FAILED", str(checker.message)[:100]) + footer())
                return
            checker.fetch_ar_token(game)
        elif platform == "51":
            from bot.services.checker_51 import Game51AccountChecker
            checker = Game51AccountChecker(username, password)
            if not checker.perform_login():
                await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
                    text=box("❌ FAILED", str(checker.message)[:100]) + footer())
                return
        else:
            from bot.services.checker_jai import AccountChecker, AutoBetEngine, make_levels
            engine = AutoBetEngine(username, password, game, 2, 2.0, 55)
            engine.checker.lottery_api_base_url = "https://h5.ar-lottery06.com"
            engine.checker.lottery_draw_base_url = "https://draw.ar-lottery06.com"
            engine.login()
            engine.checker.fetch_ar_token(game)
            checker = engine.checker
    except Exception as e:
        await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
            text=box("❌ LOGIN FAILED", str(e)[:100]) + footer())
        return

    if user_id in ab:
        ab[user_id].pop("login_user", None)
        ab[user_id].pop("login_pass", None)

    # 3-FUND STATE: each fund has independent level
    bot_state = {
        "running": True,
        "start_balance": start_balance,
        "balance": start_balance,
        "target_amount": target_amount,
        "profit": 0,
        "total_won": 0,
        "total_lost": 0,
        "rounds": 0,
        "levels": [1, 1, 1],  # [f1_level, f2_level, f3_level]
        "pending": None,
        "last_seen_period": None,
    }
    _active_bots[user_id] = bot_state
    await _update_profit(user_id, chat_id, bot_state, "RUNNING", pn)

    while bot_state["running"]:
        try:
            user = await get_user(user_id)
            if user.get("banned"):
                break

            # Check target reached
            if target_amount > 0 and bot_state["profit"] >= target_amount:
                try:
                    await bot.send_message(chat_id,
                        box("🎉 TARGET REACHED!",
                            f"<b>Profit:</b> +{bot_state['profit']:.2f}\n"
                            f"<b>Target:</b> ₹{target_amount}\n\nBot auto-stopping...") + footer())
                except Exception:
                    pass
                bot_state["running"] = False
                break

            if platform == "bdgwin":
                history = checker.fetch_draw_history(game, 6)
            elif platform == "51":
                type_id = user_data.get("game51_type_id", 30)
                history = checker.fetch_draw_history(type_id, 6)
            else:
                history = checker.fetch_draw_history(6)

            if not history:
                await asyncio.sleep(1)
                continue

            latest = str(history[0].get("issueNumber", ""))
            nums = [int(x.get("number", 0)) for x in history[:6]]

            # ── CHECK PENDING RESULT ──
            if bot_state["pending"]:
                pending = bot_state["pending"]
                if str(pending["period"]) == latest:
                    actual_num = nums[0]
                    actual_bs = "BIG" if actual_num >= 5 else "SMALL"
                    actual_color = "GREEN" if actual_num in {1, 3, 5, 7, 9} else "RED"

                    f1_won = pending["f1_bs"] == actual_bs and pending["f1_co"] == actual_color
                    f2_won = pending["f2_bs"] == actual_bs and pending["f2_co"] == actual_color
                    f3_won = pending["f3_bs"] == actual_bs and pending["f3_co"] == actual_color

                    f1_bs_ok = pending["f1_bs"] == actual_bs
                    f1_co_ok = pending["f1_co"] == actual_color
                    f2_bs_ok = pending["f2_bs"] == actual_bs
                    f2_co_ok = pending["f2_co"] == actual_color
                    f3_bs_ok = pending["f3_bs"] == actual_bs
                    f3_co_ok = pending["f3_co"] == actual_color

                    # Calculate per-fund results
                    f1_bet = pending["f1_bet"]
                    f2_bet = pending["f2_bet"]
                    f3_bet = pending["f3_bet"]

                    # Fund 1 result
                    if f1_won:
                        f1_result = "WIN"
                        bot_state["total_won"] += f1_bet * 0.98
                        bot_state["levels"][0] = 1  # reset to level 1
                    elif f1_bs_ok or f1_co_ok:
                        f1_result = "EVEN"
                    else:
                        f1_result = "LOSS"
                        bot_state["total_lost"] += f1_bet
                        bot_state["levels"][0] = min(bot_state["levels"][0] + 1, len(FUND_LEVELS))

                    # Fund 2 result
                    if f2_won:
                        f2_result = "WIN"
                        bot_state["total_won"] += f2_bet * 0.98
                        bot_state["levels"][1] = 1
                    elif f2_bs_ok or f2_co_ok:
                        f2_result = "EVEN"
                    else:
                        f2_result = "LOSS"
                        bot_state["total_lost"] += f2_bet
                        bot_state["levels"][1] = min(bot_state["levels"][1] + 1, len(FUND_LEVELS))

                    # Fund 3 result
                    if f3_won:
                        f3_result = "WIN"
                        bot_state["total_won"] += f3_bet * 0.98
                        bot_state["levels"][2] = 1
                    elif f3_bs_ok or f3_co_ok:
                        f3_result = "EVEN"
                    else:
                        f3_result = "LOSS"
                        bot_state["total_lost"] += f3_bet
                        bot_state["levels"][2] = min(bot_state["levels"][2] + 1, len(FUND_LEVELS))

                    bot_state["pending"] = None
                    bot_state["profit"] = bot_state["total_won"] - bot_state["total_lost"]
                    bot_state["balance"] = bot_state["start_balance"] + bot_state["profit"]
                    bot_state["rounds"] += 1

                    total_bet = f1_bet + f2_bet + f3_bet
                    result_summary = f"F1:{f1_result} F2:{f2_result} F3:{f3_result}"

                    await update_stats(user_id, platform,
                        total_bet if "WIN" in (f1_result + f2_result + f3_result) else 0,
                        total_bet if "LOSS" in (f1_result + f2_result + f3_result) else 0,
                        result_summary)
                    await add_history(user_id, platform, latest,
                        f"F1:{pending['f1_bs']}/{pending['f1_co']}",
                        f"F2:{pending['f2_bs']}/{pending['f2_co']}",
                        actual_num, actual_bs, actual_color,
                        total_bet, result_summary, bot_state["profit"],
                        max(bot_state["levels"]))
                    await _update_profit(user_id, chat_id, bot_state, result_summary, pn)

                await asyncio.sleep(1)
                continue

            # ── WAIT FOR NEW PERIOD ──
            if latest == bot_state["last_seen_period"]:
                await asyncio.sleep(1)
                continue
            bot_state["last_seen_period"] = latest

            # ── PREDICT ──
            pattern_bs = [("B" if n >= 5 else "S") for n in reversed(nums)]
            pattern_co = [("G" if n in {1, 3, 5, 7, 9} else "R") for n in reversed(nums)]

            from bot.services.checker_bdgwin import predict_bs as bs_pred_fn, predict_color as co_pred_fn
            bs_pred, _ = bs_pred_fn(pattern_bs)
            co_pred, _ = co_pred_fn(pattern_co)

            # ── GET BET AMOUNTS FOR EACH FUND ──
            f1_lv = min(bot_state["levels"][0] - 1, len(FUND_LEVELS) - 1)
            f2_lv = min(bot_state["levels"][1] - 1, len(FUND_LEVELS) - 1)
            f3_lv = min(bot_state["levels"][2] - 1, len(FUND_LEVELS) - 1)

            f1_bet = FUND_LEVELS[f1_lv][1]  # fund1 bet
            f2_bet = FUND_LEVELS[f2_lv][2]  # fund2 bet
            f3_bet = FUND_LEVELS[f3_lv][3]  # fund3 bet

            total_bs_bet = f1_bet + f2_bet + f3_bet
            total_co_bet = f1_bet + f2_bet + f3_bet

            # ── PLACE 3-FUND DUAL BET ──
            try:
                if platform == "bdgwin":
                    open_issue = checker.fetch_open_issue(game)
                    if open_issue:
                        checker.place_dual_bet(open_issue, game, bs_pred, co_pred,
                                               total_bs_bet, total_co_bet)
                        bot_state["pending"] = {
                            "period": open_issue,
                            "f1_bs": bs_pred, "f1_co": co_pred, "f1_bet": f1_bet,
                            "f2_bs": bs_pred, "f2_co": co_pred, "f2_bet": f2_bet,
                            "f3_bs": bs_pred, "f3_co": co_pred, "f3_bet": f3_bet,
                        }
                elif platform == "51":
                    type_id = user_data.get("game51_type_id", 30)
                    open_issue = checker.fetch_open_issue(type_id)
                    if open_issue:
                        bs_content = f"BigSmall_{bs_pred.capitalize()}"
                        color_content = f"Color_{co_pred.capitalize()}"
                        checker.place_dual_bet(open_issue, type_id,
                                               total_bs_bet, total_co_bet,
                                               bs_content, color_content)
                        bot_state["pending"] = {
                            "period": open_issue,
                            "f1_bs": bs_pred, "f1_co": co_pred, "f1_bet": f1_bet,
                            "f2_bs": bs_pred, "f2_co": co_pred, "f2_bet": f2_bet,
                            "f3_bs": bs_pred, "f3_co": co_pred, "f3_bet": f3_bet,
                        }
                else:
                    open_issue = checker.fetch_open_issue()
                    if open_issue:
                        checker.place_wingo_bet(open_issue, total_bs_bet, 1,
                                                f"BigSmall_{bs_pred.capitalize()}", game)
                        checker.place_wingo_bet(open_issue, total_co_bet, 1,
                                                f"Color_{co_pred.capitalize()}", game)
                        bot_state["pending"] = {
                            "period": open_issue,
                            "f1_bs": bs_pred, "f1_co": co_pred, "f1_bet": f1_bet,
                            "f2_bs": bs_pred, "f2_co": co_pred, "f2_bet": f2_bet,
                            "f3_bs": bs_pred, "f3_co": co_pred, "f3_bet": f3_bet,
                        }
                await _update_profit(user_id, chat_id, bot_state, "BET PLACED", pn)
            except Exception as e:
                import logging
                logging.error(f"Bet failed: {e}")

            await asyncio.sleep(user_data.get("bet_delay", 1.0))
        except Exception as e:
            import logging
            logging.error(f"Betting error: {e}")
            await asyncio.sleep(3)

    # ── SESSION ENDED ──
    if user_id in _profit_messages:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=_profit_messages[user_id],
                text=format_profit(bot_state, "STOPPED", pn) + footer(), reply_markup=main_menu_kb())
        except Exception:
            pass
        await asyncio.sleep(5)
        if user_id in _profit_messages:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=_profit_messages[user_id])
            except Exception:
                pass
            _profit_messages.pop(user_id, None)

    _active_bots.pop(user_id, None)
    await update_user(user_id, {"logged_in": 0, "login_user": "", "start_balance": 0})

    try:
        await bot.send_message(chat_id,
            box("💰 SESSION ENDED",
                f"Profit: <code>{bot_state.get('profit',0):.2f}</code>\n"
                f"Rounds: <code>{bot_state.get('rounds',0)}</code>\n\n"
                "All data cleared.\nUse /start for fresh login.") + footer(),
            reply_markup=referral_only_kb())
    except Exception:
        pass


async def _update_profit(user_id, chat_id, state, status, platform):
    msg_id = _profit_messages.get(user_id)
    if not msg_id:
        return
    from bot.bot_instance import bot
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=msg_id,
            text=format_profit(state, status, platform) + footer(), reply_markup=main_menu_kb())
    except Exception:
        pass
