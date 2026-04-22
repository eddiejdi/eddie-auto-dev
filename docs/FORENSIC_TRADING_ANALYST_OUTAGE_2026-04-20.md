# Relatório Forense — Outage trading-analyst GPU0
**Data do incidente:** 2026-04-18 → 2026-04-20  
**Resolvido:** 2026-04-20 14:13  
**Autor:** Infrastructure Agent  

---

## Resumo Executivo

O agente `crypto-agent@BTC_USDT_*.service` operou com **404 em loop** por ~2 dias porque o modelo Ollama `trading-analyst` foi referenciado em configuração mas **nunca provisionado** no servidor GPU0 (`:11434`). O fallback foi `qwen3:0.6b` sem prompt especializado.

---

## Timeline Forense

| Data/Hora | Evento | Evidência |
|-----------|--------|-----------|
| **2026-04-07 10:47** | `/etc/systemd/system/crypto-agent@.service.d/common.conf` criado com `EnvironmentFile=/etc/crypto-agent/models.env` | `stat Birth: 2026-04-07 10:47` |
| **2026-04-07 10:50** | `/etc/crypto-agent/` dir criado | `stat Birth: 2026-04-07 10:50` |
| **2026-04-07 13:57** | Commit `692e3c85` — `wikijs_configure.py` já referencia `trading-analyst` como modelo pretendido | `git show 692e3c85` |
| **2026-04-16 13:06** | Commit `11d46354` (Infrastructure Agent) — "Refine trading runtime and deploy profiles" — `trading_agent.py` adota `OLLAMA_PLAN_MODEL` via env var | `git log -S OLLAMA_PLAN_MODEL` |
| **2026-04-16 20:53** | `/etc/crypto-agent/models.env` **recriado** com `OLLAMA_PLAN_MODEL=trading-analyst` | `stat Birth: 2026-04-16 20:53` |
| **2026-04-16 21:13** | `models.env` ajustado (modificação) | `stat Modify` |
| **2026-04-18 18:26** | Agente inicializa — primeira evidência no journal | `journalctl -u crypto-agent@BTC_USDT_conservative` |
| **2026-04-18 19:46** | Ollama GPU0: `Load failed sha256-a3de86cd...` (GPU discovery timeout — bug independente) | `journalctl -u ollama.service` |
| **2026-04-19 00:09→23:45** | Ollama reiniciado ~15x (bug GPU discovery timeout) | `journalctl -u ollama.service` |
| **2026-04-20 07:31** | Agente reinicia — 404 persiste (`trading-analyst` not found) | `journalctl` PID 1781998 |
| **2026-04-20 14:13** | **FIX**: `trading-analyst` criado via Modelfile (base: `qwen3:0.6b`) | `git c163d82f` |

---

## Causa-Raiz Identificada

### Agente causador
**`Infrastructure Agent <agent@shared-auto-dev>`** — commit `11d46354` (2026-04-16 13:06)

### Sequência de falha

```
1. Apr 7  → common.conf instalado: EnvironmentFile=/etc/crypto-agent/models.env
              (provavelmente com phi4-mini ou qwen3 como modelo inicial)

2. Apr 16 13:06 → commit 11d46354:
   - trading_agent.py refatorado para usar OLLAMA_PLAN_MODEL env var
   - default no código: "phi4-mini:latest"
   - env var sobrescreve via models.env

3. Apr 16 20:53 → models.env recriado por root com:
   OLLAMA_PRIMARY_MODEL=trading-analyst
   OLLAMA_PLAN_MODEL=trading-analyst
   OLLAMA_TRADE_PARAMS_MODEL=trading-analyst
   OLLAMA_TRADE_WINDOW_MODEL=trading-analyst
   ⚠️  SEM executar: ollama create trading-analyst

4. Apr 18+ → Agent hits 404 em loop:
   POST /api/generate → {"error":"model 'trading-analyst' not found"}
   Fallback: qwen3:0.6b (sem prompt especializado de trading)

5. Apr 20 14:13 → FIX: models/Modelfile.trading-analyst criado e aplicado
```

