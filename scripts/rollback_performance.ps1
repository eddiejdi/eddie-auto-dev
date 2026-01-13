<# 
Rollback partial changes made by apply_performance.ps1

Run as Administrator. This will attempt to restore the previous power scheme
saved in `scripts/previous_power_scheme.txt`.
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
$prevFile = Join-Path $scriptsDir 'previous_power_scheme.txt'
if ((Test-Path $prevFile) -and (Get-Content $prevFile).Trim()) {
    $guid = (Get-Content $prevFile).Trim()
    Write-Output "Restaurando esquema de energia anterior: $guid"
    try {
        powercfg /S $guid
        Write-Output "Esquema restaurado."
    } catch {
        Write-Warning "Falha ao restaurar esquema: $_"
    }
} else {
    Write-Warning "Arquivo de esquema anterior não encontrado ou vazio: $prevFile"
}

Write-Output "Rollback parcial concluído. Não há alterações automáticas em TRIM ou .wslconfig aplicadas aqui."
