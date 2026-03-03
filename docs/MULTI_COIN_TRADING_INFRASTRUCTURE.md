# Multi-Coin Trading Infrastructure — Guia Completo

**Data**: 2026-02-25 → 2026-03-03  
**Ambiente**: Homelab Production (192.168.15.2)  
**Status**: ✅ Operacional  
**Banco de dados**: PostgreSQL (eddie-postgres, porta 5433, database `btc_trading`) — **SQLite PROIBIDO**  

---

## 📋 Sumário

Infraestrutura multi-moeda do AutoCoinBot: 6 pares de criptomoedas operando com agentes independentes, exporters Prometheus dedicados e dashboard Grafana unificado com seletor dropdown.

---

## 🏗️ Arquitetura

```
┌────────────────────────────────────────────────────────────────┐
│                        HOMELAB (192.168.15.2)                  │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ trading_agent│  │ trading_agent│  │ trading_agent│  ...x6   │
│  │  --live      │  │  --config    │  │  --config    │         │
│  │  (BTC)       │  │  ETH_USDT    │  │  XRP_USDT    │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                 │                 │                  │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐         │
│  │  exporter    │  │  exporter    │  │  exporter    │  ...x6   │
│  │  :9092       │  │  :9098       │  │  :9094       │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                 │                 │                  │
│  ┌──────▼─────────────────▼─────────────────▼──────────────┐   │
│  │                    PROMETHEUS (:9090)                     │  │
│  │  jobs: autocoinbot-exporter, crypto-exporter-{coin}      │  │
│  └──────────────────────┬──────────────────────────────────┘   │
│                         │                                      │
│  ┌──────────────────────▼──────────────────────────────────┐   │
│  │                    GRAFANA (:3002)                        │  │
│  │  Dashboard: Trading Agent Monitor                        │  │
│  │  Dropdown: coin_job → filtra todos os painéis            │  │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                │
│  Acesso externo: https://grafana.rpa4all.com (via cloudflared) │
└────────────────────────────────────────────────────────────────┘
```

---

## 📊 Mapa de Portas e Jobs

| Moeda      | Exporter Port | API Port | Prometheus Job            | Config File            | Modo Atual |
|------------|:------------:|:--------:|---------------------------|------------------------|:----------:|
| **BTC-USDT** | 9092 | 8511 | `autocoinbot-exporter`     | `config.json`          | 🟢 LIVE    |
| **ETH-USDT** | 9098 | 8512 | `crypto-exporter-eth_usdt` | `config_ETH_USDT.json` | 🧪 DRY_RUN |
| **XRP-USDT** | 9094 | 8513 | `crypto-exporter-xrp_usdt` | `config_XRP_USDT.json` | 🧪 DRY_RUN |
| **SOL-USDT** | 9095 | 8514 | `crypto-exporter-sol_usdt` | `config_SOL_USDT.json` | 🧪 DRY_RUN |
| **DOGE-USDT**| 9096 | 8515 | `crypto-exporter-doge_usdt`| `config_DOGE_USDT.json`| 🧪 DRY_RUN |
| **ADA-USDT** | 9097 | 8516 | `crypto-exporter-ada_usdt` | `config_ADA_USDT.json` | 🧪 DRY_RUN |

**Localização base**: `/home/homelab/myClaude/btc_trading_agent/`

---

## 🖥️ Dashboard Grafana

### Arquivo provisionado
- **Único arquivo ativo**: `btc_trading_dashboard_v3_prometheus.json`
- **UID**: `237610b0-0eb1-4863-8832-835ee7d7338d`
- **Provisioning dir**: `/home/homelab/monitoring/grafana/provisioning/dashboards/`
- **Update interval**: 30 segundos

### Variável de template (dropdown)
```json
{
  "name": "coin_job",
  "type": "custom",
  "query": "BTC-USDT : autocoinbot-exporter, ETH-USDT : crypto-exporter-eth_usdt, ...",
  "current": { "text": "BTC-USDT", "value": "autocoinbot-exporter" }
}
```

