import json
from datetime import datetime
from database import init_db, get_db
from buffer_client import BufferClient

INITIAL_TOKENS = [
    ("Conta 1 (sr.mamacoofc1)", "slFjxQI6JuTFE_PiSPR-DTH1uEjbHaq5MneSawdqobT"),
    ("Conta 2 (erickkaruan135)", "BZHxzVg6yB_ZPyTu3_g1IY0nRIKCAVzrcwSyPtiyaJP"),
    ("Conta 3 (tentavutahshsv)", "3-cBTDdx7lwKfMqxK_L3s4IHdm2yjyePUigXcKmOM8E"),
]

DEFAULT_HASHTAGS = "#fyp #foryou #viral #tiktok #curiosidades #historias #trending"
DEFAULT_TIMES = ["10:30", "14:30", "18:30"]

def seed():
    init_db()
    conn = get_db()
    cursor = conn.cursor()
    
    for acc_name, token in INITIAL_TOKENS:
        token = token.strip()
        print(f"Cadastrando/Atualizando token: {acc_name}...")
        try:
            client = BufferClient(token)
            data = client.get_account_and_channels()
            account = data.get("account", {})
            email = account.get("email") or acc_name
            orgs = account.get("organizations", [])
            org_id = orgs[0]["id"] if orgs else ""
            
            # Insere ou atualiza conta
            cursor.execute("SELECT id FROM accounts WHERE token = ?", (token,))
            existing_acc = cursor.fetchone()
            if existing_acc:
                acc_id = existing_acc["id"]
                cursor.execute(
                    "UPDATE accounts SET name = ?, email = ?, org_id = ? WHERE id = ?",
                    (acc_name, email, org_id, acc_id)
                )
            else:
                cursor.execute(
                    "INSERT INTO accounts (name, token, email, org_id, created_at) VALUES (?, ?, ?, ?, ?)",
                    (acc_name, token, email, org_id, datetime.now().isoformat())
                )
                acc_id = cursor.lastrowid
            
            # Insere canais
            channels = data.get("channels", [])
            for ch in channels:
                ch_id = ch["id"]
                ch_name = ch["name"]
                ch_service = ch.get("service", "tiktok")
                
                cursor.execute("SELECT id FROM profiles WHERE channel_id = ?", (ch_id,))
                existing_prof = cursor.fetchone()
                if not existing_prof:
                    cursor.execute("""
                        INSERT INTO profiles (
                            account_id, channel_id, name, service, default_hashtags,
                            daily_times, is_ai_default, max_buffer_queue, active, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        acc_id, ch_id, ch_name, ch_service, DEFAULT_HASHTAGS,
                        json.dumps(DEFAULT_TIMES), 1, 10, 1, datetime.now().isoformat()
                    ))
                    print(f"  + Perfil inserido: @{ch_name} ({ch_service})")
                else:
                    print(f"  * Perfil já cadastrado: @{ch_name}")
                    
        except Exception as e:
            print(f"Erro ao processar {acc_name}: {e}")
            
    conn.commit()
    conn.close()
    print("Seed concluído com sucesso!")

if __name__ == "__main__":
    seed()
