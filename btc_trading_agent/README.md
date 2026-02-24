# Bitcoin Trading Agent 24/7 🤖

Agente autônomo de trading de Bitcoin que opera 24 horas por dia usando a API da KuCoin.

## 📁 Estrutura

btc_trading_agent/
├── kucoin_api.py      # Wrapper da API KuCoin (autenticação HMAC)
├── fast_model.py      # Modelo ML ultra-rápido (Q-Learning + Ensemble)
├── training_db.py     # Banco de dados SQLite para treinamento
├── trading_agent.py   # Agente principal 24/7
├── webui_integration.py    # API Flask para Open WebUI
├── openwebui_tool.py       # Tool/Function para Open WebUI
├── deploy.sh          # Script de deploy
├── btc-trading-agent.service  # Serviço systemd (agente)
├── btc-webui-api.service      # Serviço systemd (API)
├── logs/              # Logs do agente
├── data/              # Dados de trading
└── models/            # Modelos treinados
## 🚀 Instalação Rápida

```bash
cd /home/homelab/myClaude/btc_trading_agent
chmod +x deploy.sh
./deploy.sh install
## 🌐 Integração com Open WebUI

### 1. Iniciar a API
```bash
# Manualmente
python3 webui_integration.py --port 8510

# Ou como serviço
sudo cp btc-webui-api.service /etc/systemd/system/
sudo systemctl enable btc-webui-api
sudo systemctl start btc-webui-api
### 2. Endpoints Disponíveis
| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/price` | GET | Preço atual do BTC |
| `/api/analysis` | GET | Análise técnica completa |
| `/api/status` | GET | Status do agente |
| `/api/trades` | GET | Trades recentes |
| `/api/performance` | GET | Estatísticas de performance |
| `/api/ask` | POST | Perguntas em linguagem natural |
| `/api/chat` | POST | Compatível com Open WebUI |

### 3. Usar no Open WebUI
A API pode ser consultada diretamente pelo modelo LLM. Exemplos de perguntas:

- "Qual o preço do Bitcoin?"
- "Mostre a análise técnica do BTC"
- "Qual o sinal atual de trading?"
- "Como está a performance do agente?"
- "O RSI está sobrecomprado?"

### 4. Adicionar como Tool/Function
Copie o arquivo `openwebui_tool.py` para o diretório de functions do Open WebUI ou crie uma nova tool na interface com as funções:

- `btc_price()` - Preço atual
- `btc_analysis()` - Análise técnica
- `btc_signal()` - Sinal BUY/SELL/HOLD
- `btc_trades(limit)` - Histórico de trades
- `btc_performance()` - Métricas de performance
- `btc_ask(question)` - Pergunta em linguagem natural

## ⚙️ Configuração

### 1. Obter credenciais KuCoin

1. Acesse [KuCoin API Management](https://www.kucoin.com/account/api)
2. Crie uma nova API key com permissões de trading
3. Configure as variáveis de ambiente:

```bash
export KUCOIN_API_KEY="sua_api_key"
export KUCOIN_API_SECRET="sua_api_secret"
export KUCOIN_API_PASSPHRASE="sua_passphrase"
Ou edite o arquivo `.env`:
```bash
nano /home/homelab/myClaude/btc_trading_agent/.env
## 🎮 Uso

### Modo Dry Run (Simulação)
```bash
python3 trading_agent.py --dry-run
### Modo Live (⚠️ Dinheiro Real!)
```bash
python3 trading_agent.py --live
### Modo Daemon (Background 24/7)
```bash
python3 trading_agent.py --daemon --dry-run
### Como Serviço Systemd
```bash
sudo systemctl enable btc-trading-agent
sudo systemctl start btc-trading-agent
sudo journalctl -u btc-trading-agent -f
## 🧠 Como Funciona

### 1. Coleta de Dados
- Preço em tempo real via API REST
- Order book (profundidade bid/ask)
- Histórico de trades recentes
- Indicadores técnicos (RSI, momentum, volatilidade)

### 2. Modelo de Decisão
O modelo usa um ensemble de 4 estratégias:

| Estratégia | Peso | Descrição |
|------------|------|-----------|
| Technical | 30% | RSI, EMA, momentum |
| Orderbook | 25% | Imbalance bid/ask |
| Flow | 25% | Pressão de compra/venda |
| Q-Learning | 20% | Aprendizado por reforço |

### 3. Execução
- **HOLD**: Manter posição atual
- **BUY**: Comprar BTC (30% do saldo disponível)
- **SELL**: Vender posição inteira

### 4. Aprendizado
O Q-Learning aprende continuamente:
- Estado: discretização de RSI, momentum, volatilidade, trend
- Ações: HOLD, BUY, SELL
- Recompensa: PnL do trade

## 📊 Parâmetros

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| `POLL_INTERVAL` | 5s | Intervalo entre análises |
| `MIN_TRADE_INTERVAL` | 60s | Cooldown entre trades |
| `MIN_CONFIDENCE` | 50% | Confiança mínima para executar |
| `MIN_TRADE_AMOUNT` | $10 | Valor mínimo por trade |
| `MAX_POSITION_PCT` | 30% | Máximo do saldo em posição |

## 📈 Monitoramento

### Grafana + Prometheus (v2 — 2026-02-24)

O agente é monitorado em tempo real via Prometheus exporter + Grafana dashboard.

#### Arquitetura

```
┌─────────────────┐     scrape 5s     ┌──────────────┐    query    ┌──────────────┐
│ prometheus       │ ◄──────────────── │  exporter     │            │   Grafana     │
│ :9090            │                   │  :9092        │            │   :3002       │
└────────┬────────┘                   └──────┬───────┘            └──────┬───────┘
         │                                    │                          │
         │  PromQL queries                    │  SQLite + KuCoin API     │  Dashboard
         └────────────────────────────────────┴──────────────────────────┘
                                              │
                                    ┌─────────┴─────────┐
                                    │  trading_agent.db  │
                                    │  config.json       │
                                    └───────────────────┘
