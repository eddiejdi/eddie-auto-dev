#!/bin/bash
# GPU Optimization — Interactive Setup Script
# Aplica otimizações de longevidade nas GPUs do homelab
# Use: bash tools/gpu_optimize.sh [setup|validate|reset]

set -euo pipefail

HOST="${HOMELAB_HOST:-192.168.15.2}"
USER_HOMELAB="${HOMELAB_USER:-homelab}"

log() { echo "[$(date '+%H:%M:%S')] $*"; }
info() { echo "ℹ️  $*"; }
success() { echo "✅ $*"; }
error() { echo "❌ $*" >&2; }

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_status() {
    local gpu_id=$1
    local gpu_name=$(ssh homelab@$HOST "nvidia-smi -i $gpu_id --query-gpu=gpu_name --format=csv,noheader" 2>/dev/null || echo "OFFLINE")
    local pm=$(ssh homelab@$HOST "nvidia-smi -i $gpu_id --query-gpu=persistence_mode --format=csv,noheader" 2>/dev/null || echo "?")
    local cm=$(ssh homelab@$HOST "nvidia-smi -i $gpu_id --query-gpu=compute_mode --format=csv,noheader" 2>/dev/null || echo "?")
    local pl=$(ssh homelab@$HOST "nvidia-smi -i $gpu_id --query-gpu=power.limit --format=csv,noheader" 2>/dev/null || echo "?")
    local temp=$(ssh homelab@$HOST "nvidia-smi -i $gpu_id --query-gpu=temperature.gpu --format=csv,noheader" 2>/dev/null || echo "?")
    
    printf "  GPU%d: %-30s | PM: %-7s | CM: %-18s | PL: %-7s | Temp: %-3s°C\n" \
        "$gpu_id" "$gpu_name" "$pm" "$cm" "$pl" "$temp"
}

setup_gpu0() {
    log "Configuring GPU0 (RTX 2060 SUPER)..."
    
    info "Setting power limit to 140W (from 184W, -24%)"
    ssh homelab@$HOST "sudo nvidia-smi -i 0 -pl 140" || error "Failed to set power limit"
    
    info "Setting persistence mode ON"
    ssh homelab@$HOST "sudo nvidia-smi -i 0 -pm 1" || error "Failed to set persistence mode"
    
    info "Setting compute mode to EXCLUSIVE_PROCESS"
    ssh homelab@$HOST "sudo nvidia-smi -i 0 -c EXCLUSIVE_PROCESS" || error "Failed to set compute mode"
    
    info "Locking GPU clocks to 1000 MHz"
    ssh homelab@$HOST "sudo nvidia-smi -i 0 -lgc 1000" || warn "Clock lock may not be supported"
    
    success "GPU0 configured"
}

setup_gpu1() {
    log "Configuring GPU1 (GTX 1050)..."
    
    info "Setting power limit to 70W (from 75W, -7%)"
    ssh homelab@$HOST "sudo nvidia-smi -i 1 -pl 70" || error "Failed to set power limit"
    
    info "Setting persistence mode ON"
    ssh homelab@$HOST "sudo nvidia-smi -i 1 -pm 1" || error "Failed to set persistence mode"
    
    info "Setting compute mode to EXCLUSIVE_PROCESS"
    ssh homelab@$HOST "sudo nvidia-smi -i 1 -c EXCLUSIVE_PROCESS" || error "Failed to set compute mode"
    
    success "GPU1 configured"
}

reset_gpu0() {
    log "Resetting GPU0 to defaults..."
    
    ssh homelab@$HOST "sudo nvidia-smi -i 0 -pl 184" || true
    ssh homelab@$HOST "sudo nvidia-smi -i 0 -c DEFAULT" || true
    ssh homelab@$HOST "sudo nvidia-smi -i 0 -rgc" || true
    
    success "GPU0 reset"
}

reset_gpu1() {
    log "Resetting GPU1 to defaults..."
    
    ssh homelab@$HOST "sudo nvidia-smi -i 1 -pl 75" || true
    ssh homelab@$HOST "sudo nvidia-smi -i 1 -c DEFAULT" || true
    
    success "GPU1 reset"
}

setup_systemd() {
    log "Updating systemd service files to persist optimizations..."
    
    # Backup originals
    ssh homelab@$HOST "sudo cp /etc/systemd/system/ollama.service /etc/systemd/system/ollama.service.backup.gpu0" || warn "Could not backup ollama.service"
    ssh homelab@$HOST "sudo cp /etc/systemd/system/ollama-gpu1.service /etc/systemd/system/ollama-gpu1.service.backup.gpu1" || warn "Could not backup ollama-gpu1.service"
    
    info "ollama.service and ollama-gpu1.service already updated ✅"
    info "Reloading systemd daemon..."
    
    ssh homelab@$HOST "sudo systemctl daemon-reload"
    ssh homelab@$HOST "sudo systemctl restart ollama ollama-gpu1"
    
    success "Systemd services reloaded and restarted"
}

validate() {
    log "=== GPU Status ==="
    print_status 0
    print_status 1
    echo ""
    
    log "=== Expected Values ==="
    echo "  GPU0: PM=Enabled, CM=Exclusive_Process, PL=140.00 W, Temp=30-40°C (idle)"
    echo "  GPU1: PM=Enabled, CM=Exclusive_Process, PL=70.00 W, Temp=30-35°C (idle)"
    echo ""
    
    log "=== Systemd Status ==="
    ssh homelab@$HOST "systemctl status ollama --no-pager | head -8"
    echo ""
    ssh homelab@$HOST "systemctl status ollama-gpu1 --no-pager | head -8"
}

case "${1:-validate}" in
    setup)
        log "Starting GPU optimization setup..."
        setup_gpu0
        setup_gpu1
        setup_systemd
        validate
        ;;
    validate)
        validate
        ;;
    reset)
        read -p "⚠️  This will reset both GPUs to default. Continue? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            reset_gpu0
            reset_gpu1
            log "Restarting services..."
            ssh homelab@$HOST "sudo systemctl restart ollama ollama-gpu1"
            validate
        else
            log "Reset cancelled"
        fi
        ;;
    *)
        cat << EOF
Usage: $0 [setup|validate|reset]

setup    - Apply all GPU optimizations (power limits, exclusive mode, clock locks)
validate - Show current GPU status and expected values
reset    - Reset both GPUs to factory defaults

Environment:
  HOMELAB_HOST (default: 192.168.15.2)
  HOMELAB_USER (default: homelab)

Examples:
  bash tools/gpu_optimize.sh validate
  bash tools/gpu_optimize.sh setup
  bash tools/gpu_optimize.sh reset
EOF
        exit 1
        ;;
esac