### Convenções de query
- **Todas** as expressões Prometheus usam `{job="$coin_job"}`
- **Títulos** de painéis incluem `(${coin_job:text})` para mostrar a moeda selecionada
- **Título do dashboard**: `🤖 Trading Agent Monitor - ${coin_job:text}`
- **Legends** em painéis stat/gauge usam `legendFormat` descritivo

### Painel completo (44 expressões)
| Tipo | Qtd | Exemplo |
|------|-----|---------|
| stat | 19 | `btc_price{job="$coin_job"}`, `btc_trading_open_position_count`, `btc_trading_avg_entry_price` |
| timeseries | 6 | `btc_trading_equity_usdt{job="$coin_job"}` |
| piechart | 2 | `btc_trading_decisions_total{job="$coin_job", action="BUY"}` |
| table | 2 | `btc_trading_last_trade_info{job="$coin_job"}` |
| gauge | 1 | `btc_trading_rsi{job="$coin_job"}` |
| text | 1 | (header) |

---

## � Multi-Posição (Dollar-Cost Averaging)

> **Desde 2026-03-03**: O agente suporta acumular múltiplas entradas BUY antes de vender.

### Como funciona
1. **BUY #1**: Compra `max_position_pct / max_positions` do saldo USDT (ex: 20%/3 ≈ 6.67%)
2. **BUY #2**: Após cooldown (30min), se outro sinal BUY forte (>= 75% confiança) surgir, acumula. Preço médio ponderado é recalculado.
3. **BUY #3**: Terceira entrada → `position_count = max_positions` (limite atingido, bloqueia novos BUYs)
4. **SELL**: Vende **toda** a posição acumulada. PnL calculado contra o preço médio ponderado.

### Parâmetros em `config.json`
| Parâmetro | Default | Descrição |
|-----------|---------|------------|
| `max_positions` | 3 | Máximo de entradas BUY acumuladas |
| `max_position_pct` | 0.2 | % do saldo total alocável (dividido entre `max_positions`) |
| `min_confidence` | 0.75 | Confiança mínima para qualquer trade |
| `min_trade_interval` | 1800 | Cooldown entre trades (30min) |
| `max_daily_trades` | 3 | Máximo de ciclos (buy+sell) por dia |
| `max_daily_loss` | 50 | Perda diária máxima em USD |

### Estado do agente (`AgentState`)
```python
@dataclass
class AgentState:
    position: float = 0.0        # BTC total acumulado
    entry_price: float = 0.0     # Preço médio ponderado
    position_count: int = 0      # Número de entradas (BUYs) acumuladas
    entries: list = field(...)   # [{price, size, ts}] por entrada
```

### Preço médio ponderado
```
new_avg = (old_position * old_entry_price + new_size * new_price) / (old_position + new_size)
```

### Métricas Prometheus (novas)
| Métrica | Tipo | Descrição |
|---------|------|------------|
| `btc_trading_open_position_count` | gauge | Número de entradas BUY abertas (0 a max_positions) |
| `btc_trading_avg_entry_price` | gauge | Preço médio ponderado da posição aberta |

### Bootstrap (restart recovery)
Ao reiniciar, o agente reconstrói a multi-posição do DB: percorre os últimos trades até encontrar um SELL, e acumula todos os BUYs subsequentes como entradas abertas.

### SL/TP
Stop-loss e take-profit são calculados sobre o `entry_price` (preço médio ponderado). A venda no auto-exit é da posição **total** acumulada.

---

## �🔧 Prometheus Exporter

### Arquivo principal
`/home/homelab/myClaude/btc_trading_agent/prometheus_exporter.py`

### Banco de dados: PostgreSQL (NÃO SQLite)

> **⛔ REGRA ABSOLUTA**: O exporter conecta ao **PostgreSQL** via `psycopg2`.  
> O arquivo SQLite (`data/trading_agent.db`) existe mas está **OBSOLETO e DESATUALIZADO**.  
> **NUNCA** usar `import sqlite3` ou `sqlite3.connect()` no exporter ou em novos scripts de trading.

