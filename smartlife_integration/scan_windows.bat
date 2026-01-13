@echo off
REM Script para escanear dispositivos Tuya no Windows
REM Execute este script diretamente no Windows (não no WSL)

echo ============================================================
echo    Tuya Device Scanner - Windows
echo ============================================================
echo.

REM Verificar se Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale Python primeiro.
    pause
    exit /b 1
)

REM Instalar tinytuya se necessário
echo Verificando tinytuya...
pip install tinytuya --quiet

echo.
echo Escaneando dispositivos na rede local...
echo (Aguarde ate 30 segundos)
echo.

python -c "import tinytuya; devices = tinytuya.deviceScan(verbose=True); print(); print('Dispositivos:', devices)"

echo.
echo ============================================================
echo Scan finalizado!
pause
