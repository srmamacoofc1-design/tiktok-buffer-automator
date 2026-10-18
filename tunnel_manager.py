import os
import re
import time
import subprocess
import threading
import logging
from urllib.parse import quote

CLOUDFLARED_EXE = os.path.join(os.path.dirname(__file__), "cloudflared.exe")

class CloudflareTunnel:
    _instance = None
    _proc = None
    _url = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = CloudflareTunnel()
            return cls._instance

    def __init__(self):
        self.url = None
        self.running = False
        self.thread = None

    def start(self, port: int = 8000):
        if self.running and self.url:
            return self.url

        if not os.path.exists(CLOUDFLARED_EXE):
            logging.error(f"cloudflared.exe não encontrado em {CLOUDFLARED_EXE}")
            return None

        cmd = [CLOUDFLARED_EXE, "tunnel", "--url", f"http://127.0.0.1:{port}"]
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        self.running = True

        # Lê a saída até achar a URL do túnel
        start_time = time.time()
        while time.time() - start_time < 20:
            line = self._proc.stderr.readline()
            if "trycloudflare.com" in line:
                m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if m:
                    self.url = m.group(0)
                    logging.info(f"Túnel Cloudflare ativo: {self.url}")
                    break

        # Inicia thread para drenar stderr e evitar travamento
        def drain_stderr():
            while self.running and self._proc:
                try:
                    if not self._proc.stderr.readline():
                        break
                except Exception:
                    break
        self.thread = threading.Thread(target=drain_stderr, daemon=True)
        self.thread.start()

        return self.url

    def get_public_url_for_file(self, local_path: str) -> str:
        tunnel_url = self.start()
        if not tunnel_url:
            raise Exception("Não foi possível iniciar o túnel Cloudflare.")

        # Caminho relativo a partir de Shorts_210_EDITADOS
        base_shorts = r"C:\Users\leurickkkk77\Downloads\Shorts_210_EDITADOS"
        rel_path = os.path.relpath(local_path, base_shorts)
        
        # Converte para URL path com quote
        parts = rel_path.replace("\\", "/").split("/")
        quoted_parts = [quote(p) for p in parts]
        url_path = "/".join(quoted_parts)
        
        return f"{tunnel_url}/shorts/{url_path}"

    def stop(self):
        self.running = False
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None
        self.url = None
