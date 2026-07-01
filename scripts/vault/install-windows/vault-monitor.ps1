# Homelab Vault Monitor — roda em background no Windows
# Detecta o pendrive Kingston (VAULT-START) e inicia o servidor + abre o navegador
# Instalado como Scheduled Task via install-vault.ps1

param(
    [string]$PythonExe = "python",
    [string]$VaultBootLabel = "VAULT-START",
    [int]   $Port = 8765,
    [int]   $PollSec = 5
)

$LogFile  = "$env:LOCALAPPDATA\HomelabVault\monitor.log"
$PidFile  = "$env:LOCALAPPDATA\HomelabVault\server.pid"
$null     = New-Item -ItemType Directory -Force -Path (Split-Path $LogFile)

function Write-Log($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    "[$ts] $msg" | Tee-Object -FilePath $LogFile -Append | Out-Null
}

function Get-VaultDrive {
    Get-WmiObject Win32_LogicalDisk |
        Where-Object { $_.VolumeName -eq $VaultBootLabel } |
        Select-Object -First 1 -ExpandProperty DeviceID
}

function Get-LibreCryptDrive {
    # Tenta detectar drive montado pelo LibreCrypt (volume label "homelab-vault")
    Get-WmiObject Win32_LogicalDisk |
        Where-Object { $_.VolumeName -like "*vault*" -and $_.DeviceID -ne (Get-VaultDrive) } |
        Select-Object -First 1 -ExpandProperty DeviceID
}

function Test-ServerRunning {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:$Port/api/status" `
                               -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        return $r.StatusCode -eq 200
    } catch { return $false }
}

function Start-VaultServer($vaultDrive) {
    if (Test-ServerRunning) {
        Write-Log "Servidor já em execução na porta $Port"
        return
    }

    # Localizar vault-server.py — primeiro no vault, depois no boot FAT32
    $bootDrive = Get-VaultDrive
    $serverScript = $null
    foreach ($candidate in @("${vaultDrive}\vault-server.py", "${bootDrive}\vault-server.py")) {
        if (Test-Path $candidate) { $serverScript = $candidate; break }
    }

    if (-not $serverScript) {
        Write-Log "ERRO: vault-server.py não encontrado"
        return
    }

    Write-Log "Iniciando servidor: $PythonExe $serverScript (vault=$vaultDrive)"
    $env:VAULT_DRIVE  = $vaultDrive + "\"
    $env:VAULT_PORT   = $Port
    $proc = Start-Process -FilePath $PythonExe `
                          -ArgumentList "`"$serverScript`"" `
                          -WindowStyle Hidden -PassThru
    $proc.Id | Out-File -FilePath $PidFile -Encoding ascii

    # Aguardar servidor subir (max 15s)
    $ok = $false
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep 1
        if (Test-ServerRunning) { $ok = $true; break }
    }

    if ($ok) {
        Write-Log "Servidor OK — abrindo navegador"
        Start-Process "http://localhost:$Port"
    } else {
        Write-Log "AVISO: servidor não respondeu após 15s"
    }
}

function Stop-VaultServer {
    if (Test-Path $PidFile) {
        $pid = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($pid) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Log "Servidor encerrado (PID $pid)"
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

Write-Log "Monitor iniciado — aguardando pendrive '$VaultBootLabel'..."

$wasConnected = $false

while ($true) {
    $bootDrive   = Get-VaultDrive
    $vaultDrive  = Get-LibreCryptDrive

    $connected = ($null -ne $bootDrive)

    if ($connected -and -not $wasConnected) {
        Write-Log "Pendrive detectado: boot=$bootDrive vault=$vaultDrive"

        if ($vaultDrive) {
            Start-VaultServer $vaultDrive
        } else {
            Write-Log "Partição LUKS não montada. Abra com LibreCrypt e aguarde."
            # Aguardar até 60s pelo LibreCrypt montar
            for ($w = 0; $w -lt 12; $w++) {
                Start-Sleep 5
                $vaultDrive = Get-LibreCryptDrive
                if ($vaultDrive) {
                    Write-Log "LibreCrypt montou: $vaultDrive"
                    Start-VaultServer $vaultDrive
                    break
                }
            }
        }
        $wasConnected = $true
    }
    elseif (-not $connected -and $wasConnected) {
        Write-Log "Pendrive removido — encerrando servidor"
        Stop-VaultServer
        $wasConnected = $false
    }

    Start-Sleep $PollSec
}
