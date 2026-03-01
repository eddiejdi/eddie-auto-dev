# Trading Agent Self-Healing com Ollama 🤖

Sistema de monitoramento e recuperação automática para os 6 trading agents (BTC, ETH, XRP, SOL, DOGE, ADA) usando detecção inteligente de stalls via Ollama LLM.

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRADING AGENTS (6x)                          │
│  ✅ crypto-agent@BTC_USDT (port 9092)                           │
│  ✅ crypto-agent@ETH_USDT (port 9093)                           │
│  ✅ crypto-agent@XRP_USDT (port 9094)                           │
│  ✅ crypto-agent@SOL_USDT (port 9095)                           │
│  ✅ crypto-agent@DOGE_USDT (port 9096)                          │
│  ✅ crypto-agent@ADA_USDT (port 9097)                           │
│                                                                  │
│  ├─ Writes: PostgreSQL (btc.decisions, btc.trades)             │
│  └─ Heartbeat: /tmp/crypto_agent_BTC_USDT_heartbeat (epoch)    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│               PROMETHEUS EXPORTERS (6x + 1 Selfheal)            │
│  📊 crypto-exporter@BTC_USDT (9092/metrics)                      │
│  📊 crypto-exporter@ETH_USDT (9093/metrics)                      │
│  ...                                                             │
│  🔧 trading-selfheal-exporter (9120/metrics)                     │
│     ├─ Detects stalls via PostgreSQL queries                     │
│     ├─ Uses Ollama for root-cause analysis                      │
│     └─ Auto-restarts via sudo systemctl restart               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│        OLLAMA LOCAL LLM (192.168.15.2:11434)                    │
│  🧠 qwen2.5-coder:7b — analyzes logs → root cause              │
│     ├─ Input: journalctl logs (last 50 lines)                   │
│     ├─ Output: {"cause": "...", "severity": "...", ...}        │
│     └─ Latency: ~5-15 sec for 2000-char analysis               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│            PROMETHEUS + ALERTMANAGER                            │
│  ✅ Scrape crypto-exporters:9092-9097 (every 15s)              │
│  ✅ Scrape trading-selfheal:9120 (every 15s)                   │
│  ✅ Evaluate alert_rules.yml (trading_agent_alerts group)      │
│  📢 Fire alerts on TradingAgentDown, TradingAgentStalled, etc.  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│              GRAFANA DASHBOARD                                   │
│  📈 Self-Healing Status Grid (6 coins)                          │
│  📊 Stall Detection Gauges (age of last decision)               │
│  📊 Restart History (counters per coin)                         │
│  📝 Audit Log (self-heal events in JSON)                        │
└─────────────────────────────────────────────────────────────────┘
```

## Como Funciona o Self-Healing

### 1. **Health Check (every 30 seconds)**

Para cada agent:
```
1. systemctl is-active crypto-agent@SYMBOL.service → Must be "active"
2. pgrep -f "trading_agent.py.*SYMBOL" → Process must be running
3. SELECT MAX(timestamp) FROM btc.decisions WHERE symbol=SYMBOL
   - If (now - last_decision) > 600s → STALLED
```

Se todas as 3 checks passam: **HEALTHY**
Se alguma falha: **consecutive_failures++**

### 2. **Ollama Diagnosis (after 2 consecutive failures)**

Antes de fazer restart, o self-healer:
```bash
1. Coleta últimas 50 linhas de logs via:
   journalctl -u crypto-agent@SYMBOL -n 50 --no-pager

2. Envia para Ollama com prompt:
   "Analyze these logs for {SYMBOL} and identify root cause of stall.
    Provide JSON: {cause, severity, action, explanation}"

3. Ollama processa (espera ~5-15s) e retorna:
   {"cause": "DB lock on decisions table", 
    "severity": "high",
    "action": "auto-restart",
    "explanation": "Cursor.execute blocked on DB lock"}

4. Log do resultado + incorpora no reason do restart:
   "SELF-HEAL: restarting BTC-USDT | reason: stalled (age=1500s) | Ollama: DB lock on decisions table"
