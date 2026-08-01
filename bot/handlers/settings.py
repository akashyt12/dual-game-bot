from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.database import get_user, update_user
from bot.keyboards import settings_kb, main_menu_kb, box, footer

router = Router()


@router.callback_query(F.data == "settings")
async def cb_settings(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    await bot.send_message(callback.message.chat.id,
        box("⚙ SETTINGS", "Adjust your settings:") + footer(),
        reply_markup=settings_kb(user))
    await callback.answer()


@router.callback_query(F.data == "toggle_restart")
async def cb_toggle_restart(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    new_val = 0 if user.get("auto_restart", 1) else 1
    await update_user(user_id, {"auto_restart": new_val})
    user = await get_user(user_id)
    try:
        await callback.message.edit_text(
            box("⚙ SETTINGS", f"<b>Auto Restart:</b> {'ON' if new_val else 'OFF'}") + footer(),
            reply_markup=settings_kb(user))
    except Exception:
        pass
    await callback.answer(f"Restart: {'ON' if new_val else 'OFF'}")