```python
# ✅ CORRETO — PostgreSQL
import psycopg2
PG_DSN = os.environ.get("DATABASE_URL", "postgresql://postgres:eddie_memory_2026@localhost:5433/postgres")
DB_SCHEMA = "btc"  # Tabelas: btc.trades, btc.decisions, btc.market_states, btc.performance_stats
conn = psycopg2.connect(PG_DSN)
conn.autocommit = True  # OBRIGATÓRIO — evita cascata de erros transacionais
cursor = conn.cursor()
cursor.execute(f"SET search_path TO {DB_SCHEMA}, public")

# ❌ PROIBIDO — SQLite
# import sqlite3
# conn = sqlite3.connect("data/trading_agent.db")  # DADOS DESATUALIZADOS!
```

**Conexão PostgreSQL:**
| Parâmetro | Valor |
|-----------|-------|
| Container | `eddie-postgres` |
| Porta exposta | `5433` (host) → `5432` (container) |
| Database | `btc_trading` (produção) / `postgres` (MCP — dados stale) |
| Schema | `btc` |
| Usuário | `postgres` |
| Senha | `eddie_memory_2026` |
| DSN (produção) | `postgresql://postgres:eddie_memory_2026@localhost:5433/btc_trading` |
| DSN (MCP/stale) | `postgresql://postgres:eddie_memory_2026@localhost:5433/postgres` |

**Tabelas no schema `btc`:**
| Tabela | Colunas-chave | Diferenças vs SQLite |
|--------|--------------|---------------------|
| `btc.trades` | id, timestamp, symbol, side, price, size, pnl, dry_run, metadata, mode | `dry_run` é **boolean** (não integer), `metadata` é **jsonb** |
| `btc.decisions` | id, timestamp, symbol, action, confidence, features | `features` é **jsonb** (não text) |
| `btc.market_states` | id, timestamp, symbol, price, rsi, momentum, volatility, trend, bid, ask, spread, volume | Inclui bid/ask/spread/volume do orderbook |
| `btc.performance_stats` | id, timestamp, symbol, total_trades, win_rate, total_pnl, sharpe_ratio | Mais campos que SQLite |

**Regras de queries:**
- **TODAS** as queries DEVEM filtrar por `symbol=%s` — sem exceção
- `dry_run` é **boolean**: usar `True/False`, não `1/0`
- `autocommit = True` é **obrigatório** para evitar `InFailedSqlTransaction` em cascata
- `features` (jsonb) retorna `dict` diretamente — não precisa `json.loads()`

### Endpoints HTTP
| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/metrics` | GET | Métricas Prometheus (scrape target) |
| `/health` | GET | Health check JSON |
| `/mode` | GET | Modo atual (LIVE/DRY_RUN) |
| `/config` | GET | Configuração atual |
| `/set-live` | GET | Ativa modo LIVE no config |
| `/set-dry` | GET | Ativa modo DRY_RUN no config |
| `/toggle-mode` | GET | Alterna entre modos |

### Variável CONFIG_PATH (per-coin via env var)
```python
# Cada exporter instância resolve seu próprio config via COIN_CONFIG_FILE
CONFIG_PATH = BASE_DIR / os.environ.get("COIN_CONFIG_FILE", "config.json")
# BTC → config.json, ETH → config_ETH_USDT.json, etc.
```

### Prometheus scrape config
```yaml
# /home/homelab/monitoring/prometheus.yml (montado em /etc/prometheus/prometheus.yml)

- job_name: 'autocoinbot-exporter'
  static_configs:
    - targets: ['172.17.0.1:9092']
  scrape_interval: 15s

- job_name: 'crypto-exporter-eth_usdt'
  scrape_interval: 30s
  static_configs:
    - targets: ['172.17.0.1:9098']
      labels:
        coin: 'ETH-USDT'
        instance: 'eth_usdt'
