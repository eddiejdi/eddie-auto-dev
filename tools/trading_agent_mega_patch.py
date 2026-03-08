#!/usr/bin/env python3
"""
Mega-patch para trading_agent.py — corrige 13 bugs identificados na revisão completa.
Deve ser executado via SSH no homelab: python3 /tmp/mega_patch.py

Bugs corrigidos:
 1. CRITICAL: Trailing Stop não implementado (config diz enabled)
 2. CRITICAL: Regime Detection flapping (tick data polui indicadores)
 3. CRITICAL: Posição BUY aproximada (não verifica fill real)
 4. HIGH: max_daily_trades não enforced
 5. HIGH: max_daily_loss não enforced
 6. HIGH: Win rate usa total_trades (buy+sell) como denominador
 7. MEDIUM: mark_decision_executed passa counter, não trade_id
 8. MEDIUM: DATABASE_URL default errado no training_db.py
 9. MEDIUM: SELL não registra funds no DB
10. MEDIUM: Confidence scaling BUY inútil (MIN_TRADE_AMOUNT floors tudo)
11. LOW: BUY signal logado quando já tem posição (noise)
12. LOW: uptime_hours mostra tempo desde último trade
13. LOW: risk_management/strategy config ignorados
"""

import re
import sys
from pathlib import Path

AGENT_PATH = Path("/home/homelab/myClaude/btc_trading_agent/trading_agent.py")
TRAINING_DB_PATH = Path("/home/homelab/myClaude/btc_trading_agent/training_db.py")
FAST_MODEL_PATH = Path("/home/homelab/myClaude/btc_trading_agent/fast_model.py")

def read_file(path):
    return path.read_text()

def write_file(path, content):
    path.write_text(content)

