@echo off
:: Homelab Vault — Windows Launcher
:: Inicia o servidor Python e abre o painel no navegador
title Homelab Vault

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERRO] Python nao encontrado.
    echo  Instale em: https://python.org/downloads
    echo  Marque "Add Python to PATH" durante a instalacao.
    echo.
    echo  ATENCAO: o vault usa LUKS (criptografia Linux nativa).
    echo  Para abrir no Windows, instale LibreCrypt:
    echo  https://github.com/t-d-k/LibreCrypt
    echo.
    pause
    exit /b 1
)

:: Detectar drive do pendrive (onde este .bat esta rodando)
set VAULT_DRIVE=%~d0
set VAULT_SERVER=%VAULT_DRIVE%\vault-server.py
set VAULT_UI=%VAULT_DRIVE%\ui\index.html

:: Verificar se servidor ja esta rodando
curl -s http://localhost:8765/api/status >nul 2>&1
if not errorlevel 1 (
    echo  Servidor ja rodando — abrindo navegador...
    start http://localhost:8765
    exit /b 0
)

:: Iniciar servidor em background
echo  Iniciando servidor Homelab Vault...
set VAULT_MOUNT=%VAULT_DRIVE%\
start /min python "%VAULT_SERVER%" --windows

:: Aguardar servidor subir (max 10s)
set /a tries=0
:wait_loop
timeout /t 1 /nobreak >nul
curl -s http://localhost:8765/api/status >nul 2>&1
if not errorlevel 1 goto :open
set /a tries+=1
if %tries% lss 10 goto :wait_loop

echo  [AVISO] Servidor demorou para iniciar. Tentando abrir mesmo assim...

:open
echo  Abrindo painel...
start http://localhost:8765
echo.
echo  Vault UI rodando em http://localhost:8765
echo  Feche esta janela para encerrar o servidor.
pause
taskkill /f /im python.exe /fi "WINDOWTITLE eq Homelab Vault*" >nul 2>&1
