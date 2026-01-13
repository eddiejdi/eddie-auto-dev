<# 
Apply recommended performance optimizations for Windows + WSL2.

Run as Administrator. The script:
- saves current power scheme
- enables Ultimate Performance (if available) or High Performance
- ensures TRIM is enabled
- generates a recommended .wslconfig in `scripts/.wslconfig.recommended`
- lists startup programs to `scripts/startup_items.csv`
- shuts down WSL so new config can be applied after user copies the file

This script is conservative and writes backups to the `scripts/` folder.
#>

function Ensure-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
        Write-Error "Execute este script como Administrador. Saindo."
        exit 1
    }
}

Ensure-Admin

$scriptsDir = Join-Path -Path (Get-Location) -ChildPath "scripts"
if (-not (Test-Path $scriptsDir)) { New-Item -Path $scriptsDir -ItemType Directory | Out-Null }

# Save current active power scheme
$activeOutput = (powercfg /GETACTIVESCHEME) 2>&1
if ($activeOutput -match '([0-9a-fA-F\-]{36})') { $currentGUID = $matches[1] } else { $currentGUID = "" }
Set-Content -Path (Join-Path $scriptsDir 'previous_power_scheme.txt') -Value $currentGUID
Write-Output "GUID do esquema ativo salvo: $currentGUID"

# Try to enable Ultimate Performance, fallback to High performance
$ultimateGUID = 'e9a42b02-d5df-448d-aa00-03f14749eb61'
$highGUID = '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c'

Write-Output "Tentando habilitar Ultimate Performance..."
$dupOut = try { powercfg -duplicatescheme $ultimateGUID 2>&1 } catch { $_ }
if ($dupOut -and ($dupOut -match '([0-9a-fA-F\-]{36})')) {
    $newGUID = $matches[1]
    powercfg /S $newGUID
    Write-Output "Esquema Ultimate Performance habilitado: $newGUID"
} else {
    Write-Output "Ultimate Performance não disponível ou já existe. Tentando High Performance."
    powercfg /S $highGUID
    Write-Output "Esquema High Performance habilitado: $highGUID"
}

# Ensure TRIM (DisableDeleteNotify = 0)
try {
    $trim = fsutil behavior query DisableDeleteNotify 2>&1
    if ($trim -notmatch 'DisableDeleteNotify\s*=\s*0') {
        Write-Output "Habilitando TRIM..."
        fsutil behavior set DisableDeleteNotify 0 | Out-Null
        Write-Output "TRIM habilitado."
    } else {
        Write-Output "TRIM já habilitado."
    }
} catch {
    Write-Warning "Falha ao verificar/definir TRIM: $_"
}

# Collect system info and generate .wslconfig recommendation
try {
    $cs = Get-CimInstance -ClassName Win32_ComputerSystem
    $memBytes = $cs.TotalPhysicalMemory
    $memGB = [math]::Floor($memBytes / 1GB)
    $cores = (Get-CimInstance -ClassName Win32_Processor | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
    if (-not $cores) { $cores = 1 }

    $wslMemGB = [math]::Max(1, [math]::Floor($memGB * 0.75))
    $wslProcs = [math]::Max(1, [int]($cores - 1))

    $wslconfig = @"
[wsl2]
memory=${wslMemGB}GB
processors=${wslProcs}
swap=0
localhostForwarding=true
"@

    $wslPath = (Join-Path $scriptsDir '.wslconfig.recommended')
    Set-Content -Path $wslPath -Value $wslconfig -Encoding UTF8
    Write-Output "Template .wslconfig criado em: $wslPath"
    Write-Output "Recomendação: copie para %USERPROFILE%\.wslconfig e então rode 'wsl --shutdown'"
} catch {
    Write-Warning "Falha ao gerar .wslconfig: $_"
}

# Exportar lista de programas de inicialização (para revisão manual)
try {
    Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, User | Export-Csv -Path (Join-Path $scriptsDir 'startup_items.csv') -NoTypeInformation -Encoding UTF8
    Write-Output "Lista de itens de inicialização exportada para scripts/startup_items.csv"
} catch {
    Write-Warning "Falha ao exportar itens de inicialização: $_"
}

# Shutdown WSL so new settings take effect after user copies .wslconfig
try {
    Write-Output "Reiniciando WSL (wsl --shutdown)..."
    wsl --shutdown
} catch {
    Write-Warning "Falha ao executar wsl --shutdown: $_"
}

Write-Output "Pronto. Revise scripts/startup_items.csv e copie scripts/.wslconfig.recommended para %USERPROFILE%\ .wslconfig se estiver de acordo."
Write-Output "Um rollback parcial está disponível em scripts/rollback_performance.ps1"
