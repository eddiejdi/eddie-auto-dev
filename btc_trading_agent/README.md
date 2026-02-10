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
