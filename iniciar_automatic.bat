@echo off
cls
echo =========================================
echo       INICIANDO AUTOMATIC
echo =========================================

rem Se a pasta .venv ja existir, pula direto para a inicializacao
if exist ".venv" goto INICIAR_APP

echo [LOG] Criando ambiente virtual Python 3.11...
py -3.11 -m venv .venv

echo [LOG] Instalando pacotes offline...
.venv\Scripts\python.exe -m pip install --no-index --find-links=pacotes_automacao pandas requests playwright keyring reflex

echo [LOG] Configuracao inicial concluida!

:INICIAR_APP
echo [LOG] Ambiente pronto. Iniciando Reflex...
call .venv\Scripts\activate.bat
reflex run

pause