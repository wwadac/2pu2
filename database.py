import sqlite3
import datetime

DB_NAME = "bot.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            referrer_id INTEGER,
            balance INTEGER DEFAULT 0,
            referrals_count INTEGER DEFAULT 0,
            rewarded INTEGER DEFAULT 0,
            joined_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            required_channel TEXT,
            check_subscription INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)
    # Вставляем настройки по умолчанию, если их нет
    cur.execute("INSERT OR IGNORE INTO settings (id, required_channel, check_subscription) VALUES (1, '', 0)")
    conn.commit()
    conn.close()

def add_user(user_id, username, referrer_id=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if cur.fetchone():
        conn.close()
        return False
    joined = datetime.datetime.now().isoformat()
    cur.execute("""
        INSERT INTO users (id, username, referrer_id, joined_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, username, referrer_id, joined))
    conn.commit()
    conn.close()
    return True

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    return user

def update_user_balance(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def increment_referrals(referrer_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE id = ?", (referrer_id,))
    conn.commit()
    conn.close()

def mark_rewarded(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET rewarded = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_settings():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT required_channel, check_subscription FROM settings WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    return {"channel": row[0], "enabled": bool(row[1])}

def update_settings(channel, enabled):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE settings SET required_channel = ?, check_subscription = ? WHERE id = 1",
                (channel, 1 if enabled else 0))
    conn.commit()
    conn.close()

def add_withdrawal(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    created = datetime.datetime.now().isoformat()
    cur.execute("INSERT INTO withdrawals (user_id, amount, created_at) VALUES (?, ?, ?)",
                (user_id, amount, created))
    conn.commit()
    conn.close()

def get_pending_withdrawals():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, amount, created_at FROM withdrawals WHERE status='pending'")
    rows = cur.fetchall()
    conn.close()
    return rows

def update_withdrawal_status(withdrawal_id, status):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE withdrawals SET status = ? WHERE id = ?", (status, withdrawal_id))
    conn.commit()
    conn.close()

def get_total_users():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]
    conn.close()
    return total

def get_total_balance():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT SUM(balance) FROM users")
    total = cur.fetchone()[0] or 0
    conn.close()
    return total
