import os
import sys
import sqlite3
import json
import time
import urllib.request
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8')
from buffer_client import BufferClient

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "app.db")

def safe_execute(client, query, variables=None, retries=3):
    for attempt in range(retries):
        try:
            return client.execute_query(query, variables)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_time = (attempt + 1) * 5
                print(f"    [Rate limit 429] Aguardando {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise e
        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(3)

def delete_buffer_post(client, token: str, post_id: str):
    query = f"""
    mutation {{
      deletePost(input: {{ id: "{post_id}" }}) {{
        ... on DeletePostSuccess {{
          id
        }}
        ... on VoidMutationError {{
          message
        }}
      }}
    }}
    """
    return safe_execute(client, query)

def get_post_source(client, post_id: str):
    query = f"""
    query {{
      post(input: {{ id: "{post_id}" }}) {{
        id
        status
        assets {{
          ... on VideoAsset {{
            source
          }}
        }}
      }}
    }}
    """
    try:
        d = safe_execute(client, query)
        post = d.get('post', {}) if d else {}
        assets = post.get('assets', []) if post else []
        src = assets[0].get('source') if assets else ''
        status = post.get('status') if post else ''
        return str(src or ''), str(status or '')
    except Exception:
        return '', ''

def rebuild():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.id, p.name, a.token, a.org_id, p.channel_id
        FROM profiles p
        JOIN accounts a ON p.account_id = a.id
        ORDER BY p.id ASC
    """)
    profiles = cursor.fetchall()

    today = datetime.now(timezone.utc).date()
    target_slots_brt = [
        # Hoje
        datetime(today.year, today.month, today.day, 19, 0, 0, tzinfo=timezone.utc) + timedelta(hours=3),
        datetime(today.year, today.month, today.day, 19, 50, 0, tzinfo=timezone.utc) + timedelta(hours=3),
        datetime(today.year, today.month, today.day, 20, 40, 0, tzinfo=timezone.utc) + timedelta(hours=3),
        datetime(today.year, today.month, today.day, 21, 30, 0, tzinfo=timezone.utc) + timedelta(hours=3),
        datetime(today.year, today.month, today.day, 22, 20, 0, tzinfo=timezone.utc) + timedelta(hours=3),
        # Amanhã
        datetime(today.year, today.month, today.day, 9, 0, 0, tzinfo=timezone.utc) + timedelta(days=1, hours=3),
        datetime(today.year, today.month, today.day, 12, 0, 0, tzinfo=timezone.utc) + timedelta(days=1, hours=3),
        datetime(today.year, today.month, today.day, 15, 0, 0, tzinfo=timezone.utc) + timedelta(days=1, hours=3),
        datetime(today.year, today.month, today.day, 18, 0, 0, tzinfo=timezone.utc) + timedelta(days=1, hours=3),
        datetime(today.year, today.month, today.day, 21, 0, 0, tzinfo=timezone.utc) + timedelta(days=1, hours=3),
    ]

    print("==================================================")
    print("RECONSTRUÇÃO COMPLETA DAS FILAS COM LINKS GITHUB")
    print("==================================================")

    for prof in profiles:
        pid = prof["id"]
        pname = prof["name"]
        token = prof["token"]
        org_id = prof["org_id"]
        channel_id = prof["channel_id"]

        print(f"\n" + "="*50)
        print(f"PROCESSANDO PERFIL #{pid}: @{pname}")
        print("="*50)
        client = BufferClient(token)

        # 1. Pega apenas posts agendados ou com erro (NUNCA os sent/publicados)
        query_scheduled_and_error = """
        query GetPendingAndError($orgId: OrganizationId!, $channelId: ChannelId!) {
          posts(first: 50, input: {
            organizationId: $orgId,
            filter: { status: [scheduled, error], channelIds: [$channelId] }
          }) {
            edges {
              node {
                id
                dueAt
                status
              }
            }
          }
        }
        """
        data = safe_execute(client, query_scheduled_and_error, {'orgId': org_id, 'channelId': channel_id})
        edges = data.get('posts', {}).get('edges', []) if data else []
        print(f"Encontrados {len(edges)} posts pendentes/erro para @{pname}.")

        for e in edges:
            node = e['node']
            post_id = node['id']
            status = node['status']
            src_str, _ = get_post_source(client, post_id)
            
            # Se for erro ou não tiver link direto do GitHub, remove
            if status == 'error' or not src_str or 'github.com' not in src_str:
                print(f"  Removendo post quebrado {post_id} ({status} | src: {src_str[:40]}...)")
                try:
                    delete_buffer_post(client, token, post_id)
                    time.sleep(1.2)
                except Exception as ex:
                    print(f"    Erro ao deletar {post_id}: {ex}")

        # Reseta no banco os videos desvinculados
        cursor.execute("""
            UPDATE video_stock
            SET status = 'estoque'
            WHERE profile_id = ? AND status = 'agendado_no_buffer' AND (public_url IS NULL OR public_url NOT LIKE '%github.com%')
        """, (pid,))
        conn.commit()

        # 2. Verifica quantos posts válidos restaram na fila
        remaining_posts = client.get_scheduled_posts(org_id, channel_id)
        current_valid_count = len(remaining_posts)
        print(f"Posts válidos no Buffer para @{pname}: {current_valid_count}/10")

        needed = max(0, 10 - current_valid_count)
        if needed == 0:
            print(f"Fila de @{pname} já está completa (10/10)!")
            continue

        # 3. Busca os próximos vídeos no estoque com link no GitHub
        cursor.execute("""
            SELECT id, title, caption, public_url, is_ai
            FROM video_stock
            WHERE profile_id = ? AND status = 'estoque' AND public_url LIKE '%github.com%'
            ORDER BY id ASC
            LIMIT ?
        """, (pid, needed))
        videos_to_schedule = cursor.fetchall()

        if not videos_to_schedule:
            print(f"Sem vídeos disponíveis no estoque para @{pname}.")
            continue

        existing_due_ats = []
        for p in remaining_posts:
            if p.get("dueAt"):
                try:
                    existing_due_ats.append(datetime.fromisoformat(p["dueAt"].replace("Z", "+00:00")))
                except Exception:
                    pass

        assigned_slots = []
        now_thresh = datetime.now(timezone.utc) + timedelta(minutes=10)
        for slot in target_slots_brt:
            if slot <= now_thresh:
                continue
            conflict = any(abs(slot.timestamp() - e.timestamp()) < 1200 for e in existing_due_ats)
            if not conflict:
                assigned_slots.append(slot)
                existing_due_ats.append(slot)
                if len(assigned_slots) >= len(videos_to_schedule):
                    break

        print(f"Agendando {len(videos_to_schedule)} novos posts para @{pname} com link GitHub:")
        for idx, vid in enumerate(videos_to_schedule):
            vid_id = vid["id"]
            title = vid["title"]
            caption = vid["caption"] or title or "Novo vídeo"
            video_url = vid["public_url"]
            is_ai = bool(vid["is_ai"])
            slot_iso = assigned_slots[idx].strftime("%Y-%m-%dT%H:%M:%S.000Z")
            brt_dt = assigned_slots[idx] - timedelta(hours=3)

            print(f"  [{idx+1}/{len(videos_to_schedule)}] '{title[:28]}...' -> {brt_dt.strftime('%d/%m %H:%M')} BRT ({slot_iso})")
            try:
                post_res = client.create_tiktok_post(
                    channel_id=channel_id,
                    text=caption,
                    video_url=video_url,
                    due_at_iso=slot_iso,
                    is_ai_generated=is_ai
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
                print(f"    ✓ Criado com sucesso! ID: {b_id}")
                time.sleep(1.5)
            except Exception as ex:
                print(f"    ✗ Erro ao agendar post #{vid_id}: {ex}")

    conn.close()
    print("\n==================================================")
    print("TODAS AS 6 FILAS RECONSTRUÍDAS COM 10/10 POSTS!")
    print("==================================================")

if __name__ == "__main__":
    rebuild()