```

#### Prometheus Exporter (`prometheus_exporter.py`)

Servidor HTTP na porta **9092** que expõe métricas do agente para o Prometheus.

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/metrics` | GET | Métricas Prometheus (text/plain) |
| `/health` | GET | Health check (JSON) |
| `/config` | GET | Config atual (JSON) |
| `/mode` | GET | Página HTML com modo atual e botões |
| `/toggle-mode` | GET/POST | Alterna DRY ↔ LIVE |
| `/set-live` | GET | Força modo LIVE |
| `/set-dry` | GET | Força modo DRY |
| `/set-mode` | POST | Define modo via JSON `{"live_mode": true}` |

##### Métricas filtradas por modo

As métricas principais refletem automaticamente o **modo ativo** (DRY ou LIVE):

| Métrica | Tipo | Descrição |
|---------|------|-----------|
| `btc_price{symbol="BTC-USDT"}` | gauge | Preço BTC (global) |
| `btc_trading_total_trades` | counter | Total trades (modo ativo) |
| `btc_trading_winning_trades` | counter | Trades vencedores (modo ativo) |
| `btc_trading_losing_trades` | counter | Trades perdedores (modo ativo) |
| `btc_trading_win_rate` | gauge | Win rate 0-1 (modo ativo) |
| `btc_trading_total_pnl` | gauge | PnL total USDT (modo ativo) |
| `btc_trading_avg_pnl` | gauge | PnL médio por trade (modo ativo) |
| `btc_trading_best_trade_pnl` | gauge | Melhor trade (modo ativo) |
| `btc_trading_worst_trade_pnl` | gauge | Pior trade (modo ativo) |
| `btc_trading_cumulative_pnl` | gauge | PnL acumulado (modo ativo) |
| `btc_trading_cumulative_pnl_24h` | gauge | PnL acumulado 24h (modo ativo) |
| `btc_trading_trades_24h` | gauge | Trades últimas 24h (modo ativo) |
| `btc_trading_trades_1h` | gauge | Trades última hora (modo ativo) |
| `btc_trading_open_position_btc` | gauge | Posição aberta BTC (modo ativo) |
| `btc_trading_open_position_usdt` | gauge | Posição aberta USDT (modo ativo) |

