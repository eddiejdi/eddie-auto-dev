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

**Deploy concluído:** 2026-08-02  
**PR:** https://github.com/eddiejdi/eddie-auto-dev/pull/296

## ⚠️ Upgrade Ollama — Incidente 2026-08-02

**Tentativa de upgrade para v0.32.5:** ❌ Falhou

O binário canário disponível estava incompleto — faltava o `llama-server`:
```
error starting llama-server: llama-server binary not found
```

**Ação tomada:** Rollback automático para v0.17.6 ✅

**Lições aprendidas:**
- Não usar binários canary/incompletos em produção
- Validar integridade dos arquivos antes de substituir
- Script `upgrade-ollama.sh` precisa verificar presença de `llama-server` pós-download

**Próxima tentativa:** Baixar release oficial completa do GitHub (tarball completo, não build local).

## ✅ Upgrade Ollama v0.32.5 — Concluído 2026-08-03

**Causa raiz do incidente anterior:** não era a versão em si — era um binário canário/local incompleto usado nos primeiros testes. O asset oficial `ollama-linux-amd64.tar.zst` da release `v0.32.5` no GitHub é válido e completo (1.42GB, `sha256` consistente, inclui `bin/ollama` + `lib/ollama/*.so`, com CUDA `cuda_v12`/`cuda_v13` e Vulkan). URLs assinadas do GitHub (`release-assets.githubusercontent.com`) expiram em ~1h — downloads muito lentos podem falhar por expiração da URL, não por asset inexistente.

**Descoberta importante:** desde ~v0.31, o Ollama usa layout de biblioteca dividida (`bin/ollama` dinamicamente ligado a `lib/ollama/*.so`), igual ao que já existia em produção em `/usr/local/lib/ollama/`. Não é mais um binário estático único — **substituir só `/usr/local/bin/ollama` sem sincronizar `/usr/local/lib/ollama/` quebra o serviço**.

**Processo de validação usado (nenhuma etapa pulada):**
1. Validado via GitHub API que o asset `ollama-linux-amd64.tar.zst` da v0.32.5 existe e tem `content-length` correto
2. Download completo no servidor (1.422.353.729 bytes, batendo exato com o header) — versões anteriores tinham sido interrompidas por timeout/URL expirada
3. Extraído e validado: binários são ELF válidos, `llama-server` presente (o incidente anterior tinha binário canário sem esse arquivo)
4. **Testado isolado** (porta 11439, `systemd-run`/processo à parte, sem tocar produção) — `LFM2.5-VL-450M` carregou e gerou texto corretamente (erro `output_norm` ausente da v0.17.6 confirmado resolvido)
5. **Aplicado em produção com cautela em 2 etapas:**
   - Backup completo de `/usr/local/bin/ollama` + `/usr/local/lib/ollama/` (4.3GB) antes de qualquer mudança
   - Binário trocado via `mv` atômico (evita erro `Text file busy` ao trocar arquivo em uso por processo já rodando)
   - **GPU1 primeiro** (não-crítico): reiniciado, validado `lfm2.5-fast:gpu1` (produção) intacto, depois `LFM2.5-VL-450M` testado com CUDA real — funcionando
   - **GPU0 por último** (trading-analyst ao vivo): checada exposição de trading antes (posição pequena ~$47, 0 trades em 7d, modo shadow) — reiniciado, `trading-analyst` recarregou em VRAM (~25s de load) e respondeu corretamente

**Status final (2026-08-03 08:52 -03):**

| Serviço | Versão | Status |
|---------|--------|--------|
| ollama (GPU0, RTX 3060) | v0.32.5 | ✅ `trading-analyst` residente, respondendo |
| ollama-gpu1 (GTX 1050) | v0.32.5 | ✅ `lfm2.5-fast:gpu1` residente + `LFM2.5-VL-450M` testado |
| ollama-gpu-coordinator | — | ✅ saudável, 3 endpoints ativos |

**Backup para rollback (se necessário):**
```bash
sudo cp /usr/local/bin/ollama.backup.pre_v0325_20260803_084135 /usr/local/bin/ollama
sudo rsync -a --delete /usr/local/lib/ollama.backup.pre_v0325_20260803_084135/ /usr/local/lib/ollama/
sudo systemctl restart ollama ollama-gpu1
```

**Pendência:** `LFM2.5-VL-450M` ainda não está integrado como substituto do Moondream no fluxo de análise de imagem do Telegram — só foi validado tecnicamente. Isso é trabalho futuro separado.

**Próxima revisão:** integrar VL-450M no pipeline de imagens do Telegram substituindo Moondream.