# ... (repetir para cada moeda)
```

---

## ⚠️ Operações Comuns

### Ativar modo LIVE de uma moeda
```bash
# Via HTTP (GET endpoint!)
curl http://192.168.15.2:9098/set-live   # ETH

# Verificar
curl http://192.168.15.2:9098/mode
# {"live_mode": true, "mode": "LIVE", "label": "💰 REAL"}
```

### Verificar saúde de todos os exporters
```bash
for port in 9092 9094 9095 9096 9097 9098; do
  echo "Port $port: $(curl -s http://localhost:$port/health)"
done
```

### Reiniciar Grafana (aplica provisioning)
```bash
sudo docker restart grafana
# Aguardar ~5 seg para startup completo
```

### Verificar dados por moeda no Prometheus
```bash
curl -s 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=btc_price{job="crypto-exporter-eth_usdt"}'
```

---

## 🔴 Lições Aprendidas — Erros Críticos e Prevenções

### 1. 🚫 Títulos duplicados no provisioning do Grafana

**Erro**: Dois arquivos JSON de dashboard com o **mesmo título** na mesma pasta de provisioning.

**Sintoma**: Grafana logava a cada 30 segundos:
```
WARN "dashboard title is not unique in folder" title="..." times=2
WARN "dashboards provisioning provider has no database write permissions because of duplicates"
```
**Consequência**: **NENHUMA atualização** do dashboard era aplicada. Todas as edições nos arquivos JSON eram ignoradas silenciosamente. O dashboard ficava "travado" numa versão antiga.

**Causa raiz**: `btc_trading_dashboard.json` (antigo) e `btc_trading_dashboard_v3_prometheus.json` tinham ambos o título `🤖 Trading Agent Monitor - ${coin_job:text}`.

**Correção**: Remover/renomear o arquivo duplicado. Manter apenas **um arquivo** por dashboard na pasta de provisioning.

**Prevenção**:
- ✅ **REGRA**: cada dashboard deve ter um título ÚNICO na pasta de provisioning
- ✅ **REGRA**: cada dashboard deve ter um UID ÚNICO
- ✅ Antes de editar dashboards, verificar: `ls *.json` na pasta de provisioning
- ✅ Após editar, verificar logs: `sudo docker logs grafana --since 60s 2>&1 | grep -i "duplicate\|not unique"`
- ✅ Se criar nova versão de um dashboard, **remover ou renomear** o antigo

---

### 2. 🚫 CONFIG_PATH global compartilhado entre exporters

**Erro**: Variável global `CONFIG_PATH` era hardcoded para `config.json` no módulo.

**Sintoma**: Chamar `/set-live` em qualquer exporter (ETH, DOGE, etc.) alterava o `config.json` do BTC em vez do config da moeda correta.

**Consequência**: Todas as 5 moedas secundárias inadvertidamente ativaram o modo LIVE do BTC.

**Correção**:
```python
# prometheus_exporter.py → main()
def main(config_path, symbol, db_path, port):
    global CONFIG_PATH
    CONFIG_PATH = config_path  # ← Cada instância define seu próprio path
