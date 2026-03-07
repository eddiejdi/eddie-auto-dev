# Quick Reference: Pipeline Dual-GPU

## ✅ Status Atual
- **GPU0 (RTX 2060)**: Processing final → Ativa + Otimizada (PL 140W)
- **GPU1 (GTX 1050)**: Context preprocessing → Ativa + Otimizada (PL 70W)
- **Proxy**: http://192.168.15.2:8512 → Operacional
- **Docs**: Ver [GPU_OPTIMIZATION_COMPLETE.md](docs/GPU_OPTIMIZATION_COMPLETE.md) para detalhes técnicos

## 🧪 Testar Manualmente

### Verifique GPU utilization
```bash
ssh homelab@192.168.15.2 "watch -n 1 nvidia-smi"
```

### Monitorar logs em tempo real
```bash
ssh homelab@192.168.15.2 "sudo journalctl -u llm-optimizer -f"
```

### Teste direto ao proxy
```bash
# Pequeno contexto (< 2K tokens) → GPU0
curl -X POST http://192.168.15.2:8512/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-coder:7b",
    "messages": [{"role": "user", "content": "O que é Python?"}],
    "stream": true
  }' | head -20

# Grande contexto (> 2K tokens) → GPU1 + GPU0
# (adaptando seu contexto maior)
```

## 📊 Como Funciona

### Fluxo de Decisão no Proxy
```
Request chega com stream=true
    ↓
Estima tokens = len(messages) / 4
    ↓
├─ < 2K tokens    → Direto GPU0 (rápido)
├─ 2-6K tokens    → GPU1 sumariza + GPU0 responde
└─ > 6K tokens    → GPU1 map-reduce + GPU0 responde
```

### Portas Ollama
- **:11434** - GPU0 (RTX 2060) qwen2.5-coder:7b
- **:11435** - GPU1 (GTX 1050) qwen3:1.7b

## 🔧 Ajustes

### Mudar thresholds (arquivo proxy)
```bash
ssh homelab@192.168.15.2
# Edit /home/homelab/llm-optimizer/llm_optimizer.py
STRATEGY_A_MAX = 2000    # tokens → GPU0 direto
STRATEGY_B_MAX = 6000    # tokens → GPU1 preprocess
# > STRATEGY_B_MAX → map-reduce
```

### Reiniciar proxy após mudanças
```bash
ssh homelab@192.168.15.2 "sudo systemctl restart llm-optimizer"
```

## 🚀 Próximas Features

- [ ] Teste com Cline (VS Code)
- [ ] Monitorar latência real
- [ ] Expandir para iGPU (Intel Iris)
- [ ] Dashboard Prometheus com métricas dual-GPU

## 📝 Logs Importantes

Verifique se você vê estas linhas nos logs:
```
/api/chat: direto GPU0 (X tokens, stream=True) → estratégia rápida
/api/chat: dual-GPU pipeline B (X tokens) → GPU1 + GPU0
/api/chat: map-reduce pipeline C (X tokens) → GPU1 chunks + GPU0
```

## ⚡ Performance Esperada

- **< 2K tokens**: ~2-3 seg (GPU0 direto)
- **2-6K tokens**: ~5-8 seg (GPU1 + GPU0)
- **> 6K tokens**: ~10-15 seg (map-reduce)

(Tempos variam com modelo e hardware)

## 🐛 Troubleshooting

| Problema | Solução |
|----------|---------|
| GPU1 não usa memória | Verifique thresholds, teste com > 2K tokens |
| Respostas lentas | Ajuste STRATEGY_A_MAX/STRATEGY_B_MAX |
| Proxy não responde | `sudo systemctl restart llm-optimizer` |
| GPU out of memory | Reduzir STRATEGY_B_MAX ou MAX_CTX_SIZE |

---

**Last Updated**: 2026-03-01 13:30 UTC
