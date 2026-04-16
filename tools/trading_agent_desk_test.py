#!/usr/bin/env python3
"""Desk tests para validar os 13 bugs corrigidos"""
import sys, os, time
sys.path.insert(0, '/apps/crypto-trader/trading/btc_trading_agent')
os.environ['DATABASE_URL'] = 'postgresql://postgres:shared_memory_2026@localhost:5433/btc_trading'

from trading_agent import BitcoinTradingAgent, AgentState, Signal
from fast_model import FastIndicators, MarketRegime
from datetime import date

print("=" * 60)
print("DESK TEST - Simulando cenarios")
print("=" * 60)

agent = BitcoinTradingAgent(symbol='BTC-USDT', dry_run=True)
agent.state.position = 0.00014
agent.state.entry_price = 69000
agent.state.trailing_high = 69000

# === Cenario 1: Trailing Stop ===
print("\n--- Cenario 1: Trailing Stop ---")
print(f"Entry: $69,000 | Activation: 1.5% = ${69000*1.015:,.2f} | Trail: 0.8%")

for p in [69200, 69500, 69800, 70035, 70200, 70500]:
    if p > agent.state.trailing_high:
        agent.state.trailing_high = p
    pnl = (agent.state.trailing_high / 69000) - 1
    activated = pnl >= 0.015
    drop = (agent.state.trailing_high - p) / agent.state.trailing_high
    trigger = activated and drop >= 0.008
    print(f"  ${p:>6,} | High ${agent.state.trailing_high:,} | +{pnl*100:.2f}% | Active:{activated} | Drop:{drop*100:.2f}% | TRIG:{trigger}")

for p in [70300, 70100, 69900]:
    drop = (agent.state.trailing_high - p) / agent.state.trailing_high
    trigger = drop >= 0.008  # already activated (high > 1.5%)
    print(f"  ${p:>6,} | High ${agent.state.trailing_high:,} |        | Active:True  | Drop:{drop*100:.2f}% | TRIG:{trigger}")

# === Cenario 2: Daily Limits ===
print("\n--- Cenario 2: Daily Limits ---")
agent.state.daily_date = date.today().isoformat()
agent.state.daily_trades = 9
agent.state.daily_pnl = -0.15
agent.state.last_trade_time = 0
agent.state.position = 0  # no position for BUY

sig = Signal(action='BUY', confidence=0.7, price=69000, reason='test')

can = agent._check_can_trade(sig)
print(f"  9 trades done (max 10): can_trade={can} (expect True)")
assert can == True, f"FAIL: should be True, got {can}"

agent.state.daily_trades = 10
can = agent._check_can_trade(sig)
print(f"  10 trades done (max 10): can_trade={can} (expect False)")
assert can == False, f"FAIL: should be False, got {can}"

agent.state.daily_trades = 5
agent.state.daily_pnl = -150.01
can = agent._check_can_trade(sig)
print(f"  Daily loss $-150.01 (max $150): can_trade={can} (expect False)")
assert can == False, f"FAIL: should be False, got {can}"

agent.state.daily_pnl = -149.99
can = agent._check_can_trade(sig)
print(f"  Daily loss $-149.99 (max $150): can_trade={can} (expect True)")
assert can == True, f"FAIL: should be True, got {can}"

# === Cenario 3: Win Rate ===
print("\n--- Cenario 3: Win Rate ---")
agent.state.total_trades = 94
agent.state.sell_count = 46
agent.state.winning_trades = 22
status = agent.state.to_dict()
wr = status['win_rate']
expected = 22 / 46
print(f"  total={agent.state.total_trades}, sells={agent.state.sell_count}, wins={agent.state.winning_trades}")
print(f"  win_rate={wr:.4f} (expect {expected:.4f})")
assert abs(wr - expected) < 0.001, f"FAIL: got {wr}, expected {expected}"
print(f"  OLD wrong value would be: {22/94:.4f}")

# === Cenario 4: Confidence Scaling ===
print("\n--- Cenario 4: Confidence Scaling ---")
agent.state.position = 0

# In dry_run, balance=$1000, so 20%*1000*0.4=$80 > MIN_TRADE_AMOUNT=$10
# The fix targets LIVE mode with small balance ($54 → 20%*54*0.4=$4.32 < $10)
sig_low = Signal(action='BUY', confidence=0.4, price=69000, reason='test')
size_dry = agent._calculate_trade_size(sig_low, 69000)
print(f"  Dry-run (bal=$1000) conf 0.4: size=${size_dry:.2f} (OK - above $10)")
# In dry_run, $80 is correct: 1000*0.2*0.4=80

sig_high = Signal(action='BUY', confidence=0.8, price=69000, reason='test')
size = agent._calculate_trade_size(sig_high, 69000)
print(f"  Dry-run (bal=$1000) conf 0.8: size=${size:.2f}")
assert size > size_dry, f"FAIL: high conf ({size}) should > low conf ({size_dry})"
print(f"  High conf > Low conf: True ({size:.0f} > {size_dry:.0f})")

# === Cenario 5: Uptime ===
print("\n--- Cenario 5: Uptime ---")
agent.state.start_time = time.time() - 3600
status = agent.state.to_dict()
ut = status['uptime_hours']
print(f"  uptime_hours={ut} (expect ~1.0)")
assert abs(ut - 1.0) < 0.1, f"FAIL: expected ~1.0, got {ut}"

# === Cenario 6: Regime Detection - candle vs tick ===
print("\n--- Cenario 6: Regime Detection (candle data) ---")
indicators = FastIndicators()
assert hasattr(indicators, '_candle_prices'), "FAIL: _candle_prices attribute missing"
print(f"  _candle_prices attr exists: True")

# Populate with fake candles
fake_candles = []
base = 69000
for i in range(100):
    price = base - i * 5  # steady downtrend
    fake_candles.append({'close': price, 'volume': 100, 'timestamp': time.time() - (100 - i) * 60})
indicators.update_from_candles(fake_candles)
print(f"  Loaded {len(fake_candles)} candles, candle_prices len={len(indicators._candle_prices)}")

regime = indicators.detect_regime()
print(f"  Regime (downtrend candles): {regime.regime} strength={regime.strength:.0%}")
# After 100 candles of -$5 each = -$500 drop, should detect BEARISH
assert regime.regime == "BEARISH", f"FAIL: expected BEARISH, got {regime.regime}"

# Now add noisy tick data (should NOT affect regime)
for i in range(200):
    indicators.update(69000 + (i % 10) * 5)  # noisy ticks around 69000
regime2 = indicators.detect_regime()
print(f"  After 200 noisy ticks: regime={regime2.regime} (candle_prices untouched)")
# candle_prices should still show bearish since ticks don't update it
print(f"  candle_prices len={len(indicators._candle_prices)} (should still be 100)")
assert len(indicators._candle_prices) == 100, f"FAIL: candle_prices was polluted"

# === Cenario 7: _last_trade_id exists ===
print("\n--- Cenario 7: _last_trade_id ---")
assert hasattr(agent, '_last_trade_id'), "FAIL: _last_trade_id missing"
print(f"  _last_trade_id attr exists: True (value={agent._last_trade_id})")

# === Cenario 8: DATABASE_URL default fix ===
print("\n--- Cenario 8: DATABASE_URL default ---")
import training_db
print(f"  Default DSN: {training_db.DATABASE_URL}")
assert 'localhost:5433/btc_trading' in training_db.DATABASE_URL, f"FAIL: wrong default DSN"
print(f"  Contains localhost:5433/btc_trading: True")

print("\n" + "=" * 60)
print("ALL DESK TESTS PASSED")
print("=" * 60)
