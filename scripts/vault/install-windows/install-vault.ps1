# Homelab Vault — Instalador Windows
# Requer: Windows 10+, PowerShell 5+
# Execute como Administrador

#Requires -RunAsAdministrator

param(
    [string]$PythonVersion = "3.12.0",
    [int]   $Port = 8765
)

$ErrorActionPreference = "Stop"
$InstallDir  = "$env:LOCALAPPDATA\HomelabVault"
$MonitorDir  = "$InstallDir\scripts"
$TaskName    = "HomelabVaultMonitor"
$ShortcutDst = "$env:USERPROFILE\Desktop\Homelab Vault.lnk"

function Write-Step($n, $msg) {
    Write-Host ""
    Write-Host "[$n] $msg" -ForegroundColor Cyan
}

function Write-OK($msg)   { Write-Host "    OK: $msg"   -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    AVISO: $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "    ERRO: $msg"  -ForegroundColor Red }

# ── Banner ────────────────────────────────────────────────────────────────────
Clear-Host
Write-Host ""
Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "  ║       HOMELAB VAULT — INSTALADOR     ║" -ForegroundColor Magenta
Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""
Write-Host "  Este instalador configura:" -ForegroundColor Gray
Write-Host "    • Python 3 (se ausente)" -ForegroundColor Gray
Write-Host "    • Monitor de USB em background" -ForegroundColor Gray
Write-Host "    • Atalho na área de trabalho" -ForegroundColor Gray
Write-Host "    • Autostart ao login" -ForegroundColor Gray
Write-Host ""
Write-Host "  Pré-requisito manual: LibreCrypt para abrir a partição LUKS" -ForegroundColor Yellow
Write-Host "  Download: https://github.com/t-d-k/LibreCrypt/releases" -ForegroundColor Yellow
Write-Host ""
Read-Host "  Pressione Enter para continuar ou Ctrl+C para cancelar"

# ── 1. Python ─────────────────────────────────────────────────────────────────
Write-Step "1/5" "Verificando Python..."

