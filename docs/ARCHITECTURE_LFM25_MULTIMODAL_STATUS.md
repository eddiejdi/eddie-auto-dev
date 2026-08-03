# Arquitetura Multimodal LFM2.5 — Status 2026-08-02

**Contexto:** Migrar de Moondream (alucina, ocupa GPU0 do trading) para uma arquitetura descentralizada usando a família LFM2.5 da Liquid AI.

## Objetivo final

```
┌─────────────────────────────────────────────────────────┐
│ Servidor 192.168.15.2 (32GB RAM + RTX 3060 + GTX 1050) │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  RTX 3060 (GPU0, 12GB)          GTX 1050 (GPU1, 2GB)   │
│  ├─ trading-analyst (intocável)  └─ Multimodal        │
│     (porta 11434 via coordinator)    ├─ LFM2.5-VL-450M │
│                                      └─ LFM2.5-Audio   │
│                                                         │
│  CPU (load alto, não viável)                           │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ NAS 192.168.15.4 (8GB RAM + RTX 2060 Super 8GB)        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  RTX 2060 (8GB VRAM, sobra)                            │
│  ├─ dolphin-2.9-llama3-8b (WhatsApp, KEEP_ALIVE=-1)    │
│  └─ [futuro] LFM2.5-Thinking (se RAM permitir)         │
│                                                         │
│  RAM: 8GB total, ~450MB disponíveis, SEM SWAP          │
│  ⚠️ Gargalo crítico — coordenador precisa consciência  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Decisões tomadas

| Item | Decisão | Justificativa |
|------|---------|---------------|
| **LFM2.5 em CPU** | ❌ Cancelado | Load average 13.87/16 threads; geração de 80 tokens não completou em 90s |
| **GTX 1050 para multimodal** | ✅ Confirmado | 2GB VRAM suficiente para VL-450M (~500MB) + Audio-1.5B (~1.5GB) |
| **NAS para VL/áudio** | ⚠️ Pendente RAM | VRAM sobra, mas RAM zerada sem swap = risco OOM em produção |
| **Soft-pin no coordenador** | ✅ Ativo (`GPU_COORD_SOFT_PIN=1`) | Permite spill entre GPUs se endpoint pinado estiver ocupado |
| **Trading exclusivo na GPU0** | ✅ Mantido (`GPU_COORD_TRADING_EXCLUSIVE_GPU0=1`) | Evita timeout do analyst quando agenda enche a GPU0 |

## Implementação concluída

### 1. Exporter de RAM para NAS

**Arquivos:**
- `tools/nas_ram_exporter.py` — HTTP server simples, lê `/proc/meminfo`
- `systemd/nas-ram-exporter.service` — unit systemd
- `scripts/deploy-nas-ram-exporter.sh` — deploy automatizado
- `docs/variables-taxonomy/NAS_RAM_EXPORTER.md` — documentação

**Endpoint:**
```bash
curl http://127.0.0.1:11447/ram
# {"mem_total_mb": 7999.2, "mem_available_mb": 450.3}
```

### 2. Coordenador com consciência de RAM

**Variáveis ambientais (adicionadas ao service file):**
```bash
Environment=OLLAMA_NAS_RAM_EXPORTER_HOST=http://192.168.15.4:11447
Environment=GPU_COORD_NAS_RAM_MARGIN_MB=400
Environment=GPU_COORD_NAS_RAM_MODEL_OVERHEAD_MB=500
Environment=GPU_COORD_NAS_MIN_FREE_RAM_MB=900
```

**Comportamento:**
- Polla RAM da NAS a cada 10s
- Se `ram_available < 900MB`, evicta proativamente maior modelo ocioso
- Antes de rotear `:nas`, garante `ram_available > needed + 400MB`
- Fail-open: se exporter cair, continua roteando (não bloqueia)

### 3. Scripts de teste e upgrade

- `scripts/test-gpu-coordinator-ram.sh` — valida sintaxe e testa exporter localmente
- `scripts/upgrade-ollama.sh` — download, backup, install, rollback automático

## Status atual

| Componente | Status | Observações |
|------------|--------|-------------|
| Exporter RAM | ✅ Pronto | Testado localmente, lendo corretamente |
| Coordenador | ✅ Atualizado | Código em `/workspace/eddie-auto-dev/tools/` |
| Service files | ✅ Criados | Aguardando deploy manual |
| NAS deployment | ⏳ Pendente | SSH não configurado, precisa deploy manual |
| Coordinator service | ⏳ Pendente | Precisa copiar service file e iniciar |
| Ollama upgrade | ⏳ Pendente | 0.17.6 → 0.32.5 para destravar VL-450M |
| GPU1 service | ⏳ Pendente | `ollama-gpu1.service` existe mas desabilitado |

## Próximos passos

### Immediato (hoje)

1. **Deploy manual na NAS** (requer acesso SSH/sudo):
   ```bash
   # Da workstation para 192.168.15.4
   scp /workspace/eddie-auto-dev/tools/nas_ram_exporter.py homelab@192.168.15.4:/apps/eddie-auto-dev/tools/
   scp /workspace/eddie-auto-dev/systemd/nas-ram-exporter.service homelab@192.168.15.4:/tmp/
   
   ssh homelab@192.168.15.4 <<'EOF'
   sudo mv /tmp/nas-ram-exporter.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now nas-ram-exporter
   curl -s http://127.0.0.1:11447/ram
   EOF
   ```

2. **Iniciar coordenador na workstation**:
   ```bash
   sudo cp /workspace/eddie-auto-dev/systemd/ollama-gpu-coordinator.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now ollama-gpu-coordinator
   journalctl -u ollama-gpu-coordinator -f
   ```

3. **Testar roteamento**:
   ```bash
   # Deveria rotar para GPU0 (trading) ou GPU1/NAS (auxiliares)
   curl -X POST http://127.0.0.1:11437/api/generate \
     -H "Content-Type: application/json" \
     -d '{"model":"lfm2.5:gpu1","prompt":"test","stream":false}'
   ```

### Curto prazo (esta semana)

4. **Upgrade Ollama** (destrava VL-450M):
   ```bash
   chmod +x /workspace/eddie-auto-dev/scripts/upgrade-ollama.sh
   sudo /workspace/eddie-auto-dev/scripts/upgrade-ollama.sh
   ```

5. **Pull e testar VL-450M**:
   ```bash
   ollama pull lm2.5-vl:450m
   ollama run lm2.5-vl:450m:gpu1 'descreva esta imagem' < caminho/para/imagem.jpg
   ```

6. **Ajustar keep-alive do WhatsApp na NAS** (opção B discutida):
   - Mudar `KEEP_ALIVE=-1` para `KEEP_ALIVE=20m` no `ollama-nas.service`
   - Permitir que VL/Thinking compartilhem slot quando WhatsApp está ocioso
   - Coordenador gerencia eviction por pressão de RAM

## Riscos mitigados

| Risco | Mitigação |
|-------|-----------|
| OOM na NAS ao carregar modelo novo | Exporter RAM + eviction proativa no coordenador |
| Trading afetado por auxiliares | `TRADING_EXCLUSIVE_GPU0=1` impede rota de agenda para GPU0 |
| Upgrade Ollama quebra produção | Script faz backup automático + rollback se health check falhar |
| Vulkan conflita com NVIDIA em 0.32.5 | Documentado; pode exportar `OLLAMA_VULKAN=0` se necessário |
| Exporter RAM cai | Fail-open no coordenador (continua roteando baseado em VRAM só) |

## Benchmarks anteriores (referência)

**LFM2.5-Instruct vs Thinking na GTX 1050 (Q4_0):**
- Velocidade: empate técnico (~32 tok/s)
- Matemática: ambos corretos, Thinking gasta 2.5× mais tokens pensando
- Extração JSON: Instruct vence (33 tokens vs loop infinito de deliberação)
- Ver `docs/BENCHMARK_LFM2.5_GPU1_2026-08-02.md`

**Conclusão:** manter `lfm2.5-fast` como default na GPU1; Thinking disponível para tarefas pontuais de raciocínio.

---

**Próxima revisão:** após deploy na NAS e teste do VL-450M (meta: 2026-08-05)