```

### 3. **Auto-Restart (if needed)**

```bash
$ sudo systemctl restart crypto-agent@BTC_USDT.service
```

Com **rate limits**:
- Max 3 restarts/hora por agent
- Cooldown de 60s entre restarts
- Falhas >= 6 vezes → alerta crítico para intervenção manual

### 4. **Metrics + Alerting**

Métricas expostas (port 9120):
```
trading_agent_up{symbol="BTC-USDT"} = 1 (healthy) ou 0 (down)
trading_agent_stalled{symbol="BTC-USDT"} = 1 (no decisions) ou 0 (ok)
trading_agent_last_decision_age_seconds{symbol="BTC-USDT"} = 1523
trading_ollama_analyze_total{symbol="BTC-USDT"} = 5 (analyses done)
trading_ollama_analysis_latency_seconds{symbol="BTC-USDT"} = 8.2
trading_agent_restart_total{symbol="BTC-USDT"} = 2 (restarts)
trading_agent_consecutive_failures{symbol="BTC-USDT"} = 0
trading_selfheal_actions_total{action="restart", symbol="BTC-USDT"} = inc()
trading_selfheal_actions_total{action="ollama_error", symbol="BTC-USDT"} = inc()
```

**Alert Rules** (no Grafana):
- `TradingAgentDown` → red alert (3+ min down)
- `TradingAgentStalled` → yellow warning (5+ min stalled)
- `TradingDecisionsGap` → yellow (> 15 min without decision)
- `TradingSelfHealExhausted` → red (> 6 consecutive failures)
- `TradingOllamaAnalysisFailed` → yellow (LLM failures > 5 in 1h)

## Deploy

### Quick Start

```bash
cd /home/edenilson/eddie-auto-dev
bash btc_trading_agent/deploy_trading_selfheal.sh homelab@192.168.15.2
```

O script:
1. Cria `/var/lib/eddie/trading-heal/` no homelab
2. Copia `trading_selfheal_exporter.py` + config + systemd service
3. Instala dependências: `psycopg2-binary`, `prometheus_client`, `httpx`
4. Configura sudoers para permitir `sudo systemctl restart crypto-agent@*` sem senha
5. Atualiza `prometheus.yml` → adiciona jobs para crypto-exporters (9092-9097) e trading-selfheal (9120)
6. Atualiza `alert_rules.yml` → descomeenta grupo `trading_agent_alerts`
7. Inicia `systemctl start trading-selfheal-exporter`

### Verification

```bash
# 1. Check service status
ssh homelab@192.168.15.2 "sudo systemctl status trading-selfheal-exporter"

# 2. Check health endpoint
curl -s http://192.168.15.2:9121/status | jq

# 3. View recent events
curl -s http://192.168.15.2:9121/audit | jq '.[-10:]'

# 4. Verify Prometheus scraping
curl -s http://192.168.15.2:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="trading-selfheal" or .labels.job=="crypto-exporters")'

# 5. Check dashboard
open "https://grafana.rpa4all.com/d/237610b0-trading-agent-monitor"
```

## Environment Variables

Configure no `/etc/systemd/system/trading-selfheal-exporter.service`:

```bash
# Ollama integration
OLLAMA_ENABLED=true|false                           # default: true
OLLAMA_HOST=http://192.168.15.2:11434               # default
OLLAMA_MODEL=qwen2.5-coder:7b                       # default
OLLAMA_TIMEOUT=30                                   # seconds

# PostgreSQL (must match DB where trades/decisions are stored)
POSTGRES_HOST=192.168.15.2                          # homelab IP
POSTGRES_PORT=5433                                  # default
POSTGRES_USER=postgres
POSTGRES_PASSWORD=eddie_memory_2026
POSTGRES_DB=postgres

# Self-healing logic
TRADING_HEAL_INTERVAL=30                            # check interval (seconds)
TRADING_HEAL_STALL_THRESHOLD=600                    # 10 minutes = stalled
TRADING_HEAL_MAX_RESTARTS=3                         # per hour, per agent
TRADING_HEAL_COOLDOWN=60                            # seconds between restarts

# Data directory
TRADING_HEAL_DATA_DIR=/var/lib/eddie/trading-heal   # audit logs
```

Para modificar:
```bash
sudo systemctl edit trading-selfheal-exporter
# Editar Environment=...
sudo systemctl daemon-reload
sudo systemctl restart trading-selfheal-exporter
```

## Integração com Ollama

### Por que Ollama?

1. **Offline**: Não consome tokens cloud (Copilot/OpenAI)
2. **Rápido**: ~5-15s para analisar 50 linhas + estado do agente
3. **Inteligente**: Detecta automaticamente:
   - DB locks (psycopg2.OperationalError)
   - API timeouts (urllib timeout)
   - Deadlocks (transaction conflicts)
   - Thread stalls (RWLock contention)
   - Memory issues (OOM Killer)

### Exemplo de Análise

**Logs do agente**:
```
[2026-02-27 20:40:00] ❌ Loop error: psycopg2.OperationalError: while releasing the cursor
[2026-02-27 20:40:01] ⚠️ Trying to reconnect to DB...
[2026-02-27 20:40:05] ⚠️ Price unavailable (timeout)
[2026-02-27 20:40:10] ⚠️ Price unavailable (timeout)
[2026-02-27 20:41:00] ⚠️ Price unavailable (timeout)
```

**Ollama análise**:
```json
{
  "cause": "DB lock + network timeout",
  "severity": "high",
  "action": "auto-restart",
  "explanation": "Cursor locked on decisions table, API timeouts due to backoff. Restart recommended."
}
```

**Result**: Agent restarted com diagnóstico claro no audit log

### Desabilitar Ollama (fallback)

Se Ollama estiver down, o exporter:
1. Tenta análise, timeout após 30s
2. Incrementa métrica `trading_selfheal_actions_total{action="ollama_error"}`
3. **Continua com restart mesmo assim** (apenas sem diagnosis)
4. Logs: "WARNING: Ollama analysis error for BTC-USDT..."

## Logs e Audit

### Journalctl (systemd logs)

```bash
# Real-time logs
sudo journalctl -u trading-selfheal-exporter -f

