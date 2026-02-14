from aiogram import Bot
from aiogram.types import ChatMember

async def check_subscription(user_id: int, bot: Bot, channel: str) -> bool:
    if not channel:
        return True  # если канал не указан, считаем подписку выполненной
    try:
        member = await bot.get_chat_member(chat_id=f"@{channel}", user_id=user_id)
        return member.status not in [ChatMember.LEFT, ChatMember.KICKED]
    except Exception:
        return False