### Componente com defeito

O **workflow de deploy** que escreve `models.env` não inclui validação de que o modelo referenciado existe no Ollama. Esta é uma **gap de provisionamento**: config-first sem model-first.

---

## Evidências Físicas

```bash
# /etc/systemd/system/crypto-agent@.service.d/common.conf
# Centralizado: edite /etc/crypto-agent/models.env para trocar modelos
EnvironmentFile=/etc/crypto-agent/models.env   ← ignore_errors=no (fatal se missing)

# /etc/crypto-agent/models.env (criado Apr 16 20:53 por root)
OLLAMA_PRIMARY_MODEL=trading-analyst
OLLAMA_PLAN_MODEL=trading-analyst
OLLAMA_TRADE_PARAMS_MODEL=trading-analyst
OLLAMA_TRADE_WINDOW_MODEL=trading-analyst
OLLAMA_TRADE_PARAMS_CONSERVATIVE_MODEL=qwen3:0.6b
OLLAMA_TRADE_PARAMS_FALLBACK_MODEL=qwen3:0.6b
OLLAMA_TRADE_WINDOW_FALLBACK_MODEL=qwen3:0.6b

# trading_agent.py linha 1147
_OLLAMA_PLAN_MODEL = os.getenv("OLLAMA_PLAN_MODEL", "phi4-mini:latest")
#                                                     ↑ fallback hardcoded (não trading-analyst)
```

---

## Fix Aplicado

```bash
# 1. Modelfile criado
cat models/Modelfile.trading-analyst
# FROM qwen3:0.6b
# SYSTEM """Trading analyst especializado ..."""

# 2. Modelo criado no GPU0
ollama create trading-analyst -f models/Modelfile.trading-analyst
# → cb235fdfb19e, 522MB

# 3. Confirmação
curl http://192.168.15.2:11434/api/generate -d '{"model":"trading-analyst","prompt":"ok","stream":false}'
# → 200 OK
```

---

## Ações Preventivas

### 1. Adicionar validação no deploy script

O `scripts/deploy_btc_trading_profiles.sh` deve verificar o modelo antes de iniciar o agente:

```bash
validate_ollama_model() {
  local host="${1:-http://192.168.15.2:11434}"
  local model
  model="$(grep '^OLLAMA_PLAN_MODEL=' /etc/crypto-agent/models.env | cut -d= -f2)"
  if ! curl -sf "${host}/api/tags" | python3 -c "
import sys,json
models=[m['name'].split(':')[0] for m in json.load(sys.stdin)['models']]
sys.exit(0 if '${model}'.split(':')[0] in models else 1)"; then
    echo "❌ Modelo '${model}' não encontrado no Ollama ${host}" >&2
    echo "   Execute: ollama create ${model} -f models/Modelfile.${model}" >&2
    exit 1
  fi
  echo "✅ Ollama model '${model}' verificado"
}
```

### 2. models.env deve ser atômico com Modelfile

Toda alteração de `OLLAMA_PLAN_MODEL` em `models.env` deve ter um Modelfile correspondente em `models/Modelfile.<nome>` e ser aplicada com:
```bash
ollama create <nome> -f models/Modelfile.<nome>
```

### 3. phi4-mini como próximo upgrade

```bash
# Verificar download em andamento:
screen -r phi4mini_pull
# Após download:
# Atualizar models.env para phi4-mini:latest (mais capaz que qwen3:0.6b)
```

---

## Estado Atual (pós-fix)

```
GPU0 (:11434): trading-analyst:latest → 200 OK ✅
GPU1 (:11435): qwen3:0.6b (fallback) ✅
phi4-mini: download em andamento (screen -r phi4mini_pull)
Agentes: crypto-agent@BTC_USDT_conservative/aggressive → funcionais
```
