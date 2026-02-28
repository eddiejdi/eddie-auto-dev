#!/bin/bash
# Deploy Selfhealing Scripts to Homelab
# Automatiza instalação de scripts em tools/selfheal/ como serviços systemd
# Uso: ./deploy_self_healing_services.sh [homelab_user] [homelab_host]

set -euo pipefail

HOMELAB_USER=${1:-"homelab"}
HOMELAB_HOST=${2:-"192.168.15.2"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/tools/selfheal"
LOG_FILE="/tmp/selfhealing_deploy_$(date +%Y%m%d_%H%M%S).log"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    local level=$1
    shift
    local msg="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[${timestamp}]${NC} [${level}] ${msg}" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}✅ $@${NC}" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}❌ $@${NC}" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}⚠️  $@${NC}" | tee -a "$LOG_FILE"
}

validate_connectivity() {
    log "INFO" "Validando conectividade com homelab..."
    
    if ! ssh -q "$HOMELAB_USER@$HOMELAB_HOST" "echo OK" > /dev/null 2>&1; then
        error "Não consigo conectar em $HOMELAB_USER@$HOMELAB_HOST"
        exit 1
    fi
    
    success "Conectividade OK"
}

get_script_info() {
    local script=$1
    local name=$(basename "$script" .sh)
    local service_name="ollama-${name}"
    
    echo "$name:$service_name"
}

deploy_script() {
    local script_path=$1
    local script_name=$(basename "$script_path")
    local script_base=$(basename "$script_path" .sh)
    local service_name="ollama-${script_base}"
    
    log "INFO" "Deployando $script_name..."
    
    # 1. Transfer
    log "INFO" "  → Transferindo para /tmp/..."
    if ! scp "$script_path" "$HOMELAB_USER@$HOMELAB_HOST:/tmp/$script_name" >> "$LOG_FILE" 2>&1; then
        error "Falha ao transferir $script_name"
        return 1
    fi
    success "  → $script_name transferido"
    
    # 2. Install
    log "INFO" "  → Instalando em /usr/local/bin/..."
    if ! ssh "$HOMELAB_USER@$HOMELAB_HOST" \
        "sudo mv /tmp/$script_name /usr/local/bin/ && sudo chmod +x /usr/local/bin/$script_name" >> "$LOG_FILE" 2>&1; then
        error "Falha ao instalar $script_name"
        return 1
    fi
    success "  → Instalado e executable"
    
    # 3. Create systemd service
    log "INFO" "  → Criando serviço systemd..."
    
    local service_file="/etc/systemd/system/${service_name}.service"
    
    # Determine ExecStart based on script
    local exec_start="/usr/local/bin/$script_name"
    if [[ "$script_base" == "ollama_frozen_monitor" ]]; then
        exec_start="$exec_start 180 15 3 60"
    fi
    
    local service_content="[Unit]
Description=Ollama Self-Healing - $(echo $script_base | sed 's/_/ /g')
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=root
ExecStart=$exec_start
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"
    
    if ! echo "$service_content" | ssh "$HOMELAB_USER@$HOMELAB_HOST" \
        "sudo tee $service_file > /dev/null" >> "$LOG_FILE" 2>&1; then
        error "Falha ao criar $service_file"
        return 1
    fi
    success "  → Serviço criado"
    
    # 4. Daemon reload
    log "INFO" "  → Recarregando systemd daemon..."
    if ! ssh "$HOMELAB_USER@$HOMELAB_HOST" "sudo systemctl daemon-reload" >> "$LOG_FILE" 2>&1; then
        error "Falha ao recarregar daemon"
        return 1
    fi
    success "  → Daemon recarregado"
    
    # 5. Enable
    log "INFO" "  → Habilitando para boot automático..."
    if ! ssh "$HOMELAB_USER@$HOMELAB_HOST" "sudo systemctl enable $service_name.service" >> "$LOG_FILE" 2>&1; then
        error "Falha ao habilitar $service_name"
        return 1
    fi
    success "  → Habilitado para boot"
    
    # 6. Start
    log "INFO" "  → Iniciando serviço..."
    if ! ssh "$HOMELAB_USER@$HOMELAB_HOST" "sudo systemctl start $service_name.service" >> "$LOG_FILE" 2>&1; then
        error "Falha ao iniciar $service_name"
        return 1
    fi
    success "  → Serviço iniciado"
}

