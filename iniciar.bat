@echo off
title TikTok Buffer Automator Pro
echo ======================================================
echo    INICIANDO TIKTOK BUFFER AUTOMATOR PRO
echo ======================================================
echo.
cd /d "%~dp0"

echo [1/2] Verificando dependencias...
python -m pip install fastapi uvicorn requests python-multipart >nul 2>&1

echo [2/2] Iniciando servidor e abrindo painel no navegador...
start http://localhost:8000
python main.py

pause
