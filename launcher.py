import os
import sys
import webbrowser
import threading
import time
import uvicorn

# Garante o diretório correto de trabalho
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

os.chdir(base_dir)
sys.path.insert(0, base_dir)

def open_browser():
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    print("=" * 60)
    print("   INICIANDO TIKTOK BUFFER AUTOMATOR PRO (6 CONTAS)")
    print("=" * 60)
    print("Abrindo navegador em http://127.0.0.1:8000 ...")
    print("Mantenha esta janela aberta enquanto quiser que o robo sincronize!")
    print("=" * 60)
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("main:app", host="127.0.0.1", port=8000, log_level="warning")
