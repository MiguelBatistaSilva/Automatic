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

rem O bot do Telegram NAO sobe daqui: ele usa uma credencial UNICA pra todo
rem mundo, e o Telegram so aceita UM processo escutando por token — se cada
rem pessoa que baixar este .bat tambem subisse o bot, eles brigariam entre si
rem (erro 409, conflito). Quem hospeda o bot usa iniciar_bot.bat, so naquela
rem maquina.

echo [LOG] Ambiente pronto. Iniciando Reflex...
call .venv\Scripts\activate.bat
reflex run

pause