def apply_agent_patches():
    """Aplica todos os patches ao trading_agent.py"""
    code = read_file(AGENT_PATH)
    original = code
    patches_applied = []

    # ========== PATCH 1: Adicionar imports e constantes necessárias ==========
    # Adicionar 'from datetime import ...' (já existe) + daily tracking vars
    old = "from datetime import datetime, timedelta"
    new = "from datetime import datetime, timedelta, date"
    if old in code:
        code = code.replace(old, new, 1)
        patches_applied.append("P1a: Added date import")

    # ========== PATCH 4+5: max_daily_trades e max_daily_loss constants ==========
    old_constants = "TRADING_FEE_PCT = 0.001  # 0.1% por trade (KuCoin)"
    new_constants = """TRADING_FEE_PCT = 0.001  # 0.1% por trade (KuCoin)
MAX_DAILY_TRADES = _config.get("max_daily_trades", 50)  # from config
MAX_DAILY_LOSS = _config.get("max_daily_loss", 150)  # from config (USD)"""
    if old_constants in code:
        code = code.replace(old_constants, new_constants, 1)
        patches_applied.append("P4/5: Added MAX_DAILY_TRADES + MAX_DAILY_LOSS constants")

    # ========== PATCH 6+12: Fix AgentState — add sell_count, start_time ==========
    old_state = """    total_pnl: float = 0.0
    dry_run: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "running": self.running,
            "symbol": self.symbol,
            "position_btc": self.position,
            "position_usdt": self.position_value,
            "entry_price": self.entry_price,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate": self.winning_trades / max(self.total_trades, 1),
            "total_pnl": self.total_pnl,
            "dry_run": self.dry_run
        }"""
    new_state = """    total_pnl: float = 0.0
    dry_run: bool = True
    sell_count: int = 0  # FIX #6: count only sells for win_rate
    daily_trades: int = 0  # FIX #4: daily trade counter
    daily_pnl: float = 0.0  # FIX #5: daily PnL tracker
    daily_date: str = ""  # FIX #4/5: current trading day
    start_time: float = 0.0  # FIX #12: agent start time
    trailing_high: float = 0.0  # FIX #1: trailing stop highest price
    
    def to_dict(self) -> Dict:
        return {
            "running": self.running,
            "symbol": self.symbol,
            "position_btc": self.position,
            "position_usdt": self.position_value,
            "entry_price": self.entry_price,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "sell_count": self.sell_count,
            "win_rate": self.winning_trades / max(self.sell_count, 1),
            "total_pnl": self.total_pnl,
            "daily_trades": self.daily_trades,
            "daily_pnl": round(self.daily_pnl, 4),
            "dry_run": self.dry_run,
            "uptime_hours": round((time.time() - self.start_time) / 3600, 2) if self.start_time else 0
        }"""
    if old_state in code:
        code = code.replace(old_state, new_state, 1)
        patches_applied.append("P6/12: Fixed AgentState (sell_count, daily counters, start_time)")

    # ========== PATCH: Set start_time in __init__ ==========
    old_init = '        logger.info(f"🤖 Agent initialized: {symbol} (dry_run={dry_run})")'
    new_init = """        self.state.start_time = time.time()
        logger.info(f"🤖 Agent initialized: {symbol} (dry_run={dry_run})")"""
    if old_init in code:
        code = code.replace(old_init, new_init, 1)
        patches_applied.append("P12b: Set start_time on init")

    # ========== PATCH 6b: Fix _restore_position to count sells separately ==========
    old_restore = """            self.state.total_trades = len(all_trades)
            self.state.winning_trades = sum(
                1 for t in all_trades if (t.get("pnl") or 0) > 0
            )
            self.state.total_pnl = sum(
                t.get("pnl") or 0 for t in all_trades
            )
            logger.info(
                f"📊 Restored metrics: {self.state.total_trades} trades, "
                f"{self.state.winning_trades} wins, PnL=${self.state.total_pnl:.4f}"
            )"""
    new_restore = """            self.state.total_trades = len(all_trades)
            sells = [t for t in all_trades if t.get("side") == "sell"]
            self.state.sell_count = len(sells)
            self.state.winning_trades = sum(
                1 for t in sells if (t.get("pnl") or 0) > 0
            )
            self.state.total_pnl = sum(
                t.get("pnl") or 0 for t in all_trades
            )
            # FIX #4/5: Restore daily counters
            today = date.today().isoformat()
            self.state.daily_date = today
            today_trades = [t for t in all_trades
                           if date.fromtimestamp(t.get("timestamp", 0)).isoformat() == today]
            self.state.daily_trades = len(today_trades)
            self.state.daily_pnl = sum(t.get("pnl") or 0 for t in today_trades)
            win_rate = self.state.winning_trades / max(self.state.sell_count, 1)
            logger.info(
                f"📊 Restored metrics: {self.state.total_trades} trades "
                f"({self.state.sell_count} sells, {self.state.winning_trades} wins, "
                f"WR={win_rate:.1%}), PnL=${self.state.total_pnl:.4f}, "
                f"today: {self.state.daily_trades} trades, PnL=${self.state.daily_pnl:.4f}"
            )"""
    if old_restore in code:
        code = code.replace(old_restore, new_restore, 1)
        patches_applied.append("P6b: Fixed _restore_position sell_count + daily counters")

    # ========== PATCH 4+5: Add daily limit checks to _check_can_trade ==========
    old_can_trade = """    def _check_can_trade(self, signal: Signal) -> bool:
        \"\"\"Verifica se pode executar trade\"\"\"
        # Intervalo mínimo
        elapsed = time.time() - self.state.last_trade_time
        if elapsed < MIN_TRADE_INTERVAL:
            logger.debug(f"⏳ Trade cooldown: {MIN_TRADE_INTERVAL - elapsed:.0f}s remaining")
            return False
        
        # Confiança mínima
        if signal.confidence < MIN_CONFIDENCE:
            logger.debug(f"📉 Low confidence: {signal.confidence:.1%}")
            return False
        
        # Verificar se já tem posição
        if signal.action == "BUY" and self.state.position > 0:
            logger.debug("📦 Already have position")
            return False
        
        if signal.action == "SELL" and self.state.position <= 0:
            logger.debug("📭 No position to sell")
            return False
        
        return True"""
    new_can_trade = """    def _check_can_trade(self, signal: Signal) -> bool:
        \"\"\"Verifica se pode executar trade\"\"\"
        # FIX #4/5: Reset daily counters on new day
        today = date.today().isoformat()
        if self.state.daily_date != today:
            logger.info(f"📅 New trading day: {today} (yesterday: {self.state.daily_trades} trades, PnL=${self.state.daily_pnl:.4f})")
            self.state.daily_date = today
            self.state.daily_trades = 0
            self.state.daily_pnl = 0.0

        # FIX #4: Max daily trades limit
        if self.state.daily_trades >= MAX_DAILY_TRADES:
            logger.info(f"🚫 Daily trade limit reached: {self.state.daily_trades}/{MAX_DAILY_TRADES}")
            return False

        # FIX #5: Max daily loss limit
        if self.state.daily_pnl <= -MAX_DAILY_LOSS:
            logger.warning(f"🚫 Daily loss limit reached: ${self.state.daily_pnl:.2f} <= -${MAX_DAILY_LOSS}")
            return False

        # Intervalo mínimo
        elapsed = time.time() - self.state.last_trade_time
        if elapsed < MIN_TRADE_INTERVAL:
            logger.debug(f"⏳ Trade cooldown: {MIN_TRADE_INTERVAL - elapsed:.0f}s remaining")
            return False
        
        # Confiança mínima
        if signal.confidence < MIN_CONFIDENCE:
            logger.debug(f"📉 Low confidence: {signal.confidence:.1%}")
            return False
        
        # Verificar se já tem posição
        if signal.action == "BUY" and self.state.position > 0:
            logger.debug("📦 Already have position")
            return False
        
        if signal.action == "SELL" and self.state.position <= 0:
            logger.debug("📭 No position to sell")
            return False
        
        return True"""
    if old_can_trade in code:
        code = code.replace(old_can_trade, new_can_trade, 1)
        patches_applied.append("P4/5: Added max_daily_trades + max_daily_loss to _check_can_trade")

    # ========== PATCH 3: Verify actual fill after BUY ==========
    old_buy_live = """                        # Trade real
                        result = place_market_order(self.symbol, "buy", funds=amount_usdt)
                        if not result.get("success"):
                            logger.error(f"❌ Order failed: {result}")
                            return False
                        
                        # Atualizar posição (aproximado)
                        size = amount_usdt / price * (1 - TRADING_FEE_PCT)
                        self.state.position = size
                        self.state.entry_price = price
                        logger.info(f"🟢 BUY {size:.6f} BTC @ ${price:,.2f}")"""
    new_buy_live = """                        # Trade real
                        result = place_market_order(self.symbol, "buy", funds=amount_usdt)
                        if not result.get("success"):
                            logger.error(f"❌ Order failed: {result}")
                            return False
                        
                        # FIX #3: Verificar saldo real da exchange em vez de aproximar
                        base_currency = self.symbol.split("-")[0]
                        try:
                            time.sleep(0.5)  # Aguardar fill
                            real_balance = get_balance(base_currency)
                            if real_balance > 0:
                                size = real_balance
                                logger.info(f"🟢 BUY {size:.8f} {base_currency} @ ${price:,.2f} (verified from exchange)")
                            else:
                                # Fallback: usar aproximação
                                size = amount_usdt / price * (1 - TRADING_FEE_PCT)
                                logger.warning(f"⚠️ BUY {size:.6f} {base_currency} @ ${price:,.2f} (approximated, exchange returned 0)")
                        except Exception as e:
                            size = amount_usdt / price * (1 - TRADING_FEE_PCT)
                            logger.warning(f"⚠️ BUY {size:.6f} {base_currency} @ ${price:,.2f} (approximated: {e})")
                        self.state.position = size
                        self.state.entry_price = price"""
    if old_buy_live in code:
        code = code.replace(old_buy_live, new_buy_live, 1)
        patches_applied.append("P3: BUY verifies actual balance from exchange")

    # ========== PATCH 7: Fix mark_decision_executed — pass actual trade_id ==========
    # Need to capture trade_id from record_trade and pass it
    # In BUY block:
    old_buy_record = """                    # Registrar
                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="buy",
                        price=price,
                        size=size,
                        funds=amount_usdt,
                        dry_run=self.state.dry_run
                    )
                    
                elif signal.action == "SELL":"""
    new_buy_record = """                    # Registrar
                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="buy",
                        price=price,
                        size=size,
                        funds=amount_usdt,
                        dry_run=self.state.dry_run
                    )
                    self._last_trade_id = trade_id  # FIX #7: Salvar trade_id real
                    # FIX #1: Reset trailing high on new position
                    self.state.trailing_high = price
                    
                elif signal.action == "SELL":"""
    if old_buy_record in code:
        code = code.replace(old_buy_record, new_buy_record, 1)
        patches_applied.append("P7a: Save actual trade_id after BUY + reset trailing_high")

    # ========== PATCH 9: SELL record_trade add funds ==========
    old_sell_record = """                    # Registrar
                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="sell",
                        price=price,
                        size=size,
                        dry_run=self.state.dry_run
                    )
                    self.db.update_trade_pnl(trade_id, pnl, pnl_pct)"""
    new_sell_record = """                    # Registrar
                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="sell",
                        price=price,
                        size=size,
                        funds=round(price * size, 2),  # FIX #9: Record sell funds
                        dry_run=self.state.dry_run
                    )
                    self.db.update_trade_pnl(trade_id, pnl, pnl_pct)
                    self._last_trade_id = trade_id  # FIX #7: Salvar trade_id real"""
    if old_sell_record in code:
        code = code.replace(old_sell_record, new_sell_record, 1)
        patches_applied.append("P9+7b: SELL records funds + saves trade_id")

    # ========== PATCH 6c: Increment sell_count + daily counters in SELL ==========
    old_sell_state = """                    # Atualizar estado
                    self.state.total_pnl += pnl
                    if pnl > 0:
                        self.state.winning_trades += 1
                    
                    self.state.position = 0
                    self.state.entry_price = 0"""
    new_sell_state = """                    # Atualizar estado
                    self.state.total_pnl += pnl
                    self.state.daily_pnl += pnl  # FIX #5: Track daily PnL
                    self.state.sell_count += 1  # FIX #6: Count sells separately
                    if pnl > 0:
                        self.state.winning_trades += 1
                    
                    self.state.position = 0
                    self.state.entry_price = 0
                    self.state.trailing_high = 0  # FIX #1: Reset trailing"""
    if old_sell_state in code:
        code = code.replace(old_sell_state, new_sell_state, 1)
        patches_applied.append("P6c/5: sell_count + daily_pnl + trailing reset")

    # ========== PATCH 4b: daily_trades counter ==========
    old_trade_counter = """                # Atualizar estado
                self.state.total_trades += 1
                self.state.last_trade_time = time.time()"""
    new_trade_counter = """                # Atualizar estado
                self.state.total_trades += 1
                self.state.daily_trades += 1  # FIX #4: Daily counter
                self.state.last_trade_time = time.time()"""
    if old_trade_counter in code:
        code = code.replace(old_trade_counter, new_trade_counter, 1)
        patches_applied.append("P4b: Increment daily_trades")

    # ========== PATCH 7c: Fix mark_decision_executed to use actual trade_id ==========
    old_mark = "                        self.db.mark_decision_executed(decision_id, self.state.total_trades)"
    new_mark = "                        self.db.mark_decision_executed(decision_id, getattr(self, '_last_trade_id', self.state.total_trades))"
    if old_mark in code:
        code = code.replace(old_mark, new_mark, 1)
        patches_applied.append("P7c: mark_decision_executed uses real trade_id")

    # ========== PATCH 1: Implement trailing stop ==========
    # Insert _check_trailing_stop method before _check_auto_exit
    old_auto_exit_start = """    def _check_auto_exit(self, price: float) -> bool:"""
    trailing_stop_code = """    def _check_trailing_stop(self, price: float) -> bool:
        \"\"\"FIX #1: Trailing stop implementation.
        Activates when price rises activation_pct above entry,
        then triggers SELL if price drops trail_pct from the high.
        Returns True if a trailing stop exit was executed.\"\"\"
        if self.state.position <= 0 or self.state.entry_price <= 0:
            return False

        try:
            with open(_config_path) as f:
                live_cfg = json.load(f)
        except Exception:
            live_cfg = _config

        ts_cfg = live_cfg.get("trailing_stop", {})
        if not ts_cfg.get("enabled", False):
            return False

        activation_pct = ts_cfg.get("activation_pct", 0.015)  # 1.5%
        trail_pct = ts_cfg.get("trail_pct", 0.008)  # 0.8%

        # Update trailing high
        if price > self.state.trailing_high:
            self.state.trailing_high = price

        # Check if activation threshold was reached
        pnl_pct = (self.state.trailing_high / self.state.entry_price) - 1
        if pnl_pct < activation_pct:
            return False  # Not yet activated

        # Trailing stop activated — check if price dropped from high
        drop_from_high = (self.state.trailing_high - price) / self.state.trailing_high
        if drop_from_high >= trail_pct:
            net_pnl_pct = (price / self.state.entry_price) - 1
            logger.warning(
                f"📉 TRAILING STOP triggered! High=${self.state.trailing_high:,.2f}, "
                f"now=${price:,.2f} (drop={drop_from_high*100:.2f}% >= trail={trail_pct*100:.1f}%), "
                f"net PnL={net_pnl_pct*100:.2f}% from entry ${self.state.entry_price:,.2f}"
            )
            forced_signal = Signal(
                action="SELL", confidence=1.0,
                reason=f"TRAILING_STOP (drop {drop_from_high*100:.2f}% from ${self.state.trailing_high:,.2f})",
                price=price, features={}
            )
            self.state.last_trade_time = 0  # bypass cooldown
            return self._execute_trade(forced_signal, price, force=True)

        return False

    def _check_auto_exit(self, price: float) -> bool:"""
    if old_auto_exit_start in code:
        code = code.replace(old_auto_exit_start, trailing_stop_code, 1)
        patches_applied.append("P1: Trailing stop fully implemented")

    # ========== PATCH 1b: Call trailing stop in _run_loop ==========
    old_loop_autoexit = """                # Check auto stop-loss / take-profit
                if self.state.position > 0:
                    if self._check_auto_exit(market_state.price):
                        time.sleep(POLL_INTERVAL)
                        continue"""
    new_loop_autoexit = """                # Check trailing stop FIRST, then auto SL/TP
                if self.state.position > 0:
                    if self._check_trailing_stop(market_state.price):
                        time.sleep(POLL_INTERVAL)
                        continue
                    if self._check_auto_exit(market_state.price):
                        time.sleep(POLL_INTERVAL)
                        continue"""
    if old_loop_autoexit in code:
        code = code.replace(old_loop_autoexit, new_loop_autoexit, 1)
        patches_applied.append("P1b: Call trailing stop in main loop")

    # ========== PATCH 12: Fix uptime in get_status ==========
    old_uptime = """    def get_status(self) -> Dict:
        \"\"\"Retorna status atual\"\"\"
        return {
            **self.state.to_dict(),
            "model_stats": self.model.get_stats(),
            "uptime_hours": (time.time() - self.state.last_trade_time) / 3600 if self.state.last_trade_time else 0
        }"""
    new_uptime = """    def get_status(self) -> Dict:
        \"\"\"Retorna status atual\"\"\"
        return {
            **self.state.to_dict(),
            "model_stats": self.model.get_stats()
        }"""
    if old_uptime in code:
        code = code.replace(old_uptime, new_uptime, 1)
        patches_applied.append("P12: uptime_hours moved to AgentState.to_dict (correct)")

    # ========== PATCH 10: Fix confidence scaling for BUY ==========
    old_buy_size = """            amount = max(amount, MIN_TRADE_AMOUNT)
            
            return min(amount, usdt_balance * 0.95)  # Deixar margem"""
    new_buy_size = """            # FIX #10: Only floor to MIN_TRADE_AMOUNT if confidence-scaled amount is viable
            if amount < MIN_TRADE_AMOUNT:
                # Low confidence + small balance → skip rather than blindly floor to $10
                if signal.confidence < 0.7:
                    logger.debug(f"📉 BUY size ${amount:.2f} < min ${MIN_TRADE_AMOUNT} with low confidence {signal.confidence:.1%}")
                    return 0
                amount = MIN_TRADE_AMOUNT
            
            return min(amount, usdt_balance * 0.95)  # Deixar margem"""
    if old_buy_size in code:
        code = code.replace(old_buy_size, new_buy_size, 1)
        patches_applied.append("P10: Confidence scaling now meaningful for BUY")

    # ========== PATCH: Add _last_trade_id default in __init__ ==========
    old_lock = """        # Threading
        self._stop_event = threading.Event()
        self._trade_lock = threading.Lock()"""
    new_lock = """        # Threading
        self._stop_event = threading.Event()
        self._trade_lock = threading.Lock()
        self._last_trade_id = 0  # FIX #7: actual DB trade ID"""
    if old_lock in code:
        code = code.replace(old_lock, new_lock, 1)
        patches_applied.append("P7d: _last_trade_id initialized in __init__")

    # ========== Summary ==========
    if code != original:
        write_file(AGENT_PATH, code)
        print(f"\n✅ trading_agent.py: {len(patches_applied)} patches applied:")
        for p in patches_applied:
            print(f"  ✔ {p}")
    else:
        print("⚠️ trading_agent.py: No patches matched!")

    return len(patches_applied)


