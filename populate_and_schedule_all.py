import os
import http.server
import socketserver

import threading
import time
import urllib.request
import functools
import subprocess
import re
import requests
import sqlite3
import sys
from urllib.parse import quote
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8')

from buffer_client import BufferClient
from feeder import get_next_available_slots

PORT = 8080
SHORTS_DIR = r"C:\Users\leurickkkk77\Downloads\Shorts_210_EDITADOS"
CLOUDFLARED_EXE = r"C:\Users\leurickkkk77\.gemini\antigravity\scratch\tiktok-buffer-automator\cloudflared.exe"
DB_PATH = r"C:\Users\leurickkkk77\.gemini\antigravity\scratch\tiktok-buffer-automator\data\app.db"

def run_all():
    print("=" * 60)
    print("INICIANDO SERVIDOR LOCAL E TUNEL CLOUDFLARE PARA ENVIO")
    print("=" * 60)

    # 1. Inicia servidor HTTP na porta 8080
    Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=SHORTS_DIR)
    httpd = socketserver.TCPServer(('127.0.0.1', PORT), Handler)
    http_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    http_thread.start()
    print("1. Servidor de streaming local ativo na porta 8080.")

    # 2. Inicia o túnel Cloudflare
    cmd = [CLOUDFLARED_EXE, 'tunnel', '--url', f'http://127.0.0.1:{PORT}']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')

    tunnel_url = None
    t0 = time.time()
    while time.time() - t0 < 30:
        line = proc.stderr.readline()
        if 'trycloudflare.com' in line:
            m = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
            if m:
                tunnel_url = m.group(0)
                break

    if not tunnel_url:
        print("Erro: Não foi possível obter a URL do túnel Cloudflare.")
        proc.terminate()
        httpd.shutdown()
        return

    print(f"2. Túnel Cloudflare ativo: {tunnel_url}")
    print("Aguardando 6s para propagação do DNS Cloudflare...")
    time.sleep(6)

    # 3. Conecta ao banco de dados
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.id, p.name, p.channel_id, a.token, a.org_id
        FROM profiles p
        JOIN accounts a ON p.account_id = a.id
        ORDER BY p.id ASC
    """)
    profiles = cursor.fetchall()

    daily_times = ["09:00", "12:00", "15:00", "18:00", "21:00"]
    total_scheduled_now = 0

    # Atualiza o vídeo 12 da Conta 2 que já foi agendado no teste
    cursor.execute("""
        UPDATE video_stock
        SET status = 'agendado_no_buffer',
            buffer_post_id = '6ad4e760a48c8f8371a3752b',
            scheduled_at = '2026-10-20T12:00:00.000Z'
        WHERE profile_id = 3 AND filename LIKE '12 - a tempestade%'
    """)
    conn.commit()

    for pid, pname, channel_id, token, org_id in profiles:
        print(f"\n" + "-" * 50)
        print(f"PROCESSANDO PERFIL #{pid}: @{pname}")
        print("-" * 50)

        client = BufferClient(token)

        try:
            current_posts = client.get_scheduled_posts(org_id, channel_id)
            current_count = len(current_posts)
            print(f"Fila atual no Buffer: {current_count}/10 posts")
        except Exception as e:
            print(f"Erro ao consultar Buffer para @{pname}: {e}")
            continue

        free_slots = max(0, 10 - current_count)
        if free_slots == 0:
            print(f"Fila do Buffer já está cheia (10/10)! Mantendo estoque preparado.")
            continue

        # Busca os próximos vídeos no estoque
        cursor.execute("""
            SELECT id, filename, title, caption, local_path
            FROM video_stock
            WHERE profile_id = ? AND status = 'estoque'
            ORDER BY id ASC
            LIMIT ?
        """, (pid, free_slots))
        videos_to_post = cursor.fetchall()

        if not videos_to_post:
            print(f"Sem vídeos pendentes no estoque para @{pname}.")
            continue

        print(f"Agendando {len(videos_to_post)} vídeos para completar a fila do Buffer...")

        existing_dates = []
        for p in current_posts:
            if p.get("dueAt"):
                try:
                    existing_dates.append(datetime.fromisoformat(p["dueAt"].replace("Z", "+00:00")))
                except Exception:
                    pass

        target_slots = get_next_available_slots(existing_dates, daily_times, len(videos_to_post))

        for idx, (vid_id, filename, title, caption, local_path) in enumerate(videos_to_post):
            slot_iso = target_slots[idx].strftime("%Y-%m-%dT%H:%M:%S.000Z")

            # Constrói a URL pública via túnel Cloudflare
            rel_path = os.path.relpath(local_path, SHORTS_DIR).replace("\\", "/")
            parts = rel_path.split("/")
            quoted_url = tunnel_url + "/" + "/".join([quote(p) for p in parts])

            print(f"  [{idx+1}/{len(videos_to_post)}] Agendando '{title[:35]}...' para {slot_iso}")

            try:
                post_res = client.create_tiktok_post(
                    channel_id=channel_id,
                    text=caption,
                    video_url=quoted_url,
                    due_at_iso=slot_iso,
                    is_ai_generated=True
                )
                b_id = post_res.get("id", "")
                cursor.execute("""
                    UPDATE video_stock
                    SET status = 'agendado_no_buffer',
                        buffer_post_id = ?,
                        scheduled_at = ?,
                        public_url = ?
                    WHERE id = ?
                """, (b_id, slot_iso, quoted_url, vid_id))
                conn.commit()
                total_scheduled_now += 1
                print(f"    ✓ Sucesso! ID no Buffer: {b_id}")
                time.sleep(1.5)
            except Exception as e:
                print(f"    ✗ Erro ao agendar: {e}")

    conn.close()
    proc.terminate()
    httpd.shutdown()

    print("\n" + "=" * 60)
    print(f"FINALIZADO COM SUCESSO! Total de novos vídeos agendados no Buffer agora: {total_scheduled_now}")
    print("=" * 60)

if __name__ == '__main__':
    run_all()