Métricas com label `mode` para comparação entre modos:

| Métrica | Labels | Descrição |
|---------|--------|-----------|
| `btc_trading_mode_total_trades{mode="dry\|live"}` | mode | Total trades por modo |
| `btc_trading_mode_pnl{mode="dry\|live"}` | mode | PnL por modo |
| `btc_trading_mode_win_rate{mode="dry\|live"}` | mode | Win rate por modo |
| `btc_trading_mode_winning{mode="dry\|live"}` | mode | Winning trades por modo |
| `btc_trading_mode_losing{mode="dry\|live"}` | mode | Losing trades por modo |
| `btc_trading_active_mode{mode="dry\|live"}` | mode | Modo atualmente ativo |

Métricas globais (não filtradas por modo):

| Métrica | Tipo | Descrição |
|---------|------|-----------|
| `btc_trading_rsi` | gauge | RSI (0-100) |
| `btc_trading_momentum` | gauge | Momentum |
| `btc_trading_volatility` | gauge | Volatilidade (0-1) |
| `btc_trading_trend` | gauge | Tendência (-1 a +1) |
| `btc_trading_orderbook_imbalance` | gauge | Imbalance orderbook |
| `btc_trading_decisions_total{action}` | counter | Decisões por tipo |
| `btc_trading_agent_running` | gauge | Agente rodando (1/0) |
| `btc_trading_live_mode` | gauge | Modo ativo (0=DRY, 1=LIVE) |
| `btc_trading_exit_*` | counter | Trades fechados por motivo (modo ativo) |

##### Detecção de Status do Agente

O exporter detecta se o agente está rodando via:
1. `pgrep -f trading_agent.py` — verifica processo
2. Última atividade no DB (< 5 min) — fallback

##### Preço BTC

Fonte primária: última decisão do DB. Fallback: KuCoin API (`/api/v1/market/orderbook/level1`).

#### Grafana Dashboard

- **UID**: `btc-trading-monitor`
- **Datasource**: Prometheus (`dfc0w4yioe4u8e`)
- **Scrape interval**: 5s
- **32 painéis** organizados em seções:
  - Topo: Preço BTC, PnL, Win Rate, Total Trades, Status, Modo, Botões
  - Gráficos: Preço em tempo real, PnL acumulado, RSI, Decisões
  - Tabelas: Dados de comparação entre modos
  - Config: Stop Loss, Take Profit, Trailing Stop

##### Botões de Controle (Painel HTML)

Os botões usam `fetch()` JavaScript para alternar o modo sem sair do dashboard:
- **🔄 Alternar** — troca DRY ↔ LIVE
- **💰 REAL** — força modo LIVE
- **🧪 DRY** — força modo DRY

Ao clicar, mostra "⏳ Alterando..." e recarrega o dashboard em 3 segundos.

> **Requisito**: `disable_sanitize_html = true` no Grafana (`custom.ini`) para que o HTML/JS funcione.

#### Serviço Systemd

```ini
# /etc/systemd/system/autocoinbot-exporter.service
[Unit]
Description=AutoCoinBot Prometheus Exporter
After=network.target

[Service]
Type=simple
User=homelab
WorkingDirectory=/home/homelab/myClaude/btc_trading_agent
ExecStart=/usr/bin/python3 /home/homelab/myClaude/btc_trading_agent/prometheus_exporter.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable autocoinbot-exporter
sudo systemctl start autocoinbot-exporter
sudo systemctl status autocoinbot-exporter
```

#### Prometheus Config

