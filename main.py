import os
import shutil
import json
import logging
from typing import List, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, get_db
from buffer_client import BufferClient
from feeder import sync_profile, sync_all_active_profiles, FeederWorker, log_event

logging.basicConfig(level=logging.INFO)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

feeder_worker = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global feeder_worker
    init_db()
    # Inicia o FeederWorker para monitorar a cada 300 segundos (5 minutos)
    feeder_worker = FeederWorker(interval_seconds=300)
    feeder_worker.start()
    logging.info("FeederWorker em background ativado.")
    yield
    if feeder_worker:
        feeder_worker.stop()
        logging.info("FeederWorker desativado.")

app = FastAPI(title="TikTok Buffer Automator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

SHORTS_DIR = r"C:\Users\leurickkkk77\Downloads\Shorts_210_EDITADOS"
if os.path.exists(SHORTS_DIR):
    app.mount("/shorts", StaticFiles(directory=SHORTS_DIR), name="shorts")


@app.get("/", response_class=HTMLResponse)
def index():
    html_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Frontend em construção...</h1>"

@app.get("/api/profiles")
def list_profiles():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, a.name as account_name, a.email as account_email, a.token, a.org_id
        FROM profiles p
        JOIN accounts a ON p.account_id = a.id
        ORDER BY p.id ASC
    """)
    rows = cursor.fetchall()
    
    profiles = []
    for r in rows:
        p = dict(r)
        pid = p["id"]
        
        # Parse horários diários
        try:
            p["daily_times"] = json.loads(p["daily_times"]) if p["daily_times"] else ["09:00", "12:00", "15:00", "18:00", "21:00"]
        except Exception:
            p["daily_times"] = ["09:00", "12:00", "15:00", "18:00", "21:00"]

            
        posts_per_day = max(1, len(p["daily_times"]))
        
        # Contagem de vídeos no estoque local
        cursor.execute("SELECT COUNT(*) as count FROM video_stock WHERE profile_id = ? AND status = 'estoque'", (pid,))
        stock_count = cursor.fetchone()["count"]
        p["stock_count"] = stock_count
        
        # Contagem de vídeos agendados no Buffer
        cursor.execute("SELECT COUNT(*) as count FROM video_stock WHERE profile_id = ? AND status = 'agendado_no_buffer'", (pid,))
        scheduled_local_count = cursor.fetchone()["count"]
        p["scheduled_local_count"] = scheduled_local_count
        
        # Contagem em tempo real na fila do Buffer
        try:
            client = BufferClient(p["token"])
            remote_scheduled = client.get_scheduled_posts(p["org_id"], p["channel_id"])
            p["buffer_queue_count"] = len(remote_scheduled)
            p["buffer_online"] = True
        except Exception as e:
            p["buffer_queue_count"] = scheduled_local_count
            p["buffer_online"] = False
            p["buffer_error"] = str(e)
            
        # Cálculo de duração do estoque em dias
        total_remaining = stock_count
        duration_days = round(total_remaining / posts_per_day, 1)
        end_date = datetime.now() + timedelta(days=duration_days)
        
        p["duration_days"] = duration_days
        p["duration_text"] = f"{duration_days} dias (até {end_date.strftime('%d/%m/%Y')})" if total_remaining > 0 else "Estoque vazio"
        
        profiles.append(p)
        
    conn.close()
    return profiles

@app.get("/api/profiles/{profile_id}/metrics")

def get_profile_metrics(profile_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, a.token, a.org_id
        FROM profiles p
        JOIN accounts a ON p.account_id = a.id
        WHERE p.id = ?
    """, (profile_id,))
    p = cursor.fetchone()
    conn.close()
    if not p:
        raise HTTPException(status_code=404, detail="Perfil não encontrado")

    client = BufferClient(p["token"])
    metrics = client.get_channel_metrics(p["org_id"], p["channel_id"])
    metrics["profile_name"] = p["name"]
    return metrics

@app.get("/api/metrics-summary")
def get_all_metrics():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.name, p.channel_id, a.token, a.org_id
        FROM profiles p
        JOIN accounts a ON p.account_id = a.id
        WHERE p.active = 1
    """)

    profiles = cursor.fetchall()
    conn.close()

    summary = {
        "total_views": 0,
        "total_likes": 0,
        "total_comments": 0,
        "total_shares": 0,
        "total_reach": 0,
        "profiles": []
    }

    for p in profiles:
        try:
            client = BufferClient(p["token"])
            m = client.get_channel_metrics(p["org_id"], p["channel_id"])
            m["profile_id"] = p["id"]
            m["profile_name"] = p["name"]
            summary["total_views"] += m.get("total_views", 0)
            summary["total_likes"] += m.get("total_likes", 0)
            summary["total_comments"] += m.get("total_comments", 0)
            summary["total_shares"] += m.get("total_shares", 0)
            summary["total_reach"] += m.get("total_reach", 0)
            summary["profiles"].append(m)
        except Exception as e:
            summary["profiles"].append({"profile_id": p["id"], "profile_name": p["name"], "error": str(e)})

    return summary


@app.post("/api/profiles/{profile_id}/settings")
def update_profile_settings(
    profile_id: int,
    daily_times: str = Form(...), # JSON string ["10:00", "14:00"]
    default_hashtags: str = Form(...),
    max_buffer_queue: int = Form(10)
):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE profiles
        SET daily_times = ?, default_hashtags = ?, max_buffer_queue = ?
        WHERE id = ?
    """, (daily_times, default_hashtags, max_buffer_queue, profile_id))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Configurações salvas!"}

