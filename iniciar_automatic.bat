@echo off
title AutomaticApp
cls
echo =========================================
echo       INICIANDO AUTOMATIC
echo =========================================

rem Se a pasta .venv ja existir, pula direto para a inicializacao
if exist ".venv" goto INICIAR_APP

echo [LOG] Criando ambiente virtual Python 3.11...
py -3.11 -m venv .venv

echo [LOG] Instalando pacotes offline...
.venv\Scripts\python.exe -m pip install --no-index --find-links=pacotes_automacao pandas requests playwright keyring reflex python-telegram-bot

echo [LOG] Configuracao inicial concluida!

:INICIAR_APP
echo [LOG] Verificando atualizacoes pendentes...
.venv\Scripts\python.exe atualizar.py

rem O bot do Telegram se liga pela tela do Assistente, aba Agente. O Telegram so
rem aceita UM processo por token: ligue em uma maquina so (erro 409, conflito).

echo [LOG] Ambiente pronto. Iniciando Reflex...
call .venv\Scripts\activate.bat
reflex run

pause