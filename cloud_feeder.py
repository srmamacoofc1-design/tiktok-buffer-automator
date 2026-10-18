import sqlite3
import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from buffer_client import BufferClient
from feeder import get_next_available_slots

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "app.db")

def run_cloud_feeder():
    if not os.path.exists(DB_PATH):
        logging.error(f"Banco de dados nao encontrado em {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.*, a.token, a.org_id, a.name as account_name
        FROM profiles p
        JOIN accounts a ON p.account_id = a.id
        WHERE p.active = 1
        ORDER BY p.id ASC
    """)
    profiles = cursor.fetchall()

    daily_times_default = ["09:00", "12:00", "15:00", "18:00", "21:00"]
    total_pushed = 0

    for prof in profiles:
        pid = prof["id"]
        pname = prof["name"]
        channel_id = prof["channel_id"]
        token = prof["token"]
        org_id = prof["org_id"]
        max_queue = prof["max_buffer_queue"] or 10

        daily_times = daily_times_default
        if prof["daily_times"]:
            try:
                daily_times = json.loads(prof["daily_times"])
            except Exception:
                pass

        logging.info(f"--- Verificando perfil #{pid} (@{pname}) ---")
        client = BufferClient(token)

        try:
            current_scheduled = client.get_scheduled_posts(org_id, channel_id)
            current_count = len(current_scheduled)
            logging.info(f"@{pname}: {current_count}/{max_queue} posts atualmente agendados no Buffer.")
        except Exception as e:
            logging.error(f"Erro ao consultar Buffer para @{pname}: {e}")
            continue

        free_slots = max(0, max_queue - current_count)
        if free_slots == 0:
            logging.info(f"Fila cheia para @{pname}. Aguardando publicacoes.")
            continue

        # Busca videos do estoque que tenham public_url valida
        cursor.execute("""
            SELECT * FROM video_stock
            WHERE profile_id = ? AND status = 'estoque' AND public_url IS NOT NULL AND public_url != ''
            ORDER BY id ASC
            LIMIT ?
        """, (pid, free_slots))
        available_videos = cursor.fetchall()

        if not available_videos:
            logging.info(f"Sem videos com link em nuvem prontos no estoque para @{pname}.")
            continue

        existing_due_ats = []
        for p in current_scheduled:
            try:
                due_str = p.get("dueAt")
                if due_str:
                    existing_due_ats.append(datetime.fromisoformat(due_str.replace("Z", "+00:00")))
            except Exception:
                pass

        target_slots = get_next_available_slots(existing_due_ats, daily_times, len(available_videos))

        for idx, vid in enumerate(available_videos):
            vid_id = vid["id"]
            slot_iso = target_slots[idx].strftime("%Y-%m-%dT%H:%M:%S.000Z")
            caption = vid["caption"] or vid["title"] or "Novo video"
            video_url = vid["public_url"]

            logging.info(f"Agendando #{vid_id} ('{vid['title'][:30]}...') para {slot_iso}")
            try:
                post_res = client.create_tiktok_post(
                    channel_id=channel_id,
                    text=caption,
                    video_url=video_url,
                    due_at_iso=slot_iso,
                    is_ai_generated=bool(vid["is_ai"])
                )
                b_id = post_res.get("id", "")
                cursor.execute("""
                    UPDATE video_stock
                    SET status = 'agendado_no_buffer',
                        buffer_post_id = ?,
                        scheduled_at = ?
                    WHERE id = ?
                """, (b_id, slot_iso, vid_id))
                conn.commit()
                total_pushed += 1
                logging.info(f"  ✓ Agendado com sucesso! Buffer ID: {b_id}")
            except Exception as e:
                logging.error(f"  ✗ Erro ao agendar #{vid_id}: {e}")

    conn.close()
    logging.info(f"Ciclo concluido. Total de novos posts agendados na nuvem: {total_pushed}")

if __name__ == "__main__":
    run_cloud_feeder()
