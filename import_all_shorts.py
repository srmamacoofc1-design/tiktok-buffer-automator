import os
import re
import sys
import json
import sqlite3
import requests
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding='utf-8')

BASE_SHORTS = r'C:\Users\leurickkkk77\Downloads\Shorts_210_EDITADOS'
SEO_FILE = os.path.join(BASE_SHORTS, 'TODOS_OS_TITULOS_E_SEO_209_VIDEOS.txt')
DB_PATH = r'C:\Users\leurickkkk77\.gemini\antigravity\scratch\tiktok-buffer-automator\data\app.db'

# Mapeamento Conta (pasta) -> ID do Perfil no Banco
# Conta 1 -> @leurickshop (ID 1)
# Conta 2 -> @erickmania5 (ID 3)
# Conta 3 -> @leurick_o_meno (ID 2)
# Conta 4 -> @leurick.k1 (ID 4)
# Conta 5 -> @a.bia69 (ID 5)
# Conta 6 -> @dicas.dejair (ID 6)
CONTA_TO_PROFILE_ID = {
    1: 1, # @leurickshop
    2: 3, # @erickmania5
    3: 2, # @leurick_o_meno
    4: 4, # @leurick.k1
    5: 5, # @a.bia69
    6: 6, # @dicas.dejair
}

def parse_seo_file():
    with open(SEO_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()

    entries = re.split(r'-{40,}', text)
    parsed = {}
    for entry in entries:
        header_m = re.search(r'\[Conta\s+(\d+)\]\s+V[ÍI]DEO\s+(\d+)\s+-\s+(.*?\.mp4)', entry, re.IGNORECASE)
        if header_m:
            conta = int(header_m.group(1))
            v_num = int(header_m.group(2))
            fname = header_m.group(3).strip()
            
            title_m = re.search(r'T[íi]tulo:\s*(.*?)\n', entry)
            title = title_m.group(1).strip() if title_m else fname
            
            legenda_m = re.search(r'Legenda:\s*\n(.*?)(?=\Z|# ===)', entry, re.DOTALL)
            legenda = legenda_m.group(1).strip() if legenda_m else title
            
            # Limpa legenda se terminar com marcadores
            parsed[(conta, v_num)] = {
                'filename': fname,
                'title': title,
                'caption': legenda
            }
    return parsed

def match_seo(conta: int, filename: str, seo_data: dict):
    # Tenta casar pelo número inicial do arquivo (ex: "11 - ...")
    num_m = re.match(r'^(\d+)\s*-\s*', filename)
    if num_m:
        v_num = int(num_m.group(1))
        if (conta, v_num) in seo_data:
            return seo_data[(conta, v_num)]

    # Fallback: procura por palavras-chave do nome do arquivo
    clean_f = re.sub(r'^\d+\s*-\s*', '', filename).replace('.mp4', '').strip().lower()
    for (c, v_num), item in seo_data.items():
        if c == conta:
            if clean_f in item['filename'].lower() or item['filename'].lower() in clean_f:
                return item

    # Se não encontrar no SEO, gera título limpo
    clean_title = os.path.splitext(filename)[0]
    clean_title = re.sub(r'^\d+\s*-\s*', '', clean_title).strip()
    return {
        'filename': filename,
        'title': clean_title.upper() + "! 😱🔥",
        'caption': f"{clean_title.upper()}! 😱🔥\n\n#roblox #historiasroblox #pov #curiosidades #jogos #robloxbrasil #viral #fyp #foryou"
    }

def import_stock():
    print("=== 1. Carregando dados de SEO e Títulos ===")
    seo_data = parse_seo_file()
    print(f"Total de títulos carregados: {len(seo_data)}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    total_added = 0

    for conta_num in range(1, 7):
        profile_id = CONTA_TO_PROFILE_ID[conta_num]
        folder_path = os.path.join(BASE_SHORTS, f"Conta {conta_num}")
        
        cursor.execute("SELECT name FROM profiles WHERE id = ?", (profile_id,))
        prof_row = cursor.fetchone()
        prof_name = prof_row[0] if prof_row else f"Perfil {profile_id}"

        print(f"\n--- Processando Conta {conta_num} -> @{prof_name} ---")

        if not os.path.exists(folder_path):
            print(f"Aviso: pasta {folder_path} não encontrada.")
            continue

        # Lista apenas os arquivos na pasta principal (ignora subpasta postados)
        files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith('.mp4')])
        print(f"Vídeos encontrados para abastecer: {len(files)}")

        for filename in files:
            full_path = os.path.join(folder_path, filename)
            seo = match_seo(conta_num, filename, seo_data)

            # Verifica se já foi inserido no estoque
            cursor.execute(
                "SELECT id FROM video_stock WHERE profile_id = ? AND filename = ?",
                (profile_id, filename)
            )
            existing = cursor.fetchone()

            if not existing:
                cursor.execute("""
                    INSERT INTO video_stock (
                        profile_id, filename, title, caption, local_path, is_ai, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, 1, 'estoque', ?)
                """, (
                    profile_id, filename, seo['title'], seo['caption'],
                    full_path, datetime.now().isoformat()
                ))
                total_added += 1

    conn.commit()
    conn.close()
    print(f"\n==========================================")
    print(f"ESTOQUE ABASTECIDO COM SUCESSO! Total de novos vídeos no estoque: {total_added}")

if __name__ == '__main__':
    import_stock()
