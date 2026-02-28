#!/bin/bash
# Fix: Ollama volta para CPU após reinício
# Causa: módulos NVIDIA não carregam automaticamente + nvidia-persistenced ausente
# Executar como: sudo bash fix_ollama_gpu_persistence.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[FIX]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERR]${NC} $1"; }

echo "============================================================"
echo "  Fix: Ollama GPU persistence após reboot"
echo "============================================================"
echo ""

# ---------- DIAGNÓSTICO RÁPIDO ----------
echo "=== DIAGNÓSTICO ATUAL ==="

echo -n "  nvidia-smi disponível: "
if command -v nvidia-smi &>/dev/null; then
    echo "✅"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>/dev/null || true
else
    err "✗ nvidia-smi não encontrado! Drivers podem não estar instalados."
fi

echo ""
echo -n "  Módulos NVIDIA carregados: "
if lsmod | grep -q "^nvidia "; then
    echo "✅ $(lsmod | grep '^nvidia' | awk '{print $1}' | tr '\n' ' ')"
else
    warn "✗ Módulos NVIDIA NÃO estão carregados"
fi

echo ""
echo -n "  nvidia-persistenced: "
if systemctl is-active --quiet nvidia-persistenced 2>/dev/null; then
    echo "✅ ativo"
else
    warn "✗ desabilitado ou inativo"
fi

echo ""
echo -n "  libcuda.so localização: "
LIBCUDA_PATH=$(ldconfig -p 2>/dev/null | grep "libcuda.so" | head -1 | awk '{print $NF}')
if [ -n "$LIBCUDA_PATH" ]; then
    echo "✅ $LIBCUDA_PATH"
    LIBCUDA_DIR=$(dirname "$LIBCUDA_PATH")
else
    warn "✗ libcuda.so não encontrado no ldconfig"
    LIBCUDA_DIR="/usr/lib/x86_64-linux-gnu"
fi

echo ""
echo -n "  DKMS status: "
if command -v dkms &>/dev/null; then
    DKMS_OUT=$(dkms status 2>/dev/null | grep nvidia | head -3)
    if echo "$DKMS_OUT" | grep -q "installed"; then
        echo "✅"
    else
        warn "Possível problema: $DKMS_OUT"
    fi
else
    warn "dkms não instalado"
fi

echo ""
echo ""

# ---------- FIX 1: Auto-load de módulos NVIDIA no boot ----------
log "FIX 1/4: Configurar auto-load de módulos NVIDIA"

if [ ! -f /etc/modules-load.d/nvidia.conf ]; then
    tee /etc/modules-load.d/nvidia.conf > /dev/null <<'EOF'
# Carrega módulos NVIDIA automaticamente no boot
nvidia
nvidia_uvm
nvidia_drm
nvidia_modeset
EOF
    log "  → /etc/modules-load.d/nvidia.conf criado"
else
    log "  → /etc/modules-load.d/nvidia.conf já existe (mantido)"
    cat /etc/modules-load.d/nvidia.conf
fi

# ---------- FIX 2: nvidia-persistenced ----------
log "FIX 2/4: Habilitar nvidia-persistenced"

if command -v nvidia-persistenced &>/dev/null; then
    systemctl enable --now nvidia-persistenced 2>/dev/null && \
        log "  → nvidia-persistenced habilitado e iniciado" || \
        warn "  → Falha ao iniciar nvidia-persistenced"
else
    warn "  → nvidia-persistenced não encontrado; pulando"
    warn "    Instale com: sudo apt install nvidia-utils-$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | cut -d. -f1 || echo '550')"
fi

# ---------- FIX 3: Corrigir LD_LIBRARY_PATH no drop-in cuda.conf ----------
log "FIX 3/4: Corrigir caminhos de biblioteca CUDA no Ollama"

mkdir -p /etc/systemd/system/ollama.service.d

# Detectar caminho CUDA real
CUDA_LIB=""
for p in /usr/local/cuda/lib64 /usr/lib/x86_64-linux-gnu /usr/local/lib/x86_64-linux-gnu; do
    if ls "$p"/libcuda.so* &>/dev/null 2>&1; then
        CUDA_LIB="$p"
        break
    fi
done

# Fallback para diretório onde ldconfig encontrou
[ -z "$CUDA_LIB" ] && CUDA_LIB="$LIBCUDA_DIR"
[ -z "$CUDA_LIB" ] && CUDA_LIB="/usr/lib/x86_64-linux-gnu"

log "  → Caminho CUDA detectado: $CUDA_LIB"

tee /etc/systemd/system/ollama.service.d/cuda.conf > /dev/null <<EOF
# Auto-gerado por fix_ollama_gpu_persistence.sh em $(date)
[Service]
Environment="PATH=/usr/local/cuda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="LD_LIBRARY_PATH=/usr/local/cuda/lib64:${CUDA_LIB}:/usr/lib/x86_64-linux-gnu"
Environment="CUDA_VISIBLE_DEVICES=0"
Environment="CUDA_HOME=/usr/local/cuda"
EOF

log "  → cuda.conf atualizado com caminho correto"

# ---------- FIX 4: Dependência do ollama em nvidia-persistenced ----------
log "FIX 4/4: Adicionar dependência Ollama → nvidia-persistenced"

tee /etc/systemd/system/ollama.service.d/gpu-dependency.conf > /dev/null <<'EOF'
# Garante que GPU está pronta antes do Ollama subir
[Unit]
After=nvidia-persistenced.service
Wants=nvidia-persistenced.service
EOF

log "  → gpu-dependency.conf criado"

