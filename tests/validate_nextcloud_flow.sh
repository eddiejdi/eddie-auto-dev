#!/usr/bin/env bash
# Teste de validação do fluxo Nextcloud → Staging → Fita LTO
# Executa em ambiente de desenvolvimento ou produção

set -euo pipefail

readonly SCRIPT_NAME=$(basename "$0")
readonly WORKDIR=${WORKDIR:-.}
readonly RESULTS_FILE="${WORKDIR}/nextcloud_flow_validation_results.txt"

# Cores para output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

# Contadores
PASS=0
FAIL=0
WARN=0

log_pass() {
    echo -e "${GREEN}✓${NC} $1" | tee -a "$RESULTS_FILE"
    ((PASS++))
}

log_fail() {
    echo -e "${RED}✗${NC} $1" | tee -a "$RESULTS_FILE"
    ((FAIL++))
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1" | tee -a "$RESULTS_FILE"
    ((WARN++))
}

log_section() {
    echo "" | tee -a "$RESULTS_FILE"
    echo "=== $1 ===" | tee -a "$RESULTS_FILE"
}

echo "Validação do Fluxo Nextcloud → Staging → Fita LTO" | tee "$RESULTS_FILE"
echo "Data: $(date -Iseconds)" | tee -a "$RESULTS_FILE"
echo "" | tee -a "$RESULTS_FILE"

# ─── Teste 1: Mount point /mnt/lto6-nc ───────────────────────────────────────
log_section "1. Mount Point /mnt/lto6-nc"

if findmnt /mnt/lto6-nc &>/dev/null; then
    mount_source=$(findmnt -T /mnt/lto6-nc -o SOURCE -n)
    if [[ "$mount_source" =~ lto6-cache ]]; then
        log_pass "Mount /mnt/lto6-nc aponta para staging: $mount_source"
    else
        log_fail "Mount source inválido: $mount_source (esperado /mnt/raid1/lto6-cache)"
    fi
else
    log_warn "Mount /mnt/lto6-nc não existe (dev environment?)"
fi

# ─── Teste 2: Staging em disco ─────────────────────────────────────────────────
log_section "2. Staging em Disco"

if [[ -d /mnt/raid1/lto6-cache ]]; then
    log_pass "Diretório /mnt/raid1/lto6-cache existe"

    # Verificar permissões
    perm=$(stat -c "%a" /mnt/raid1/lto6-cache)
    owner=$(stat -c "%U:%G" /mnt/raid1/lto6-cache)

    if [[ "$perm" == "770" ]]; then
        log_pass "Permissões corretas: $perm"
    else
        log_warn "Permissões: $perm (esperado 770)"
    fi

    if [[ "$owner" == "www-data:www-data" ]] || [[ "$owner" == "root:root" ]]; then
        log_pass "Dono correto: $owner"
    else
        log_warn "Dono: $owner"
    fi
else
    log_warn "Diretório /mnt/raid1/lto6-cache não existe"
fi

# ─── Teste 3: Container Nextcloud ──────────────────────────────────────────────
log_section "3. Container Nextcloud"

if docker ps --format "table {{.Names}}" | grep -q nextcloud-app; then
    log_pass "Container nextcloud-app está rodando"

    # Testar escrita
    if docker exec -u www-data nextcloud-app sh -c 'p=/var/www/html/external/LTO/.probe-flow-test; date > "$p" && rm -f "$p"' &>/dev/null; then
        log_pass "Escrita www-data em /var/www/html/external/LTO funciona"
    else
        log_fail "Falha na escrita como www-data (verificar permissões no staging)"
    fi

    # Testar storage externo
    if docker exec nextcloud-app php occ files_external:list 2>/dev/null | grep -q /LTO; then
        log_pass "Storage externo /LTO está listado no Nextcloud"
    else
        log_warn "Storage externo /LTO não listado (pode estar desabilitado)"
    fi
else
    log_warn "Container nextcloud-app não está rodando"
fi

# ─── Teste 4: Serviço ltfs-cache-flush ────────────────────────────────────────
log_section "4. Serviço ltfs-cache-flush"

if systemctl list-unit-files | grep -q ltfs-cache-flush.service; then
    log_pass "Serviço ltfs-cache-flush.service existe"

    # Verificar se está habilitado
    if systemctl is-enabled ltfs-cache-flush.service &>/dev/null; then
        log_pass "Serviço está habilitado"
    else
        log_warn "Serviço não está habilitado: systemctl enable ltfs-cache-flush.service"
    fi

    # Verificar drop-ins
    if [[ -d /etc/systemd/system/ltfs-cache-flush.service.d ]]; then
        drop_in_count=$(ls /etc/systemd/system/ltfs-cache-flush.service.d/*.conf 2>/dev/null | wc -l)
        if [[ $drop_in_count -gt 0 ]]; then
            log_pass "$drop_in_count drop-in(s) configurado(s)"
        fi
    else
        log_warn "Sem drop-ins em /etc/systemd/system/ltfs-cache-flush.service.d"
    fi
else
    log_warn "ltfs-cache-flush.service não encontrado (pode estar apenas em NAS)"
fi

# Verificar timer
if systemctl list-unit-files | grep -q ltfs-cache-flush.timer; then
    log_pass "Timer ltfs-cache-flush.timer existe"
else
    log_warn "Timer ltfs-cache-flush.timer não encontrado"
fi

# ─── Teste 5: Orchestrator NAS (SSH) ────────────────────────────────────────
log_section "5. Orchestrator LTFS na NAS"

if command -v ssh &>/dev/null; then
    if timeout 5 ssh -o ConnectTimeout=3 root@192.168.15.4 "test -f /var/db/ltfs-tools/ltfs_recovery.py" &>/dev/null; then
        log_pass "Orchestrator /var/db/ltfs-tools/ltfs_recovery.py acessível via SSH"
    else
        log_warn "Não conseguiu acessar NAS via SSH (verificar conectividade)"
    fi
else
    log_warn "ssh não disponível"
fi

# ─── Teste 6: Verificação de arquivo-prova ────────────────────────────────────
log_section "6. Limpeza de Arquivo-Prova"

if [[ -f /mnt/raid1/lto6-cache/.probe* ]]; then
    log_fail "Arquivo-prova ainda existe em staging (remover: rm /mnt/raid1/lto6-cache/.probe*)"
else
    log_pass "Nenhum arquivo-prova em staging"
fi

# ─── Resumo ──────────────────────────────────────────────────────────────────
log_section "RESUMO"
echo "Passou: $PASS | Falhou: $FAIL | Avisos: $WARN" | tee -a "$RESULTS_FILE"

if [[ $FAIL -eq 0 ]]; then
    echo -e "${GREEN}Fluxo Nextcloud → Staging → Fita pronto para produção${NC}" | tee -a "$RESULTS_FILE"
    exit 0
else
    echo -e "${RED}Existem $FAIL falhas críticas${NC}" | tee -a "$RESULTS_FILE"
    exit 1
fi
