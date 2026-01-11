@echo off
REM Script para executar navegacao OAuth com Selenium no Windows
REM Usa o Chrome que ja esta aberto com debug

cd /d %~dp0

REM Verificar se Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo Python nao encontrado. Instalando via pip...
    goto :instalar_python
)

REM Verificar Selenium
python -c "import selenium" >nul 2>&1
if errorlevel 1 (
    echo Instalando Selenium...
    pip install selenium
)

REM Executar script
python oauth_navigator_win.py
pause
goto :eof

:instalar_python
echo Por favor instale Python de https://python.org
pause
