from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.config import BOT_VERSION, CREATOR, ADMIN_USERNAME


def channels_join_kb(channels: list) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        link = ch.get("invite_link") or f"https://t.me/{ch['channel_id'].replace('@','')}"
        buttons.append([InlineKeyboardButton(text=f"📢 {ch['name']}", url=link)])
    buttons.append([InlineKeyboardButton(text="✅ I Have Joined - Verify", callback_data="check_joined")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶ START BOT", callback_data="start_bot"),
         InlineKeyboardButton(text="📊 STATUS", callback_data="status")],
        [InlineKeyboardButton(text="💰 PROFIT", callback_data="profit"),
         InlineKeyboardButton(text="⚙ SETTINGS", callback_data="settings")],
        [InlineKeyboardButton(text="🎯 GAME", callback_data="game_select"),
         InlineKeyboardButton(text="🛑 STOP", callback_data="stop_bot")],
        [InlineKeyboardButton(text="🔄 SWITCH", callback_data="switch_platform"),
         InlineKeyboardButton(text="📝 REFERRAL", callback_data="referral_page")],
        [InlineKeyboardButton(text="👤 PROFILE", callback_data="user_info")],
    ])


def platform_select_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 JAI CLUB", callback_data="platform_jai")],
        [InlineKeyboardButton(text="🎯 51 GAME", callback_data="platform_51")],
        [InlineKeyboardButton(text="💰 BDG WIN", callback_data="platform_bdgwin")],
        [InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")],
    ])


def game_menu_kb_jai() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ 30 SEC", callback_data="game_30s"),
         InlineKeyboardButton(text="🔥 1 MIN", callback_data="game_1m")],
        [InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")],
    ])


def game_menu_kb_51() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ 30 SEC", callback_data="game51_30"),
         InlineKeyboardButton(text="🔥 1 MIN", callback_data="game51_1m")],
        [InlineKeyboardButton(text="💎 3 MIN", callback_data="game51_3m"),
         InlineKeyboardButton(text="⭐ 5 MIN", callback_data="game51_5m")],
        [InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")],
    ])


def game_menu_kb_bdgwin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ 30 SEC", callback_data="bdgwin_30s"),
         InlineKeyboardButton(text="🔥 1 MIN", callback_data="bdgwin_1m")],
        [InlineKeyboardButton(text="💎 3 MIN", callback_data="bdgwin_3m"),
         InlineKeyboardButton(text="⭐ 5 MIN", callback_data="bdgwin_5m")],
        [InlineKeyboardButton(text="🏆 10 MIN", callback_data="bdgwin_10m")],
        [InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")],
    ])


def settings_kb(user_data: dict) -> InlineKeyboardMarkup:
    ar = "ON" if user_data.get("auto_restart", 1) else "OFF"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 Base Bet: {user_data.get('total_bet', 2)}", callback_data="set_bet")],
        [InlineKeyboardButton(text=f"📈 Martingale: {user_data.get('multiplier', 2.0)}x", callback_data="set_multiplier")],
        [InlineKeyboardButton(text=f"🎯 Target: {user_data.get('profit_target', 20)}%", callback_data="set_target")],
        [InlineKeyboardButton(text=f"🛑 Stop Loss: {user_data.get('stop_loss', 0)}%", callback_data="set_stoploss")],
        [InlineKeyboardButton(text=f"🔄 Auto Restart: {ar}", callback_data="toggle_restart")],
        [InlineKeyboardButton(text=f"⏱ Bet Delay: {user_data.get('bet_delay', 1.0)}s", callback_data="set_delay")],
        [InlineKeyboardButton(text=f"📊 Confidence: {user_data.get('confidence', 55)}%", callback_data="set_confidence")],
        [InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")],
    ])


def stop_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ YES STOP", callback_data="confirm_stop"),
         InlineKeyboardButton(text="❌ NO", callback_data="cancel_stop")],
    ])


def admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 STATS", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 ADD CHANNEL", callback_data="admin_addch"),
         InlineKeyboardButton(text="🗑 DEL CHANNEL", callback_data="admin_delch")],
        [InlineKeyboardButton(text="🔑 GENERATE KEY", callback_data="admin_genkey"),
         InlineKeyboardButton(text="📋 ALL KEYS", callback_data="admin_keys")],
        [InlineKeyboardButton(text="💰 ADD POINTS", callback_data="admin_addpts")],
        [InlineKeyboardButton(text="🚫 BAN USER", callback_data="admin_ban"),
         InlineKeyboardButton(text="✅ UNBAN USER", callback_data="admin_unban")],
        [InlineKeyboardButton(text="📣 BROADCAST", callback_data="admin_broadcast")],
    ])


def referral_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀ BACK TO MENU", callback_data="back_menu")],
    ])


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀ BACK", callback_data="back_menu")],
    ])


def referral_only_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 MY REFERRALS", callback_data="referral_page")],
        [InlineKeyboardButton(text="💎 PREMIUM", callback_data="premium_info")],
        [InlineKeyboardButton(text="👤 PROFILE", callback_data="user_info")],
    ])


def footer() -> str:
    return f"\n\n<i>╰ {BOT_VERSION} │ {CREATOR} │ Play at own risk ╯</i>"


def box(title: str, body: str) -> str:
    return f"╔{'═'*22}╗\n  « <b>{title}</b> »\n╚{'═'*22}╝\n\n{body}"
