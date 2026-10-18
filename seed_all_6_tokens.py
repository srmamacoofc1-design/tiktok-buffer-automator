import urllib.request
import json
import sys
from datetime import datetime
from database import init_db, get_db
from buffer_client import BufferClient

ALL_6_TOKENS = [
    ("Conta 1", "slFjxQI6JuTFE_PiSPR-DTH1uEjbHaq5MneSawdqobT"),
    ("Conta 2", "3-cBTDdx7lwKfMqxK_L3s4IHdm2yjyePUigXcKmOM8E"),
    ("Conta 3", "BZHxzVg6yB_ZPyTu3_g1IY0nRIKCAVzrcwSyPtiyaJP"),
    ("Conta 4", "PS1U2ykMkUqh7joW2eNNqecRt7DSdVUINMLPxdnorUR"),
    ("Conta 5", "URNr3UjaHXN2--8t9kz9pVzgP3se94UAe6oLju_tS_8"),
    ("Conta 6", "zJ8HvsQ0QQEJcWDO9QY1HPWBtCw0kIoAN9Yz3eYF1xh"),
]

sys.stdout.reconfigure(encoding='utf-8')

# 5 horários por dia (manhã, almoço, tarde, fim de tarde, noite)
FIVE_DAILY_TIMES = ["09:00", "12:00", "15:00", "18:00", "21:00"]
DEFAULT_HASHTAGS = "#fyp #foryou #viral #tiktok #curiosidades #historias #trending"

def seed_all():
    init_db()
    conn = get_db()
    cursor = conn.cursor()
    
    total_profiles = 0

    for name, token in ALL_6_TOKENS:
        token = token.strip()
        print(f"\n==========================================")
        print(f"Processando {name}...")
        try:
            client = BufferClient(token)
            data = client.get_account_and_channels()
            account = data.get("account", {})
            email = account.get("email") or name
            orgs = account.get("organizations", [])
            org_id = orgs[0]["id"] if orgs else ""
            
            print(f"  Email: {email} | Org: {org_id}")

            cursor.execute("SELECT id FROM accounts WHERE token = ?", (token,))
            existing_acc = cursor.fetchone()
            if existing_acc:
                acc_id = existing_acc["id"]
                cursor.execute(
                    "UPDATE accounts SET name = ?, email = ?, org_id = ? WHERE id = ?",
                    (name, email, org_id, acc_id)
                )
            else:
                cursor.execute(
                    "INSERT INTO accounts (name, token, email, org_id, created_at) VALUES (?, ?, ?, ?, ?)",
                    (name, token, email, org_id, datetime.now().isoformat())
                )
                acc_id = cursor.lastrowid

            channels = data.get("channels", [])
            print(f"  Canais encontrados ({len(channels)}):")
            for ch in channels:
                ch_id = ch["id"]
                ch_name = ch["name"]
                ch_service = ch.get("service", "tiktok")
                print(f"    -> [{ch_service}] @{ch_name} (ID: {ch_id})")

                cursor.execute("SELECT id FROM profiles WHERE channel_id = ?", (ch_id,))
                existing_prof = cursor.fetchone()
                if not existing_prof:
                    cursor.execute("""
                        INSERT INTO profiles (
                            account_id, channel_id, name, service, default_hashtags,
                            daily_times, is_ai_default, max_buffer_queue, active, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, 1, 10, 1, ?)
                    """, (
                        acc_id, ch_id, ch_name, ch_service, DEFAULT_HASHTAGS,
                        json.dumps(FIVE_DAILY_TIMES), datetime.now().isoformat()
                    ))
                else:
                    cursor.execute("""
                        UPDATE profiles
                        SET daily_times = ?
                        WHERE id = ?
                    """, (json.dumps(FIVE_DAILY_TIMES), existing_prof["id"]))
                total_profiles += 1

        except Exception as e:
            print(f"  ERRO em {name}: {e}")

    conn.commit()
    conn.close()
    print(f"\n==========================================")
    print(f"Finalizado! Total de {total_profiles} canais processados com 5 vídeos/dia.")

if __name__ == "__main__":
    seed_all()