```

**Prevenção**:
- ✅ Evitar variáveis globais mutáveis entre instâncias
- ✅ Sempre testar endpoints de controle (`/set-live`, `/set-dry`) em moeda secundária e verificar que **apenas** o config correto foi alterado
- ✅ Teste de validação: `curl .../set-live` no DOGE → verificar que `config.json` (BTC) NÃO mudou

---

### 3. 🚫 Queries Prometheus hardcoded com `{symbol="BTC-USDT"}`

**Erro**: Painéis de preço usavam `btc_price{symbol="BTC-USDT"}` em vez de `btc_price{job="$coin_job"}`.

**Sintoma**: Ao trocar o dropdown para ETH/DOGE/etc., os painéis de preço continuavam mostrando o preço do BTC.

**Correção**: Substituir **todas** as referências hardcoded por `{job="$coin_job"}`.

**Prevenção**:
- ✅ **REGRA**: toda expressão Prometheus no dashboard DEVE usar `{job="$coin_job"}`
- ✅ Nunca usar `{symbol="BTC-USDT"}` — o label `job` é o discriminador
- ✅ Script de validação:
  ```bash
  python3 -c "
  import json
  d = json.load(open('dashboard.json'))
  for p in d['panels']:
      for t in p.get('targets',[]):
          e = t.get('expr','')
          if 'BTC-USDT' in e or ('symbol' in e and 'coin_job' not in e):
              print(f'HARDCODED: panel {p[\"id\"]}: {e}')
  "
  ```

---

### 4. 🚫 `/set-live` é GET, não POST

**Erro**: Tentar ativar modo live com `curl -X POST .../set-live` retorna 405 ou não funciona.

**Fato**: O handler HTTP do exporter implementa `/set-live` como **GET**.

**Prevenção**:
- ✅ Usar `curl http://host:port/set-live` (sem `-X POST`)
- ✅ Documentar endpoints claramente (esta seção)

---

### 5. 🚫 Métricas com mesmo nome mas semântica diferente

**Erro**: Todas as moedas exportam `btc_price` (nome herdado do BTC original).

**Consequência potencial**: Sem filtro `{job=...}`, uma query `btc_price` retorna 6 resultados misturados. Dashboard mostrava legendas duplicadas.

**Prevenção**:
- ✅ **SEMPRE** filtrar por `{job="$coin_job"}` ou `{job="nome-específico"}`
- ✅ Considerar renomear métricas para `crypto_price` (já existe como alias) em futuras refatorações
- ✅ Na criação de novos painéis, nunca usar métricas sem label filter

---

### 6. 🚫 Dashboard provisioning "editable" vs persistência

**Fato**: Com `editable: true` no provisioning, alterações manuais no Grafana UI **são sobrescritas** a cada ciclo de provisioning (30 seg).

**Prevenção**:
- ✅ **SEMPRE** editar o arquivo JSON no disco, nunca pela UI do Grafana
- ✅ Alterações pela UI duram no máximo 30 segundos
- ✅ Para editar: `sudo vim /home/homelab/monitoring/grafana/provisioning/dashboards/btc_trading_dashboard_v3_prometheus.json` → Grafana recarrega automaticamente

---

### 7. 🚫 Conflito de provisioning bloqueia silenciosamente

**Fato**: Quando o Grafana detecta duplicata, ele **não aplica nenhuma alteração** de nenhum dos dashboards duplicados. Fica em loop de warning silencioso.

**Diagnóstico rápido**:
```bash
# Verificar se provisioning está bloqueado
sudo docker logs grafana --since 60s 2>&1 | grep "no database write permissions"
# Se aparecer → há duplicata. Investigar:
sudo docker logs grafana --since 60s 2>&1 | grep "not unique"
```

---

### 8. ⛔ SQLite PROIBIDO — Usar SOMENTE PostgreSQL

**Erro (2026-02-28)**: O exporter usava `sqlite3.connect("data/trading_agent.db")` para buscar dados de trading. O banco SQLite estava **desatualizado** — faltavam 30+ trades do BTC, dados de ETH discrepantes, ADA tinha trades fantasma.

**Sintoma**: Gauges do Grafana mostravam valores incorretos:
- BTC: 1381 trades (SQLite) vs 1411 trades (PostgreSQL) — 30 trades sem registrar
- ETH: PnL -$2.10 (SQLite) vs PnL +$0.22 (PostgreSQL) — sinal INVERTIDO
- ADA: 1 trade no SQLite, 0 no PostgreSQL — trade fantasma

**Causa raiz**: O `trading_engine.py` (agente principal) migrou para PostgreSQL mas o `prometheus_exporter.py` continuava lendo o SQLite antigo. Os dados divergiam silenciosamente.

