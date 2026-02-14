from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def main_menu_keyboard():
    kb = [
        [KeyboardButton(text="👤 Мой профиль")],
        [KeyboardButton(text="🔗 Реферальная ссылка")],
        [KeyboardButton(text="💸 Вывести средства")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def subscription_keyboard(channel: str):
    url = f"https://t.me/{channel}" if channel else ""
    kb = [
        [InlineKeyboardButton(text="📢 Подписаться", url=url)],
        [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_menu_keyboard():
    kb = [
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💰 Заявки на вывод", callback_data="admin_withdrawals")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def settings_keyboard(enabled: bool, channel: str):
    status = "✅ Включена" if enabled else "❌ Выключена"
    kb = [
        [InlineKeyboardButton(text=f"Проверка подписки: {status}", callback_data="toggle_sub_check")],
        [InlineKeyboardButton(text="Изменить канал", callback_data="set_channel")],
        [InlineKeyboardButton(text="« Назад", callback_data="admin_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def withdrawals_keyboard(withdrawals):
    kb = []
    for w in withdrawals:
        w_id, user_id, amount, created = w
        kb.append([InlineKeyboardButton(text=f"Заявка #{w_id}: {amount} руб. от {user_id}",
                                        callback_data=f"withdraw_{w_id}")])
    kb.append([InlineKeyboardButton(text="« Назад", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def withdrawal_action_keyboard(w_id: int):
    kb = [
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{w_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{w_id}")],
        [InlineKeyboardButton(text="« Назад", callback_data="admin_withdrawals")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)