$pythonCmd = $null
foreach ($candidate in @("python", "python3", "py")) {
    try {
        $ver = & $candidate --version 2>&1
        if ($ver -match "Python 3\.") {
            $pythonCmd = $candidate
            Write-OK "$ver encontrado ($candidate)"
            break
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Warn "Python 3 não encontrado. Instalando via winget..."
    try {
        winget install --id Python.Python.3.12 --silent --accept-package-agreements `
              --accept-source-agreements
        $env:PATH += ";$env:LOCALAPPDATA\Programs\Python\Python312"
        $pythonCmd = "python"
        Write-OK "Python instalado"
    } catch {
        Write-Fail "Não foi possível instalar automaticamente."
        Write-Host ""
        Write-Host "  Instale manualmente: https://python.org/downloads" -ForegroundColor Yellow
        Write-Host "  Marque 'Add Python to PATH' e rode este instalador novamente." -ForegroundColor Yellow
        Read-Host "  Enter para sair"
        exit 1
    }
}

# ── 2. LibreCrypt check ───────────────────────────────────────────────────────
Write-Step "2/5" "Verificando LibreCrypt..."

$lcPath = @(
    "C:\Program Files\LibreCrypt\LibreCrypt.exe",
    "C:\Program Files (x86)\LibreCrypt\LibreCrypt.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($lcPath) {
    Write-OK "LibreCrypt encontrado em $lcPath"
} else {
    Write-Warn "LibreCrypt não encontrado."
    Write-Host ""
    Write-Host "  Para abrir a partição LUKS no Windows, instale o LibreCrypt:" -ForegroundColor Yellow
    Write-Host "  https://github.com/t-d-k/LibreCrypt/releases" -ForegroundColor Yellow
    Write-Host ""
    $ans = Read-Host "  Abrir página de download agora? [s/N]"
    if ($ans -eq "s" -or $ans -eq "S") {
        Start-Process "https://github.com/t-d-k/LibreCrypt/releases"
    }
    Write-Host ""
    Write-Host "  Continuando instalação sem LibreCrypt..." -ForegroundColor Gray
}

# ── 3. Instalar scripts ───────────────────────────────────────────────────────
Write-Step "3/5" "Instalando scripts em $InstallDir..."

$null = New-Item -ItemType Directory -Force -Path $MonitorDir

# Copiar monitor e scripts do pendrive (se disponível) ou do diretório atual
$scriptSrc = $PSScriptRoot
$monitor   = "$scriptSrc\vault-monitor.ps1"

if (-not (Test-Path $monitor)) {
    Write-Fail "vault-monitor.ps1 não encontrado em $scriptSrc"
    exit 1
}

Copy-Item $monitor "$MonitorDir\vault-monitor.ps1" -Force
Write-OK "vault-monitor.ps1 instalado"

# Script de atalho manual (abre browser se servidor já rodando)
$launcherScript = @"
`$running = `$false
try {
    `$r = Invoke-WebRequest -Uri 'http://localhost:$Port/api/status' -UseBasicParsing -TimeoutSec 2
    `$running = `$r.StatusCode -eq 200
} catch {}

if (`$running) {
    Start-Process 'http://localhost:$Port'
} else {
    `$drive = Get-WmiObject Win32_LogicalDisk | Where-Object { `$_.VolumeName -eq 'VAULT-START' }
    if (-not `$drive) {
        [System.Windows.Forms.MessageBox]::Show(
            'Insira o pendrive Homelab Vault e abra a particao LUKS com LibreCrypt.',
            'Homelab Vault', 'OK', 'Information')
    } else {
        [System.Windows.Forms.MessageBox]::Show(
            'Pendrive detectado. Abra a particao LUKS com LibreCrypt e aguarde.',
            'Homelab Vault', 'OK', 'Information')
    }
}
"@
$launcherScript | Out-File "$InstallDir\open-vault.ps1" -Encoding utf8
Write-OK "Launcher instalado"

# ── 4. Scheduled Task (monitor + autostart) ───────────────────────────────────
Write-Step "4/5" "Criando Scheduled Task '$TaskName'..."

# Remover task anterior se existir
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action  = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-WindowStyle Hidden -NonInteractive -ExecutionPolicy Bypass -File `"$MonitorDir\vault-monitor.ps1`" -Port $Port -PythonExe `"$pythonCmd`""

# Dispara ao fazer login
$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Homelab Vault — monitora pendrive e inicia servidor UI" | Out-Null

Write-OK "Scheduled Task criada (inicia automaticamente ao login)"

# ── 5. Atalho na área de trabalho ─────────────────────────────────────────────
Write-Step "5/5" "Criando atalho na área de trabalho..."

$wsh   = New-Object -ComObject WScript.Shell
$short = $wsh.CreateShortcut($ShortcutDst)
$short.TargetPath       = "powershell.exe"
$short.Arguments        = "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$InstallDir\open-vault.ps1`""
$short.WorkingDirectory = $InstallDir
$short.Description      = "Homelab Vault — painel de backup e KuCoin"
# Ícone de cadeado do shell32
$short.IconLocation     = "shell32.dll,47"
$short.Save()
Write-OK "Atalho criado: $ShortcutDst"

# ── Iniciar monitor agora ─────────────────────────────────────────────────────
$ans = Read-Host "`n  Iniciar o monitor agora? [S/n]"
if ($ans -ne "n" -and $ans -ne "N") {
    Start-ScheduledTask -TaskName $TaskName
    Write-OK "Monitor iniciado em background"
}

# ── Resumo ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║           INSTALAÇÃO CONCLUÍDA               ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Como usar:" -ForegroundColor White
Write-Host "    1. Insira o pendrive Kingston" -ForegroundColor Gray
Write-Host "    2. Abra a particao LUKS com LibreCrypt (senha do vault)" -ForegroundColor Gray
Write-Host "    3. O navegador abre automaticamente em http://localhost:$Port" -ForegroundColor Gray
Write-Host "    4. Login: admin / admin" -ForegroundColor Gray
Write-Host ""
Write-Host "  Atalho criado: 'Homelab Vault' na area de trabalho" -ForegroundColor Gray
Write-Host "  Log do monitor: $InstallDir\monitor.log" -ForegroundColor Gray
Write-Host ""
Write-Host "  Para desinstalar:" -ForegroundColor Gray
Write-Host "    Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor DarkGray
Write-Host ""
Read-Host "  Enter para fechar"
