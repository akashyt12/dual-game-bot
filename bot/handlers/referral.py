from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from bot.config import REFERRAL_POINTS, REQUIRED_POINTS
from bot.database import get_user, update_user, get_referral_count
from bot.keyboards import box, footer, referral_kb, referral_only_kb

router = Router()
pending_referrals = {}


@router.callback_query(F.data == "referral_page")
async def cb_referral(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    refs = await get_referral_count(user_id)
    pts = user.get("points", 0)
    ref_link = f"t.me/predictor20lord_bot?start=REF_{user_id}"
    txt = box("📝 REFERRALS",
        f"<b>Your Link:</b>\n<code>{ref_link}</code>\n\n"
        f"<b>Referrals:</b> <code>{refs}</code>\n"
        f"<b>Points:</b> <code>{pts}</code> / <code>{REQUIRED_POINTS}</code>\n\n"
        f"<i>Each referral = {REFERRAL_POINTS} points</i>") + footer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    from bot.bot_instance import bot
    await bot.send_message(callback.message.chat.id, txt, reply_markup=referral_kb(),
                           parse_mode="HTML")
    await callback.answer()


@router.message(F.text.startswith("/refer"))
async def cmd_refer(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    refs = await get_referral_count(user_id)
    pts = user.get("points", 0)
    ref_link = f"t.me/predictor20lord_bot?start=REF_{user_id}"
    await message.answer(
        box("📝 REFERRALS",
            f"<b>Your Link:</b>\n<code>{ref_link}</code>\n\n"
            f"<b>Referrals:</b> <code>{refs}</code>\n"
            f"<b>Points:</b> <code>{pts}</code> / <code>{REQUIRED_POINTS}</code>\n\n"
            f"<i>Each referral = {REFERRAL_POINTS} points</i>") + footer(),
        reply_markup=referral_kb())
