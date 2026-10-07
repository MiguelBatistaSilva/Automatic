@echo off
title Atualizar Automatic
cd /d "%~dp0"
cls
echo =========================================
echo       ATUALIZAR AUTOMATIC
echo =========================================
echo.
echo  ANTES DE CONTINUAR: feche a janela do Automatic
echo  (a janela preta "AutomaticApp") e o navegador dele.
echo.
pause

rem Sem a .venv o app nunca foi aberto nesta maquina: o iniciar_automatic.bat
rem cria o ambiente na primeira vez, e ja vem com a versao mais nova.
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [ERRO] Ambiente nao encontrado. Abra o iniciar_automatic.bat uma vez primeiro.
    echo.
    pause
    exit /b 1
)

echo.
.venv\Scripts\python.exe atualizar.py --baixar
if errorlevel 1 (
    echo.
    echo [ERRO] A atualizacao NAO foi concluida. Veja as mensagens acima.
    echo        Se precisar, mande um print desta janela para o suporte.
) else (
    echo.
    echo [OK] Concluido. Pode abrir o Automatic pelo iniciar_automatic.bat.
)
echo.
pause
