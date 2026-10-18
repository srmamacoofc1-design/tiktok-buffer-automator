import os
import sys
import sqlite3
import subprocess
import time

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "app.db")
RELEASE_TAG = "v1.0.0"
REPO = "srmamacoofc1-design/tiktok-buffer-automator"
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Reset any previous incorrect github url
    cursor.execute("""
        UPDATE video_stock
        SET public_url = NULL
        WHERE public_url LIKE '%c1_vid2_12%' OR public_url LIKE '%c1_vid3_13%'
    """)
    conn.commit()

    cursor.execute("""
        SELECT id, profile_id, filename, local_path, title
        FROM video_stock
        WHERE status = 'estoque' AND (public_url IS NULL OR public_url = '' OR public_url LIKE '%127.0.0.1%')
        ORDER BY id ASC
    """)
    videos = cursor.fetchall()
    total = len(videos)

    print(f"==================================================")
    print(f"INICIANDO UPLOAD AUTOMÁTICO DE {total} VÍDEOS PARA A NUVEM")
    print(f"==================================================")
    sys.stdout.flush()

    uploaded = 0
    errors = 0

    for idx, (vid_id, profile_id, filename, local_path, title) in enumerate(videos):
        if not os.path.exists(local_path):
            print(f"[{idx+1}/{total}] Arquivo não encontrado no disco: {local_path}")
            sys.stdout.flush()
            errors += 1
            continue

        asset_name = f"c{profile_id}_vid{vid_id}.mp4"
        staging_path = os.path.join(UPLOADS_DIR, asset_name)

        if os.path.exists(staging_path):
            try:
                os.remove(staging_path)
            except Exception:
                pass

        try:
            os.link(local_path, staging_path)
        except Exception:
            import shutil
            shutil.copyfile(local_path, staging_path)

        size_mb = os.path.getsize(staging_path) / (1024 * 1024)
        print(f"[{idx+1}/{total}] Enviando {asset_name} ({size_mb:.1f} MB) - Perfil #{profile_id} - '{title[:30]}...'")
        sys.stdout.flush()

        cmd = ["gh", "release", "upload", RELEASE_TAG, staging_path, "--clobber"]
        t0 = time.time()
        res = subprocess.run(cmd, capture_output=True, text=True)

        # Remove arquivo temporario de staging
        try:
            os.remove(staging_path)
        except Exception:
            pass

        if res.returncode == 0:
            elapsed = time.time() - t0
            public_url = f"https://github.com/{REPO}/releases/download/{RELEASE_TAG}/{asset_name}"
            cursor.execute("UPDATE video_stock SET public_url = ? WHERE id = ?", (public_url, vid_id))
            conn.commit()
            uploaded += 1
            print(f"  ✓ [{idx+1}/{total}] Sucesso em {elapsed:.1f}s! Link permanente: {public_url}")
            sys.stdout.flush()
        else:
            print(f"  ✗ Erro ao enviar {asset_name}: {res.stderr.strip()}")
            sys.stdout.flush()
            errors += 1

    conn.close()
    print(f"\n==================================================")
    print(f"UPLOAD FINALIZADO! {uploaded} vídeos hospedados na nuvem. Erros: {errors}")
    print(f"==================================================")
    sys.stdout.flush()

if __name__ == "__main__":
    main()
