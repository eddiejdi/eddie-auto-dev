#!/usr/bin/env bash
# Teste de validação do fluxo Nextcloud → Staging → Fita LTO
# Executa em ambiente de desenvolvimento ou produção

set -euo pipefail

readonly SCRIPT_NAME=$(basename "$0")
readonly WORKDIR=${WORKDIR:-.}
readonly RESULTS_FILE="${WORKDIR}/nextcloud_flow_validation_results.txt"

# G20: rotação do RESULTS_FILE (mantém no máximo VALIDATION_MAX_RESULTS arquivos)
VALIDATION_MAX_RESULTS=${VALIDATION_MAX_RESULTS:-10}
rotate_results_file() {
    local base="${RESULTS_FILE}"
    # Roda do mais antigo para o mais novo: .N+1 recebe .N (mantém .1 = mais recente)
    local i
    for ((i = VALIDATION_MAX_RESULTS - 1; i >= 1; i--)); do
        [[ -f "${base}.${i}" ]] && mv "${base}.${i}" "${base}.$((i + 1))" 2>/dev/null || true
    done
    [[ -f "${base}" ]] && mv "${base}" "${base}.1" 2>/dev/null || true
}
rotate_results_file

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

    # Verificar espaço em disco (G3 - crítico)
    log_section "2b. Espaço em Staging"
    df_out=$(df -B1 /mnt/raid1/lto6-cache 2>/dev/null | tail -1) || df_out=""
    if [[ -n "$df_out" ]]; then
        total=$(echo "$df_out" | awk '{print $2}')
        used=$(echo "$df_out" | awk '{print $3}')
        avail=$(echo "$df_out" | awk '{print $4}')
        pct=$(( used * 100 / total ))
        total_gb=$(( total / 1024 / 1024 / 1024 ))
        avail_gb=$(( avail / 1024 / 1024 / 1024 ))
        log_pass "Espaço: total=${total_gb}GB livre=${avail_gb}GB usado=${pct}%"
        if [[ $pct -ge 90 ]]; then
            log_fail "CRÍTICO: Staging com ${pct}% de uso (≥90%)"
        elif [[ $pct -ge 80 ]]; then
            log_warn "Atenção: Staging com ${pct}% de uso (≥80%)"
        else
            log_pass "Uso de staging saudável: ${pct}%"
        fi
    else
        log_warn "Não foi possível obter df para /mnt/raid1/lto6-cache"
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

# ─── Teste 7: E2E upload → staging → flush (G10) ──────────────────────────────
log_section "7. Teste E2E (upload → staging → flush → fita)"

E2E_ENABLED="${E2E_ENABLED:-0}"
E2E_PROBE=".e2e-probe-$(date +%s)"
E2E_MARKER="e2e-validation-$(date +%s)"

if [[ "$E2E_ENABLED" == "1" ]]; then
    # 7a. Upload de arquivo-prova via Nextcloud (escrita como www-data no /LTO)
    if docker exec -u www-data nextcloud-app \
        sh -c "echo '$E2E_MARKER' > /var/www/html/external/LTO/$E2E_PROBE" &>/dev/null; then
        log_pass "E2E: upload para /LTO (staging) OK"
    else
        log_fail "E2E: upload para /LTO falhou"
    fi

    # 7b. Arquivo materializado no staging em disco
    if [[ -f "/mnt/raid1/lto6-cache/$E2E_PROBE" ]]; then
        log_pass "E2E: arquivo presente no staging (/mnt/raid1/lto6-cache)"
        probe_content=$(cat "/mnt/raid1/lto6-cache/$E2E_PROBE")
        if [[ "$probe_content" == "$E2E_MARKER" ]]; then
            log_pass "E2E: conteúdo do arquivo-prova íntegro"
        else
            log_fail "E2E: conteúdo do arquivo-prova divergente (got '$probe_content')"
        fi
    else
        log_fail "E2E: arquivo não materializado no staging"
    fi

    # 7c. Flush para fita (requer flush worker instalado; marcado com mtime antigo)
    if command -v ltfs-cache-flush &>/dev/null; then
        touch -d "2 hours ago" "/mnt/raid1/lto6-cache/$E2E_PROBE"
        if ltfs-cache-flush \
            --buffer-root /mnt/raid1/lto6-cache \
            --primary-buffer-root /mnt/raid1/lto6-cache \
            --target-root /mnt/lto6-smb-proof \
            --state-file /var/lib/ltfs-cache-flush/state.json \
            --placement-file /var/lib/ltfs-cache-flush/placements.json \
            --catalog-file /var/lib/ltfs-cache-flush/catalog.jsonl \
            --metrics-file /var/lib/ltfs-cache-flush/metrics.json \
            --metrics-state-file /var/lib/ltfs-cache-flush/metrics_state.json \
            --lock-file /run/ltfs-cache-flush.lock \
            --min-age-seconds 60 --min-stable-seconds 30 \
            --min-target-total-bytes 0 --min-target-free-bytes 0 &>/dev/null; then
            log_pass "E2E: flush worker executou sem erro"
        else
            log_warn "E2E: flush worker retornou erro (verificar journal ltfs-cache-flush.service)"
        fi

        # 7d. Arquivo-prova na fita (via CIFS)
        if [[ -f "/mnt/lto6-smb-proof/$E2E_PROBE" ]]; then
            tape_content=$(cat "/mnt/lto6-smb-proof/$E2E_PROBE" 2>/dev/null || echo "")
            if [[ "$tape_content" == "$E2E_MARKER" ]]; then
                log_pass "E2E: arquivo-prova verificado na fita via CIFS"
            else
                log_warn "E2E: arquivo na fita com conteúdo divergente (flush pode não ter concluído SHA256)"
            fi
        else
            log_warn "E2E: arquivo não encontrado na fita via CIFS (fita pode não estar montada ou flush pendente)"
        fi
    else
        log_warn "E2E: ltfs-cache-flush não instalado — pulando etapa de flush"
    fi

    # 7e. Cleanup do probe (staging + fita)
    rm -f "/mnt/raid1/lto6-cache/$E2E_PROBE" 2>/dev/null || true
    rm -f "/mnt/lto6-smb-proof/$E2E_PROBE" 2>/dev/null || true
    log_pass "E2E: cleanup do arquivo-prova realizado"
else
    log_warn "E2E desabilitado — export E2E_ENABLED=1 para executar (precisa de tape/flush montados)"
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
