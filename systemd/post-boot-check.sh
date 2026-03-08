#!/usr/bin/env bash
# =============================================================================
# Post-Boot Check — Validação automática de serviços críticos após boot
# Instalação: sudo cp systemd/post-boot-check.sh /usr/local/bin/
#              sudo chmod +x /usr/local/bin/post-boot-check.sh
# Versão: 3.0 (2026-03-06)
# =============================================================================
set -euo pipefail

LOG="/var/log/post-boot-check.log"
FAILED=0
WARNED=0
CHECKED=0
TELEGRAM_API="http://localhost:8503/api/notify"

# Cores para output no journal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "$1" | tee -a "$LOG"
}

check_service() {
    local name="$1"
    CHECKED=$((CHECKED + 1))
    if systemctl is-active --quiet "$name" 2>/dev/null; then
        log "${GREEN}[OK]${NC} systemd: $name"
    else
        log "${RED}[FAIL]${NC} systemd: $name"
        FAILED=$((FAILED + 1))
    fi
}

# Serviço opcional — WARN se inativo, não conta como FAIL
check_service_optional() {
    local name="$1" reason="${2:-opcional}"
    CHECKED=$((CHECKED + 1))
    if systemctl is-active --quiet "$name" 2>/dev/null; then
        log "${GREEN}[OK]${NC} systemd: $name"
    else
        log "${YELLOW}[WARN]${NC} systemd: $name (${reason})"
        WARNED=$((WARNED + 1))
    fi
}

check_docker() {
    local container="$1"
    CHECKED=$((CHECKED + 1))
    local state
    state=$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null || echo "false")
    if [[ "$state" == "true" ]]; then
        log "${GREEN}[OK]${NC} docker: $container"
    else
        log "${RED}[FAIL]${NC} docker: $container"
        FAILED=$((FAILED + 1))
    fi
}

check_docker_healthy() {
    local container="$1"
    CHECKED=$((CHECKED + 1))
    local health
    health=$(docker inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null || echo "none")
    local running
    running=$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null || echo "false")
    if [[ "$health" == "healthy" ]]; then
        log "${GREEN}[OK]${NC} docker: $container (healthy)"
    elif [[ "$running" == "true" ]]; then
        log "${YELLOW}[WARN]${NC} docker: $container (running mas health=$health)"
        WARNED=$((WARNED + 1))
    else
        log "${RED}[FAIL]${NC} docker: $container (parado)"
        FAILED=$((FAILED + 1))
    fi
}

check_port() {
    local name="$1" port="$2"
    CHECKED=$((CHECKED + 1))
    if ss -tlnp | grep -q ":${port} " 2>/dev/null; then
        log "${GREEN}[OK]${NC} porta $port: $name"
    else
        log "${RED}[FAIL]${NC} porta $port: $name"
        FAILED=$((FAILED + 1))
    fi
}

check_mount() {
    local path="$1"
    CHECKED=$((CHECKED + 1))
    if mountpoint -q "$path" 2>/dev/null; then
        local usage
        usage=$(df -h "$path" 2>/dev/null | tail -1 | awk '{print $5}')
        log "${GREEN}[OK]${NC} mount: $path (uso: $usage)"
    else
        log "${RED}[FAIL]${NC} mount: $path"
        FAILED=$((FAILED + 1))
    fi
}