**Correção**:
```python
# ANTES (ERRADO):
import sqlite3
DB_PATH = BASE_DIR / "data" / "trading_agent.db"
conn = sqlite3.connect(self.db_path)

# DEPOIS (CORRETO):
import psycopg2
PG_DSN = os.environ.get("DATABASE_URL", "postgresql://postgres:eddie_memory_2026@localhost:5433/postgres")
conn = psycopg2.connect(self.pg_dsn)
conn.autocommit = True
cursor.execute("SET search_path TO btc, public")
```

**Bugs adicionais corrigidos na mesma migração**:
1. **6 queries sem filtro `AND symbol=%s`** — win_rate/total_pnl eram iguais para todas as moedas (somavam todos os símbolos)
2. **`dry_run` integer vs boolean** — `WHERE dry_run=1` não funciona no PgSQL (é `WHERE dry_run=true`)
3. **Cascata `InFailedSqlTransaction`** — sem `autocommit=True`, uma query falhada (ex: coluna `exit_reason` inexistente) causava falha em TODAS as queries subsequentes
4. **Placeholders `?` vs `%s`** — SQLite usa `?`, PostgreSQL usa `%s`

**Prevenção**:
- ⛔ **NUNCA** usar `import sqlite3` em scripts de trading
- ⛔ **NUNCA** ler de `data/trading_agent.db` — arquivo obsoleto
- ✅ **SEMPRE** usar `psycopg2` + `PG_DSN` + schema `btc`
- ✅ **SEMPRE** usar `conn.autocommit = True`
- ✅ **SEMPRE** filtrar por `AND symbol=%s` em TODAS as queries
- ✅ **SEMPRE** usar `%s` (não `?`) como placeholder
- ✅ Referência funcional: `btc_query.py` (usa PostgreSQL corretamente)

---

### 9. 🚫 Queries sem filtro `AND symbol=%s`

**Erro (2026-02-28)**: 6 queries no exporter não incluíam `AND symbol=%s`, retornando dados somados de TODAS as moedas.

**Sintoma**: win_rate, total_pnl, avg_pnl, cumulative_pnl_24h, exit_reasons, last_trade e indicadores técnicos mostravam valores **idênticos** para todas as moedas no dropdown.

**Queries afetadas**:
```sql
-- ERRADO: retorna dados de TODAS as moedas
SELECT ... FROM trades WHERE pnl IS NOT NULL AND dry_run=%s
SELECT ... FROM trades WHERE timestamp > %s AND dry_run=%s 
SELECT ... FROM trades WHERE dry_run=%s ORDER BY timestamp DESC LIMIT 1
SELECT ... FROM decisions WHERE timestamp > %s GROUP BY action
SELECT ... FROM market_states ORDER BY timestamp DESC LIMIT 1

-- CORRETO: filtra por moeda específica
SELECT ... FROM trades WHERE pnl IS NOT NULL AND dry_run=%s AND symbol=%s
```

**Prevenção**:
- ✅ **REGRA**: toda query em `trades`, `decisions` ou `market_states` DEVE incluir `AND symbol=%s`
- ✅ Validar com: `grep -n 'FROM trades\|FROM decisions\|FROM market_states' prometheus_exporter.py | grep -v symbol`
- Se o grep retornar alguma linha → tem query sem filtro symbol → corrigir imediatamente

---

## 🔍 Checklist para Alterações no Dashboard

Antes de qualquer alteração nos dashboards de trading:

```
□ Há apenas UM arquivo JSON por dashboard na pasta de provisioning?
□ Cada dashboard tem título ÚNICO?
□ Cada dashboard tem UID ÚNICO?
□ Todas as expressões Prometheus usam {job="$coin_job"}?
□ Títulos dos painéis incluem (${coin_job:text})?
□ legendFormat definido em painéis stat/gauge?
□ Após editar, logs limpos? (sem "not unique" ou "no database write permissions")
□ Dados validados para pelo menos 2 moedas diferentes via Prometheus API?
□ Análises de dados/logs roteadas para Ollama local (economia de tokens)?
```

---

## 🧠 Ollama — Processamento Local (Economia de Tokens)

