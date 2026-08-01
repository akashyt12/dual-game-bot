from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable
from bot.database import get_user, get_channels, is_admin


class ChannelCheckMiddleware(BaseMiddleware):
    SKIP_CALLBACKS = {"check_joined", "back_menu"}
    SKIP_COMMANDS = {"/start"}

    async def __call__(self, handler: Callable, event: Message | CallbackQuery,
                        data: Dict[str, Any]) -> Any:
        user_id = event.from_user.id

        if await is_admin(user_id):
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            if event.data in self.SKIP_CALLBACKS:
                return await handler(event, data)

        if isinstance(event, Message):
            text = (event.text or "").strip()
            if text.startswith("/start"):
                return await handler(event, data)

        user = await get_user(user_id)
        if user.get("banned"):
            return None

        channels = await get_channels()
        if not channels:
            return await handler(event, data)

        if user.get("verified_channels"):
            return await handler(event, data)

        if isinstance(event, Message):
            from bot.keyboards import channels_join_kb
            await event.answer(
                "📢 <b>Please join all our channels first!</b>\n\n"
                "Click each button below to join, then click <b>✅ Verify</b>.",
                reply_markup=channels_join_kb(channels)
            )
        elif isinstance(event, CallbackQuery):
            from bot.keyboards import channels_join_kb
            try:
                await event.message.edit_text(
                    "📢 <b>Please join all our channels first!</b>\n\n"
                    "Click each button below to join, then click <b>✅ Verify</b>.",
                    reply_markup=channels_join_kb(channels)
                )
            except Exception:
                pass
            await event.answer("Join all channels first!", show_alert=True)
        return None
