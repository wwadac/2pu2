import sqlite3
import os

class Database:
    def __init__(self, db_path="bot_data.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                mode TEXT DEFAULT 'private',
                dataset_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS datasets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question TEXT,
                answer TEXT,
                keywords TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        self.conn.commit()
    
    def add_user(self, user_id, username):
        self.cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        self.conn.commit()
    
    def set_mode(self, user_id, mode):
        self.cursor.execute(
            "UPDATE users SET mode = ? WHERE user_id = ?",
            (mode, user_id)
        )
        self.conn.commit()
    
    def get_mode(self, user_id):
        self.cursor.execute(
            "SELECT mode FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = self.cursor.fetchone()
        return result[0] if result else 'private'
    
    def set_dataset_file(self, user_id, filename):
        self.cursor.execute(
            "UPDATE users SET dataset_file = ? WHERE user_id = ?",
            (filename, user_id)
        )
        self.conn.commit()
    
    def get_dataset_file(self, user_id):
        self.cursor.execute(
            "SELECT dataset_file FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None
    
    def clear_dataset(self, user_id):
        self.cursor.execute(
            "DELETE FROM datasets WHERE user_id = ?",
            (user_id,)
        )
        self.conn.commit()
    
    def add_qa_pair(self, user_id, question, answer, keywords):
        self.cursor.execute(
            "INSERT INTO datasets (user_id, question, answer, keywords) VALUES (?, ?, ?, ?)",
            (user_id, question, answer, keywords)
        )
        self.conn.commit()
    
    def get_all_qa_pairs(self, user_id):
        self.cursor.execute(
            "SELECT question, answer, keywords FROM datasets WHERE user_id = ?",
            (user_id,)
        )
        return self.cursor.fetchall()
    
    def get_all_users_with_datasets(self):
        self.cursor.execute(
            "SELECT DISTINCT user_id FROM datasets"
        )
        return [row[0] for row in self.cursor.fetchall()]
