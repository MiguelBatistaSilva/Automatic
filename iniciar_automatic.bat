@echo off
cd /d %~dp0

if not exist .venv (
    echo [INFO] Criando ambiente...
    python -m venv .venv
    echo [INFO] Instalando pacotes OFFLINE...
    .venv\Scripts\python -m pip install --no-index --find-links=pacotes_automacao pandas selenium PyQt6
)

echo [INFO] Iniciando Automatic...
.venv\Scripts\python main.py
pause