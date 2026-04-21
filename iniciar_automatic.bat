@echo off
title CATI Automacao - Loader
cd /d %~dp0

:: 1. Verifica se o Python existe
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Python nao instalado ou nao configurado no PATH.
    pause
    exit /b
)

:: 2. Gerencia o Ambiente Virtual
if not exist .venv (
    echo [INFO] Criando ambiente virtual pela primeira vez...
    python -m venv .venv
    echo [INFO] Instalando dependencias (isso pode demorar um pouco)...
    .venv\Scripts\pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org --upgrade pip
    .venv\Scripts\pip install -r requirements.txt
)

:: 3. Inicia a Aplicacao
echo [INFO] Iniciando Automatic v6.0...
.venv\Scripts\python main.py

:: 4. Mantem a janela aberta se houver erro
if %errorlevel% neq 0 (
    echo.
    echo [!] O programa encerrou de forma inesperada.
    pause
)