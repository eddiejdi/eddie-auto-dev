# 📈 Vertical de Investimentos - Eddie Auto-Dev

## 🎯 Visão Geral

A Vertical de Investimentos é uma nova área de negócios da Eddie Auto-Dev, focada em **trading automatizado de criptomoedas** utilizando inteligência artificial e agents autônomos.

---

## 🏗️ Estrutura Organizacional

```
┌─────────────────────────────────────────────────────────────────┐
│                      DIRETOR                                    │
│                   (Estratégico)                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
┌────────┴────────┐             ┌────────┴────────┐
│ SUPERINTENDENTE │             │ SUPERINTENDENTE │
│   Investments   │             │    Finance      │
└────────┬────────┘             └────────┬────────┘
         │                               │
┌────────┴────────┐             ┌────────┴────────┐
│  COORDENADOR    │             │  COORDENADOR    │
│    Trading      │             │   Treasury      │
└────────┬────────┘             └────────┬────────┘
         │                               │
    [Squad Trading]               [Squad Finance]
```

---

## 🤖 Squad Trading (Crypto Squad)

### Membros

| Agent | Função | Status |
|-------|--------|--------|
| **AutoCoinBot** | Bot de trading autônomo | 🟡 Em Correção |
| **BacktestAgent** | Backtesting de estratégias | 🆕 A Criar |
| **StrategyAgent** | Desenvolvimento de estratégias | 🆕 A Criar |
| **RiskManagerAgent** | Gestão de risco | 🆕 A Criar |

### 🔄 Múltiplas Instâncias

> **É permitido executar várias instâncias do mesmo agent simultaneamente.**

| Instância | Par | Porta | Status |
|-----------|-----|-------|--------|
| `AutoCoinBot_BTC` | BTC-USDT | 8515 | 🟡 Ativo |
| `AutoCoinBot_ETH` | ETH-USDT | 8516 | 🆕 A Criar |
| `AutoCoinBot_SOL` | SOL-USDT | 8517 | 🆕 A Criar |

**Regras para Múltiplas Instâncias:**
- Cada instância deve ter um **ID único**: `{AgentName}_{symbol}`
- Instâncias **compartilham** o mesmo RAG mas têm **estado independente**
- Cada instância opera em **par diferente** ou **estratégia diferente**
- Avaliação de performance é **individual por instância**
- Systemd service: `autocoinbot@{symbol}.service`

### AutoCoinBot (Principal)

**Descrição:** Bot de trading automatizado para criptomoedas na exchange KuCoin.

| Propriedade | Valor |
|-------------|-------|
| **Localização** | `/home/eddie/AutoCoinBot/` |
| **Service** | `autocoinbot.service` |
| **Porta** | 8515 |
| **Par** | BTC-USDT |
| **Exchange** | KuCoin |
| **Credenciais** | `.env` (KUCOIN_USER/KUCOIN_PASS) |

**Modos de Operação:**
- `buy` - Apenas compras
- `sell` - Apenas vendas
- `mixed` - Compra e venda (RECOMENDADO)
- `flow` - Trading baseado em fluxo

**Funcionalidades Atuais:**
- ✅ Compra automática (DCA por fluxo)
- ✅ Eternal Mode (reinício automático)
- ✅ Múltiplos bots simultâneos
- ❌ Venda automática (EM DESENVOLVIMENTO)
- ❌ Backtest (A IMPLEMENTAR)
- ❌ Otimização de estratégia (A IMPLEMENTAR)

### BacktestAgent

**Descrição:** Engine de backtesting para testar estratégias em dados históricos.

**Funcionalidades Planejadas:**
- Simulação com dados históricos
- Métricas de performance (Sharpe, Sortino, Max Drawdown)
- Otimização de parâmetros (Grid Search, Bayesian)
- Comparação de estratégias

### StrategyAgent

**Descrição:** Desenvolvimento e gestão de estratégias de trading.

**Estratégias Planejadas:**
- DCA (Dollar Cost Averaging)
- Flow Trading (análise de fluxo)
- Scalping (operações rápidas)
- Swing Trading (médio prazo)
- Trend Following (seguir tendência)

### RiskManagerAgent

**Descrição:** Gestão de risco e proteção de capital.

**Funcionalidades Planejadas:**
- Stop-loss dinâmico
- Take-profit escalonado
- Position sizing (Kelly Criterion)
- Drawdown limits
- Risk/Reward ratio

---

## 💼 Squad Finance (Treasury Squad)

### Membros

| Agent | Função | Status |
|-------|--------|--------|
| **PortfolioAgent** | Gestão de portfólio | 🆕 A Criar |
| **ReportingAgent** | Relatórios de P&L | 🆕 A Criar |
| **ComplianceAgent** | Compliance tributário | 🆕 A Criar |
| **TaxAgent** | Cálculo de impostos | 🆕 A Criar |

---

## 🏆 Sistema de Incentivos (Gamificação)

### Regra de Punição e Recompensa

> **A área de Investimentos opera sob regime de meritocracia baseada em performance financeira real.**

O **saldo em moedas (USDT/BTC)** serve como métrica de punição ou recompensa para todos os agents da vertical:

### 💰 Recompensas (Lucro > 0)

| Performance | Recompensa | Benefício |
|-------------|-----------|-----------|
| **Lucro ≥ 1%** | 🥉 Bronze | Prioridade normal de recursos |
| **Lucro ≥ 5%** | 🥈 Prata | +25% recursos de CPU/RAM |
| **Lucro ≥ 10%** | 🥇 Ouro | +50% recursos + prioridade no queue |
| **Lucro ≥ 20%** | 💎 Diamante | Autonomia total + budget extra |

