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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username)
    
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я бот-ассистент на основе твоего датасета.

📚 Как пользоваться:
1. Отправь мне файл .json или .txt с вопросами и ответами
2. Я проиндексирую его
3. Задавай вопросы — я буду отвечать из твоего датасета!

Формат файла:
📄 JSON:
[
  {{"question": "Как дела?", "answer": "Отлично!"}},
  {{"question": "Твой любимый цвет?", "answer": "Синий"}}
]

📄 TXT:
Как дела?

Отлично!

Твой любимый цвет?

Синий

Команды:
/start - начать
/help - помощь
    """
    
    keyboard = [
        [InlineKeyboardButton("📤 Загрузить датасет", callback_data="upload")],
        [InlineKeyboardButton("⚙️ Режим: Приватный", callback_data="toggle_mode")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 ИНСТРУКЦИЯ

📤 ЗАГРУЗКА ДАТАСЕТА:
1. Подготовь файл .json или .txt
2. Отправь его как документ (не как фото!)
3. Бот обработает и сохранит данные

🔐 РЕЖИМЫ:
• Приватный (по умолчанию): отвечаю только тебе
• Публичный: отвечаю всем из твоего датасета

💡 СОВЕТЫ:
• Используй разные формулировки вопросов
• Чем больше данных — тем точнее ответы
• Для лучшего поиска добавляй синонимы

❓ ПРОБЛЕМЫ?
• Файл не загружается? Убедись, что отправляешь как ДОКУМЕНТ
• Нет ответа? Проверь, есть ли похожие вопросы в датасете
    """
    await update.message.reply_text(help_text)

async def upload_dataset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not update.message.document:
        await update.message.reply_text("Пожалуйста, отправь файл как документ (.json или .txt)")
        return
    
    document = update.message.document
    
    if not document.filename.lower().endswith(('.json', '.txt')):
        await update.message.reply_text("❌ Поддерживаются только .json и .txt файлы!")
        return
    
    await update.message.reply_text("⏳ Обрабатываю файл...")
    
    try:
        file = await context.bot.get_file(document.file_id)
        user_folder = Path(DATASETS_FOLDER) / str(user.id)
        user_folder.mkdir(exist_ok=True)
        file_path = user_folder / document.filename
        await file.download_to_drive(str(file_path))
        
        qa_pairs = RAGEngine.parse_dataset_file(str(file_path))
        
        if not qa_pairs:
            await update.message.reply_text(
                "❌ Не удалось распарсить файл. Проверь формат:\n"
                "JSON: [{\"question\": \"...\", \"answer\": \"...\"}]\n"
                "TXT: Вопрос\\n\\nОтвет"
            )
            return
        
        db.clear_dataset(user.id)
        for question, answer, keywords in qa_pairs:
            db.add_qa_pair(user.id, question, answer, keywords)
        
        db.set_dataset_file(user.id, document.filename)
        
        stats = RAGEngine.get_stats(qa_pairs)
        await update.message.reply_text(
            f"✅ Датасет загружен!\n{stats}\n\nТеперь можешь задавать вопросы!"
        )
    
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    
    if text.startswith('/'):
        return
    
    mode = db.get_mode(user.id)
    
    if mode == "private":
        qa_pairs = db.get_all_qa_pairs(user.id)
        answer = RAGEngine.find_best_answer(text, qa_pairs)
        
        if answer:
            await update.message.reply_text(answer)
        else:
            await update.message.reply_text(
                "🤔 Не нашёл ответа в твоём датасете.\n"
                "Попробуй переформулировать или добавь больше данных."
            )
    
    elif mode == "public":
        users_with_datasets = db.get_all_users_with_datasets()
        if not users_with_datasets:
            await update.message.reply_text("У владельца нет датасета.")
            return
        
        for owner_id in users_with_datasets:
            qa_pairs = db.get_all_qa_pairs(owner_id)
            answer = RAGEngine.find_best_answer(text, qa_pairs)
            if answer:
                await update.message.reply_text(answer)
                return
        
        await update.message.reply_text("🤔 Не нашёл ответа в датасете.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if query.data == "upload":
        await query.edit_message_text(
            "📤 ОТПРАВЬ ФАЙЛ\n\n"
            "Отправь .json или .txt файл как документ.\n"
            "Формат:\n"
            "JSON: [{\"q\": \"...\", \"a\": \"...\"}]\n"
            "TXT: Вопрос\\n\\nОтвет",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
            ]])
        )
    
    elif query.data == "toggle_mode":
        current = db.get_mode(user_id)
        new_mode = "public" if current == "private" else "private"
        db.set_mode(user_id, new_mode)
        
        mode_text = "🌐 Публичный" if new_mode == "public" else "🔐 Приватный"
        await query.edit_message_text(
            f"✅ Режим изменён на {mode_text}\n\n"
            f"Теперь бот работает в режиме: {mode_text}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
            ]])
        )
    
    elif query.data == "stats":
        qa_pairs = db.get_all_qa_pairs(user_id)
        stats = RAGEngine.get_stats(qa_pairs)
        await query.edit_message_text(
            f"📊 СТАТИСТИКА ДАТАСЕТАА:\n{stats}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
            ]])
        )
    
    elif query.data == "back_to_main":
        mode = db.get_mode(user_id)
        mode_btn = "🌐 Публичный" if mode == "public" else "🔐 Приватный"
        
        keyboard = [
            [InlineKeyboardButton("📤 Загрузить датасет", callback_data="upload")],
            [InlineKeyboardButton(f"⚙️ Режим: {mode_btn}", callback_data="toggle_mode")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("👋 Главное меню", reply_markup=reply_markup)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")

def main():
    if not BOT_TOKEN or BOT_TOKEN == "":
        logger.error("❌ BOT_TOKEN не установлен! Создай файл .env с токеном.")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.Document.ALL, upload_dataset))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    logger.info("✅ Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
