# 🚨 RELATÓRIO DIAGNÓSTICO - AGENTE DE TRADING BTC

**Data:** 27 de Fevereiro de 2026  
**Status:** CRÍTICO - Operando em PREJUÍZO  
**Localização:** `/home/homelab/myClaude/btc_trading_agent/`

---

## 📊 SITUAÇÃO ATUAL

### Estatísticas (Últimas 24h)

| Métrica | Valor | Status |
|---------|-------|--------|
| **Total de Trades** | 46 | ⚠️ |
| **Win Rate** | 26.1% | 🔴 CRÍTICO |
| **PnL Total** | -$7.41 | 🔴 PERDENDO |
| **PnL Médio** | -$0.32 | 🔴 NEGATIVO |
| **Maior Perda** | -$5.19 (ADA) | 🔴 |
| **Maior Ganho** | +$1.34 (DOGE) | 🟡 Baixo |

### Por Moeda (24h)

```
ADA-USDT   | 0.0% win rate | -$5.19 (MAIS PERDAS!)
ETH-USDT   | 28.6% win    | -$2.10
XRP-USDT   | 20.0% win    | -$2.02
BTC-USDT   | 0.0% win rate | -$0.11
DOGE-USDT  | 40.0% win ✓  | +$2.01 (ÚNICA COM LUCRO!)
```

---

## 🐛 PROBLEMAS PERMANENTES IDENTIFICADOS

### 1. 🔴 **AUTO TAKE-PROFIT DESATIVADO** (CRÍTICO!)

**Problema:**
```json
"auto_take_profit": {
  "enabled": false,  // ❌ DESATIVADO!
  "pct": 0.03
}
```

**Impacto:**
- Posições que ganham **3%+** ficam abertas indefinidamente
- Aguarda sinal manual para fechar (lentidão em escalping)
- Exposição desnecessária a reversão de preço
- Lucros "previstos" viram perdas por preguiça

**Exemplo real:**
```
Trade 2811 | ETH | BUY @2061.73 → SELL @2069.93 = +$0.94 ✓
  => Poderia ter saído automático em +3%, mas ficou aberto esperando
```

**Recomendação:**
```json
"auto_take_profit": {
  "enabled": true,  // ✓ ATIVAR!
  "pct": 0.025      // 2.5% - mais relevante que 3% em scalping
}
```

---

### 2. 🔴 **MIN CONFIDENCE MUITO BAIXO**

**Problema:**
```json
"min_confidence": 0.72  // Apenas 72%!
```

**Impacto:**
- Aceita sinais fracos com chance de **28% de falha**
- Em scalping (margens <1%), isso destrói rentabilidade
- A Win Rate de 26% prova que os sinais são ruins

**Análise:**
```
Confidence 0.72 com Win Rate 26% = sinais PÉSSIMOS
Esperado: Win Rate ≥ 55% para scalping com posição típica
Atual: Win Rate = 26% (FALHA sistemática do modelo)
```

**Recomendação:**
```json
"min_confidence": 0.85  // Mínimo 85% para aceitar trade
```

---

### 3. 🟡 **MIN NET PROFIT MUITO BAIXO**

**Problema:**
```json
"min_net_profit": {
  "usd": 0.05,      // Apenas 5 centavos!
  "pct": 0.002      // 0.2% de lucro mínimo
}
```

**Impacto:**
- Com taxa KuCoin = 0.1% (buy) + 0.1% (sell) = 0.2% em fees
- Lucros mínimos são **ZERADOS pelas taxas**
- Tá pagando taxa por NADA

**Cálculo Real:**
```
1. Buy 0.1 ETH @$2,000 = $200 + 0.2fee = -$0.40
2. Sell 0.1 ETH @$2,004 = $200.40 + 0.2fee = -$0.40
3. Lucro bruto: $0.40
4. Lucro líquido: $0.40 - $0.80 (fees) = -$0.40 ❌ PERDA!
```

**Recomendação:**
```json
"min_net_profit": {
  "usd": 0.50,      // Mínimo $0.50 por trade
  "pct": 0.015      // 1.5% de lucro mínimo (cobre fees+spread)
}
```

---

### 4. 🟡 **ESTRATÉGIA DE SCALPING COM MARGIN PEQUENA**

**Problema:**
```json
"stop_loss_pct": 0.02,      // 2%
"take_profit_pct": 0.03,    // 3%
"min_spread_bps": 5         // Apenas 5bps de spread mínimo
```

**Impacto:**
- Razão Risk:Reward = 1:1.5 (OK, mas apertado)
- Spread de 5 bps = $1 em $20k position = MÍNIMO
- Em volatilidade, entrada sai no mesmo nível

**Problema Adicional:**
```python
# Na função _calculate_trade_size (linha 424-427):
if pnl > 0 and net_profit < min_required and price > stop_loss_price:
    logger.warning("SELL skipped — net profit too low")
    return 0  # ❌ NÃO VENDE!
```

**O que acontece:**
1. Trade ganha 0.5%
2. Net profit $0.03 < mínimo $0.05 requerido
3. **BOT RECUSA VENDER** (return 0)
4. Posição fica aberta esperando subir mais
5. Preço cai, vira perda, stop-loss é acionado

---

### 5. 🔴 **MODELO DE PREDIÇÃO COM BAIXÍSSIMA PRECISÃO**

**Evidência:**
- Win Rate = 26.1% (chance é 50%)
- **BOT PERDE MAIS QUE ACERTA**
- Modelo `FastTradingModel` está **detreinado ou com features ruins**