**REGRA OBRIGATÓRIA**: toda inferência LLM nos fluxos de trading (análise de trades, geração de decisões, processamento de logs) DEVE usar Ollama local **ANTES** de qualquer API cloud.

| Parâmetro | Valor |
|-----------|-------|
| Servidor | `http://192.168.15.2:11434` (homelab) |
| GPU | RTX 2060 SUPER 8GB VRAM |
| Modelo code | `qwen2.5-coder:7b` (~31 tok/s) |
| Modelo general | `qwen3:14b` (~20 tok/s) |
| Env vars | `OLLAMA_HOST`, `OLLAMA_MODEL` |
| Contexto máx | 32768 tokens |
| Timeout | 120-600s (depende da complexidade) |

**Fallback chain**: `Ollama` → `OpenWebUI` → `Copilot API` (último recurso)

**Economia estimada**: 50-80% de redução no consumo de tokens cloud.

```py
# Exemplo: análise de trade via Ollama (NÃO consumir tokens cloud)
import httpx, os

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")

async def analyze_trade_local(trade_data: dict) -> str:
    prompt = f"Analise este trade e sugira melhorias: {trade_data}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=120.0
        )
        return resp.json().get("response", "")
```

---

## 📁 Referências de Arquivos

| Arquivo | Localização | Descrição |
|---------|------------|-----------|
| Dashboard ativo | `homelab:/home/homelab/monitoring/grafana/provisioning/dashboards/btc_trading_dashboard_v3_prometheus.json` | Dashboard principal (ÚNICO) |
| Dashboard backup | `homelab:...btc_trading_dashboard.json.bak` | Versão antiga (backup, não provisionada) |
| Provisioning YAML | `homelab:/home/homelab/monitoring/grafana/provisioning/dashboards/dashboards.yml` | Config do provisionamento |
| Prometheus config | `homelab:/home/homelab/monitoring/prometheus.yml` | Scrape targets |
| Exporter | `homelab:/home/homelab/myClaude/btc_trading_agent/prometheus_exporter.py` | Exporter HTTP + métricas |
| Config BTC | `homelab:...btc_trading_agent/config.json` | Config do BTC (LIVE) |
| Config {COIN} | `homelab:...btc_trading_agent/config_{COIN}_USDT.json` | Config de cada moeda |

---

## 🕐 Histórico de Alterações

| Data | Alteração | Commit |
|------|-----------|--------|
| 2026-02-25 | Infraestrutura multi-moeda (6 pares) | `bc1688a` |
| 2026-02-25 | Remoção do limite diário de trades | `bc1688a` |
| 2026-02-25 | Dropdown `coin_job` no dashboard | — |
| 2026-02-25 | Fix CONFIG_PATH global no exporter | — |
| 2026-02-26 | Fix queries hardcoded de preço | — |
| 2026-02-26 | Remoção do dashboard duplicado (título) | — |
| 2026-02-26 | Títulos e legendas dinâmicos | — |
| 2026-02-28 | **Migração SQLite → PostgreSQL** no exporter | — |
| 2026-02-28 | Fix 6 queries sem filtro `AND symbol=%s` | — |
| 2026-02-28 | Fix `dry_run` integer→boolean, `?`→`%s`, autocommit | — |
| 2026-02-28 | CONFIG_PATH via env var `COIN_CONFIG_FILE` | — |
| 2026-03-03 | Métricas `trade_flow`, `bid_volume`, `ask_volume`, `spread` no exporter | — |
| 2026-03-03 | bid/ask/spread/volume no `record_market_state()` | — |
| 2026-03-03 | Performance tuning: `min_confidence` 0.75, cooldown 30min, daily limits | — |
| 2026-03-03 | **Multi-posição** (max 3 BUYs, preço médio ponderado) | — |
| 2026-03-03 | Métricas `open_position_count`, `avg_entry_price` no exporter | — |
| 2026-03-03 | Database de produção: `btc_trading` (não `postgres`) | — |
