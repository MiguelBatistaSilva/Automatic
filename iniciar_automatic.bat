@echo off
cd /d %~dp0

:: ─── Verificar Python 3.11 ───────────────────────────────────────────────────
set PYTHON_OK=0

py -3.11 --version >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=py -3.11
    set PYTHON_OK=1
)

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

:: ─── Primeira execucao: criar venv e abrir janela de instalacao ──────────────
if not exist .venv (
    echo Criando ambiente virtual...
    %PYTHON_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )

    start /wait "" ".venv\Scripts\pythonw.exe" instalador.py
    if %errorlevel% neq 0 (
        echo [ERRO] A instalacao dos pacotes falhou. Verifique a janela de instalacao.
        pause
        exit /b 1
    )
)

:: ─── Iniciar aplicacao ────────────────────────────────────────────────────────
start "" ".venv\Scripts\pythonw.exe" main.py
