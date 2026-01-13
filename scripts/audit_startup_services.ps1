<# 
Gera um relatório de auditoria com itens de inicialização, serviços e drivers.

Execute como Administrador. Saídas:
- scripts/audit/startup_items.csv
- scripts/audit/services.csv
- scripts/audit/drivers.csv
- scripts/audit/video.txt
- scripts/audit/summary.txt
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

$base = Join-Path (Get-Location) 'scripts\audit'
if (-not (Test-Path $base)) { New-Item -Path $base -ItemType Directory | Out-Null }

Write-Output "Exportando itens de inicialização..."
try {
    Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, User | Export-Csv -Path (Join-Path $base 'startup_items.csv') -NoTypeInformation -Encoding UTF8
} catch { Write-Warning "Falha export startup: $_" }

Write-Output "Exportando serviços (estado e modo)..."
try {
    Get-Service | Select-Object Name, DisplayName, Status, StartType | Export-Csv -Path (Join-Path $base 'services.csv') -NoTypeInformation -Encoding UTF8
} catch { Write-Warning "Falha export services: $_" }

Write-Output "Analisando drivers instalados (pnp signed)..."
try {
    Get-CimInstance Win32_PnPSignedDriver | Select-Object DeviceName, DriverVersion, Manufacturer, DriverDate, InfName, ClassGuid | Export-Csv -Path (Join-Path $base 'drivers.csv') -NoTypeInformation -Encoding UTF8
} catch { Write-Warning "Falha export drivers: $_" }

Write-Output "Coletando informações da GPU..."
try {
    Get-CimInstance Win32_VideoController | Format-List * > (Join-Path $base 'video.txt')
} catch { Write-Warning "Falha coletar GPU: $_" }

# Summary recommendations (heurísticas básicas)
$summary = @()

# Detect services set to Automatic but Stopped -> possível ajuste
try {
    $autoStopped = Get-Service | Where-Object { $_.StartType -eq 'Automatic' -and $_.Status -ne 'Running' } | Select-Object Name, Status, StartType
    if ($autoStopped) {
        $summary += "Serviços em Automatic mas não em execução:"
        $autoStopped | ForEach-Object { $summary += " - $($_.Name) ($($_.Status))" }
    }
} catch {}

# Detect drivers antigos (heurística: DriverDate menor que 2 anos)
try {
    $oldDrivers = Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DriverDate -ne $null } | Where-Object { ([datetime]$_.DriverDate) -lt (Get-Date).AddYears(-2) } | Select-Object DeviceName, DriverVersion, DriverDate
    if ($oldDrivers) {
        $summary += "Drivers com data anterior a 2 anos (rever):"
        $oldDrivers | ForEach-Object { $summary += " - $($_.DeviceName) $($_.DriverVersion) $($_.DriverDate)" }
    }
} catch {}

if (-not $summary) { $summary = @('Nenhuma anomalia heurística detectada automaticamente. Revise os arquivos CSV/TXT gerados.') }

Set-Content -Path (Join-Path $base 'summary.txt') -Value $summary -Encoding UTF8

Write-Output "Relatório gerado em scripts/audit/. Revise 'summary.txt', 'startup_items.csv', 'services.csv', e 'drivers.csv'."