# Last 100 lines
sudo journalctl -u trading-selfheal-exporter -n 100

# JSON format
sudo journalctl -u trading-selfheal-exporter -o json
```

### Audit Log (JSON Lines)

```bash
# View last 10 events
curl -s http://192.168.15.2:9121/audit | jq '.[-10:]'

# Filter restarts
curl -s http://192.168.15.2:9121/audit | jq '.[] | select(.action=="restart")'

# Filter Ollama analyses
curl -s http://192.168.15.2:9121/audit | jq '.[] | select(.action=="ollama_error")'

# File location
cat /var/lib/eddie/trading-heal/trading_heal_audit.jsonl | tail -20
```

### Event Types

```
action: "restart"        → Agent was restarted
action: "recovered"      → Agent recovered to healthy after failures
action: "rate_limited"   → Restart blocked due to rate limit
action: "ollama_error"   → Ollama analysis failed
```

## Troubleshooting

### Agent keeps restarting (loop)

```bash
# Check why it's failing
journalctl -u crypto-agent@BTC_USDT -n 50

# If rate_limited:
curl -s http://192.168.15.2:9121/audit | jq '.[] | select(.symbol=="BTC-USDT")'

# Check consecutive_failures in metrics
curl -s http://192.168.15.2:9120/metrics | grep consecutive_failures
```

### Ollama análysis slow or timing out

```bash
# Check Ollama health
curl -s http://192.168.15.2:11434/api/tags | jq

# Increase timeout
sudo systemctl edit trading-selfheal-exporter
# Add: Environment=OLLAMA_TIMEOUT=60
sudo systemctl restart trading-selfheal-exporter
```

### PostgreSQL connection fails

```bash
# Check PostgreSQL
psql -h 192.168.15.2 -p 5433 -U postgres -d postgres -c "SELECT 1"

# Verify DSN in service
systemctl cat trading-selfheal-exporter | grep POSTGRES
```

### Metrics not appearing in Prometheus

```bash
# Check if exporter is running
ss -tlnp | grep 9120

# Manually scrape
curl -s http://192.168.15.2:9120/metrics

# Check Prometheus scrape config
curl -s http://192.168.15.2:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="trading-selfheal")'
```

## Métricas Chave para Dashboard

### Status Grid (6 coins)

```promql
trading_agent_up{symbol=~"BTC|ETH|XRP|SOL|DOGE|ADA"}
```
Exibe: 🟢 (up=1) ou 🔴 (up=0)

### Stall Gauge (age of decisions)

```promql
trading_agent_last_decision_age_seconds{symbol="$symbol"}
```
Thresholds:
- 🟢 green: < 5 min
- 🟡 yellow: 5-10 min
- 🔴 red: > 10 min

### Restart Trend

```promql
increase(trading_agent_restart_total[1h])
```
Shows restart frequency

### Ollama Latency

```promql
trading_ollama_analysis_latency_seconds{symbol="$symbol"}
```
Average LLM analysis time

### Ollama Failures

```promql
increase(trading_selfheal_actions_total{action="ollama_error"}[1h])
```
Count of failed analyses

## Roadmap

- [ ] Integrar análise de memória + CPU antes de restart
- [ ] Callback para notificar via Telegram/WhatsApp em caso de repeated failures
- [ ] ML model para detectar padrão de stalls (temporal patterns)
- [ ] Multi-coin comparison: se N coins travaram ao mesmo tempo → problema global (API, DB, network)
- [ ] Graceful shutdown detection (agent stopping intentionally vs crashing)
- [ ] Heartbeat file fallback se PostgreSQL estiver down

## Referências

- [Ollama Documentation](https://ollama.ai)
- [Prometheus AlertRules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
- [Systemd Service Management](https://www.freedesktop.org/software/systemd/man/systemctl.html)
- [Trading Agent Codebase](./trading_agent.py)
