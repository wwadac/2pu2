import logging
import os
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    filters, 
    ContextTypes
)
from database import Database
from rag_engine import RAGEngine
from config import BOT_TOKEN, DATASETS_FOLDER

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация БД
db = Database()

# Состояния (для простоты используем глобальные переменные)
USER_STATES = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    db.add_user(user.id, user.username)
    
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я бот-ассистент, который отвечает на сообщения на основе твоего датасета.

📋 Что я умею:
• 📤 Загружать датасеты через файлы (.json, .txt)
• 🎯 Отвечать на вопросы из датасета
• 🔒 Работать в приватном или публичном режиме
• 📊 Показывать статистику датасета

📚 Поддерживаемые форматы файлов:

📄 JSON:
[
  {{"question": "Как дела?", "answer": "Отлично!"}},
  {{"question": "Сколько времени?", "answer": "Посмотри на часы 😄"}}
]

📄 TXT:
Как дела?

Отлично!

Сколько времени?

Посмотри на часы 😄

Используй команду /help для подробной инструкции!
    """
    
    keyboard = [
        [InlineKeyboardButton("📤 Загрузить датасет", callback_data="upload")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = """
📖 ПОДРОБНАЯ ИНСТРУКЦИЯ

📤 ЗАГРУЗКА ДАТАСЕТА:
1. Подготовь файл в формате .json или .txt
2. Отправь файл боту (как документ)
3. Бот автоматически загрузит и проиндексирует его

⚙️ РЕЖИМЫ РАБОТЫ:

🔐 Приватный режим (по умолчанию):
• Бот отвечает ТОЛЬКО тебе
• Использует ТВОЙ датасет
• Никто другой не может получить ответы

🌐 Публичный режим:
• Бот отвечает ВСЕМ пользователям
• Использует ТВОЙ датасет
• Любой может задавать вопросы

📊 СТАТИСТИКА:
• Показывает количество записей в датасете
• Среднюю длину вопросов и ответов

💡 СОВЕТЫ:
• Чем больше записей в датасете — тем точнее ответы
• Используй разнообразные формулировки вопросов
• Добавляй синонимы для лучшего поиска

🆘 ПРОБЛЕМЫ?
• Если бот не отвечает — проверь формат файла
• Убедись, что в файле есть данные
• Попробуй перезагрузить датасет
    """
    await update.message.reply_text(help_text)

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню настроек"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    current_mode = db.get_mode(user_id)
    
    mode_emoji = "🔐" if current_mode == "private" else "🌐"
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'✅ ' if current_mode == 'private' else ''}Приватный режим", 
                callback_data="set_private"
            ),
            InlineKeyboardButton(
                f"{'✅ ' if current_mode == 'public' else ''}Публичный режим", 
                callback_data="set_public"
            )
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"""
⚙️ НАСТРОЙКИ

Текущий режим: {mode_emoji} {current_mode.capitalize()}

🔐 Приватный режим:
   Только ты можешь получать ответы

🌐 Публичный режим:
   Все пользователи могут получать ответы из твоего датасета

