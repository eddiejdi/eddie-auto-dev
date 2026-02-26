# Multi-Coin Trading Infrastructure — Guia Completo

**Data**: 2026-02-25/26  
**Ambiente**: Homelab Production (192.168.15.2)  
**Status**: ✅ Operacional  

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
| stat | 17 | `btc_price{job="$coin_job"}` |
| timeseries | 6 | `btc_trading_equity_usdt{job="$coin_job"}` |
| piechart | 2 | `btc_trading_decisions_total{job="$coin_job", action="BUY"}` |
| table | 2 | `btc_trading_last_trade_info{job="$coin_job"}` |
| gauge | 1 | `btc_trading_rsi{job="$coin_job"}` |
| text | 1 | (header) |

---

## 🔧 Prometheus Exporter

### Arquivo principal
`/home/homelab/myClaude/btc_trading_agent/prometheus_exporter.py`

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

### Variável global CONFIG_PATH
```python
# Em main():
global CONFIG_PATH
CONFIG_PATH = config_path  # CRÍTICO: cada instância usa seu próprio config
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
