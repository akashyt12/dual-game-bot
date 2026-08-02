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


def img(name):
    p = IMAGES_DIR / name
    return str(p) if p.exists() else None


def format_profit(state, status="RUNNING", platform="JAI CLUB"):
    profit = state.get("profit", 0)
    start = state.get("start_balance", 0)
    pct = ((profit / start) * 100) if start > 0 else 0
    target = state.get("profit_target", 20)
    tgt = f"{target}% OK" if pct >= target else f"{target}%"
    sign = "+" if profit >= 0 else ""
    return box(f"💰 {platform}",
        f"<b>Status:</b> {status}\n\n"
        f"<b>Profit:</b> <code>{sign}{profit:.2f}</code>\n"
        f"<b>%:</b> <code>{sign}{pct:.1f}%</code>\n"
        f"<b>Target:</b> <code>{tgt}</code>\n\n"
        f"<b>Won:</b> <code>{state.get('total_won',0):.2f}</code> | "
        f"<b>Lost:</b> <code>{state.get('total_lost',0):.2f}</code>\n"
        f"<b>Wins:</b> <code>{state.get('wins',0)}</code> | "
        f"<b>Losses:</b> <code>{state.get('losses',0)}</code>\n"
        f"<b>DW:</b> <code>{state.get('double_win',0)}</code> | "
        f"<b>DL:</b> <code>{state.get('double_loss',0)}</code>\n"
        f"<b>Level:</b> <code>{state.get('level',0)}</code>\n\n"
        f"<i>{time.strftime('%H:%M:%S')}</i>")


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

    # Stop the bot loop
    if user_id in _active_bots:
        _active_bots[user_id]["running"] = False

    # Wipe ALL login data from RAM
    _active_bots.pop(user_id, None)
    _profit_messages.pop(user_id, None)

    # Wipe ALL login data from DB - fresh start next time
    await update_user(user_id, {
        "logged_in": 0,
        "login_user": "",
        "start_balance": 0,
    })

    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    await bot.send_message(callback.message.chat.id,
        box("🛑 STOPPED", "All data cleared.\nUse /start for fresh login.") + footer(),
        reply_markup=main_menu_kb())
    await callback.answer("🛑 Stopped! All data cleared.")


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
    txt = box("📊 STATUS",
        f"<b>Platform:</b> {pn}\n<b>Status:</b> {st}\n"
        f"<b>Balance:</b> <code>{bd.get('balance',0):.2f}</code>\n"
        f"<b>Profit:</b> <code>{bd.get('profit',0):.2f}</code>\n"
        f"<b>Level:</b> <code>{bd.get('level',0)}</code>\n"
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
    curr = bd.get("balance", 0)
    profit = curr - start
    pct = ((profit / start) * 100) if start > 0 else 0
    user = await get_user(user_id)
    target = user.get("profit_target", 20)
    tgt = "REACHED!" if pct >= target else f"{target}%"
    txt = box("💰 PROFIT",
        f"<b>Profit:</b> <code>{profit:.2f}</code>\n"
        f"<b>%:</b> <code>{pct:.1f}%</code>\n"
        f"<b>Target:</b> <code>{tgt}</code>\n\n"
        f"<b>Wins:</b> <code>{bd.get('double_win',0)}</code> | "
        f"<b>Losses:</b> <code>{bd.get('double_loss',0)}</code>\n"
        f"<b>Level:</b> <code>{bd.get('level',0)}</code>") + footer()
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


async def start_betting(user_id, chat_id, user_data):
    from bot.bot_instance import _active_bots as ab, bot

    # Read ALL from RAM - never from DB
    session = ab.get(user_id, {})
    platform = user_data.get("platform", "jai")
    username = session.get("login_user", "")
    password = session.get("login_pass", "")
    start_balance = session.get("start_balance", 0)

    game = user_data.get("game", "WinGo_30S")
    total_bet = user_data.get("total_bet", 2)
    multiplier = user_data.get("multiplier", 2.0)
    profit_target = user_data.get("profit_target", 20)

    if not username or not password or not start_balance:
        await bot.send_message(chat_id,
            box("❌ NO LOGIN DATA", "Use /start to login fresh.") + footer())
        return

    pn = {"jai": "JAI CLUB", "bdgwin": "BDGWIN", "51": "51GAME"}.get(platform, "JAI CLUB")

    msg = await bot.send_message(chat_id,
        box("⏳ LOGGING IN...", f"<b>{pn}</b>") + footer(), reply_markup=main_menu_kb())
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
            levels = _make_levels(start_balance, total_bet, multiplier)
        elif platform == "51":
            from bot.services.checker_51 import Game51AccountChecker
            checker = Game51AccountChecker(username, password)
            if not checker.perform_login():
                await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
                    text=box("❌ FAILED", str(checker.message)[:100]) + footer())
                return
            levels = _make_levels(start_balance, total_bet, multiplier)
        else:
            from bot.services.checker_jai import AccountChecker, AutoBetEngine, make_levels
            engine = AutoBetEngine(username, password, game, total_bet, multiplier, 55)
            engine.checker.lottery_api_base_url = "https://h5.ar-lottery06.com"
            engine.checker.lottery_draw_base_url = "https://draw.ar-lottery06.com"
            engine.login()
            engine.checker.fetch_ar_token(game)
            engine.start_balance = start_balance
            engine.current_balance = start_balance
            levels = make_levels(start_balance, total_bet, multiplier)
            checker = engine.checker
    except Exception as e:
        await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
            text=box("❌ LOGIN FAILED", str(e)[:100]) + footer())
        return

    # Wipe login creds from RAM after successful login
    if user_id in ab:
        ab[user_id].pop("login_user", None)
        ab[user_id].pop("login_pass", None)

    bot_state = {
        "running": True, "start_balance": start_balance, "balance": start_balance,
        "profit": 0, "total_won": 0, "total_lost": 0, "wins": 0, "losses": 0,
        "double_win": 0, "double_loss": 0, "level": 0, "pending": None,
        "last_seen_period": None, "target_hit": False, "profit_target": profit_target,
    }
    _active_bots[user_id] = bot_state
    await _update_profit(user_id, chat_id, bot_state, "RUNNING", pn)

    while bot_state["running"]:
        try:
            user = await get_user(user_id)
            if user.get("banned"):
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
                        bot_state["total_won"] += pending["total_bet"] * 0.98
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
                            await bot.send_message(chat_id,
                                box("🎉 TARGET!", f"<b>Profit:</b> +{bot_state['profit']:.2f} ({pct:.1f}%)") + footer())
                        except Exception:
                            pass

                    await update_stats(user_id, platform, pending.get("total_bet", 0) if "WIN" in result else 0,
                                       pending.get("total_bet", 0) if "LOSS" in result else 0, result)
                    await add_history(user_id, platform, latest, pending.get("bs_prediction",""),
                                      pending.get("color_prediction",""), actual_num, actual_bs, actual_color,
                                      pending.get("total_bet", 0), result, bot_state["profit"], bot_state["level"])
                    await _update_profit(user_id, chat_id, bot_state, result, pn)

                await asyncio.sleep(1)
                continue

            if latest == bot_state["last_seen_period"]:
                await asyncio.sleep(1)
                continue
            bot_state["last_seen_period"] = latest

            pattern_bs = [("B" if n >= 5 else "S") for n in reversed(nums)]
            pattern_co = [("G" if n in {1,3,5,7,9} else "R") for n in reversed(nums)]

            from bot.services.checker_bdgwin import predict_bs as bs_pred_fn, predict_color as co_pred_fn
            bs_pred, _ = bs_pred_fn(pattern_bs)
            co_pred, _ = co_pred_fn(pattern_co)

            if bot_state["level"] >= len(levels):
                bot_state["running"] = False
                break

            lv = levels[bot_state["level"]]
            try:
                if platform == "bdgwin":
                    open_issue = checker.fetch_open_issue(game)
                    if open_issue:
                        checker.place_dual_bet(open_issue, game, bs_pred, co_pred, lv["bs_bet"], lv["color_bet"])
                        bot_state["pending"] = {"period": open_issue, "bs_prediction": bs_pred,
                                                 "color_prediction": co_pred, "total_bet": lv["total_bet"],
                                                 "level": lv["level"]}
                elif platform == "51":
                    type_id = user_data.get("game51_type_id", 30)
                    open_issue = checker.fetch_open_issue(type_id)
                    if open_issue:
                        bs_content = f"BigSmall_{bs_pred.capitalize()}"
                        color_content = f"Color_{co_pred.capitalize()}"
                        checker.place_dual_bet(open_issue, type_id, lv["bs_bet"], lv["color_bet"], bs_content, color_content)
                        bot_state["pending"] = {"period": open_issue, "bs_prediction": bs_pred,
                                                 "color_prediction": co_pred, "total_bet": lv["total_bet"],
                                                 "level": lv["level"]}
                else:
                    open_issue = checker.fetch_open_issue()
                    if open_issue:
                        checker.place_wingo_bet(open_issue, lv["bs_bet"], 1, f"BigSmall_{bs_pred.capitalize()}", game)
                        checker.place_wingo_bet(open_issue, lv["color_bet"], 1, f"Color_{co_pred.capitalize()}", game)
                        bot_state["pending"] = {"period": open_issue, "bs_prediction": bs_pred,
                                                 "color_prediction": co_pred, "total_bet": lv["total_bet"],
                                                 "level": lv["level"]}
                await _update_profit(user_id, chat_id, bot_state, "WAITING", pn)
            except Exception as e:
                import logging
                logging.error(f"Bet failed: {e}")

            await asyncio.sleep(user_data.get("bet_delay", 1.0))
        except Exception as e:
            import logging
            logging.error(f"Betting error: {e}")
            await asyncio.sleep(3)

    # Bot loop ended - wipe everything
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

    # Wipe ALL from RAM
    _active_bots.pop(user_id, None)

    # Wipe ALL from DB
    await update_user(user_id, {
        "logged_in": 0,
        "login_user": "",
        "start_balance": 0,
    })

    try:
        await bot.send_message(chat_id,
            box("💰 SESSION ENDED", "All data cleared.\nUse /start for fresh login.") + footer(),
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


def _make_levels(balance, start_total, multiplier):
    import math
    levels = []
    per_market = max(1, math.ceil(start_total / 2))
    risk = 0
    lvl = 1
    while True:
        total = per_market * 2
        if risk + total > balance:
            break
        risk += total
        levels.append({"level": lvl, "color_bet": per_market, "bs_bet": per_market,
                        "total_bet": total, "cumulative_risk": risk})
        nxt = math.ceil(per_market * multiplier)
        if nxt <= per_market:
            nxt = per_market + 1
        per_market = nxt
        lvl += 1
        if lvl > 50:
            break
    return levels
