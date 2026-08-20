@echo off
cls
echo =========================================
echo       INICIANDO BOT DO TELEGRAM
echo =========================================
echo.
echo Use este atalho SO na maquina que hospeda o bot. A credencial do Assyst
echo usada por ele e UNICA pra todo mundo, e o Telegram so aceita UM processo
echo escutando pelo mesmo token de bot ao mesmo tempo — rodar em mais de uma
echo maquina derruba um ao outro (erro de conflito).
echo.
echo Configure o token e a credencial antes, pelo app: menu Opcoes -^> Telegram.
echo.

rem Se a pasta .venv ja existir, pula direto para a inicializacao
if exist ".venv" goto INICIAR_BOT

echo [LOG] Criando ambiente virtual Python 3.11...
py -3.11 -m venv .venv

echo [LOG] Instalando pacotes offline...
.venv\Scripts\python.exe -m pip install --no-index --find-links=pacotes_automacao pandas requests playwright keyring reflex python-telegram-bot

echo [LOG] Configuracao inicial concluida!

:INICIAR_BOT
echo [LOG] Verificando atualizacoes pendentes...
.venv\Scripts\python.exe atualizar.py

echo [LOG] Iniciando bot do Telegram...
.venv\Scripts\python.exe -m bot.main

pause
