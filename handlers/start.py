from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.deep_link import decode_payload
import database as db
import utils
from keyboards import main_menu_keyboard, subscription_keyboard
from config import ADMIN_ID

router = Router()

@router.message(CommandStart(deep_link=True))
async def start_deep_link(message Message, bot)
    payload = decode_payload(message.text.split()[1])
    try
        referrer_id = int(payload)
    except ValueError
        referrer_id = None
    await start_handler(message, bot, referrer_id)

@router.message(CommandStart())
async def start_no_link(message Message, bot)
    await start_handler(message, bot, None)

async def start_handler(message Message, bot, referrer_id int = None)
    user_id = message.from_user.id
    username = message.from_user.username or no_username
    is_new = db.add_user(user_id, username, referrer_id)
    settings = db.get_settings()
    
    # Проверка подписки
    if settings[enabled] and settings[channel]
        subscribed = await utils.check_subscription(user_id, bot, settings[channel])
        if not subscribed
            await message.answer(
                Для использования бота необходимо подписаться на канал.n
                После подписки нажмите кнопку 'Проверить подписку'.,
                reply_markup=subscription_keyboard(settings[channel])
            )
            return
    
    # Начисление бонуса рефереру
    if referrer_id and referrer_id != user_id
        user = db.get_user(user_id)
        if user and user[5] == 0
            db.update_user_balance(referrer_id, 12)
            db.increment_referrals(referrer_id)
            db.mark_rewarded(user_id)
            try
                await bot.send_message(referrer_id, 🎉 По вашей ссылке зарегистрировался новый пользователь! Вам начислено 12 рублей.)
            except
                pass
    
    await message.answer(
        fДобро пожаловать, {message.from_user.full_name}!n
        Используйте меню для навигации.,
        reply_markup=main_menu_keyboard()
    )

@router.callback_query(F.data == check_sub)
async def check_sub_callback(callback CallbackQuery, bot)
    user_id = callback.from_user.id
    settings = db.get_settings()
    
    if settings[enabled] and settings[channel]
        subscribed = await utils.check_subscription(user_id, bot, settings[channel])
        if subscribed
            user = db.get_user(user_id)
            if user and user[2] and user[5] == 0
                db.update_user_balance(user[2], 12)
                db.increment_referrals(user[2])
                db.mark_rewarded(user_id)
                try
                    await bot.send_message(user[2], 🎉 По вашей ссылке зарегистрировался новый пользователь! Вам начислено 12 рублей.)
                except
                    pass
            await callback.message.delete()
            await callback.message.answer(✅ Спасибо за подписку! Добро пожаловать., reply_markup=main_menu_keyboard())
        else
            await callback.answer(❌ Вы ещё не подписались на канал. Попробуйте снова после подписки., show_alert=True)
    else
        await callback.answer(Проверка подписки не требуется., show_alert=True)