check_ollama_gpu() {
    # GPU0 — RTX 2060 SUPER (LLM principal)
    CHECKED=$((CHECKED + 1))
    local gpu0_info
    gpu0_info=$(curl -sf --max-time 10 http://localhost:11434/api/ps 2>/dev/null || echo "")
    if [[ -n "$gpu0_info" ]]; then
        log "${GREEN}[OK]${NC} ollama: API GPU0 respondendo (:11434)"
    else
        log "${YELLOW}[WARN]${NC} ollama: API GPU0 não respondeu (pode estar carregando modelo)"
        WARNED=$((WARNED + 1))
    fi

    # GPU1 — GTX 1050 (Controller CUDA permanente)
    CHECKED=$((CHECKED + 1))
    local gpu1_info
    gpu1_info=$(curl -sf --max-time 10 http://localhost:11435/api/ps 2>/dev/null || echo "")
    if [[ -n "$gpu1_info" ]]; then
        # Verificar se o modelo controller está carregado
        local gpu1_model
        gpu1_model=$(echo "$gpu1_info" | python3 -c "import sys,json;m=json.load(sys.stdin).get('models',[]);print(m[0]['name'] if m else '')" 2>/dev/null || echo "")
        CHECKED=$((CHECKED + 1))
        if [[ "$gpu1_model" == *"qwen3:0.6b"* ]]; then
            log "${GREEN}[OK]${NC} ollama: GPU1 controller carregado ($gpu1_model, Forever)"
        elif [[ -n "$gpu1_model" ]]; then
            log "${YELLOW}[WARN]${NC} ollama: GPU1 com modelo inesperado: $gpu1_model (esperado qwen3:0.6b)"
            WARNED=$((WARNED + 1))
        else
            log "${YELLOW}[WARN]${NC} ollama: GPU1 API ativa mas sem modelo carregado"
            WARNED=$((WARNED + 1))
        fi
    else
        log "${RED}[FAIL]${NC} ollama: API GPU1 não respondeu (:11435) — controller offline!"
        FAILED=$((FAILED + 1))
    fi

    # Verificar se nvidia-smi detecta 2 GPUs
    CHECKED=$((CHECKED + 1))
    local gpu_count
    gpu_count=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l)
    if [[ "$gpu_count" -ge 2 ]]; then
        log "${GREEN}[OK]${NC} nvidia: $gpu_count GPU(s) detectada(s)"
    elif [[ "$gpu_count" -ge 1 ]]; then
        log "${YELLOW}[WARN]${NC} nvidia: apenas $gpu_count GPU detectada (esperado 2)"
        WARNED=$((WARNED + 1))
    else
        log "${RED}[FAIL]${NC} nvidia: nenhuma GPU detectada"
        FAILED=$((FAILED + 1))
    fi

    # Verificar VRAM GPU0
    CHECKED=$((CHECKED + 1))
    local gpu0_vram
    gpu0_vram=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 0 2>/dev/null || echo "0")
    if [[ "$gpu0_vram" -gt 100 ]]; then
        log "${GREEN}[OK]${NC} nvidia: GPU0 VRAM em uso (${gpu0_vram} MiB)"
    else
        log "${YELLOW}[WARN]${NC} nvidia: GPU0 VRAM ociosa (Ollama pode não estar usando GPU)"
        WARNED=$((WARNED + 1))
    fi

    # Verificar VRAM GPU1 (controller permanente ~1085 MiB)
    CHECKED=$((CHECKED + 1))
    local gpu1_vram
    gpu1_vram=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 1 2>/dev/null || echo "0")
    if [[ "$gpu1_vram" -gt 500 ]]; then
        log "${GREEN}[OK]${NC} nvidia: GPU1 VRAM em uso (${gpu1_vram} MiB — controller ativo)"
    else
        log "${YELLOW}[WARN]${NC} nvidia: GPU1 VRAM baixa (${gpu1_vram} MiB — modelo pode não estar carregado)"
        WARNED=$((WARNED + 1))
    fi
}

check_postgres() {
    CHECKED=$((CHECKED + 1))
    if pg_isready -h localhost -p 5433 -q 2>/dev/null; then
        log "${GREEN}[OK]${NC} postgresql: porta 5433"
    elif docker exec shared-postgres pg_isready -q 2>/dev/null; then
        log "${GREEN}[OK]${NC} postgresql: via container shared-postgres"
    else
        log "${RED}[FAIL]${NC} postgresql: indisponível"
        FAILED=$((FAILED + 1))
    fi
}

check_failed_units() {
    local failed_count
    failed_count=$(systemctl --failed --no-legend --no-pager 2>/dev/null | wc -l)
    CHECKED=$((CHECKED + 1))
    if [[ "$failed_count" -eq 0 ]]; then
        log "${GREEN}[OK]${NC} systemd: 0 units falhados"
    else
        log "${YELLOW}[WARN]${NC} systemd: $failed_count unit(s) falhado(s):"
        systemctl --failed --no-pager --no-legend 2>/dev/null | while read -r line; do
            log "         ↳ $(echo "$line" | awk '{print $1}')"
        done
        WARNED=$((WARNED + 1))
    fi
}

check_ip6tables_pihole() {
    CHECKED=$((CHECKED + 1))
    local rules
    rules=$(ip6tables -t nat -L PREROUTING -n 2>/dev/null | grep -c "dpt:53" || echo "0")
    if [[ "$rules" -ge 2 ]]; then
        log "${GREEN}[OK]${NC} pihole: ip6tables DNS DNAT ativo ($rules regras)"
    else
        log "${RED}[FAIL]${NC} pihole: ip6tables DNS DNAT ausente (IPv6 DNS leak!)"
        FAILED=$((FAILED + 1))
    fi
}

