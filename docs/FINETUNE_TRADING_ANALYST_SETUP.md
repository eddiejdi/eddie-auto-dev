# Setup: Fine-tuning automático do trading-analyst

## Visão geral

Pipeline automatizado que retreina o modelo `trading-analyst` (LLM) semanalmente:

```
Domingos 03:00 (timer systemd)
  │
  ▼
Dataset Builder (homelab, CPU)
  │  lê btc.llm_calls → gera JSONL
  ▼
Cópia para NAS (rsync)
  │
  ▼
QLoRA Training (NAS, RTX 2060 SUPER 8GB)
  │  llama3.1:8b base + LoRA 4-bit
  ▼
Merge + GGUF (NAS)
  │
  ▼
Import Ollama NAS
  │  trading-analyst-candidate:latest
  ▼
Validação (3 prompts de teste)
  │
  ▼
Relatório + pendente aprovação manual
```

## Pré-requisitos

### 1. venv na NAS (RTX 2060 SUPER)

```bash
# Na NAS (192.168.15.4)
ssh root@192.168.15.4

# Criar venv
python3 -m venv /opt/finetune-env
source /opt/finetune-env/bin/activate

# Instalar dependências (GPU)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install transformers>=4.45 peft bitsandbytes accelerate
pip install scipy datasets

# Verificar GPU
python3 -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

### 2. SSH key-based (homelab → NAS)

```bash
# No homelab
ssh-keygen -t ed25519 -f /var/lib/eddie/.ssh/id_ed25519 -N ""
ssh-copy-id -i /var/lib/eddie/.ssh/id_ed25519 root@192.168.15.4
```

### 3. Instalar systemd units

```bash
# No homelab
sudo cp systemd/trading-analyst-finetune.service /etc/systemd/system/
sudo cp systemd/trading-analyst-finetune.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable trading-analyst-finetune.timer
sudo systemctl start trading-analyst-finetune.timer
```

### 4. Env file

```bash
cp envfiles/trading-analyst-finetune.env.example /apps/crypto-trader/envfiles/trading-analyst-finetune.env
# Editar com valores reais se necessário
```

## Verificar status

```bash
# Timer
systemctl list-timers | grep trading-analyst

# Última execução
journalctl -u trading-analyst-finetune.service --since "7 days ago" | tail -30

# Executar manualmente
sudo systemctl start trading-analyst-finetune.service

# Dry-run (só dataset)
python3 scripts/trading_analyst_finetune_orchestrator.py --dry-run
```

## Promoção para produção

O pipeline NUNCA substitui o modelo em produção. Após validação:

1. Verificar logs: `journalctl -u trading-analyst-finetune`
2. Testar candidato manualmente: `curl http://192.168.15.4:11436/api/generate -d '{"model":"trading-analyst-candidate","prompt":"..."}'`
3. Aprovar via Telegram (approval gateway)
4. Promover:
   ```bash
   # Na NAS
   ollama cp trading-analyst-candidate:latest trading-analyst:latest
   ```

## Rollback

```bash
# Na NAS — reverter para versão anterior
# (tag anterior permanece no Ollama)
ollama cp trading-analyst:previous-tag trading-analyst:latest
```

## Troubleshooting

| Problema | Solução |
|----------|---------|
| "venv não encontrado" | Criar venv na NAS (seção 1) |
| "SSH key" | Configurar SSH key-based (seção 2) |
| "dados insuficientes" | Aguardar mais dados em btc.llm_calls (mínimo 120 samples) |
| "GPU indisponível" | Verificar `nvidia-smi` na NAS, matar processos conflitantes |
| "Ollama timeout" | Verificar Ollama rodando na NAS: `curl http://192.168.15.4:11436/api/tags` |
