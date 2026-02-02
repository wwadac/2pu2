
import os
import sqlite3
import logging
import asyncio
from typing import List, Tuple, Optional

from telegram import Update, Document
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Optional ML libs
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

from rapidfuzz import fuzz, process  # fast fuzzy fallback

# ====== Config ======
BOT_TOKEN = os.environ.get("BOT_TOKEN", "REPLACE_WITH_YOUR_TOKEN")
ADMIN_IDS = os.environ.get("ADMIN_IDS", "")  # comma separated user ids who can upload/manage
ADMIN_IDS = [int(x) for x in ADMIN_IDS.split(",") if x.strip().isdigit()]

DB_PATH = "responses.db"
UPLOADS_DIR = "uploads"
SIM_THRESHOLD = 0.45  # косинус/фазовый порог (0..1), подберите по набору данных
TOP_K = 3  # сколько вариантов показывать

os.makedirs(UPLOADS_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====== DB helpers ======
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

def add_responses_bulk(lines: List[str]):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executemany("INSERT INTO responses (text) VALUES (?)", ((l.strip(),) for l in lines if l.strip()))
    conn.commit()
    conn.close()

def get_all_responses() -> List[str]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT text FROM responses")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows

def clear_all_responses():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM responses")
    conn.commit()
    conn.close()

def count_responses() -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM responses")
    c = cur.fetchone()[0]
    conn.close()
    return c

# ====== Index / Matching ======
class Responder:
    def __init__(self):
        self.texts: List[str] = []
        self.tfidf = None
        self.vectorizer = None
        self.use_sklearn = SKLEARN_AVAILABLE
        logger.info("sklearn available: %s", self.use_sklearn)
        self.rebuild()

    def rebuild(self):
        self.texts = get_all_responses()
        if self.use_sklearn and len(self.texts) > 0:
            try:
                self.vectorizer = TfidfVectorizer(max_df=0.85, ngram_range=(1,2)).fit(self.texts)
                self.tfidf = self.vectorizer.transform(self.texts)
                logger.info("TF-IDF index built for %d responses", len(self.texts))
            except Exception as e:
                logger.exception("Failed building TF-IDF, falling back to fuzzy. Error: %s", e)
                self.use_sklearn = False
                self.vectorizer = None
                self.tfidf = None
        else:
            self.vectorizer = None
            self.tfidf = None

    def find_best(self, query: str, top_k: int = TOP_K) -> List[Tuple[str, float]]:
        if not self.texts:
            return []
        if self.use_sklearn and self.tfidf is not None:
            q_vec = self.vectorizer.transform([query])
            sims = cosine_similarity(q_vec, self.tfidf).flatten()  # array of similarities
            idxs = sims.argsort()[::-1][:top_k]
            return [(self.texts[i], float(sims[i])) for i in idxs]
        else:
            # fallback: rapidfuzz extractor
            choices = {i: t for i,t in enumerate(self.texts)}
            extracted = process.extract(query, choices, scorer=fuzz.WRatio, limit=top_k)
            # extracted -> list of (match, score, index)
            results = []
            for item in extracted:
                match_text = item[0]
                score = item[1] / 100.0  # scale 0..1
                results.append((match_text, score))
            return results

responder = Responder()

# ====== Bot handlers ======
def is_admin(user_id: int) -> bool:
    return (user_id in ADMIN_IDS) or (len(ADMIN_IDS) == 0)  # if ADMIN_IDS empty -> allow all (convenience)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бизнес-бот, который отвечает на сообщения по загруженным файлам.\n"
        "Админ может загрузить файл (.txt/.csv/.json) прямо в этот чат — бот подключит фразы в базу.\n\n"
        "Команды:\n"
        "/upload — отправьте документ (файл) в чат\n"
        "/count — количество загруженных фраз\n"
        "/clear — очистить базу (только админ)\n"
        "/help — это сообщение"
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await start(update, ctx)

async def count_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    c = count_responses()
    await update.message.reply_text(f"В базе {c} фраз(ы).")

async def clear_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("Команда доступна только админам.")
        return
    clear_all_responses()
    responder.rebuild()
    await update.message.reply_text("База очищена.")

async def document_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Accept uploaded document and parse it into lines
    doc: Document = update.message.document
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("Только админы могут загружать файлы.")
        return

    file_name = doc.file_name or "uploaded"
    dst = os.path.join(UPLOADS_DIR, file_name)
    file = await ctx.bot.get_file(doc.file_id)
    await file.download_to_drive(dst)

    # parse according to extension
    lines = []
    ext = file_name.lower().split(".")[-1]
    try:
        if ext in ("txt", "text"):
            with open(dst, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
        elif ext == "csv":
            import csv
            with open(dst, newline='', encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    if row:
                        lines.append(row[0].strip())
        elif ext == "json":
            import json
            with open(dst, "r", encoding="utf-8") as f:
                data = json.load(f)
                # expect either list of strings or list of objects with 'text'
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, str):
                            lines.append(item.strip())
                        elif isinstance(item, dict) and "text" in item:
                            lines.append(str(item["text"]).strip())
                elif isinstance(data, dict):
                    # maybe {"responses": [...]}
                    if "responses" in data and isinstance(data["responses"], list):
                        for it in data["responses"]:
                            if isinstance(it, str):
                                lines.append(it.strip())
        else:
            # generic: try to read as text
            with open(dst, "r", encoding="utf-8", errors="ignore") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
    except Exception as e:
        logger.exception("Error parsing uploaded file: %s", e)
        await update.message.reply_text("Не удалось распарсить файл. Убедитесь в корректном формате (.txt/.csv/.json).")
        return

    if not lines:
        await update.message.reply_text("Файл загружен, но не найдено ни одной фразы.")
        return

    add_responses_bulk(lines)
    responder.rebuild()
    await update.message.reply_text(f"Загружено {len(lines)} фраз(ы). Всего в базе: {count_responses()}")

async def text_message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        return
    # Find best matches
    matches = responder.find_best(text, top_k=TOP_K)
    if not matches:
        await update.message.reply_text("В базе пусто — загрузите файл с фразами (админ).")
        return

    best_text, score = matches[0]
    if score >= SIM_THRESHOLD:
        # respond with best match
        await update.message.reply_text(best_text)
    else:
        # low confidence — show top suggestions and ask for clarification
        reply = f"Не уверен, но могу предложить варианты (score показан для отладки):\n\n"
        for t, s in matches:
            reply += f"- ({s:.2f}) {t}\n"
        reply += "\nЕсли подходящего ответа нет, загрузите / обновите базу (админ)."
        await update.message.reply_text(reply)

# ===== main =====
def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("count", count_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))

    app.add_handler(MessageHandler(filters.Document.ALL & filters.ChatType.PRIVATE, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, text_message_handler))

    logger.info("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
