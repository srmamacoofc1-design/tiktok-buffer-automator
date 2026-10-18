import sqlite3
import os
from datetime import datetime, timedelta

def seed_history(db_path):
    if not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 7 dias: de 6 dias atrás até hoje
    base_date = datetime.now()
    days_data = [
        {"days_ago": 6, "views": 18400, "posts": 15, "likes": 720},
        {"days_ago": 5, "views": 21200, "posts": 18, "likes": 810},
        {"days_ago": 4, "views": 24600, "posts": 20, "likes": 890},
        {"days_ago": 3, "views": 22100, "posts": 19, "likes": 840},
        {"days_ago": 2, "views": 26800, "posts": 22, "likes": 920},
        {"days_ago": 1, "views": 27400, "posts": 21, "likes": 950},
        {"days_ago": 0, "views": 29150, "posts": 22, "likes": 986},
    ]
    
    profiles = [
        {"id": 1, "name": "leurickshop", "ratio": 0.51},
        {"id": 6, "name": "dicas.dejair", "ratio": 0.31},
        {"id": 3, "name": "erickmania5", "ratio": 0.11},
        {"id": 5, "name": "a.bia69", "ratio": 0.04},
        {"id": 2, "name": "leurick_o_meno", "ratio": 0.02},
        {"id": 4, "name": "leurick.k1", "ratio": 0.01},
    ]
    
    for day in days_data:
        d = (base_date - timedelta(days=day["days_ago"])).strftime("%Y-%m-%d")
        now_str = datetime.now().isoformat()
        for p in profiles:
            p_views = int(day["views"] * p["ratio"])
            p_posts = max(1, int(day["posts"] * p["ratio"]))
            p_likes = int(day["likes"] * p["ratio"])
            c.execute("""
                INSERT INTO daily_views_history (
                    log_date, profile_id, profile_name, views_today, posts_today, likes_today, shares_today, reach_today, total_views_snapshot, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(log_date, profile_id) DO UPDATE SET
                    views_today = excluded.views_today,
                    posts_today = excluded.posts_today,
                    likes_today = excluded.likes_today,
                    updated_at = excluded.updated_at
            """, (d, p["id"], p["name"], p_views, p_posts, p_likes, int(p_likes*0.1), int(p_views*0.65), 700000, now_str))
            
    conn.commit()
    conn.close()
    print(f"Histórico populado em {db_path}!")

seed_history("data/app.db")
seed_history("api/data/app.db")
