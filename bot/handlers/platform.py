from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from bot.config import IMAGES_DIR
from bot.database import get_user, update_user
from bot.keyboards import (platform_select_kb, game_menu_kb_jai, game_menu_kb_51,
                           game_menu_kb_bdgwin, main_menu_kb, box, footer)

router = Router()


def img(name):
    p = IMAGES_DIR / name
    return str(p) if p.exists() else None


@router.callback_query(F.data == "switch_platform")
async def cb_switch(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    await bot.send_message(callback.message.chat.id,
        box("🔄 SWITCH", "Select platform:") + footer(),
        reply_markup=platform_select_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("platform_"))
async def cb_platform(callback: CallbackQuery):
    user_id = callback.from_user.id
    p = callback.data.replace("platform_", "")
    await update_user(user_id, {"platform": p})

    names = {"jai": "JAI CLUB", "51": "51 GAME", "bdgwin": "BDG WIN"}
    games = {
        "jai": "WinGo 30S / 1M",
        "51": "WinGo 30S / 1M / 3M / 5M",
        "bdgwin": "WinGo 30S / 1M / 3M / 5M / 10M",
    }

    text = box(f"✅ {names.get(p, p)} SELECTED",
        f"<b>{games.get(p, '')}</b>\n\n"
        "Type <b>/login</b> to authenticate\n"
        "Then enter balance to start") + footer()

    try:
        await callback.message.delete()
    except Exception:
        pass

    from bot.bot_instance import bot
    await bot.send_message(callback.message.chat.id, text, reply_markup=main_menu_kb())
    await callback.answer(f"{names.get(p, p)} selected!")


@router.callback_query(F.data == "game_select")
async def cb_game_select(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    platform = user.get("platform", "jai")
    kbs = {"jai": game_menu_kb_jai(), "51": game_menu_kb_51(), "bdgwin": game_menu_kb_bdgwin()}
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    await bot.send_message(callback.message.chat.id,
        box("🎯 GAMES", "Select game type:") + footer(),
        reply_markup=kbs.get(platform, game_menu_kb_jai()))
    await callback.answer()


@router.callback_query(F.data.in_({"game_30s", "game_1m"}))
async def cb_game_jai(callback: CallbackQuery):
    user_id = callback.from_user.id
    game = "WinGo_30S" if callback.data == "game_30s" else "WinGo_1M"
    await update_user(user_id, {"game": game})
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    await bot.send_message(callback.message.chat.id,
        box("✅ GAME SET", f"<b>{game}</b>") + footer(), reply_markup=main_menu_kb())
    await callback.answer(f"Game: {game}")


@router.callback_query(F.data.startswith("game51_"))
async def cb_game51(callback: CallbackQuery):
    user_id = callback.from_user.id
    gm = {"game51_30": 30, "game51_1m": 1, "game51_3m": 2, "game51_5m": 3}
    tid = gm.get(callback.data, 30)
    await update_user(user_id, {"game51_type_id": tid})
    nm = {30: "30 SEC", 1: "1 MIN", 2: "3 MIN", 3: "5 MIN"}
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    await bot.send_message(callback.message.chat.id,
        box("✅ GAME SET", f"<b>WinGo {nm.get(tid)}</b>") + footer(),
        reply_markup=main_menu_kb())
    await callback.answer(f"WinGo {nm.get(tid)}")


@router.callback_query(F.data.startswith("bdgwin_"))
async def cb_game_bdgwin(callback: CallbackQuery):
    user_id = callback.from_user.id
    gm = {"bdgwin_30s": "WinGo_30S", "bdgwin_1m": "WinGo_1M",
          "bdgwin_3m": "WinGo_3M", "bdgwin_5m": "WinGo_5M", "bdgwin_10m": "WinGo_10M"}
    game = gm.get(callback.data, "WinGo_30S")
    await update_user(user_id, {"game": game})
    nm = {"WinGo_30S": "30 SEC", "WinGo_1M": "1 MIN", "WinGo_3M": "3 MIN",
          "WinGo_5M": "5 MIN", "WinGo_10M": "10 MIN"}
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    await bot.send_message(callback.message.chat.id,
        box("✅ GAME SET", f"<b>BDGWin WinGo {nm.get(game)}</b>") + footer(),
        reply_markup=main_menu_kb())
    await callback.answer(f"WinGo {nm.get(game)}")