# ---------- Criar ollama-optimized.conf consolidado ----------
log "FIX 5/5: Criar config otimizada consolidada (i9-9900T + RTX 2060 SUPER)"

# Remove drop-ins antigos que conflitam
for OLD_DROPIN in force-cuda.conf gpu.conf override.conf cpuaffinity.conf network.conf; do
    if [ -f "/etc/systemd/system/ollama.service.d/$OLD_DROPIN" ]; then
        mv "/etc/systemd/system/ollama.service.d/$OLD_DROPIN" \
           "/etc/systemd/system/ollama.service.d/backup-$(date +%F)/$OLD_DROPIN.bak" 2>/dev/null || true
        log "  → Movido $OLD_DROPIN para backup"
    fi
done

tee /etc/systemd/system/ollama.service.d/ollama-optimized.conf > /dev/null <<'EOF'
[Unit]
After=network-online.target basic.target

[Service]
# Cores 0-1 reservados para SO; Ollama usa 2-15 (14 threads / 6 cores completos + HT)
CPUAffinity=2-15
Type=simple
Restart=always
RestartSec=5

# THREAD DISTRIBUTION - 10 threads compute (14 disponiveis - 4 para GPU driver/CUDA)
Environment=GGML_NUM_THREADS=10
Environment=OLLAMA_NUM_THREADS=10
Environment=OMP_NUM_THREADS=10
Environment=OMP_THREAD_LIMIT=14
Environment=MKL_NUM_THREADS=10
Environment=OPENBLAS_NUM_THREADS=10

# SPREAD threads uniformemente entre cores (evita assimetria)
Environment=OMP_PROC_BIND=spread
Environment=OMP_PLACES=threads
Environment=GOMP_CPU_AFFINITY=2-15
Environment=GOMAXPROCS=6

# GPU MODE (RTX 2060 SUPER 8GB - Turing CC 7.5)
Environment=OLLAMA_NUM_GPU=999
Environment=CUDA_VISIBLE_DEVICES=0
Environment=OLLAMA_HOST=0.0.0.0:11434
Environment=OLLAMA_LOAD_TIMEOUT=15m
Environment=OLLAMA_KEEP_ALIVE=30m

# CONTEXTO DINÂMICO — controlado per-request via num_ctx nas options da API
# NÃO definir OLLAMA_CONTEXT_LENGTH aqui; cada chamada envia seu próprio num_ctx
# (ver specialized_agents/config.py → get_dynamic_num_ctx)
Environment=OLLAMA_KV_CACHE_TYPE=q8_0
Environment=OLLAMA_FLASH_ATTENTION=true
Environment=OLLAMA_NUM_PARALLEL=2
Environment=OLLAMA_MAX_LOADED_MODELS=1

ExecStart=
ExecStart=/usr/local/bin/ollama serve
EOF
log "  → ollama-optimized.conf criado"

# ---------- Aplicar e reiniciar ----------
echo ""
log "Recarregando systemd e reiniciando Ollama..."
systemctl daemon-reload
systemctl restart ollama
sleep 5

# ---------- Validação final ----------
echo ""
echo "============================================================"
echo "=== VALIDAÇÃO PÓS-FIX ==="
echo ""

echo -n "  Ollama status: "
if systemctl is-active --quiet ollama; then
    echo "✅ ativo"
else
    err "✗ Ollama não está rodando!"
    journalctl -u ollama -n 20 --no-pager
fi

echo ""
echo -n "  GPU detectada pelo Ollama: "
GPU_INFO=$(curl -s http://localhost:11434/api/ps 2>/dev/null || echo "{}")
if echo "$GPU_INFO" | grep -q "size_vram"; then
    echo "✅ GPU em uso"
    echo "$GPU_INFO" | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f'    {m[\"name\"]}: vram={m.get(\"size_vram\",0)}') for m in d.get('models',[])]" 2>/dev/null || true
else
    # Testar inferência rápida
    echo -n "  Testando inferência... "
    TEST_RESP=$(curl -s -m 30 http://localhost:11434/api/generate \
        -d '{"model":"qwen2.5-coder:7b","prompt":"say hi","stream":false}' 2>/dev/null || echo "")
    if echo "$TEST_RESP" | grep -q '"response"'; then
        echo "✅ Respondeu"
        # Checar load_duration vs prompt_eval_duration para inferir GPU vs CPU
        LOAD_DUR=$(echo "$TEST_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('load_duration',0))" 2>/dev/null || echo "0")
        EVAL_DUR=$(echo "$TEST_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('eval_duration',0))" 2>/dev/null || echo "0")
        TOKENS=$(echo "$TEST_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('eval_count',1))" 2>/dev/null || echo "1")
        if [ "$EVAL_DUR" -gt 0 ] 2>/dev/null; then
            TPS=$(python3 -c "print(round($TOKENS / ($EVAL_DUR / 1e9), 1))" 2>/dev/null || echo "?")
            echo "    Tokens/s: $TPS (>5 = GPU, <2 = CPU)"
        fi
    else
        warn "  Nenhum modelo carregado para teste"
    fi
fi

echo ""
echo -n "  Drop-ins aplicados: "
ls /etc/systemd/system/ollama.service.d/ | tr '\n' ' '
echo ""

echo ""
echo "============================================================"
echo "✅ Fix aplicado!"
echo ""
echo "PRÓXIMO PASSO: reiniciar o servidor para validar persistência:"
echo "  sudo reboot"
echo ""
echo "Após reboot, verificar GPU:"
echo "  nvidia-smi && curl -s http://localhost:11434/api/ps"
echo "============================================================"
