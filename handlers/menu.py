from aiogram import Router, F
from aiogram.types import Message
import database as db
from keyboards import main_menu_keyboard
from config import ADMIN_ID

router = Router()

@router.message(F.text == "👤 Мой профиль")
async def profile(message: Message):
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("Пользователь не найден. Введите /start для регистрации.")
        return
    
    balance = user[3]
    referrals = user[4]
    joined = user[6][:10]
    
    text = f"👤 <b>Ваш профиль</b>\n\n" \
           f"💰 Баланс: {balance} руб.\n" \
           f"👥 Рефералов: {referrals}\n" \
           f"📅 Зарегистрирован: {joined}"
    
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🔗 Реферальная ссылка")
async def referral_link(message: Message):
    bot_username = (await message.bot.me()).username
    link = f"https://t.me/{bot_username}?start={message.from_user.id}"
    text = f"🔗 Ваша реферальная ссылка:\n\n{link}\n\nПриглашайте друзей и получайте 12 рублей за каждого!"
    await message.answer(text)

@router.message(F.text == "💸 Вывести средства")
async def withdrawal(message: Message):
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start")
        return
    
    balance = user[3]
    if balance < 600:
        await message.answer(f"❌ Минимальная сумма для вывода – 600 руб. Ваш баланс: {balance} руб.")
        return
    
    db.add_withdrawal(message.from_user.id, balance)
    await message.answer("✅ Заявка на вывод создана. Ожидайте подтверждения администратора.")
    
    # Уведомление админу
    await message.bot.send_message(
        ADMIN_ID,
        f"💰 Новая заявка на вывод от @{message.from_user.username or 'no_username'} (ID: {message.from_user.id})\nСумма: {balance} руб."
    )