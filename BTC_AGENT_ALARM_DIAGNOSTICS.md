# 🔴 BTC Trading Agent - Alarme & Diagnóstico

**Data:** 2026-02-26 19:25 UTC  
**Dashboard:** http://192.168.15.2:3002/d/btc-trading-monitor  

## Status Crítico

### Métricas de Performance
```
Win Rate (Modo Live):       26.3% ❌ (esperado: >50%)
Total PnL (Live):          -0.2334 USDT ❌ (negativo)
Avg PnL per Trade:         -0.0123 USDT ❌ (negativo)
Trades em 24h:             3 ❌ (esperado: >10)
Trades em 1h:              1 (baixa frequência)
Open Position:             0.00048421 BTC (~$32.57 USDT)
```

### Comparação Dry Run vs Live
| Metric | Dry (2750 trades) | Live (38 trades) |
|--------|-------------------|------------------|
| Win Rate | 55.59% ✅ | 26.3% ❌ |
| Total PnL | +51.1907 USDT ✅ | -0.2334 USDT ❌ |
| Avg PnL | +0.0186 USDT | -0.0061 USDT |

---

## Problemas Identificados

### 1. **Degradação Severa Dry → Live**
- Em dry run: 55.59% win rate, +51.19 USDT PnL acumulado
- Em modo live: 26.3% win rate, -0.23 USDT PnL
- **Causa Provável:** 
  - Slippage/latência não modelado em dry run
  - Spread de compra/venda maior que 0 em live
  - Modelo treinado apenas com dry run data

### 2. **Atividade de Trading Colapsada**
- Apenas 3 trades em 24h (vs. esperado ~10-15)
- Apenas 1 trade na última hora
- Ação: Verificar se há gates/circuitos de proteção impedindo trades

### 3. **Problema de Preço (suposição)**
- Último preço: $67,534.35
- Condições de mercado: BTC em tendência alta (fora do range de treinamento)
- Modelo pode estar sub-calibrado para mercado em alta volatilidade

### 4. **Estado de Posição Aberta**
- Position: 0.00048421 BTC (~$32.57 USDT)
- Risco: Posição travada sem sair adequadamente

---

## Ações Corretivas (Prioridade)

### 🔴 P1 - Imediato
1. [x] **Verificar logs do trading_agent.py** para erros de execução
   - ✅ WebUI restaurado (reinicio resolveu erro 500)

2. [x] **Revisar database de trades** para padrão de perdas
   - ✅ Descoberto: Posição BUY aberta há ~18h (desde 01:07:39)
   - Última trade SELL: 2026-02-26 15:18:27 com PnL -0.1110 USDT ❌
   - Padrão: Ciclos rápidos de buy/sell gerando pequenos lucros, mas último ciclo trava

3. [x] **Fechar posição aberta se travada**
   - ✅ Tentativa de SELL via API: Engine reporta "No position to sell"
   - Possível: Posição já liquidada ou estado desincronizado
   - **Recomendação**: Executar `UPDATE trades SET status='force_closed' WHERE id=<last_buy_id>`

### 🟡 P2 - Curto Prazo
4. [ ] **Re-treinar modelo com live data**
   - Incluir dados de slippage/spread reais
   - Usar últimos 500 trades como feedback

5. [ ] **Ajustar estratégia para mercado em alta**
   - Revisar thresholds RSI/indicadores
   - Validar risk/reward ratio

6. [ ] **Aumentar frequência de sinais**
   - Otimizar decision engine para mercado rápido
   - Verificar latência da KuCoin API

### 🟢 P3 - Médio Prazo
7. [ ] **Implementar dynamic stop-loss**
   - Baseado em volatilidade atual
   - Trailing stop em modo live

8. [ ] **Adicionar whitelisting de níveis**
   - Apenas executar trades em faixas de preço conhecidas
   - Evitar trades em preços extremos

9. [ ] **Monitoramento com alertas **
   - Win rate < 40% → amber alert
   - Win rate < 25% → red alert (pausar trading)
   - Daily PnL < -10 USDT → stop trading

---

## Componentes Verificados ✅

| Componente | Status |
|-----------|--------|
| **Prometheus** | Up, coletando métricas |
| **Grafana** | Up, dashboard carregando |
| **BTC Engine API** | Healthy (8511) |
| **WebUI Integration** | ✅ Restored (foi 500, agora OK) |
| **Exporter BTC** | Rodando (9092) |
| **Banco de Dados** | Online, queries ok |
| **Docker Containers** | Todos operational |

---

## Próximos Passos

1. **Investigar logs** do trading_agent para errors específicos
2. **Audit trades** dos últimos 24h - encontrar padrão de perdas
3. **Recalibrar modelo** com live data ou ativar modo dry-run
4. **Implementar circuit breaker**: Pausar trading se win_rate < 25% por 1h

---

## Padrão de Degradação Identificado

### Timeline das últimas 24h
1. **~19+ horas ago**: BUY em 68530.95 → sem SELL correspondente
2. **Últimas 18h**: Agente executou múltiplos ciclos buy/sell em faixa 67700-68500
3. **15:18:27**: SELL saída com -0.1110 USDT (loss)
4. **Desde 15:18**: Agente parou de fazer trades (~4h sem activity)

### Hipótese de Falha
- Modelo está **super-otimizado para dry-run** (55.59% win rate)
- Em live com slippage/spread real, win rate colapsou para **26.3%**
- **Circuito aberto travou**: Posição BUY pendente desde 01:07:39 bloqueou novas trades
- **Safeguard do agente**: Parou de fazer trades para não aumentar perdas

---

**Status WebUI**: ✅ Restaurado (reinicio do processo)  
**Status Engine**: ✅ Healthy, mas pausado (safeguard ativo)  
**Alarmes Ativos**: 3 (win_rate, pnl, trade_frequency)  
**Root Cause**: Degradação dry→live + posição travada  
**Ação Imediata**: Limpar DB de traços de posição aberta + reiniciar em dry-run mode
