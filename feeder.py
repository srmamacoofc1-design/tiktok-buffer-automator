import time
import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from database import get_db
from buffer_client import BufferClient, upload_video_to_public_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def log_event(profile_id: Optional[int], level: str, message: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logs (profile_id, level, message, created_at) VALUES (?, ?, ?, ?)",
        (profile_id, level, message, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    logging.info(f"[{level.upper()}] (Profile: {profile_id}) {message}")

def get_next_available_slots(
    existing_due_ats: List[datetime],
    daily_times_str: List[str],
    count_needed: int,
    start_from: Optional[datetime] = None
) -> List[datetime]:
    """
    Calcula os próximos 'count_needed' horários disponíveis baseado nos horários diários configurados.
    Evita colidir com horários que já estão agendados no Buffer.
    """
    if not daily_times_str:
        daily_times_str = ["09:00", "12:00", "15:00", "18:00", "21:00"]
    
    # Ordenar os horários do dia (ex: 5 horários por dia)
    daily_times_str = sorted(daily_times_str)


    now = start_from or datetime.now(timezone.utc)
    
    # Se houver posts agendados, o ponto de partida deve ser após o último post agendado
    if existing_due_ats:
        last_due = max(existing_due_ats)
        if last_due > now:
            now = last_due

    # Converter horários existentes em timestamps para fácil verificação de proximidade (+- 15 min)
    existing_ts = [dt.timestamp() for dt in existing_due_ats]

    results = []
    current_day = now.date()

    # Percorre dias futuros gerando slots
    for day_offset in range(0, 180): # até 6 meses no futuro
        target_date = current_day + timedelta(days=day_offset)
        for t_str in daily_times_str:
            try:
                parts = t_str.strip().split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
            except Exception:
                hour, minute = 12, 0

            # Cria o datetime no fuso UTC (o Buffer trabalha em UTC)
            # Para o fuso de Brasília (UTC-3), somamos 3 horas se o usuário digitou horário local
            # Horário de Brasília UTC-3: 12:00 BRT = 15:00 UTC
            # Vamos tratar os horários digitados pelo usuário como horário de Brasília (UTC-3)
            slot_utc = datetime(
                target_date.year, target_date.month, target_date.day,
                hour, minute, 0, tzinfo=timezone.utc
            ) + timedelta(hours=3) # Converte BRT -> UTC

            # Só aceita se for no futuro (pelo menos 15 minutos à frente de agora)
            if slot_utc <= datetime.now(timezone.utc) + timedelta(minutes=15):
                continue

            # Verifica se já não existe post nesse mesmo horário (+- 15 minutos)
            slot_ts = slot_utc.timestamp()
            conflict = any(abs(slot_ts - ets) < 900 for ets in existing_ts)
            if not conflict:
                results.append(slot_utc)
                existing_ts.append(slot_ts)
                if len(results) >= count_needed:
                    return results

    return results

def sync_profile(profile_id: int):
    """
    Sincroniza um perfil do TikTok com o Buffer:
    1. Verifica quantos posts estão agendados no Buffer.
    2. Se houver vagas na fila (limite padrão 10), busca os próximos vídeos do estoque.
    3. Faz o upload e agenda os vídeos nas próximas datas disponíveis.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.*, a.token, a.org_id, a.name as account_name
        FROM profiles p
        JOIN accounts a ON p.account_id = a.id
        WHERE p.id = ? AND p.active = 1
    """, (profile_id,))
    profile = cursor.fetchone()
    
    if not profile:
        conn.close()
        return {"error": "Perfil não encontrado ou inativo"}

    token = profile["token"]
    org_id = profile["org_id"]
    channel_id = profile["channel_id"]
    profile_name = profile["name"]
    max_queue = profile["max_buffer_queue"] or 10
    
    daily_times = ["11:00", "15:00", "19:00"]
    if profile["daily_times"]:
        try:
            daily_times = json.loads(profile["daily_times"])
        except Exception:
            pass

    client = BufferClient(token)
    
    # 1. Obter posts atualmente agendados no Buffer
    try:
        current_scheduled = client.get_scheduled_posts(org_id, channel_id)
        current_count = len(current_scheduled)
        log_event(profile_id, "info", f"Perfil @{profile_name}: {current_count}/{max_queue} posts agendados no Buffer.")
    except Exception as e:
        log_event(profile_id, "error", f"Falha ao consultar fila do Buffer para @{profile_name}: {e}")
        conn.close()
        return {"error": str(e)}

    # Parse das datas dos posts já agendados
    existing_due_ats = []
    for p in current_scheduled:
        try:
            due_str = p.get("dueAt")
            if due_str:
                dt = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
                existing_due_ats.append(dt)
        except Exception:
            pass

    # 2. Verificar vagas disponíveis
    free_slots = max(0, max_queue - current_count)
    if free_slots == 0:
        log_event(profile_id, "info", f"Fila do Buffer cheia para @{profile_name} ({current_count}/{max_queue}). Aguardando publicações.")
        conn.close()
        return {"message": "Fila cheia", "scheduled_count": current_count, "pushed": 0}

    # 3. Buscar vídeos no estoque prontos para agendamento
    cursor.execute("""
        SELECT * FROM video_stock
        WHERE profile_id = ? AND status = 'estoque'
        ORDER BY id ASC
        LIMIT ?
    """, (profile_id, free_slots))
    stock_videos = cursor.fetchall()

    if not stock_videos:
        log_event(profile_id, "info", f"Sem vídeos no estoque para @{profile_name}.")
        conn.close()
        return {"message": "Sem vídeos no estoque", "scheduled_count": current_count, "pushed": 0}

    # 4. Calcular os próximos horários livres
    target_slots = get_next_available_slots(existing_due_ats, daily_times, len(stock_videos))

    pushed_count = 0
    for i, video in enumerate(stock_videos):
        slot_dt = target_slots[i]
        slot_iso = slot_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        vid_id = video["id"]
        local_path = video["local_path"]
        caption = video["caption"] or video["title"] or "Novo vídeo"
        is_ai = bool(video["is_ai"])

        # Se não tem URL pública ainda, faz upload
        public_url = video["public_url"]
        if not public_url:
            try:
                log_event(profile_id, "info", f"Subindo vídeo #{vid_id} ({video['filename']}) para gerar link público...")
                public_url = upload_video_to_public_url(local_path)
                cursor.execute("UPDATE video_stock SET public_url = ? WHERE id = ?", (public_url, vid_id))
                conn.commit()
            except Exception as e:
                err_msg = f"Erro no upload do vídeo #{vid_id}: {e}"
                log_event(profile_id, "error", err_msg)
                cursor.execute("UPDATE video_stock SET status = 'erro', error_message = ? WHERE id = ?", (err_msg, vid_id))
                conn.commit()
                continue

        # Agenda no Buffer
        try:
            log_event(profile_id, "info", f"Agendando post no TikTok @{profile_name} para {slot_iso}...")
            post_data = client.create_tiktok_post(
                channel_id=channel_id,
                text=caption,
                video_url=public_url,
                due_at_iso=slot_iso,
                is_ai_generated=is_ai
            )
            buffer_post_id = post_data.get("id", "")
            
            cursor.execute("""
                UPDATE video_stock
                SET status = 'agendado_no_buffer',
                    buffer_post_id = ?,
                    scheduled_at = ?
                WHERE id = ?
            """, (buffer_post_id, slot_iso, vid_id))
            conn.commit()
            pushed_count += 1
            log_event(profile_id, "success", f"Vídeo #{vid_id} agendado no Buffer com sucesso! (ID: {buffer_post_id})")
        except Exception as e:
            err_msg = f"Erro ao criar post no Buffer: {e}"
            log_event(profile_id, "error", err_msg)
            cursor.execute("UPDATE video_stock SET status = 'erro', error_message = ? WHERE id = ?", (err_msg, vid_id))
            conn.commit()

    conn.close()
    return {"message": "Sincronizado", "pushed": pushed_count}


def sync_all_active_profiles():
    """Sincroniza todos os perfis ativos cadastrados no banco de dados"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM profiles WHERE active = 1")
    profiles = cursor.fetchall()
    conn.close()
    
    results = {}
    for p in profiles:
        try:
            res = sync_profile(p["id"])
            results[p["name"]] = res
        except Exception as e:
            results[p["name"]] = {"error": str(e)}
    return results


class FeederWorker(threading.Thread):
    """Worker em background que monitora a fila a cada intervalo (padrão: 5 minutos)"""
    def __init__(self, interval_seconds: int = 300):
        super().__init__()
        self.interval = interval_seconds
        self.running = True
        self.daemon = True

    def run(self):
        logging.info("FeederWorker iniciado: monitoramento de estoque e fila ativo.")
        while self.running:
            try:
                sync_all_active_profiles()
            except Exception as e:
                logging.error(f"Erro no ciclo do FeederWorker: {e}")
            
            # Aguarda o intervalo ou até ser parado
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)

    def stop(self):
        self.running = False