```yaml
# /etc/prometheus/prometheus.yml
- job_name: 'autocoinbot-exporter'
  static_configs:
    - targets: ['localhost:9092']
  scrape_interval: 5s
  scrape_timeout: 10s
  metrics_path: '/metrics'
```

#### Exemplo de uso via curl

```bash
# Métricas completas
curl http://192.168.15.2:9092/metrics

# Alternar modo
curl http://192.168.15.2:9092/toggle-mode

# Forçar DRY
curl http://192.168.15.2:9092/set-dry

# Forçar LIVE
curl http://192.168.15.2:9092/set-live

# Health check
curl http://192.168.15.2:9092/health

# Modo atual (JSON)
curl -H 'Accept: application/json' http://192.168.15.2:9092/mode
```

### Logs
```bash
tail -f logs/agent.log
### Status
```bash
./deploy.sh status
### Database
```bash
sqlite3 data/training.db "SELECT * FROM trades ORDER BY created_at DESC LIMIT 10;"
## ⚠️ Avisos Importantes

1. **RISCO**: Trading de criptomoedas envolve risco significativo de perda
2. **TESTE PRIMEIRO**: Sempre use modo dry-run antes de ir para live
3. **CAPITAL**: Nunca invista mais do que pode perder
4. **MONITORAMENTO**: Monitore o agente regularmente
5. **API LIMITS**: Respeite os limites de rate da KuCoin (10 req/s)

## 📊 Risk Management (v2 — 2026-02-24)

O agente agora inclui camadas de proteção contra perdas:

| Mecanismo | Parâmetro | Valor | Fonte |
|---|---|---|---|
| **Stop Loss** | `stop_loss_pct` | 2% | config.json |
| **Take Profit** | `take_profit_pct` | 3% | config.json |
| **Saída Parcial** | 50% da posição | ao atingir +1.5% | trading_agent.py |
| **Trailing Stop** | ativa em +1.5%, trail 0.8% | dinâmico | config.json |
| **Limite Diário** | `max_daily_trades` | 15 trades/dia | config.json |
| **Perda Diária Máx** | `max_daily_loss` | $150/dia | config.json |
| **Confiança Mínima** | `min_confidence` | 0.60 (60%) | config.json |
| **Intervalo Mín.** | `min_trade_interval` | 180s (3 min) | config.json |

### Fluxo de Exit Conditions

```
A cada ciclo (5s), se tem posição aberta:
  1. Verifica Stop Loss (-2%) → vende TUDO imediatamente
  2. Verifica Take Profit (+3%) → vende TUDO imediatamente
  3. Verifica Saída Parcial (+1.5%) → vende 50% (uma vez)
  4. Verifica Trailing Stop:
     a. Ativa quando lucro >= 1.5%
     b. Rastreia preço máximo desde entrada
     c. Dispara se cair 0.8% do máximo → vende TUDO
  5. Só então consulta o modelo para sinais BUY/SELL/HOLD
```

### Indicadores Técnicos (v2)

- **RSI** (14 períodos de candles 1min reais)
- **Momentum** (10 candles)
- **Volatilidade** (20 candles)
- **Trend** (SMA 10 vs SMA 30)
- **Volume Ratio** (real da KuCoin)
- **Orderbook Imbalance** + **Trade Flow**

Os indicadores agora usam **candles reais de 1 minuto** da KuCoin API ao invés de ticks de 5 segundos, resultando em sinais técnicos muito mais precisos.

## 🔧 Troubleshooting

### Erro de conexão
```bash
# Testar API
./deploy.sh test
### Credenciais inválidas
```bash
# Verificar variáveis
echo $KUCOIN_API_KEY
### Serviço não inicia
```bash
sudo journalctl -u btc-trading-agent -n 50
## 📝 Licença

MIT License - Use por sua conta e risco.

## 🙏 Créditos

Baseado no projeto [AutoCoinBot](https://github.com/eddiejdi/AutoCoinBot).
