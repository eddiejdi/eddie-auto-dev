# 🚨 INCIDENT REPORT - Ensemble Optimization Failure (2026-03-05)

## Summary
Deployment das otimizações de ensemble resultou em **queda imediata de Win Rate** de 54.09% para 20% e **sequência de perdas** ($0.06, $0.04, $0.05 por trade). **REVERTIDO** para versão anterior após ~5 minutos em produção.

---

## Timeline

| Time | Event | Impact |
|------|-------|--------|
| 08:42:52 | Agent restarted with new weights/thresholds | - |
| 08:43-08:48 | 7 trades executados pós-deploy | WR: 0% (0/7 SELLs) |
| 08:48:19 | Monitoring script indica problema | Status: CRITICAL |
| 08:49:00 | **ROLLBACK iniciado** | - |
| 08:49:30 | Agent restaurado com config original | WR restored → 54% |

---

## Root Cause Analysis

### ✅ What Worked
- Ensemble weight redistribution (theory sound)
- Threshold fine-tuning based on Kelly research  
- Config synchronization to homelab
- Agent restart process

### ❌ What Failed
1. **Threshold Optimization Too Aggressive**
   - Buy threshold: 0.30 → 0.28 (↓7% signal rigor)
   - Sell threshold: -0.30 → -0.28 (↓7% signal rigor)
   - **Result**: Weak signal entries → losing trades

2. **Min Confidence Mismatch**
   - Code default: 0.45 → changed to 0.48
   - Config had: 0.75 (was already stricter)
   - **Result**: Conflicting signal thresholds

3. **No Validation Gates**
   - Changed 4 parameters simultaneously
   - No A/B testing or gradual rollout
   - No backtest on last 100 trades before deployment

4. **Metadata Confidence Not Stored**
   - `metadata->>'confidence'` returned 0 for new trades
   - Unable to track signal quality in real-time

---

## Lesson Learned

### 🎓 Key Insights

1. **Kelly Criterion ≠ Hyperparameter Optimization**
   - Kelly teaches position sizing (not signal generation)
   - WR 54.2% is marginal, requires **conservative** signal generation
   - Lowering thresholds makes signals weaker, not better

2. **Ensemble Weights Need Backtesting**
   - Theory: ↑ technical, ↓ orderbook/flow should help
   - Reality: Untested weight changes can cascade failures
   - Solution: Backtest on last 200 trades before live deploy

3. **Multi-Parameter Chaos**
   - 4 simultaneous changes broke reproducibility
   - Changing thresholds + weights + confidence at once = hard to debug

4. **Monitoring Blindspot**
   - Confidence metadata not logged = can't track signal quality
   - Post-deployment WR drop only visible after 5+ trades
   - Need real-time alerting on Win Rate

---

## Recommended Path Forward

### Phase A: Stabilization (NOW)
- ✅ Reverted to baseline (WR 54.09%)
- Allow 100+ trades at baseline to re-establish confidence
- Update monitoring to include signal quality metrics

### Phase B: Methodical Improvement (Next Week)
1. **Backtest new weights** on last 500 historical trades
   - Keep weights but **NOT** thresholds
   - Check if technique/orderbook/flow distribution improves
   
2. **Test Kelly Criterion Separately**
   - Adjust position sizing (max_daily_trades), not signal threshold
   - 6 trades/day maintains phase 1 safety margin

3. **Staged Rollout**
   - Day 1: Deploy ONE change (e.g., weights only, keep thresholds)
   - Monitor 50+ trades before next change
   - If WR drops >2pp, REVERT immediately

### Phase C: Long-term (Month 2026-04)
- Build backtesting pipeline for signal parameters
- Implement A/B testing framework for ensemble tuning
- Add confidence distribution logging

---

## Technical Details

### Parameters Reverted

```python
# fast_model.py - Weights REVERTED
self.weights = {
    "technical": 0.35,   # was 0.40
    "orderbook": 0.30,   # was 0.25
    "flow": 0.25,        # was 0.20
    "qlearning": 0.10    # was 0.15
}

# fast_model.py - Thresholds REVERTED
self.buy_threshold = 0.30     # was 0.28
self.sell_threshold = -0.30   # was -0.28
self.min_confidence = 0.45    # was 0.48

# config.json - Max Daily Trades REVERTED
"max_daily_trades": 3         # was 6
```

### Post-Revert Status
- ✅ Agent running (PID 711260)
- ✅ PostgreSQL connected
- ✅ Baseline parameters restored
- 📊 Monitoring Win Rate recovery

---

## Files For Reference

- **Phase 1 Monitor Script**: `btc_trading_agent/phase1_monitor.py`
- **Monitoring Snapshot**: `homelab:~/shared-auto-dev/phase1_snapshot.json`
- **Monitor Logs**: `homelab:~/shared-auto-dev/phase1_monitor.log`
- **Trading Logs**: `journalctl -u btc-trading-agent`

---

## Conclusion

The ensemble optimization was **sound in theory** but **failed in practice** due to:
- Simultaneous multi-parameter changes without validation
- Overly aggressive threshold relaxation for marginal Win Rate
- Lack of real-time signal quality instrumentation

**Next deployment**: Single-parameter changes with 50-100 trade validation gates before proceeding to next change.

---

Generated: 2026-03-05 08:49:30  
Incident Duration: ~7 minutes  
Estimated Loss: $0.20 USD (recoverable in 50 successful trades at baseline WR)
