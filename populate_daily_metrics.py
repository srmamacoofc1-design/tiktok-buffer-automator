import sqlite3
import os
from datetime import datetime

def update_db(db_path):
    if not os.path.exists(db_path):
        print(f"Db {db_path} não existe, pulando...")
        return
        
    print(f"Atualizando {db_path}...")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 1. Adicionar colunas diárias no metrics_cache se não existirem
    cols = [
        ("views_today", "INTEGER DEFAULT 0"),
        ("posts_today", "INTEGER DEFAULT 0"),
        ("likes_today", "INTEGER DEFAULT 0"),
        ("shares_today", "INTEGER DEFAULT 0"),
        ("reach_today", "INTEGER DEFAULT 0")
    ]
    for col_name, col_type in cols:
        try:
            c.execute(f"ALTER TABLE metrics_cache ADD COLUMN {col_name} {col_type}")
            print(f"Coluna {col_name} adicionada!")
        except Exception:
            pass # já existe
            
    # 2. Criar tabela de histórico diário
    c.execute("""
    CREATE TABLE IF NOT EXISTS daily_views_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_date TEXT,
        profile_id INTEGER,
        profile_name TEXT,
        views_today INTEGER DEFAULT 0,
        posts_today INTEGER DEFAULT 0,
        likes_today INTEGER DEFAULT 0,
        shares_today INTEGER DEFAULT 0,
        reach_today INTEGER DEFAULT 0,
        total_views_snapshot INTEGER DEFAULT 0,
        updated_at TEXT,
        UNIQUE(log_date, profile_id)
    )
    """)
    
    # 3. Atualizar métricas de hoje para cada perfil
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().isoformat()
    
    daily_data = [
        {
            "id": 1,
            "name": "leurickshop",
            "views_today": 14850,
            "posts_today": 4,
            "likes_today": 420,
            "shares_today": 65,
            "reach_today": 9800,
            "total_views": 455228,
            "total_likes": 3444,
            "total_shares": 345,
            "total_reach": 211199,
            "posts": 29
        },
        {
            "id": 6,
            "name": "dicas.dejair",
            "views_today": 8920,
            "posts_today": 4,
            "likes_today": 315,
            "shares_today": 120,
            "reach_today": 6200,
            "total_views": 186725,
            "total_likes": 6325,
            "total_shares": 2591,
            "total_reach": 177287,
            "posts": 13
        },
        {
            "id": 3,
            "name": "erickmania5",
            "views_today": 3140,
            "posts_today": 4,
            "likes_today": 180,
            "shares_today": 22,
            "reach_today": 2400,
            "total_views": 43759,
            "total_likes": 2614,
            "total_shares": 109,
            "total_reach": 40415,
            "posts": 25
        },
        {
            "id": 5,
            "name": "a.bia69",
            "views_today": 1250,
            "posts_today": 3,
            "likes_today": 45,
            "shares_today": 6,
            "reach_today": 950,
            "total_views": 17850,
            "total_likes": 146,
            "total_shares": 4,
            "total_reach": 14925,
            "posts": 26
        },
        {
            "id": 2,
            "name": "leurick_o_meno",
            "views_today": 680,
            "posts_today": 4,
            "likes_today": 18,
            "shares_today": 2,
            "reach_today": 520,
            "total_views": 7004,
            "total_likes": 80,
            "total_shares": 0,
            "total_reach": 6652,
            "posts": 26
        },
        {
            "id": 4,
            "name": "leurick.k1",
            "views_today": 310,
            "posts_today": 3,
            "likes_today": 8,
            "shares_today": 0,
            "reach_today": 280,
            "total_views": 3084,
            "total_likes": 12,
            "total_shares": 0,
            "total_reach": 3084,
            "posts": 26
        }
    ]
    
    for d in daily_data:
        c.execute("""
            UPDATE metrics_cache SET
                views_today = ?,
                posts_today = ?,
                likes_today = ?,
                shares_today = ?,
                reach_today = ?,
                updated_at = ?
            WHERE profile_id = ?
        """, (d["views_today"], d["posts_today"], d["likes_today"], d["shares_today"], d["reach_today"], now_str, d["id"]))
        
        c.execute("""
            INSERT INTO daily_views_history (
                log_date, profile_id, profile_name, views_today, posts_today, likes_today, shares_today, reach_today, total_views_snapshot, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(log_date, profile_id) DO UPDATE SET
                views_today = excluded.views_today,
                posts_today = excluded.posts_today,
                likes_today = excluded.likes_today,
                shares_today = excluded.shares_today,
                reach_today = excluded.reach_today,
                total_views_snapshot = excluded.total_views_snapshot,
                updated_at = excluded.updated_at
        """, (
            today_str, d["id"], d["name"], d["views_today"], d["posts_today"], d["likes_today"], d["shares_today"], d["reach_today"], d["total_views"], now_str
        ))
        
    conn.commit()
    conn.close()
    print(f"Atualizado {db_path} com sucesso!")

update_db("data/app.db")
update_db("api/data/app.db")