### ⚠️ Punições (Prejuízo)

| Performance | Punição | Consequência |
|-------------|---------|--------------|
| **Prejuízo ≤ -2%** | ⚠️ Alerta | Notificação para revisão |
| **Prejuízo ≤ -5%** | 🔶 Suspensão | Trading pausado para análise |
| **Prejuízo ≤ -10%** | 🔴 Bloqueio | Operações suspensas até otimização |
| **Prejuízo ≤ -15%** | ❌ Reciclagem | Agent vai para re-treinamento |

### 📏 Regras de Cálculo

```python
# Cálculo de Performance
performance = ((saldo_atual - saldo_inicial) / saldo_inicial) * 100

# Período de avaliação
periodo_avaliacao = "diario"  # diario, semanal, mensal

# Saldo inicial de referência
saldo_inicial = 1000  # USDT (configurável)

# Exemplo
saldo_atual = 1050  # USDT
performance = ((1050 - 1000) / 1000) * 100  # = 5% → 🥈 Prata
```

### 🔄 Ciclo de Avaliação

1. **Diário (00:00 UTC)**: Snapshot do saldo
2. **Semanal (Domingo)**: Avaliação de performance
3. **Mensal (Dia 1)**: Reset de categorias + bônus acumulado
4. **Trimestral**: Review estratégico pelo Diretor

### 🎯 Responsabilidades por Agent

| Agent | Métrica de Avaliação |
|-------|---------------------|
| **AutoCoinBot** | Lucro líquido em USDT |
| **BacktestAgent** | Acurácia de previsões |
| **StrategyAgent** | Win Rate das estratégias |
| **RiskManagerAgent** | Drawdown evitado |
| **PortfolioAgent** | ROI do portfólio |

---

## 📊 Métricas e KPIs

### Trading Performance
| Métrica | Meta | Atual |
|---------|------|-------|
| Win Rate | > 55% | N/A |
| Profit Factor | > 1.5 | N/A |
| Sharpe Ratio | > 1.0 | N/A |
| Max Drawdown | < 15% | N/A |
| ROI Mensal | > 5% | 0% |

### Operações
| Métrica | Valor |
|---------|-------|
| Trades Executados | 3.855 |
| Trades de Compra | 3.855 (100%) |
| Trades de Venda | 0 (0%) |
| Lucro Realizado | $0.00 |
| Última Operação | 2026-01-05 |

---

## 🔧 Configuração

### Variáveis de Ambiente (.env)

```bash
# Exchange
KUCOIN_BASE=https://api.kucoin.com
KUCOIN_API_KEY=your_api_key
KUCOIN_API_SECRET=your_api_secret
KUCOIN_API_PASSPHRASE=your_passphrase

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/autocoinbot

# Authentication
KUCOIN_USER=admin
KUCOIN_PASS=senha123
```

### Configuração de Trading

```python
# Modo de operação
mode = "mixed"  # buy, sell, mixed, flow

# Eternal mode (reinício automático)
eternal_mode = True

# Targets de lucro (%)
targets = "2:0.3,5:0.4,10:0.3"  # 2%: 30%, 5%: 40%, 10%: 30%

# Stop loss (%)
stop_loss = -5.0

# Tamanho da posição
position_size = 100  # USDT
```

---

## 🚀 Roadmap

### Fase 1 - Correção (Janeiro 2026)
- [ ] Corrigir BUG-002 (página pós-login 404)
- [ ] Implementar vendas automáticas
- [ ] Ativar eternal_mode
- [ ] Testar em paper trading

### Fase 2 - Backtest (Fevereiro 2026)
- [ ] Criar BacktestAgent
- [ ] Implementar engine de backtesting
- [ ] Coletar dados históricos
- [ ] Otimizar parâmetros

### Fase 3 - Estratégias (Março 2026)
- [ ] Criar StrategyAgent
- [ ] Implementar múltiplas estratégias
- [ ] A/B testing de estratégias
- [ ] Machine Learning para seleção

### Fase 4 - Finance (Q2 2026)
- [ ] Criar Squad Finance
- [ ] Relatórios automatizados
- [ ] Compliance tributário
- [ ] Dashboard de P&L

---

## 📁 Estrutura de Arquivos

```
/home/eddie/AutoCoinBot/
├── autocoinbot/
│   ├── app.py              # Streamlit dashboard
│   ├── bot.py              # EnhancedTradeBot
│   ├── bot_core.py         # Core logic
│   ├── bot_history.json    # Histórico de trades
│   ├── database.py         # PostgreSQL manager
│   ├── api.py              # KuCoin API client
│   ├── sidebar_controller.py
│   ├── dashboard.py
│   ├── strategy.py         # [A CRIAR]
│   ├── backtest.py         # [A CRIAR]
│   ├── optimizer.py        # [A CRIAR]
│   └── autonomous.py       # [A CRIAR]
├── .env                    # Configurações
├── venv/                   # Ambiente virtual
└── requirements.txt
```

---

## 📞 Suporte

- **Dashboard:** http://192.168.15.2:8515
- **Service:** `sudo systemctl status autocoinbot`
- **Logs:** `journalctl -u autocoinbot -f`
- **Responsável:** Trading Coordinator

---

*Documento criado: 2026-01-16*
*Última atualização: 2026-01-16*
*Versão: 1.0.0*
