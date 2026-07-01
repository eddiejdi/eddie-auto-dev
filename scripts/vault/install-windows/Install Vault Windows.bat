@echo off
:: Homelab Vault — Instalador Windows
:: Eleva para Administrador automaticamente e executa o PowerShell installer
title Homelab Vault — Instalador

:: Verificar se ja e Administrador
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  Elevando privilegios de administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Verificar PowerShell
powershell -Command "exit 0" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERRO: PowerShell nao encontrado.
    echo  Instale o PowerShell: https://aka.ms/powershell
    pause
    exit /b 1
)

:: Definir politica de execucao e rodar o installer
echo.
echo  Iniciando instalador Homelab Vault...
echo.

powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0install-vault.ps1"

if errorlevel 1 (
    echo.
    echo  Instalacao encerrada com erro. Verifique as mensagens acima.
    pause
)
