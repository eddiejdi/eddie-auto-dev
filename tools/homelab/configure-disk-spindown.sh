#!/usr/bin/env bash
set -euo pipefail

# Configure disk spindown (APM) after inactivity
# Reduz consumo de energia em HDDs inativos
# 
# Spindown timeout: 20 minutos (1200 segundos = 240 unidades de 5s em hdparm)
# Discos alvo: /dev/sda, /dev/sdb, /dev/sdc

SPINDOWN_VALUE=240   # 20 minutes (240 * 5 segundos = 1200s)
LOG="/var/log/disk-spindown.log"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Configurando spindown de discos..." | tee -a "$LOG"

# Função para configurar um disco
configure_disk() {
    local disk=$1
    local timeout=$2
    
    # Verificar se o disco existe
    if ! sudo test -b "$disk" 2>/dev/null; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ⚠️  Disco não encontrado: $disk" | tee -a "$LOG"
        return 1
    fi
    
    # Configurar spindown (APM)
    # -S <value> = spindown timeout (value * 5 segundos)
    # -B <value> = APM mode
    if sudo hdparm -M 254 -S "$timeout" "$disk" >> "$LOG" 2>&1; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ✅ Spindown configurado: $disk (timeout=${timeout}*5s)" | tee -a "$LOG"
    else
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ❌ Erro ao configurar: $disk" | tee -a "$LOG"
        return 1
    fi
}

# Configurar cada disco
for disk in /dev/sda /dev/sdb /dev/sdc; do
    configure_disk "$disk" "$SPINDOWN_VALUE" || true
done

# Verificar status
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Status dos discos:" | tee -a "$LOG"
for disk in /dev/sda /dev/sdb /dev/sdc; do
    if sudo test -b "$disk" 2>/dev/null; then
        echo -n "  $disk: " | tee -a "$LOG"
        sudo hdparm -C "$disk" 2>/dev/null | grep "currently" | tee -a "$LOG" || echo "N/A" | tee -a "$LOG"
    fi
done

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Configuração concluída" | tee -a "$LOG"
