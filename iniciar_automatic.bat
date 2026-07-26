@echo off
cd /d %~dp0
title Automatic - servidor (nao feche esta janela)

REM ===========================================================================
REM  Automatic - inicializacao unica.
REM
REM  Este arquivo e o UNICO ponto de entrada do app: prepara o ambiente na
REM  primeira execucao e sobe o servidor Reflex nas seguintes. A interface abre
REM  no navegador (http://localhost:3000); o app em si roda nesta janela, entao
REM  fechar esta janela ENCERRA o Automatic.
REM
REM  Substitui o instalador.py (janela tkinter), o gerar_atalho.py e o
REM  iniciar_automatic.vbs, todos removidos junto com o PyQt6.
REM ===========================================================================

REM --- 1) Python 3.11 --------------------------------------------------------
REM  ATENCAO: dentro de parenteses, %errorlevel% e substituido quando o cmd LE o
REM  bloco, nao quando a linha roda — por isso o teste e "if errorlevel", que le
REM  o valor na hora. Com %errorlevel% aqui dentro, o .bat podia aceitar um
REM  python de outra versao e criar o venv errado.
set PYTHON_CMD=

py -3.11 --version >nul 2>&1
if not errorlevel 1 set PYTHON_CMD=py -3.11

if not defined PYTHON_CMD (
    python --version 2>&1 | findstr /C:"Python 3.11" >nul
    if not errorlevel 1 set PYTHON_CMD=python
)

if not defined PYTHON_CMD (
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

REM --- 2) Ambiente virtual ---------------------------------------------------
REM  Criado com o Python 3.11 identificado acima — o venv herda essa versao.
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  Criando ambiente virtual com: %PYTHON_CMD%
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo  [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )
)

REM  Confere a versao do venv: uma .venv antiga (de outra versao do Python) passa
REM  pelo teste acima, mas nao serve para os wheels cp311 de pacotes_automacao.
".venv\Scripts\python.exe" --version 2>&1 | findstr /C:"Python 3.11" >nul
if errorlevel 1 (
    echo.
    echo  [ERRO] A pasta .venv existente nao e Python 3.11.
    ".venv\Scripts\python.exe" --version
    echo.
    echo  Apague a pasta .venv e execute este arquivo novamente.
    echo.
    pause
    exit /b 1
)

REM --- 3) Dependencias -------------------------------------------------------
REM  Os cinco pacotes que o codigo importa de fato; o pip resolve as transitivas.
REM    pandas     -> planilha do Desmembramento (CSV -> DataFrame)
REM    requests   -> checagem de atualizacao
REM    playwright -> automacao do Chrome (usa o Chrome instalado)
REM    keyring    -> senha no Cofre de Credenciais do Windows
REM    reflex     -> a interface (roda no navegador)
REM  Mesma lista usada para gerar a pasta pacotes_automacao:
REM    py -3.11 -m pip download %PACOTES% -d pacotes_automacao
set PACOTES=pandas requests playwright keyring reflex

REM  A presenca do reflex.exe e o sinal de "ja instalado". Os wheels locais de
REM  pacotes_automacao sao usados quando existem; o que faltar vem da internet.
if not exist ".venv\Scripts\reflex.exe" (
    echo.
    echo  Instalando dependencias da automacao. Isso leva alguns minutos
    echo  e so acontece na primeira execucao...
    echo.
    ".venv\Scripts\python.exe" -m pip install %PACOTES% --find-links=pacotes_automacao
    if errorlevel 1 (
        echo.
        echo  [ERRO] Falha ao instalar as dependencias.
        echo         Verifique a conexao e a pasta pacotes_automacao.
        pause
        exit /b 1
    )
)

REM --- 4) Abrir a interface no navegador -------------------------------------
REM  Espera o servidor subir antes de abrir a pagina. Se abrir cedo demais,
REM  basta atualizar (F5) - o endereco e sempre o mesmo.
start "" ".venv\Scripts\pythonw.exe" -c "import time, webbrowser; time.sleep(12); webbrowser.open('http://localhost:3000')"

REM --- 5) Subir o servidor ---------------------------------------------------
echo.
echo  ======================================================================
echo   Automatic iniciando... a interface abre em http://localhost:3000
echo   NAO FECHE esta janela enquanto estiver usando o app.
echo  ======================================================================
echo.
".venv\Scripts\reflex.exe" run

REM Se o reflex cair, mantem a janela aberta para o erro ficar visivel.
echo.
echo  O servidor foi encerrado.
pause
