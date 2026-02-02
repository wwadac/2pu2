import sqlite3
import logging
from difflib import SequenceMatcher

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8500113818:AAECdcA15J1PBP8uYg4-bOF66RXIrZL161Y"
DB_PATH = "responses.db"
SIM_THRESHOLD = 0.4  # чувствительность (0.3–0.6 норм)
# =============================================

logging.basicConfig(level=logging.INFO)

# ================ БАЗА ДАННЫХ =================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def add_responses(lines):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO responses (text) VALUES (?)",
        [(line,) for line in lines if line.strip()]
    )
    conn.commit()
    conn.close()


def get_responses():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT text FROM responses")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows


def clear_responses():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM responses")
    conn.commit()
    conn.close()


def count_responses():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM responses")
    count = cur.fetchone()[0]
    conn.close()
    return count

# ================ ПОИСК ОТВЕТА =================
def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_best_answer(user_text):
    responses = get_responses()
    best_score = 0
    best_text = None

    for resp in responses:
        score = similarity(user_text, resp)
        if score > best_score:
            best_score = score
            best_text = resp

    if best_score >= SIM_THRESHOLD:
        return best_text

    return None

# ================== HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Бизнес-бот запущен\n\n"
        "📎 Отправь TXT-файл с ответами — каждая строка = отдельный ответ\n"
        "🗑 /clear — очистить базу\n"
        "📊 /count — сколько ответов загружено"
    )


async def count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📊 Ответов в базе: {count_responses()}")


async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_responses()
    await update.message.reply_text("🗑 База очищена")


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    file = await doc.get_file()
    content = await file.download_as_bytearray()

    try:
        text = content.decode("utf-8")
    except:
        await update.message.reply_text("❌ Файл должен быть в UTF-8")
        return

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    add_responses(lines)

    await update.message.reply_text(
        f"✅ Загружено {len(lines)} строк\n"
        f"📊 Всего в базе: {count_responses()}"
    )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = find_best_answer(update.message.text)

    if answer:
        await update.message.reply_text(answer)
    else:
        await update.message.reply_text("❓ Не нашёл подходящий ответ")

# ================== ЗАПУСК ====================
def main():
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("count", count_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(MessageHandler(filters.Document.TEXT, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("✅ Бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