Выбери режим работы:
        """,
        reply_markup=reply_markup
    )

async def stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика датасета"""
    query = update.callback_query
    if query:
        await query.answer()
    
    user_id = update.effective_user.id
    qa_pairs = db.get_all_qa_pairs(user_id)
    
    if not qa_pairs:
        text = "📊 Статистика\n\nУ тебя ещё нет загруженного датасета.\nИспользуй /upload для загрузки."
    else:
        text = RAGEngine.get_stats(qa_pairs)
        text = "📊 Статистика датасета:\n" + text
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def upload_dataset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка загрузки файла"""
    user = update.effective_user
    
    if not update.message.document:
        await update.message.reply_text("Пожалуйста, отправь файл как документ (.json или .txt)")
        return
    
    document = update.message.document
    
    # Проверяем формат
    if not document.filename.endswith(('.json', '.txt')):
        await update.message.reply_text("❌ Поддерживаются только .json и .txt файлы!")
        return
    
    # Скачиваем файл
    file = await context.bot.get_file(document.file_id)
    
    # Создаём папку для пользователя
    user_folder = Path(DATASETS_FOLDER) / str(user.id)
    user_folder.mkdir(exist_ok=True)
    
    # Сохраняем файл
    file_path = user_folder / document.filename
    await file.download_to_drive(str(file_path))
    
    # Парсим и сохраняем в БД
    await update.message.reply_text("⏳ Загружаю и обрабатываю датасет...")
    
    qa_pairs = RAGEngine.parse_dataset_file(str(file_path))
    
    if not qa_pairs:
        await update.message.reply_text(
            "❌ Не удалось распарсить файл. Проверь формат данных!"
        )
        return
    
    # Очищаем старый датасет и добавляем новый
    db.clear_dataset(user.id)
    for question, answer, keywords in qa_pairs:
        db.add_qa_pair(user.id, question, answer, keywords)
    
    db.set_dataset_file(user.id, document.filename)
    
    # Показываем статистику
    stats = RAGEngine.get_stats(qa_pairs)
    
    await update.message.reply_text(
        f"✅ Датасет успешно загружен!\n{stats}\n\nТеперь можешь задавать вопросы!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка обычных сообщений (вопросов)"""
    user = update.effective_user
    user_message = update.message.text
    
    # Игнорируем команды
    if user_message.startswith('/'):
        return
    
    # Проверяем режим пользователя
    user_mode = db.get_mode(user.id)
    
    # Если приватный режим — отвечаем только владельцу датасета
    if user_mode == "private":
        qa_pairs = db.get_all_qa_pairs(user.id)
        answer = RAGEngine.find_best_answer(user_message, qa_pairs)
        
        if answer:
            await update.message.reply_text(answer)
        else:
            await update.message.reply_text(
                "🤔 Не нашёл подходящего ответа в твоём датасете.\n"
                "Попробуй переформулировать вопрос или добавь больше данных в файл."
            )
    
    # Если публичный режим — ищем по всем датасетам
    elif user_mode == "public":
        # Получаем всех пользователей с датасетами
        users_with_datasets = db.get_all_users_with_datasets()
        
        if not users_with_datasets:
            await update.message.reply_text("У владельца ещё нет загруженного датасета.")
            return
        
        # Ищем ответ по всем датасетам
        best_answer = None
        best_score = 0
        
        for owner_id in users_with_datasets:
            qa_pairs = db.get_all_qa_pairs(owner_id)
            answer = RAGEngine.find_best_answer(user_message, qa_pairs)
            
            if answer:
                # Можно добавить логику выбора лучшего ответа
                best_answer = answer
                break
        
        if best_answer:
            await update.message.reply_text(best_answer)
        else:
            await update.message.reply_text(
                "🤔 Не нашёл ответа в датасете.\n"
                "Владельцу стоит добавить больше данных!"
            )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if query.data == "upload":
        await query.edit_message_text(
            "📤 ЗАГРУЗКА ДАТАСЕТА\n\n"
            "Отправь мне файл с датасетом (.json или .txt):\n\n"
            "Формат JSON:\n"
            "[{\"question\": \"...\", \"answer\": \"...\"}]\n\n"
            "Формат TXT:\n"
            "Вопрос 1\n\n"
            "Ответ 1",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
            ]])
        )
    
    elif query.data == "settings":
        await settings_menu(update, context)
    
    elif query.data == "stats":
        await stats_menu(update, context)
    
    elif query.data == "set_private":
        db.set_mode(user_id, "private")
        await query.edit_message_text(
            "✅ Режим изменён на 🔐 Приватный\n\n"
            "Теперь бот отвечает только тебе.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="settings")
            ]])
        )
    
    elif query.data == "set_public":
        db.set_mode(user_id, "public")
        await query.edit_message_text(
            "✅ Режим изменён на 🌐 Публичный\n\n"
            "Теперь все пользователи могут получать ответы из твоего датасета.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="settings")
            ]])
        )
    
    elif query.data == "back_to_main":
        keyboard = [
            [InlineKeyboardButton("📤 Загрузить датасет", callback_data="upload")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "👋 Главное меню\n\nВыбери действие:",
            reply_markup=reply_markup
        )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ошибок"""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """Запуск бота"""
    # Создаём приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Кнопки
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Загрузка файлов
    application.add_handler(MessageHandler(filters.Document.ALL, upload_dataset))
    
    # Обработка сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработка ошибок
    application.add_error_handler(error_handler)
    
    # Запуск
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