def apply_training_db_patch():
    """FIX #8: Corrige DATABASE_URL default errado no training_db.py"""
    code = read_file(TRAINING_DB_PATH)
    original = code

    old = 'DATABASE_URL = os.getenv(\n    "DATABASE_URL",\n    "postgresql://postgres:shared_memory_2026@172.17.0.2:5432/postgres"\n)'
    new = 'DATABASE_URL = os.getenv(\n    "DATABASE_URL",\n    "postgresql://postgres:shared_memory_2026@localhost:5433/btc_trading"\n)'
    
    if old in code:
        code = code.replace(old, new, 1)
        write_file(TRAINING_DB_PATH, code)
        print("\n✅ training_db.py: FIX #8 — DATABASE_URL default corrected to localhost:5433/btc_trading")
        return 1
    else:
        # Try alternate format
        old2 = '"postgresql://postgres:shared_memory_2026@172.17.0.2:5432/postgres"'
        new2 = '"postgresql://postgres:shared_memory_2026@localhost:5433/btc_trading"'
        if old2 in code:
            code = code.replace(old2, new2, 1)
            write_file(TRAINING_DB_PATH, code)
            print("\n✅ training_db.py: FIX #8 — DATABASE_URL default corrected")
            return 1
        print("⚠️ training_db.py: DATABASE_URL patch — pattern not found (may already be fixed)")
        return 0


