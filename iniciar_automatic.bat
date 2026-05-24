@echo off
cd /d %~dp0

if not exist .venv (
    echo [INFO] Criando ambiente...
    python -m venv .venv
    echo [INFO] Instalando pacotes OFFLINE...
    .venv\Scripts\python -m pip install --no-index --find-links=pacotes_automacao pandas selenium PyQt6 pywin32 requests
    echo [INFO] Criando atalho na area de trabalho...
    .venv\Scripts\python gerar_atalho.py
)

.venv\Scripts\pythonw.exe main.py