# =============================================================================
# INÍCIO DA VERIFICAÇÃO
# =============================================================================
echo "" > "$LOG"
log "=================================================================="
log "  Post-Boot Check v3.0 — $(date -Iseconds)"
log "  Uptime: $(uptime -p)"
log "  Boot time: $(systemd-analyze 2>/dev/null | head -1 || echo 'N/A')"
log "=================================================================="
log ""

# 0. Units falhados no systemd
log "--- Systemd Health ---"
check_failed_units

# 1. Filesystem / RAID
log ""
log "--- Filesystem ---"
check_mount "/mnt/raid1"

# 2. Serviços systemd críticos
log ""
log "--- Serviços Críticos ---"
check_service "docker"
check_service "ssh"
check_service "nvidia-persistenced"
check_service "ollama"
check_service "btc-trading-agent"
check_service "shared-telegram-bot"
check_service "specialized-agents-api"

# 3. Serviços systemd secundários
log ""
log "--- Serviços Secundários ---"
check_service "ollama-frozen-monitor"
check_service "ollama-metrics-exporter"
check_service "shared-central-metrics"
check_service "alertmanager"
check_service "alertmanager-telegram-webhook"
check_service "autocoinbot-exporter"
check_service "coordinator-agent"
check_service "diretor"
check_service "nginx"
check_service "shared-coordinator"

# 4. Serviços opcionais (WARN, não FAIL)
log ""
log "--- Serviços Opcionais ---"
check_service "ollama-gpu1"
check_service_optional "cloudflared-rpa4all" "tunnel Cloudflare"
check_service_optional "openwebui-ssh-tunnel" "SSH tunnel OpenWebUI"
check_service_optional "shared-calendar" "serviço de calendário"
check_service_optional "glances" "monitoramento Glances"
check_service_optional "btop-boot" "dashboard console"

# 5. Containers Docker
log ""
log "--- Containers Docker ---"
check_docker "shared-postgres"
check_docker_healthy "pihole"
check_docker_healthy "mailserver"
check_docker_healthy "open-webui"
check_docker "prometheus"
check_docker "grafana"
check_docker_healthy "authentik-server"
check_docker "roundcube"
check_docker "nextcloud"

# 6. GPU / Ollama
log ""
log "--- GPU / Ollama ---"
check_ollama_gpu

# 7. PostgreSQL
log ""
log "--- Banco de Dados ---"
check_postgres

# 8. Pi-hole IPv6 DNS
log ""
log "--- Pi-hole DNS ---"
check_ip6tables_pihole

# 9. Portas críticas
log ""
log "--- Portas de Rede ---"
check_port "SSH" 22
check_port "PostgreSQL" 5433
check_port "Ollama GPU0" 11434
check_port "Ollama GPU1" 11435
check_port "API Shared" 8503
check_port "Prometheus" 9090
check_port "Nginx" 80
check_port "Pi-hole DNS" 53

# =============================================================================
# RESULTADO
# =============================================================================
log ""
log "=================================================================="
if [[ "$FAILED" -gt 0 ]]; then
    log "${RED}⚠️  RESULTADO: $FAILED FALHA(s), $WARNED aviso(s) de $CHECKED verificações${NC}"
    log "=================================================================="

    # Notificar via Telegram
    curl -sf --max-time 5 "$TELEGRAM_API" \
        -H "Content-Type: application/json" \
        -d "{\"message\": \"⚠️ Post-boot check: $FAILED falha(s), $WARNED aviso(s) de $CHECKED verificações. Ver /var/log/post-boot-check.log\"}" \
        2>/dev/null || true

    exit 1
elif [[ "$WARNED" -gt 0 ]]; then
    log "${YELLOW}⚡ RESULTADO: 0 falhas, $WARNED aviso(s) de $CHECKED verificações${NC}"
    log "=================================================================="

    curl -sf --max-time 5 "$TELEGRAM_API" \
        -H "Content-Type: application/json" \
        -d "{\"message\": \"⚡ Post-boot check: 0 falhas, $WARNED aviso(s) de $CHECKED verificações. Boot: $(systemd-analyze 2>/dev/null | head -1 | sed 's/.*= //')\"}" \
        2>/dev/null || true

    exit 0
else
    log "${GREEN}✅ RESULTADO: Todos os $CHECKED serviços OK${NC}"
    log "=================================================================="

    curl -sf --max-time 5 "$TELEGRAM_API" \
        -H "Content-Type: application/json" \
        -d "{\"message\": \"✅ Post-boot check: todos os $CHECKED serviços OK. Boot: $(systemd-analyze 2>/dev/null | head -1 | sed 's/.*= //')\"}" \
        2>/dev/null || true

    exit 0
fi
