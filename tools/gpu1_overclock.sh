#!/usr/bin/env bash
# ============================================================
# GPU1 (GTX 1050) Performance Tuning — Headless Server
# ============================================================
# Aplica otimizações de longevidade e estabilidade na GTX 1050.
# OC de clock/VRAM NÃO disponível em servidor headless com
# driver nvidia 580 (nvidia-settings requer Xorg real).
#
# Uso:
#   sudo bash tools/gpu1_overclock.sh [apply|reset|status]
#
# Requer: nvidia-smi
# ============================================================

set -euo pipefail

GPU_ID=1
POWER_LIMIT=70      # Watts (de 75W TDP) — redução térmica para longevidade

ACTION="${1:-status}"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

show_status() {
    log "=== GTX 1050 (GPU $GPU_ID) Status ==="
    nvidia-smi -i "$GPU_ID" --query-gpu=gpu_name,temperature.gpu,clocks.gr,clocks.mem,clocks.max.gr,clocks.max.mem,memory.used,memory.total,power.limit,compute_mode,persistence_mode --format=csv,noheader
    echo ""
    nvidia-smi -i "$GPU_ID" --query-gpu=clocks.current.graphics,clocks.current.memory --format=csv,noheader 2>/dev/null || true
}

apply_oc() {
    log "Aplicando otimizações na GPU $GPU_ID (GTX 1050)..."

    # 1. Persistence mode
    log "  [1/3] Persistence mode ON"
    nvidia-smi -i "$GPU_ID" -pm 1

    # 2. Compute exclusive mode (só Ollama usa esta GPU)
    log "  [2/3] Compute exclusive mode"
    nvidia-smi -i "$GPU_ID" -c EXCLUSIVE_PROCESS 2>/dev/null || \
        log "  ⚠️  Compute mode já setado ou não suportado"

    # 3. Power limit (redução térmica para longevidade)
    log "  [3/3] Power limit: ${POWER_LIMIT}W (TDP: 75W)"
    nvidia-smi -i "$GPU_ID" -pl "$POWER_LIMIT" 2>/dev/null || \
        log "  ⚠️  Power limit não suportado nesta GPU"

    # NOTA: OC de clock/VRAM via nvidia-settings não funciona em
    # servidor headless com driver nvidia 580 — os atributos
    # GPUGraphicsClockOffset/GPUMemoryTransferRateOffset não são
    # expostos mesmo com coolbits=28. nvidia-smi -lgc/-ac também
    # não são suportados na GTX 1050 (Pascal consumer).

    echo ""
    log "✅ Otimizações aplicadas. Estado atual:"
    show_status
}

reset_oc() {
    log "Resetando GPU $GPU_ID para defaults..."

    nvidia-smi -i "$GPU_ID" -pl 75 2>/dev/null || true  # Reset power limit
    nvidia-smi -i "$GPU_ID" -c DEFAULT 2>/dev/null || true  # Reset compute mode

    log "✅ GPU reset para defaults"
    show_status
}

case "$ACTION" in
    apply)  apply_oc ;;
    reset)  reset_oc ;;
    status) show_status ;;
    *)
        echo "Uso: $0 [apply|reset|status]"
        exit 1
        ;;
esac
