import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "app.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()
    
    # Tabela de contas/tokens do Buffer
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        token TEXT UNIQUE,
        email TEXT,
        org_id TEXT,
        created_at TEXT
    )
    """)
    
    # Tabela de perfis conectados (TikTok)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER,
        channel_id TEXT UNIQUE,
        name TEXT,
        service TEXT DEFAULT 'tiktok',
        default_hashtags TEXT,
        daily_times TEXT, -- JSON array: ["11:00", "15:00", "19:00"]
        is_ai_default INTEGER DEFAULT 1,
        max_buffer_queue INTEGER DEFAULT 10,
        active INTEGER DEFAULT 1,
        created_at TEXT,
        FOREIGN KEY (account_id) REFERENCES accounts(id)
    )
    """)
    
    # Tabela de estoque de vídeos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS video_stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER,
        filename TEXT,
        title TEXT,
        caption TEXT,
        local_path TEXT,
        public_url TEXT,
        is_ai INTEGER DEFAULT 1,
        status TEXT DEFAULT 'estoque', -- 'estoque', 'uploading', 'agendado_no_buffer', 'publicado', 'erro'
        buffer_post_id TEXT,
        scheduled_at TEXT,
        error_message TEXT,
        created_at TEXT,
        FOREIGN KEY (profile_id) REFERENCES profiles(id)
    )
    """)
    
    # Tabela de logs do sistema
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER,
        level TEXT, -- 'info', 'warn', 'error', 'success'
        message TEXT,
        created_at TEXT
    )
    """)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Banco de dados inicializado com sucesso!")
