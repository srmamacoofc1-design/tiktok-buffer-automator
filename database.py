import sqlite3
import os
import json
import logging
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CANDIDATE_PATHS = [
    os.path.join(BASE_DIR, "data", "app.db"),
    os.path.join(BASE_DIR, "api", "data", "app.db"),
    os.path.join(os.getcwd(), "data", "app.db"),
    os.path.join(os.getcwd(), "api", "data", "app.db")
]

def resolve_db_path() -> str:
    source = None
    for p in CANDIDATE_PATHS:
        if os.path.exists(p) and os.path.getsize(p) > 0:
            source = p
            break
            
    # Se estiver rodando no Vercel (AWS Lambda)
    if os.environ.get("VERCEL"):
        tmp_path = "/tmp/app.db"
        if source and (not os.path.exists(tmp_path) or os.path.getsize(tmp_path) < os.path.getsize(source)):
            try:
                shutil.copy2(source, tmp_path)
            except Exception as e:
                logging.warning(f"Aviso ao copiar DB para /tmp: {e}")
        if os.path.exists(tmp_path):
            return tmp_path
        if source:
            return source
            
    return source or CANDIDATE_PATHS[0]

DB_PATH = resolve_db_path()

def get_db():
    path = resolve_db_path()
    try:
        conn = sqlite3.connect(path, timeout=20)
    except sqlite3.OperationalError:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if os.environ.get("VERCEL"):
        return
    path = resolve_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
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
    print(f"Banco de dados inicializado com sucesso em {resolve_db_path()}!")
