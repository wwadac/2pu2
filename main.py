# main.py
import os
import asyncio
import logging
import sqlite3
from difflib import SequenceMatcher
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

# ============ Настройки ============
TOKEN = os.environ.get("8500113818:AAECdcA15J1PBP8uYg4-bOF66RXIrZL161Y")  # задай перед запуском или положи в .env
UPLOAD_DIR = "uploads"
DB_PATH = "proposals.db"
MIN_MATCH_SCORE = 0.28  # порог для возвращения ближайшего совпадения

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ База данных (sqlite) ============
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            added_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def sync_insert_texts(texts: list[str]) -> int:
    texts_clean = [t.strip() for t in texts if t and t.strip()]
    if not texts_clean:
        return 0
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.executemany("INSERT INTO proposals (text, added_at) VALUES (?, ?)", [(t, now) for t in texts_clean])
    conn.commit()
    count = len(texts_clean)
    conn.close()
    return count


def sync_get_all_proposals() -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT text FROM proposals")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def sync_count_proposals() -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM proposals")
    n = cur.fetchone()[0]
    conn.close()
    return n


def sync_clear_proposals() -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM proposals")
    deleted = conn.total_changes
    conn.commit()
    conn.close()
    return deleted

# ============ Утилиты ============
def best_match(query: str, candidates: list[str]) -> tuple[str | None, float]:
    best = None
    best_score = 0.0
    q = query.lower()
    for c in candidates:
        score = SequenceMatcher(None, q, c.lower()).ratio()
        if score > best_score:
            best = c
            best_score = score
    return best, best_score


async def run_db(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)

# ============ Хэндлеры ============
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Привет! Я бизнес-бот.\n\n"
        "— Отправь мне файл (.txt/.csv) с предложениями (по одному предложению на строку) — "
        "я сохраню их в базу.\n"
        "— Пиши любое сообщение — я постараюсь найти подходящее предложение и ответить.\n\n"
        "Команды:\n"
        "/count — показать количество загруженных предложений\n"
        "/clear — удалить все предложения\n"
        "/help — это сообщение\n\n"
        "Если хочешь, подключи бота к Telegram Business (в настройках аккаунта) чтобы он обрабатывал входящие сообщения бизнес-аккаунта."
    )
    await update.message.reply_text(text)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_cmd(update, context)


async def count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    n = await run_db(sync_count_proposals)
    await update.message.reply_text(f"В базе {n} предложений.")


async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deleted = await run_db(sync_clear_proposals)
    await update.message.reply_text(f"Удалил {deleted} записей (если были).")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        await update.message.reply_text("Файл не найден.")
        return

    # создаём папку
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = os.path.join(UPLOAD_DIR, f"{doc.file_unique_id}_{doc.file_name or 'upload'}")
    try:
        file = await doc.get_file()
        await file.download_to_drive(filename)
    except Exception as e:
        logger.exception("Ошибка при загрузке файла")
        await update.message.reply_text("Не получилось загрузить файл. Попробуй ещё раз.")
        return

    # парсим файл: берем все строки
    try:
        with open(filename, "r", encoding="utf-8", errors="ignore") as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception:
        await update.message.reply_text("Файл не мог быть прочитан как текст. Загружайте .txt или .csv в UTF-8.")
        return

    if not lines:
        await update.message.reply_text("Файл пустой или не содержит подходящих строк.")
        return

    added = await run_db(sync_insert_texts, lines)
    await update.message.reply_text(f"Загрузил и добавил в базу {added} предложений.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if not user_text:
        return

    candidates = await run_db(sync_get_all_proposals)
    if not candidates:
        await update.message.reply_text("База пока пуста. Загрузите файл с предложениями.")
        return

    best, score = best_match(user_text, candidates)
    if best and score >= MIN_MATCH_SCORE:
        await update.message.reply_text(best + f"\n\n(совпадение: {score:.2f})")
    else:
        # если совпадение слабое — вернём 3 похожих (по убыванию) или случайное
        # найдем топ-3 по score
        scored = []
        for c in candidates:
            s = SequenceMatcher(None, user_text.lower(), c.lower()).ratio()
            scored.append((s, c))
        scored.sort(reverse=True, key=lambda x: x[0])
        top = scored[:3]
        message = "Найдено несколько вариантов (лучшие совпадения):\n\n"
        for s, c in top:
            message += f"- {c} (score: {s:.2f})\n"
        await update.message.reply_text(message)


# ============ main ============
async def main():
    if not TOKEN:
        logger.error("TG_BOT_TOKEN не задан в окружении.")
        return

    init_db()
    app = ApplicationBuilder().token(TOKEN).concurrent_updates(True).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("count", count_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))

    # Документы (файлы)
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Текстовые сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Запускаю polling...")
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Завершение работы.")
