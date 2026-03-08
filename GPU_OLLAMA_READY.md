# ✅ NVIDIA GPU + OLLAMA - CONFIGURAÇÃO CONCLUÍDA

**Data**: 27 de Fevereiro de 2026  
**GPU**: NVIDIA GeForce RTX 2060 SUPER  
**Driver**: 580.126.09  
**CUDA**: 13.0  
**Compute Capability**: 7.5 (Turing)  
**CPU**: Intel Core i9-9900T (8 cores / 16 threads)  

## 📊 Status

### ✓ Hardware Detectado
```
GPU: NVIDIA GeForce RTX 2060 SUPER
Memory: 8192 MiB
Bus ID: 00000000:02:00.0
PCI Slot: 02:00.0
Power Limit: 175W
```

### ✓ Software Instalado
- Driver NVIDIA 580.126.09
- CUDA Toolkit 13.0
- Ollama com suporte CUDA
- Kernel: 6.8.0-101 (com `iommu=off`)

## 🎯 Modelos Disponíveis

Os seguintes modelos estão carregados em Ollama e **agora usam GPU**:
- `qwen2.5-coder:7b` (4.6 GB)
- `qwen3:14b` (9.2 GB)

## 🚀 Como Usar

### 1. Teste Rápido com CURL
```bash
# No seu computador local
ssh homelab@192.168.15.2
curl -s http://localhost:11434/api/generate \
  -d '{"model":"qwen2.5-coder:7b","prompt":"1+1=","stream":false}' | python3 -m json.tool
```

### 2. Monitorar GPU em Tempo Real
```bash
# Execute no seu computador
bash /home/edenilson/shared-auto-dev/monitor_gpu_ollama.sh
```

### 3. Verificar Se GPU Está Sendo Used
```bash
# No homelab
nvidia-smi

# Deve mostrar processo `ollama` usando GPU se modelo estiver rodando
```

## ⚙️ Configurações Aplicadas

### Systemd Drop-ins para Ollama
```
/etc/systemd/system/ollama.service.d/
└── ollama-optimized.conf   # Config única consolidada
```

### Variáveis de Ambiente
```bash
# CPU Threading (i9-9900T: cores 0-2 livres para SO; Ollama restrito por CPUAffinity)
CPUAffinity=3-15                # 13 threads para Ollama; 0-2 para SO e serviços leves
GGML_NUM_THREADS=10             # 10 threads compute
OMP_PROC_BIND=spread            # Distribui uniformemente entre cores
OMP_PLACES=threads              # Cada thread em HW thread diferente
GOMAXPROCS=6                    # Go runtime: 6 cores físicos

# GPU (RTX 2060 SUPER 8GB - Turing CC 7.5)
CUDA_VISIBLE_DEVICES=0          # Use GPU 0
OLLAMA_NUM_GPU=999              # Offload máximo para VRAM
OLLAMA_FLASH_ATTENTION=true     # Otimizar attention

# Inference
OLLAMA_NUM_PARALLEL=2           # 2 requests simultâneos
OLLAMA_CONTEXT_LENGTH=32768     # Contexto estendido (Cline)
OLLAMA_KV_CACHE_TYPE=q8_0       # Cache quantizado
OLLAMA_MAX_LOADED_MODELS=1      # 1 modelo na VRAM
OLLAMA_KEEP_ALIVE=30m           # Manter modelo 30min
```

### Kernel Parameters
```bash
# GRUB: /etc/default/grub
GRUB_CMDLINE_LINUX_DEFAULT=" pci=realloc iommu=off"
# NOTA: isolcpus=0-1 foi REMOVIDO em 2026-03-01 (cores 0-2 agora disponíveis para o scheduler)
# Separação Ollama ↔ SO garantida apenas por CPUAffinity=3-15 nos drop-ins systemd
```

## 📈 Performance Esperado

Com RTX 2060 SUPER (8GB VRAM):
- **VRAM**: ~7.5 GB utilizáveis (modelos até 14B Q4_K_M cabem)
- **Inference Speed**: ~31 tokens/sec (qwen2.5-coder:7b), ~20 tok/s (qwen3:14b)
- **CPU Distribution**: uniforme em cores 3-15 (ondas simétricas no btop)
- **Latency**: ~200-500ms por token (modelos locais com GPU offload)

## 🔧 Troubleshooting

### GPU não aparece em `nvidia-smi`
```bash
# No homelab, como root:
sudo systemctl restart ollama
nvidia-smi
sudo dmesg | tail -20 | grep -i nvidia
```

### Ollama não usa GPU mesmo configurado
```bash
# Forçar detecção:
sudo systemctl stop ollama
unset CUDA_VISIBLE_DEVICES
sudo systemctl start ollama

# Verificar logs:
journalctl -u ollama -f
```

### Muita latência (GPU não acelerando)
```bash
# Verificar se GPU está em uso:
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
# Se 0% utilization durante inferência = problema
# Tente modelo menor:
curl -s http://localhost:11434/api/tags | python3 -m json.tool
```

## 📁 Arquivos de Referência

- [install_nvidia_cuda.sh](install_nvidia_cuda.sh) - Script de instalação
- [monitor_gpu_ollama.sh](monitor_gpu_ollama.sh) - Monitor de GPU
- [GTX1050_SUCCESS.txt](GTX1050_SUCCESS.txt) - Relatório de sucesso

## 🎓 Próximos Passos

1. **Fine-tune modelos**: Use GPU para treinamento de embeddings
2. **Multi-model inference**: Carregue múltiplos modelos simultaneamente
3. **Batch processing**: Processe vários prompts em paralelo
4. **Model optimization**: Quantizar modelos para melhor performance

---

**Status**: ✅ PRONTO PARA PRODUÇÃO  
**Última atualização**: 2026-02-28 02:30 UTC  
**Config**: ollama-optimized.conf (consolidado) — CPU spread + GPU offload