validate_service() {
    local script_base=$1
    local service_name="ollama-${script_base}"
    
    log "INFO" "Validando $service_name..."
    
    # Check is-active
    local status=$(ssh "$HOMELAB_USER@$HOMELAB_HOST" "sudo systemctl is-active $service_name.service 2>/dev/null || echo 'inactive'")
    
    if [[ "$status" == "active" ]]; then
        success "  → $service_name está active"
        
        # Show logs
        log "INFO" "  → Últimos logs:"
        ssh "$HOMELAB_USER@$HOMELAB_HOST" "sudo journalctl -u $service_name.service -n 5 --no-pager" | sed 's/^/      /' | tee -a "$LOG_FILE"
        
        return 0
    else
        error "  → $service_name não está active (status: $status)"
        log "INFO" "  → Logs de erro:"
        ssh "$HOMELAB_USER@$HOMELAB_HOST" "sudo journalctl -u $service_name.service -n 20 --no-pager" | sed 's/^/      /' | tee -a "$LOG_FILE"
        return 1
    fi
}

cleanup_old_artifacts() {
    log "INFO" "Limpando artefatos antigos no homelab..."
    
    # Remove old metric files
    ssh "$HOMELAB_USER@$HOMELAB_HOST" \
        "sudo rm -f /tmp/ollama_*.{txt,json,prom} 2>/dev/null || true" >> "$LOG_FILE" 2>&1
    
    success "Limpeza concluída"
}

main() {
    log "INFO" "=========================================="
    log "INFO" "Deploy de Self-Healing Services"
    log "INFO" "Homelab: $HOMELAB_USER@$HOMELAB_HOST"
    log "INFO" "=========================================="
    
    # Validate script directory exists
    if [[ ! -d "$SCRIPT_DIR" ]]; then
        error "Diretório $SCRIPT_DIR não encontrado"
        exit 1
    fi
    
    # Find all selfhealing scripts
    local scripts=()
    while IFS= read -r script; do
        scripts+=("$script")
    done < <(find "$SCRIPT_DIR" -type f -name "*.sh" | sort)
    
    if [[ ${#scripts[@]} -eq 0 ]]; then
        error "Nenhum script encontrado em $SCRIPT_DIR"
        exit 1
    fi
    
    log "INFO" "Encontrados ${#scripts[@]} script(s) para deploy:"
    for script in "${scripts[@]}"; do
        log "INFO" "  - $(basename $script)"
    done
    
    # Validate connectivity
    validate_connectivity
    
    # Cleanup old artifacts
    cleanup_old_artifacts
    
    # Deploy each script
    local failed=0
    local deployed=0
    
    for script in "${scripts[@]}"; do
        if deploy_script "$script"; then
            ((deployed++))
        else
            ((failed++))
        fi
    done
    
    log "INFO" "=========================================="
    log "INFO" "Validando serviços após deploy..."
    log "INFO" "=========================================="
    
    # Validate each service
    local failed_validation=0
    for script in "${scripts[@]}"; do
        local script_base=$(basename "$script" .sh)
        if ! validate_service "$script_base"; then
            ((failed_validation++))
        fi
    done
    
    # Summary
    log "INFO" "=========================================="
    log "INFO" "RESUMO DO DEPLOYMENT"
    log "INFO" "=========================================="
    
    if [[ $failed -eq 0 ]]; then
        success "Deploy: $deployed/$deployed scripts instalados com sucesso"
    else
        error "Deploy: $deployed instalados, $failed falharam"
    fi
    
    if [[ $failed_validation -eq 0 ]]; then
        success "Validação: Todos os serviços estão active"
    else
        error "Validação: $failed_validation serviços não estão active"
    fi
    
    log "INFO" "Log completo: $LOG_FILE"
    
    if [[ $failed -gt 0 ]] || [[ $failed_validation -gt 0 ]]; then
        error "Deployment não foi completamente bem-sucedido"
        exit 1
    else
        success "Deployment completado com sucesso!"
        exit 0
    fi
}

main "$@"
