from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from keyboards import admin_menu_keyboard, settings_keyboard, withdrawals_keyboard, withdrawal_action_keyboard
from config import ADMIN_ID

router = Router()

class AdminStates(StatesGroup):
    waiting_for_channel = State()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("👨‍💻 Админ-панель", reply_markup=admin_menu_keyboard())

@router.callback_query(F.data == "admin_settings")
async def admin_settings(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа")
        return
    
    settings = db.get_settings()
    text = "⚙️ Настройки бота:\n\n" \
           f"📢 Канал: @{settings['channel'] if settings['channel'] else 'не указан'}\n" \
           f"✅ Проверка подписки: {'включена' if settings['enabled'] else 'выключена'}"
    
    await callback.message.edit_text(text, reply_markup=settings_keyboard(settings['enabled'], settings['channel']))

@router.callback_query(F.data == "toggle_sub_check")
async def toggle_sub_check(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    settings = db.get_settings()
    new_enabled = not settings['enabled']
    db.update_settings(settings['channel'], new_enabled)
    await callback.answer(f"Проверка подписки {'включена' if new_enabled else 'выключена'}")
    await admin_settings(callback)

@router.callback_query(F.data == "set_channel")
async def set_channel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text("📝 Введите username канала (без @):")
    await state.set_state(AdminStates.waiting_for_channel)

@router.message(AdminStates.waiting_for_channel)
async def receive_channel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    channel = message.text.strip().replace("@", "")
    settings = db.get_settings()
    db.update_settings(channel, settings['enabled'])
    await message.answer(f"✅ Канал установлен: @{channel}")
    await state.clear()
    await message.answer("👨‍💻 Админ-панель", reply_markup=admin_menu_keyboard())

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    total_users = db.get_total_users()
    total_balance = db.get_total_balance()
    
    text = f"📊 <b>Статистика</b>\n\n" \
           f"👥 Всего пользователей: {total_users}\n" \
           f"💰 Общий баланс: {total_balance} руб."
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())

@router.callback_query(F.data == "admin_withdrawals")
async def admin_withdrawals(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    withdrawals = db.get_pending_withdrawals()
    if not withdrawals:
        await callback.message.edit_text("📭 Нет ожидающих заявок.", reply_markup=admin_menu_keyboard())
        return
    
    await callback.message.edit_text("💰 Ожидающие заявки на вывод:", reply_markup=withdrawals_keyboard(withdrawals))

@router.callback_query(F.data.startswith("withdraw_"))
async def process_withdrawal(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    w_id = int(callback.data.split("_")[1])
    withdrawals = db.get_pending_withdrawals()
    withdrawal = next((w for w in withdrawals if w[0] == w_id), None)
    
    if not withdrawal:
        await callback.answer("❌ Заявка уже обработана.")
        await admin_withdrawals(callback)
        return
    
    _, user_id, amount, created = withdrawal
    text = f"📝 Заявка #{w_id}\n\n" \
           f"👤 Пользователь: {user_id}\n" \
           f"💰 Сумма: {amount} руб.\n" \
           f"📅 Создана: {created[:10]}"
    
    await callback.message.edit_text(text, reply_markup=withdrawal_action_keyboard(w_id))

@router.callback_query(F.data.startswith("approve_"))
async def approve_withdrawal(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    w_id = int(callback.data.split("_")[1])
    withdrawals = db.get_pending_withdrawals()
    withdrawal = next((w for w in withdrawals if w[0] == w_id), None)
    
    if not withdrawal:
        await callback.answer("❌ Заявка уже обработана.")
        return
    
    _, user_id, amount, _ = withdrawal
    db.update_withdrawal_status(w_id, "approved")
    db.update_user_balance(user_id, -amount)
    await callback.answer("✅ Заявка одобрена")
    
    try:
        await callback.bot.send_message(user_id, f"✅ Ваша заявка на вывод {amount} руб. одобрена!")
    except:
        pass
    
    await admin_withdrawals(callback)

@router.callback_query(F.data.startswith("reject_"))
async def reject_withdrawal(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    w_id = int(callback.data.split("_")[1])
    withdrawals = db.get_pending_withdrawals()
    withdrawal = next((w for w in withdrawals if w[0] == w_id), None)
    
    if not withdrawal:
        await callback.answer("❌ Заявка уже обработана.")
        return
    
    _, user_id, amount, _ = withdrawal
    db.update_withdrawal_status(w_id, "rejected")
    await callback.answer("❌ Заявка отклонена")
    
    try:
        await callback.bot.send_message(user_id, f"❌ Ваша заявка на вывод {amount} руб. отклонена администратором.")
    except:
        pass
    
    await admin_withdrawals(callback)

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text("👨‍💻 Админ-панель", reply_markup=admin_menu_keyboard())