@app.post("/api/upload-stock")
async def upload_stock(
    background_tasks: BackgroundTasks,
    profile_id: int = Form(...),
    videos: List[UploadFile] = File(...),
    custom_hashtags: Optional[str] = Form(None),
    is_ai: bool = Form(True)
):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,))
    profile = cursor.fetchone()
    if not profile:
        conn.close()
        raise HTTPException(status_code=404, detail="Perfil não encontrado")
        
    hashtags = custom_hashtags or profile["default_hashtags"] or "#fyp #foryou #viral"
    
    added_count = 0
    now_str = datetime.now().isoformat()
    
    for upload in videos:
        original_name = upload.filename
        # Salva o arquivo no disco
        clean_name = os.path.splitext(original_name)[0].replace("_", " ").replace("-", " ").strip().title()
        save_path = os.path.join(UPLOAD_DIR, f"{int(datetime.now().timestamp()*1000)}_{original_name}")
        
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)
            
        full_caption = f"{clean_name} 😱🔥\n\n{hashtags}"
        
        cursor.execute("""
            INSERT INTO video_stock (
                profile_id, filename, title, caption, local_path, is_ai, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'estoque', ?)
        """, (profile_id, original_name, clean_name, full_caption, save_path, 1 if is_ai else 0, now_str))
        added_count += 1
        
    conn.commit()
    conn.close()
    
    log_event(profile_id, "success", f"{added_count} novos vídeos adicionados ao estoque!")
    
    # Executa a sincronização em background para já preencher a fila do Buffer
    background_tasks.add_task(sync_profile, profile_id)
    
    return {
        "status": "success",
        "added_count": added_count,
        "message": f"{added_count} vídeos adicionados ao estoque com sucesso!"
    }

@app.get("/api/stock")
def get_stock(profile_id: Optional[int] = None, status: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT s.*, p.name as profile_name FROM video_stock s JOIN profiles p ON s.profile_id = p.id WHERE 1=1"
    params = []
    
    if profile_id:
        query += " AND s.profile_id = ?"
        params.append(profile_id)
    if status:
        query += " AND s.status = ?"
        params.append(status)
        
    query += " ORDER BY s.id DESC LIMIT 100"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.delete("/api/stock/{stock_id}")
def delete_stock(stock_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM video_stock WHERE id = ?", (stock_id,))
    item = cursor.fetchone()
    if item:
        local_path = item["local_path"]
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass
        cursor.execute("DELETE FROM video_stock WHERE id = ?", (stock_id,))
        conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/sync")
def trigger_sync(background_tasks: BackgroundTasks, profile_id: Optional[int] = None):
    if profile_id:
        background_tasks.add_task(sync_profile, profile_id)
        return {"status": "started", "message": f"Sincronização iniciada para perfil #{profile_id}"}
    else:
        background_tasks.add_task(sync_all_active_profiles)
        return {"status": "started", "message": "Sincronização geral iniciada!"}

@app.get("/api/accounts")
def list_accounts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, org_id, created_at FROM accounts ORDER BY id ASC")
    accs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return accs

@app.post("/api/accounts")
def add_account(token: str = Form(...), name: Optional[str] = Form(None)):
    token = token.strip()
    try:
        client = BufferClient(token)
        data = client.get_account_and_channels()
        account = data.get("account", {})
        email = account.get("email") or name or "Buffer Account"
        orgs = account.get("organizations", [])
        org_id = orgs[0]["id"] if orgs else ""
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM accounts WHERE token = ?", (token,))
        existing = cursor.fetchone()
        if existing:
            acc_id = existing["id"]
        else:
            cursor.execute(
                "INSERT INTO accounts (name, token, email, org_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (name or email, token, email, org_id, datetime.now().isoformat())
            )
            acc_id = cursor.lastrowid
            
        channels = data.get("channels", [])
        added_channels = []
        for ch in channels:
            ch_id = ch["id"]
            ch_name = ch["name"]
            ch_service = ch.get("service", "tiktok")
            
            cursor.execute("SELECT id FROM profiles WHERE channel_id = ?", (ch_id,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO profiles (
                        account_id, channel_id, name, service, default_hashtags,
                        daily_times, is_ai_default, max_buffer_queue, active, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, 10, 1, ?)
                """, (
                    acc_id, ch_id, ch_name, ch_service,
                    "#fyp #foryou #viral #tiktok #trending",
                    json.dumps(["10:30", "14:30", "18:30"]),
                    datetime.now().isoformat()
                ))
                added_channels.append(ch_name)
                
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "message": f"Conta conectada: {email}",
            "channels_added": added_channels
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao conectar token do Buffer: {e}")

@app.get("/api/logs")
def get_logs():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.*, p.name as profile_name
        FROM logs l
        LEFT JOIN profiles p ON l.profile_id = p.id
        ORDER BY l.id DESC
        LIMIT 50
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