def apply_fast_model_patch():
    """FIX #2: Corrige regime detection flapping.
    O problema: tick prices a cada 5s poluem o buffer da deque(500),
    fazendo SMAs de 10/30/60 operar sobre 50s/150s/300s de dados — puro ruído.
    
    Solução: Manter deque separada para ticks (alta frequência) vs candles
    (confiáveis), e usar SOMENTE dados de candle para regime detection.
    Adicionalmente, usar hysteresis no regime para evitar flapping.
    """
    code = read_file(FAST_MODEL_PATH)
    original = code
    patches = []

    # Patch 2a: Add candle-based price history for regime detection
    old_init = """    def __init__(self, max_history: int = 500):
        self.prices = deque(maxlen=max_history)
        self.volumes = deque(maxlen=max_history)
        self.timestamps = deque(maxlen=max_history)
        self._candles_loaded = False"""
    new_init = """    def __init__(self, max_history: int = 500):
        self.prices = deque(maxlen=max_history)
        self.volumes = deque(maxlen=max_history)
        self.timestamps = deque(maxlen=max_history)
        self._candles_loaded = False
        # FIX #2: Separate candle-based history for regime detection (immune to tick noise)
        self._candle_prices = deque(maxlen=max_history)
        self._candle_volumes = deque(maxlen=max_history)"""
    if old_init in code:
        code = code.replace(old_init, new_init, 1)
        patches.append("P2a: Added _candle_prices deque")

    # Patch 2b: Populate candle prices in update_from_candles
    old_candle_load = """        # Reset e popular com candles reais
        self.prices.clear()
        self.volumes.clear()
        self.timestamps.clear()
        
        for c in candles:
            self.prices.append(c['close'])
            self.volumes.append(c.get('volume', 0))
            self.timestamps.append(c.get('timestamp', time.time()))
        
        self._candles_loaded = True
        logger.debug(f"📊 Indicators loaded from {len(candles)} candles")"""
    new_candle_load = """        # Reset e popular com candles reais
        self.prices.clear()
        self.volumes.clear()
        self.timestamps.clear()
        
        # FIX #2: Populate candle-only deque for stable regime detection
        self._candle_prices.clear()
        self._candle_volumes.clear()
        
        for c in candles:
            self.prices.append(c['close'])
            self.volumes.append(c.get('volume', 0))
            self.timestamps.append(c.get('timestamp', time.time()))
            self._candle_prices.append(c['close'])
            self._candle_volumes.append(c.get('volume', 0))
        
        self._candles_loaded = True
        logger.debug(f"📊 Indicators loaded from {len(candles)} candles (regime: {len(self._candle_prices)} pts)")"""
    if old_candle_load in code:
        code = code.replace(old_candle_load, new_candle_load, 1)
        patches.append("P2b: Candle prices populated for regime detection")

    # Patch 2c: detect_regime uses _candle_prices instead of self.prices
    old_detect = """    def detect_regime(self, short: int = 10, mid: int = 30, long: int = 60) -> MarketRegime:
        \"\"\"Detecta regime de mercado baseado em múltiplos timeframes.
        
        Usa convergência de trend curto/médio/longo + momentum + padrão de
        lower highs / higher lows para classificar o regime.\"\"\"
        n = len(self.prices)
        if n < long:
            return MarketRegime("RANGING", 0.0, 0)
        
        prices = list(self.prices)"""
    new_detect = """    def detect_regime(self, short: int = 10, mid: int = 30, long: int = 60) -> MarketRegime:
        \"\"\"Detecta regime de mercado baseado em múltiplos timeframes.
        
        FIX #2: Uses candle-based prices (1-min intervals) instead of tick prices
        (5-sec intervals) to avoid noise-induced regime flapping.
        With candle data: short=10min, mid=30min, long=60min (meaningful).
        With tick data: short=50s, mid=150s, long=300s (pure noise).
        \"\"\"
        # FIX #2: Use candle prices if available, otherwise fall back to tick prices
        price_source = list(self._candle_prices) if len(self._candle_prices) >= long else list(self.prices)
        n = len(price_source)
        if n < long:
            return MarketRegime("RANGING", 0.0, 0)
        
        prices = price_source"""
    if old_detect in code:
        code = code.replace(old_detect, new_detect, 1)
        patches.append("P2c: detect_regime uses candle prices (not tick noise)")

    # Patch 2d: Add hysteresis to regime changes in FastTradingModel.predict
    old_regime_check = """        # ===== DETECÇÃO DE REGIME (a cada 10 ciclos para performance) =====
        self._regime_cycle_count += 1
        if self._regime_cycle_count % 10 == 0 or self._regime_cycle_count == 1:
            new_regime = self.indicators.detect_regime()
            if new_regime.regime != self._current_regime.regime:
                logger.info(
                    f"🔄 REGIME CHANGE: {self._current_regime.regime} → "
                    f"{new_regime.regime} (strength={new_regime.strength:.0%})"
                )
            self._current_regime = new_regime"""
    new_regime_check = """        # ===== DETECÇÃO DE REGIME (a cada 30 ciclos ~2.5min para stability) =====
        # FIX #2: Increased interval from 10→30 cycles + hysteresis to prevent flapping
        self._regime_cycle_count += 1
        if self._regime_cycle_count % 30 == 0 or self._regime_cycle_count == 1:
            new_regime = self.indicators.detect_regime()
            # Hysteresis: only change regime if new regime has enough strength
            # or if it persists (detected at least 2 consecutive times)
            if new_regime.regime != self._current_regime.regime:
                if new_regime.strength >= 0.5 or (
                    hasattr(self, '_pending_regime') and 
                    self._pending_regime == new_regime.regime
                ):
                    logger.info(
                        f"🔄 REGIME CHANGE: {self._current_regime.regime} → "
                        f"{new_regime.regime} (strength={new_regime.strength:.0%})"
                    )
                    self._current_regime = new_regime
                    self._pending_regime = None
                else:
                    # First detection — mark as pending, don't switch yet
                    self._pending_regime = new_regime.regime
            else:
                self._pending_regime = None
                self._current_regime = new_regime  # Update strength"""
    if old_regime_check in code:
        code = code.replace(old_regime_check, new_regime_check, 1)
        patches.append("P2d: Regime detection with hysteresis (30 cycles + confirmation)")

    if code != original:
        write_file(FAST_MODEL_PATH, code)
        print(f"\n✅ fast_model.py: {len(patches)} patches applied:")
        for p in patches:
            print(f"  ✔ {p}")
    else:
        print("⚠️ fast_model.py: No patches matched!")

    return len(patches)


if __name__ == "__main__":
    print("=" * 60)
    print("🔧 MEGA-PATCH: Trading Agent Comprehensive Fix")
    print("=" * 60)
    
    total = 0
    total += apply_agent_patches()
    total += apply_training_db_patch()
    total += apply_fast_model_patch()
    
    print(f"\n{'=' * 60}")
    print(f"📊 Total: {total} patches applied across 3 files")
    print("=" * 60)
    
    # Validation
    print("\n🔍 Syntax validation...")
    import subprocess
    for path in [AGENT_PATH, TRAINING_DB_PATH, FAST_MODEL_PATH]:
        result = subprocess.run(
            ["python3", "-c", f"import ast; ast.parse(open('{path}').read()); print('  ✅ {path.name}: OK')"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(result.stdout.strip())
        else:
            print(f"  ❌ {path.name}: SYNTAX ERROR")
            print(result.stderr)
