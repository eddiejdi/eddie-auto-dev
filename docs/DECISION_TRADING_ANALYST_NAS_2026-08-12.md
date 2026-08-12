# Decisão — Manter `trading-analyst:latest` no NAS (RTX 2060 SUPER)

**Data:** 2026-08-12
**Status:** ✅ Aceita
**Decisores:** Dono + agente de infraestrutura
**Escopo:** Roteamento/colocação do modelo `trading-analyst:latest` no cluster Ollama

---

## Contexto

O modelo `trading-analyst:latest` (base `llama3.1:8b`, Q4_K_M, ~5GB VRAM) está
residente na **RTX 2060 SUPER da NAS** (`192.168.15.4:11436`). A política 2b do
`AGENTS.md` presumia o analyst residente na **GPU0 (RTX 3060, 12GB)**, mas o
modelo **não existe** no catálogo da GPU0 (`:11434` só tem `trading-analyst-phi4`
e `phi4:14b`).

O coordinator roteia corretamente: `score()` devolve `inf` para endpoint que não
possui o modelo (`has_model_available`), então o NAS — único com
`trading-analyst:latest` — recebe o tráfego. **Não é bug**: é o comportamento
esperado dado o catálogo atual.

### Estado levantado em 2026-08-12

| Item | Valor |
|---|---|
| Modelo residente | `trading-analyst:latest` no NAS (`:11436`) |
| Tamanho em VRAM | 5987.5 MB (modelo 100% em VRAM, sem offload CPU) |
| GPU0 (RTX 3060) | 12GB livres, sem modelo residente |
| Decode medido no NAS | **63.5 tok/s** (estável) |
| Prefill medido no NAS | ~19-38k tok/s |
| RTT rede | ~0.3ms (mesmo switch) para GPU0 e NAS |

---

## Análise — Comparativo GPU0 (RTX 3060) vs NAS (RTX 2060 SUPER)

### Raciocínio

**Nenhuma diferença.** Mesmo modelo, mesmos pesos, mesmo Modelfile, mesmo prompt
→ saída idêntica. A GPU afeta apenas velocidade, não qualidade.

### Desempenho (aproximadamente neutro, com trade-off por fase)

| Fase | NAS (RTX 2060S, 448 GB/s) | GPU0 (RTX 3060, 360 GB/s) | Quem vence |
|---|---|---|---|
| Decode (geração) | 448 GB/s | 360 GB/s (−24%) | **NAS** (~10-15%) |
| Prefill (contexto) | 11.0 TF FP32 | 12.7 TF FP32 (Ampere) | **GPU0** |
| RTT rede | ~0.3ms | ~0.3ms | empate |

- Workload de trading usa `num_predict=256` (respostas curtas) → **decode
  domina** → mover para GPU0 seria **levemente mais lento** (~10%), não mais
  rápido.
- A RTX 2060 SUPER tem **24% mais bandwidth** (448 vs 360 GB/s), fator decisivo
  para inferência de modelo ~5GB que cabe inteiro em VRAM.

### Fatores a favor de manter no NAS

1. **Desempenho de geração**: decode ~10-15% mais rápido no NAS (bandwidth).
2. **Zero risco de migração**: evitar cold-load/criar o modelo na GPU0 em produção
   (trading live).
3. **Menos mudança de superfície**: nada a migrar; estado atual já funciona.

### Fatores a favor da GPU0 (e por que foram preteridos)

1. **Política 2b** presumia analyst na GPU0 — mas era uma premissa, não uma
   necessidade técnica.
2. **Headroom de VRAM**: GPU0 (12GB) deixaria ~6GB livres p/ auxiliares; no NAS
   sobram só ~2GB. → Mitigado: o coordinator já não roteia auxiliares para o
   endpoint onde o trading reside em pressão de VRAM, e `GPU_COORD_PROTECTED_MODELS`
   garante que o analyst nunca é despejado.
3. **GPU0 ociosa** → sem impacto operacional real (o tráfego auxiliar usa GPU1).

---

## Decisão

**Manter `trading-analyst:latest` residente no NAS (RTX 2060 SUPER, `:11436`).**

- Não criar/copiar o modelo para a GPU0.
- `trading-analyst` permanece protegido de eviction (`GPU_COORD_PROTECTED_MODELS`).
- A GPU0 continua disponível para tráfego pesado/agenda/auxiliares conforme o
  coordinator decidir (sem trading residente, ela volta ao pool normal).

---

## Consequências

- **Política 2b do AGENTS.md atualizada** (2026-08-12) para refletir que o
  analyst pode residir no NAS, não necessariamente na GPU0.
- O health check do MCP (`ollama_health`) agora reporta o modelo **residente**
  real via `/api/ps`, não o configurado — evita a falsa impressão de que
  `trading-analyst` está na GPU0.
- Painel Grafana "Ollama GPU Cluster" continua mostrando o estado real
  (modelo no NAS, GPU0 vazia).

## Revisitar quando

- A RTX 2060 SUPER da NAS apresentar pressão de VRAM recorrente ou degradação
  de latência (ver incidente
  `docs/INCIDENTS/2026-07-31_NAS_RTX2060_KEEPALIVE_FREEZE_AND_METRICS_CRASHLOOP.md`).
- O workload de trading mudar para respostas longas (prefill passa a dominar).
- A GPU0 ganhar mais bandwidth (upgrade de hardware) ou o NAS ficar sem folga.