**Análise:**
```
Win Rate 26.1% com Risk:Reward 1:1.5
Expectativa: -26 × 2% + 74 × 3% = -0.52% + 2.22% = 1.7% ao dia
Realidade: -$7.41 em 24h (MUITO PIOR)

Conclusão: Não é só a configuração, o MODELO está broken
```

---

## ✅ SOLUÇÃO EM 3 PASSOS

### PASSO 1: PARAR IMEDIATAMENTE ⛔

**Ação recomendada:**
```bash
# SSH ao homelab
ssh homelab@192.168.15.2
cd /home/homelab/myClaude/btc_trading_agent

# Parar o daemon
pkill -9 -f "trading_agent.py --daemon"

# Verificar que parou
ps aux | grep trading_agent | grep -v grep  # Deve estar vazio
```

### PASSO 2: ATUALIZAR CONFIG.JSON 🔧

**Mudanças críticas:**

```json
{
  "enabled": true,
  "dry_run": false,
  "symbol": "BTC-USDT",
  "poll_interval": 5,
  "min_trade_interval": 180,
  
  // ✅ AUMENTAR CONFIANÇA
  "min_confidence": 0.85,  // WAS 0.72
  
  "min_trade_amount": 1,
  "max_position_pct": 0.8,
  "stop_loss_pct": 0.025,    // Aumentar para 2.5%
  "take_profit_pct": 0.035,  // Aumentar para 3.5%
  
  "auto_stop_loss": {
    "enabled": true,
    "pct": 0.025    // ✅ 2.5% (foi 0.02)
  },
  
  "auto_take_profit": {
    "enabled": true,    // ✅ ATIVAR!
    "pct": 0.025       // ✅ 2.5% (era false)
  },
  
  "min_net_profit": {
    "usd": 0.50,       // ✅ AUMENTAR para $0.50 (era 0.05)
    "pct": 0.015       // ✅ 1.5% (era 0.002)
  },
  
  "strategy": {
    "mode": "scalping",
    "use_trend_filter": true,
    "use_volume_filter": true,
    "rsi_oversold": 35,
    "rsi_overbought": 65,
    "min_spread_bps": 10    // ✅ AUMENTAR (era 5)
  },
  
  "trailing_stop": {
    "enabled": true,
    "activation_pct": 0.015,
    "trail_pct": 0.008
  },
  
  "notifications": {
    "enabled": true,
    "on_trade": true,
    "on_error": true
  }
}
```

### PASSO 3: RETRAINÁ O MODELO 🤖

**Verificar dados de treinamento:**
```bash
# Ver tamanho do DB
du -sh data/trading_agent.db

# Executar análise de modelo
python3 training_db.py --analyze

# Se necessário, retrainá:
python3 training_db.py --retrain --epochs=100 --validation_split=0.2
```

---

## 🛡️ SAFEGUARDS RECOMENDADOS

### 1. **Implementar Max Daily Loss (já existe, check)**
```json
"max_daily_loss": 150  // Parar se perder >$150/dia
```
✅ Já está configurado. Verificar se está sendo respeitado.

### 2. **Implementar Max Daily Trades**
```json
"max_daily_trades": 10  // Max 10 trades/dia
```
✅ Configurado. Está sendo respeitado?

### 3. **Adicionar Kill-Switch por Win Rate**
```python
# Adicionar ao código:
if win_rate_24h < 0.30:  # Se <30% win rate
    logger.critical("Win Rate CRÍTICO! Pausando bot...")
    bot.stop()
```

### 4. **Adicionar Drawdown Máximo**
```json
"risk_management": {
  "max_drawdown_pct": 0.10  // Máximo 10% de perda acumulada
}
```

### 5. **Monitoramento com Alertas**
```bash
# Telegram alert a cada 2h com status
# Grafo de PnL em tempo real (Grafana)
# Email se Win Rate < 40% por 6h
```

---

## 📋 CHECKLIST IMEDIATO

- [ ] Parar o daemon de trading
- [ ] Atualizar `config.json` com valores recomendados
- [ ] Fazer backup do banco antigo: `cp data/trading_agent.db data/trading_agent.db.bak.20260227`
- [ ] Retrainá o modelo com dados históricos
- [ ] Testar em DRY RUN mode primeiro
  ```bash
  # Editar config.json: "dry_run": true
  python3 trading_agent.py --daemon --dry
  # Deixar rodar 2-3h e verificar resultados
  ```
- [ ] Se Win Rate melhorar em DRY (>40%), ativar LIVE com posição PEQUENA
  ```json
  "max_position_pct": 0.2  // Reduzir para 20% enquanto testa
  ```
- [ ] Monitorar 24h antes de aumentar posição
- [ ] Configurar alertas Telegram/Email para anomalias

---

## 🎯 MÉTRICAS ALVO

| Métrica | Atual | Alvo |
|---------|-------|------|
| Win Rate | 26.1% | > 55% |
| PnL/dia | -$7.41 | +$5.00+ |
| Max Drawdown | ? | < 10% |
| Avg Trade | -$0.32 | +$0.25+ |
| Confidence Mín | 0.72 | 0.85+ |

---

## 📞 PRÓXIMAS AÇÕES

1. **Hoje**: Parar o bot e atualizar config
2. **Hoje**: Executar dry-run com novas configurações
3. **Amanhã**: Se dry-run OK (>40% WR), ativar live com posição reduzida
4. **3-5 dias**: Curva de aprendizado do modelo
5. **1 semana**: Avaliação completa e decisão final

---

**Relatório preparado em:** 27/02/2026 02:15 UTC  
**Próxima atualização:** Depois de implementar mudanças
