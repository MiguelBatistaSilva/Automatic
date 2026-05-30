@echo off
cd /d %~dp0

:: ─── Verificar Python 3.11 ───────────────────────────────────────────────────
set PYTHON_OK=0

:: Tenta via Python Launcher (py -3.11)
py -3.11 --version >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=py -3.11
    set PYTHON_OK=1
)

:: Tenta via comando python direto (verifica se e 3.11)
if %PYTHON_OK%==0 (
    python --version 2>&1 | findstr /C:"Python 3.11" >nul
    if %errorlevel%==0 (
        set PYTHON_CMD=python
        set PYTHON_OK=1
    )
)

if %PYTHON_OK%==0 (
    echo.
    echo  [ERRO] Python 3.11 nao encontrado nesta maquina.
    echo.
    echo  Para instalar, execute o arquivo:
    echo    Instalar_Python\python-3.11.9-amd64.exe
    echo.
    echo  Marque a opcao "Add Python to PATH" durante a instalacao.
    echo  Depois feche esta janela e execute novamente.
    echo.
    pause
    exit /b 1
)

:: ─── Criar ambiente e instalar pacotes ───────────────────────────────────────
if not exist .venv (
    echo.
    echo  [INFO] Criando ambiente virtual...
    %PYTHON_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo  [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )

    echo  [INFO] Instalando pacotes...
    .venv\Scripts\python -m pip install --no-index --find-links=pacotes_automacao pandas selenium PyQt6 pywin32 requests
    if %errorlevel% neq 0 (
        echo  [ERRO] Falha ao instalar os pacotes.
        echo  Verifique se a pasta pacotes_automacao esta presente e completa.
        pause
        exit /b 1
    )

    echo  [INFO] Criando atalho na area de trabalho...
    .venv\Scripts\python gerar_atalho.py

    echo  [INFO] Configuracao concluida com sucesso!
)

:: ─── Iniciar aplicacao ────────────────────────────────────────────────────────
.venv\Scripts\pythonw.exe main.py
