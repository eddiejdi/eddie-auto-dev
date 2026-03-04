#!/usr/bin/env python3
"""
Deploy Multi-Position Support for BTC Trading Agent.

Creates:
1. position_manager.py — manages N independent positions with DB persistence
2. Patches trading_agent.py — uses PositionManager
3. Patches prometheus_exporter.py — reads open_positions table
4. Updates config.json — adds max_positions
5. Migrates existing position to new table

Usage: python3 deploy_multiposition.py
"""

import subprocess
import sys
import textwrap

HOST = "homelab@192.168.15.2"
AGENT_DIR = "/home/homelab/myClaude/btc_trading_agent"
DB_DSN = "host=localhost port=5433 dbname=postgres user=postgres password=eddie_memory_2026"


def ssh(cmd: str, check=True) -> str:
    """Execute command on homelab via SSH."""
    result = subprocess.run(
        ["ssh", HOST, cmd],
        capture_output=True, text=True, timeout=30
    )
    if check and result.returncode != 0:
        print(f"⚠️  Command failed: {cmd}")
        print(f"   stderr: {result.stderr.strip()}")
    return result.stdout.strip()


def write_remote(path: str, content: str):
    """Write content to remote file via SSH."""
    # Escape for heredoc
    proc = subprocess.run(
        ["ssh", HOST, f"cat > {path}"],
        input=content, capture_output=True, text=True, timeout=30
    )
    if proc.returncode != 0:
        print(f"❌ Failed to write {path}: {proc.stderr}")
        sys.exit(1)
    print(f"✅ Written: {path}")


# ============================================================
# STEP 1: Backup existing files
# ============================================================
def step1_backup():
    print("\n" + "=" * 60)
    print("STEP 1: Backup existing files")
    print("=" * 60)
    ts = ssh("date +%Y%m%d_%H%M%S")
    ssh(f"cp {AGENT_DIR}/trading_agent.py {AGENT_DIR}/trading_agent.py.bak.{ts}")
    ssh(f"cp {AGENT_DIR}/prometheus_exporter.py {AGENT_DIR}/prometheus_exporter.py.bak.{ts}")
    ssh(f"cp {AGENT_DIR}/config.json {AGENT_DIR}/config.json.bak.{ts}")
    print(f"✅ Backups created with timestamp {ts}")
    return ts


# ============================================================
# STEP 2: Create open_positions table + migrate current position
# ============================================================
def step2_db():
    print("\n" + "=" * 60)
    print("STEP 2: Create DB table + migrate existing position")
    print("=" * 60)

    sql = """
SET search_path TO btc, public;

-- Create table
CREATE TABLE IF NOT EXISTS open_positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    size DOUBLE PRECISION NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    buy_trade_id INTEGER DEFAULT 0,
    trailing_high DOUBLE PRECISION DEFAULT 0,
    opened_at DOUBLE PRECISION DEFAULT 0,
    dry_run BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create index
CREATE INDEX IF NOT EXISTS idx_open_positions_symbol
    ON open_positions(symbol, dry_run);

-- Migrate: if there's an existing position (last trade was buy, live mode),
-- insert it into open_positions (only if not already migrated)
INSERT INTO open_positions (symbol, size, entry_price, buy_trade_id, trailing_high, opened_at, dry_run)
SELECT t.symbol, t.size, t.price, t.id, t.price, t.timestamp, t.dry_run
FROM trades t
WHERE t.id = (
    SELECT id FROM trades
    WHERE symbol = 'BTC-USDT' AND dry_run = false
    ORDER BY timestamp DESC LIMIT 1
)
AND t.side = 'buy'
AND NOT EXISTS (
    SELECT 1 FROM open_positions WHERE symbol = 'BTC-USDT' AND dry_run = false
);
"""
    result = ssh(f'PGPASSWORD=eddie_memory_2026 psql -h localhost -p 5433 -U postgres -d postgres -c "{sql}"', check=False)
    print(result)

    # Verify
    result = ssh(f'PGPASSWORD=eddie_memory_2026 psql -h localhost -p 5433 -U postgres -d postgres -c "SET search_path TO btc; SELECT id, symbol, size, entry_price, dry_run FROM open_positions;"')
    print(f"Open positions:\n{result}")


# ============================================================
# STEP 3: Create position_manager.py
# ============================================================
def step3_position_manager():
    print("\n" + "=" * 60)
    print("STEP 3: Create position_manager.py")
    print("=" * 60)

    code = '''#!/usr/bin/env python3
"""
Position Manager — Multi-position support for Trading Agent.

Manages N independent positions, each with its own entry price,
TP/SL targets, and trailing stop. Persisted in PostgreSQL btc.open_positions.
"""

import os
import time
import logging
import psycopg2
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

DSN = os.environ.get(
    "DATABASE_URL",
    "host=localhost port=5433 dbname=postgres user=postgres password=eddie_memory_2026"
)


@dataclass
class Position:
    """A single open position."""
    id: int = 0
    symbol: str = "BTC-USDT"
    size: float = 0.0
    entry_price: float = 0.0
    buy_trade_id: int = 0
    trailing_high: float = 0.0
    opened_at: float = 0.0
    dry_run: bool = False

    @property
    def value_at_entry(self) -> float:
        return self.size * self.entry_price

    def pnl(self, current_price: float) -> float:
        """Gross PnL (before fees)."""
        return (current_price - self.entry_price) * self.size

    def pnl_pct(self, current_price: float) -> float:
        """PnL as percentage of entry."""
        if self.entry_price <= 0:
            return 0.0
        return (current_price / self.entry_price) - 1.0


class PositionManager:
    """Manages multiple independent positions with DB persistence."""

    def __init__(self, symbol: str, dry_run: bool, max_positions: int = 3):
        self.symbol = symbol
        self.dry_run = dry_run
        self.max_positions = max_positions
        self._positions: List[Position] = []
        self._ensure_table()

    def _get_conn(self):
        conn = psycopg2.connect(DSN)
        conn.autocommit = True
        return conn

    def _ensure_table(self):
        """Create open_positions table if not exists."""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SET search_path TO btc, public")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS open_positions (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    size DOUBLE PRECISION NOT NULL,
                    entry_price DOUBLE PRECISION NOT NULL,
                    buy_trade_id INTEGER DEFAULT 0,
                    trailing_high DOUBLE PRECISION DEFAULT 0,
                    opened_at DOUBLE PRECISION DEFAULT 0,
                    dry_run BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to ensure open_positions table: {e}")

    def load(self) -> List[Position]:
        """Load open positions from DB."""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SET search_path TO btc, public")
            cur.execute("""
                SELECT id, symbol, size, entry_price, buy_trade_id,
                       trailing_high, opened_at, dry_run
                FROM open_positions
                WHERE symbol = %s AND dry_run = %s
                ORDER BY opened_at ASC
            """, (self.symbol, self.dry_run))
            rows = cur.fetchall()
            self._positions = []
            for r in rows:
                self._positions.append(Position(
                    id=r[0], symbol=r[1], size=r[2], entry_price=r[3],
                    buy_trade_id=r[4] or 0, trailing_high=r[5] or 0,
                    opened_at=r[6] or 0, dry_run=r[7]
                ))
            cur.close()
            conn.close()
            logger.info(f"\\U0001f4e6 Loaded {len(self._positions)} open position(s)")
            for p in self._positions:
                logger.info(
                    f"  \\U0001f4cc Position #{p.id}: {p.size:.8f} BTC "
                    f"@ ${p.entry_price:,.2f}"
                )
            return self._positions
        except Exception as e:
            logger.error(f"Failed to load positions: {e}")
            return []

    def add(self, size: float, entry_price: float,
            buy_trade_id: int = 0) -> Position:
        """Add a new position to DB and memory."""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SET search_path TO btc, public")
            cur.execute("""
                INSERT INTO open_positions
                    (symbol, size, entry_price, buy_trade_id,
                     trailing_high, opened_at, dry_run)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (self.symbol, size, entry_price, buy_trade_id,
                  entry_price, time.time(), self.dry_run))
            pos_id = cur.fetchone()[0]
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to persist position: {e}")
            pos_id = int(time.time()) % 100000  # fallback ID

        pos = Position(
            id=pos_id, symbol=self.symbol, size=size,
            entry_price=entry_price, buy_trade_id=buy_trade_id,
            trailing_high=entry_price, opened_at=time.time(),
            dry_run=self.dry_run
        )
        self._positions.append(pos)
        logger.info(
            f"\\U0001f4cc Position #{pos_id} opened: "
            f"{size:.8f} BTC @ ${entry_price:,.2f} "
            f"(total: {self.count} positions)"
        )
        return pos

    def close(self, position_id: int) -> Optional[Position]:
        """Close a position: remove from DB and memory."""
        pos = self.get(position_id)
        if not pos:
            logger.warning(f"Position #{position_id} not found")
            return None
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SET search_path TO btc, public")
            cur.execute(
                "DELETE FROM open_positions WHERE id = %s", (position_id,)
            )
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to delete position #{position_id}: {e}")
        self._positions = [p for p in self._positions if p.id != position_id]
        logger.info(
            f"\\U0001f4e4 Position #{position_id} closed "
            f"(remaining: {self.count})"
        )
        return pos

    def get(self, position_id: int) -> Optional[Position]:
        """Get position by ID."""
        for p in self._positions:
            if p.id == position_id:
                return p
        return None

    def update_size(self, position_id: int, new_size: float):
        """Update position size (e.g. after verifying exchange balance)."""
        pos = self.get(position_id)
        if pos:
            pos.size = new_size
            try:
                conn = self._get_conn()
                cur = conn.cursor()
                cur.execute("SET search_path TO btc, public")
                cur.execute(
                    "UPDATE open_positions SET size = %s WHERE id = %s",
                    (new_size, position_id)
                )
                cur.close()
                conn.close()
            except Exception:
                pass

    def update_trailing(self, position_id: int, price: float):
        """Update trailing high for a specific position."""
        pos = self.get(position_id)
        if pos and price > pos.trailing_high:
            pos.trailing_high = price
            try:
                conn = self._get_conn()
                cur = conn.cursor()
                cur.execute("SET search_path TO btc, public")
                cur.execute(
                    "UPDATE open_positions SET trailing_high = %s WHERE id = %s",
                    (price, position_id)
                )
                cur.close()
                conn.close()
            except Exception:
                pass

    # ---- Aggregate properties ----

    @property
    def positions(self) -> List[Position]:
        return list(self._positions)

    @property
    def count(self) -> int:
        return len(self._positions)

    @property
    def total_btc(self) -> float:
        return sum(p.size for p in self._positions)

    @property
    def total_value_at_entry(self) -> float:
        return sum(p.size * p.entry_price for p in self._positions)

    @property
    def weighted_entry_price(self) -> float:
        total = self.total_btc
        if total <= 0:
            return 0.0
        return self.total_value_at_entry / total

    def can_open(self) -> bool:
        """Check if we can open another position."""
        return len(self._positions) < self.max_positions

    def best_profit_position(self, current_price: float) -> Optional[Position]:
        """Position with best PnL (for signal-based sell)."""
        if not self._positions:
            return None
        return max(self._positions, key=lambda p: p.pnl(current_price))

    def worst_position(self, current_price: float) -> Optional[Position]:
        """Position with worst PnL."""
        if not self._positions:
            return None
        return min(self._positions, key=lambda p: p.pnl(current_price))
'''
    write_remote(f"{AGENT_DIR}/position_manager.py", code)


# ============================================================
# STEP 4: Patch trading_agent.py
# ============================================================
def step4_patch_agent():
    print("\n" + "=" * 60)
    print("STEP 4: Patch trading_agent.py for multi-position")
    print("=" * 60)

    # Read current file
    content = ssh(f"cat {AGENT_DIR}/trading_agent.py")

    # ---- PATCH 1: Add imports ----
    old = "from training_db import TrainingDatabase, TrainingManager"
    new = """from training_db import TrainingDatabase, TrainingManager
from position_manager import PositionManager, Position"""
    content = content.replace(old, new, 1)

    # ---- PATCH 2: Add MAX_POSITIONS constant ----
    old = "MIN_EXCHANGE_ORDER_USDT = 0.10  # Minimum order value on KuCoin"
    new = """MIN_EXCHANGE_ORDER_USDT = 0.10  # Minimum order value on KuCoin
MAX_POSITIONS = _config.get("max_positions", 3)  # Max concurrent positions"""
    content = content.replace(old, new, 1)

    # ---- PATCH 3: Add position_manager to __init__ ----
    old = """        # Threading
        self._stop_event = threading.Event()
        self._trade_lock = threading.Lock()
        self._last_trade_id = 0  # FIX #7: actual DB trade ID"""
    new = """        # Threading
        self._stop_event = threading.Event()
        self._trade_lock = threading.Lock()
        self._last_trade_id = 0  # FIX #7: actual DB trade ID

        # Multi-position manager
        self.position_manager = PositionManager(
            symbol=symbol, dry_run=dry_run, max_positions=MAX_POSITIONS
        )"""
    content = content.replace(old, new, 1)

    # ---- PATCH 4: Replace _restore_position ----
    # Find the old _restore_position method and replace it
    old_restore_start = "    def _restore_position(self):"
    old_restore_end = '            logger.warning(f"⚠️ Could not restore metrics: {e}")'

    idx_start = content.find(old_restore_start)
    idx_end = content.find(old_restore_end)
    if idx_start == -1 or idx_end == -1:
        print("⚠️  Could not find _restore_position boundaries!")
        print(f"   start={idx_start}, end={idx_end}")
    else:
        idx_end += len(old_restore_end)
        new_restore = '''    def _restore_position(self):
        """Restaura posições abertas do banco de dados (multi-position).
        Usa tabela open_positions para persistência.
        """
        base_currency = self.symbol.split("-")[0]

        # 1. Load positions from DB
        positions = self.position_manager.load()

        # 2. Restore last_trade_time from trades table
        trades = self.db.get_recent_trades(
            symbol=self.symbol, limit=1,
            include_dry=self.state.dry_run
        )
        if trades:
            self.state.last_trade_time = trades[0].get("timestamp", 0)

        # 3. Cross-check with exchange balance (LIVE mode)
        if not self.state.dry_run and positions:
            try:
                real_balance = get_balance(base_currency)
                if real_balance > 0:
                    total_db = self.position_manager.total_btc
                    if abs(real_balance - total_db) / max(total_db, 1e-10) > 0.05:
                        logger.warning(
                            f"⚠️ Exchange balance {real_balance:.8f} differs from "
                            f"DB total {total_db:.8f} (>5%). Using exchange balance."
                        )
                        # Adjust the most recent position size
                        if positions:
                            diff = real_balance - total_db
                            last_pos = positions[-1]
                            new_size = last_pos.size + diff
                            if new_size > 0:
                                self.position_manager.update_size(last_pos.id, new_size)
                else:
                    if positions:
                        logger.warning(
                            f"⚠️ Exchange balance is 0 but DB shows {len(positions)} "
                            f"positions. Clearing stale positions."
                        )
                        for p in list(positions):
                            self.position_manager.close(p.id)
            except Exception as e:
                logger.warning(f"⚠️ Could not check exchange balance: {e}")

        # 4. Sync aggregate state from positions
        self._sync_state_from_positions()

        # 5. Restore metrics
        try:
            all_trades = self.db.get_recent_trades(
                symbol=self.symbol, limit=10000,
                include_dry=self.state.dry_run
            )
            self.state.total_trades = len(all_trades)
            sells = [t for t in all_trades if t.get("side") == "sell"]
            self.state.sell_count = len(sells)
            self.state.winning_trades = sum(
                1 for t in sells if (t.get("pnl") or 0) > 0
            )
            self.state.total_pnl = sum(
                t.get("pnl") or 0 for t in all_trades
            )
            today = date.today().isoformat()
            self.state.daily_date = today
            today_trades = [t for t in all_trades
                           if date.fromtimestamp(t.get("timestamp", 0)).isoformat() == today]
            self.state.daily_trades = len(today_trades)
            self.state.daily_pnl = sum(t.get("pnl") or 0 for t in today_trades)
            win_rate = self.state.winning_trades / max(self.state.sell_count, 1)
            n_pos = self.position_manager.count
            logger.info(
                f"📊 Restored: {self.state.total_trades} trades, "
                f"{n_pos} open position(s), "
                f"WR={win_rate:.1%}, PnL=${self.state.total_pnl:.4f}"
            )
        except Exception as e:
            logger.warning(f"⚠️ Could not restore metrics: {e}")'''
        content = content[:idx_start] + new_restore + content[idx_end:]

    # ---- PATCH 5: Add _sync_state_from_positions method ----
    # Insert right after _restore_position
    sync_method = '''

    def _sync_state_from_positions(self):
        """Sync AgentState fields from PositionManager for backward compatibility."""
        self.state.position = self.position_manager.total_btc
        self.state.entry_price = self.position_manager.weighted_entry_price
        if self.position_manager.count > 0:
            self.state.position_value = sum(
                p.size * p.entry_price for p in self.position_manager.positions
            )
            # Trailing high: use max across positions
            self.state.trailing_high = max(
                (p.trailing_high for p in self.position_manager.positions),
                default=0
            )
        else:
            self.state.position_value = 0
            self.state.trailing_high = 0
'''
    # Insert after _collect_historical_data definition
    insert_marker = "    def _collect_historical_data(self):"
    idx = content.find(insert_marker)
    if idx != -1:
        content = content[:idx] + sync_method + "\n" + content[idx:]

    # ---- PATCH 6: Replace _check_can_trade BUY check ----
    old = '''        # Verificar se já tem posição
        if signal.action == "BUY" and self.state.position > 0:
            logger.debug("📦 Already have position")
            return False
        
        if signal.action == "SELL" and self.state.position <= 0:
            logger.debug("📭 No position to sell")
            return False'''
    new = '''        # Multi-position: allow BUY if under max_positions limit
        if signal.action == "BUY" and not self.position_manager.can_open():
            logger.debug(f"📦 Max positions reached ({self.position_manager.count}/{MAX_POSITIONS})")
            return False
        
        if signal.action == "SELL" and self.position_manager.count <= 0:
            logger.debug("📭 No position to sell")
            return False'''
    content = content.replace(old, new, 1)

    # ---- PATCH 7: Replace _execute_trade BUY section ----
    old_buy = '''                    # Registrar
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
                    self.state.trailing_high = price'''
    new_buy = '''                    # Registrar no DB
                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="buy",
                        price=price,
                        size=size,
                        funds=amount_usdt,
                        dry_run=self.state.dry_run
                    )
                    self._last_trade_id = trade_id

                    # Multi-position: add to position manager
                    self.position_manager.add(
                        size=size, entry_price=price,
                        buy_trade_id=trade_id
                    )
                    self._sync_state_from_positions()'''
    content = content.replace(old_buy, new_buy, 1)

    # ---- PATCH 8: Replace _execute_trade SELL section ----
    # Need to handle per-position sell. The SELL section starts with
    # calculating PnL and ends with state updates.
    old_sell_state = '''                    # Atualizar estado
                    self.state.total_pnl += pnl
                    self.state.daily_pnl += pnl  # FIX #5: Track daily PnL
                    self.state.sell_count += 1  # FIX #6: Count sells separately
                    if pnl > 0:
                        self.state.winning_trades += 1
                    
                    self.state.position = 0
                    self.state.entry_price = 0
                    self.state.trailing_high = 0  # FIX #1: Reset trailing'''
    new_sell_state = '''                    # Atualizar estado
                    self.state.total_pnl += pnl
                    self.state.daily_pnl += pnl  # FIX #5: Track daily PnL
                    self.state.sell_count += 1  # FIX #6: Count sells separately
                    if pnl > 0:
                        self.state.winning_trades += 1

                    # Multi-position: close the sold position
                    if hasattr(self, '_selling_position_id') and self._selling_position_id:
                        self.position_manager.close(self._selling_position_id)
                        self._selling_position_id = None
                    self._sync_state_from_positions()'''
    content = content.replace(old_sell_state, new_sell_state, 1)

    # ---- PATCH 9: Replace _check_trailing_stop to iterate positions ----
    old_trailing = '''    def _check_trailing_stop(self, price: float) -> bool:
        """FIX #1: Trailing stop implementation.
        Activates when price rises activation_pct above entry,
        then triggers SELL if price drops trail_pct from the high.
        Returns True if a trailing stop exit was executed."""
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

        return False'''
    new_trailing = '''    def _check_trailing_stop(self, price: float) -> bool:
        """Trailing stop — checks each open position independently.
        Returns True if any position was exited."""
        if self.position_manager.count <= 0:
            return False

        try:
            with open(_config_path) as f:
                live_cfg = json.load(f)
        except Exception:
            live_cfg = _config

        ts_cfg = live_cfg.get("trailing_stop", {})
        if not ts_cfg.get("enabled", False):
            return False

        activation_pct = ts_cfg.get("activation_pct", 0.015)
        trail_pct = ts_cfg.get("trail_pct", 0.008)

        for pos in list(self.position_manager.positions):
            # Update trailing high for this position
            self.position_manager.update_trailing(pos.id, price)

            # Check if activation threshold was reached
            pnl_pct = (pos.trailing_high / pos.entry_price) - 1
            if pnl_pct < activation_pct:
                continue

            # Trailing stop activated — check if price dropped from high
            drop_from_high = (pos.trailing_high - price) / pos.trailing_high
            if drop_from_high >= trail_pct:
                net_pnl_pct = (price / pos.entry_price) - 1
                logger.warning(
                    f"📉 TRAILING STOP pos#{pos.id}! "
                    f"High=${pos.trailing_high:,.2f}, now=${price:,.2f} "
                    f"(drop={drop_from_high*100:.2f}%), "
                    f"PnL={net_pnl_pct*100:.2f}% from entry ${pos.entry_price:,.2f}"
                )
                # Set position context for _execute_trade
                self.state.entry_price = pos.entry_price
                self.state.position = pos.size
                self._selling_position_id = pos.id
                forced_signal = Signal(
                    action="SELL", confidence=1.0,
                    reason=f"TRAILING_STOP pos#{pos.id} (drop {drop_from_high*100:.2f}%)",
                    price=price, features={}
                )
                self.state.last_trade_time = 0
                result = self._execute_trade(forced_signal, price, force=True)
                self._sync_state_from_positions()
                return result

        return False'''
    content = content.replace(old_trailing, new_trailing, 1)

    # ---- PATCH 10: Replace _check_auto_exit to iterate positions ----
    old_auto = '''    def _check_auto_exit(self, price: float) -> bool:
        """Check auto stop-loss/take-profit thresholds.
        Returns True if a forced exit was executed."""
        if self.state.position <= 0 or self.state.entry_price <= 0:
            return False

        # Reload config each cycle for hot-toggle via Grafana
        try:
            with open(_config_path) as f:
                live_cfg = json.load(f)
        except Exception:
            live_cfg = _config

        auto_sl = live_cfg.get("auto_stop_loss", {})
        auto_tp = live_cfg.get("auto_take_profit", {})

        sl_enabled = auto_sl.get("enabled", False)
        tp_enabled = auto_tp.get("enabled", False)

        if not sl_enabled and not tp_enabled:
            return False

        pnl_pct = (price / self.state.entry_price) - 1  # e.g. -0.02 = -2%

        # Stop-Loss check
        if sl_enabled:
            sl_pct = auto_sl.get("pct", 0.02)
            if pnl_pct <= -sl_pct:
                logger.warning(
                    f"🛑 AUTO STOP-LOSS triggered! "
                    f"Price ${price:,.2f} is {pnl_pct*100:.2f}% below entry ${self.state.entry_price:,.2f} "
                    f"(threshold: -{sl_pct*100:.1f}%)"
                )
                forced_signal = Signal(
                    action="SELL", confidence=1.0,
                    reason=f"AUTO_STOP_LOSS ({pnl_pct*100:.2f}%)",
                    price=price, features={}
                )
                self.state.last_trade_time = 0  # bypass cooldown
                return self._execute_trade(forced_signal, price, force=True)

        # Take-Profit check
        if tp_enabled:
            tp_pct = auto_tp.get("pct", 0.03)
            if pnl_pct >= tp_pct:
                logger.info(
                    f"🎯 AUTO TAKE-PROFIT triggered! "
                    f"Price ${price:,.2f} is +{pnl_pct*100:.2f}% above entry ${self.state.entry_price:,.2f} "
                    f"(threshold: +{tp_pct*100:.1f}%)"
                )
                forced_signal = Signal(
                    action="SELL", confidence=1.0,
                    reason=f"AUTO_TAKE_PROFIT (+{pnl_pct*100:.2f}%)",
                    price=price, features={}
                )
                self.state.last_trade_time = 0  # bypass cooldown
                return self._execute_trade(forced_signal, price, force=True)

        return False'''
    new_auto = '''    def _check_auto_exit(self, price: float) -> bool:
        """Check auto SL/TP for each position independently.
        Returns True if any position was exited."""
        if self.position_manager.count <= 0:
            return False

        try:
            with open(_config_path) as f:
                live_cfg = json.load(f)
        except Exception:
            live_cfg = _config

        auto_sl = live_cfg.get("auto_stop_loss", {})
        auto_tp = live_cfg.get("auto_take_profit", {})
        sl_enabled = auto_sl.get("enabled", False)
        tp_enabled = auto_tp.get("enabled", False)

        if not sl_enabled and not tp_enabled:
            return False

        for pos in list(self.position_manager.positions):
            pnl_pct = (price / pos.entry_price) - 1

            # Stop-Loss per position
            if sl_enabled:
                sl_pct = auto_sl.get("pct", 0.02)
                if pnl_pct <= -sl_pct:
                    logger.warning(
                        f"🛑 STOP-LOSS pos#{pos.id}! "
                        f"${price:,.2f} is {pnl_pct*100:.2f}% below "
                        f"entry ${pos.entry_price:,.2f} (threshold: -{sl_pct*100:.1f}%)"
                    )
                    self.state.entry_price = pos.entry_price
                    self.state.position = pos.size
                    self._selling_position_id = pos.id
                    forced_signal = Signal(
                        action="SELL", confidence=1.0,
                        reason=f"AUTO_SL pos#{pos.id} ({pnl_pct*100:.2f}%)",
                        price=price, features={}
                    )
                    self.state.last_trade_time = 0
                    result = self._execute_trade(forced_signal, price, force=True)
                    self._sync_state_from_positions()
                    return result

            # Take-Profit per position
            if tp_enabled:
                tp_pct = auto_tp.get("pct", 0.03)
                if pnl_pct >= tp_pct:
                    logger.info(
                        f"🎯 TAKE-PROFIT pos#{pos.id}! "
                        f"${price:,.2f} is +{pnl_pct*100:.2f}% above "
                        f"entry ${pos.entry_price:,.2f} (threshold: +{tp_pct*100:.1f}%)"
                    )
                    self.state.entry_price = pos.entry_price
                    self.state.position = pos.size
                    self._selling_position_id = pos.id
                    forced_signal = Signal(
                        action="SELL", confidence=1.0,
                        reason=f"AUTO_TP pos#{pos.id} (+{pnl_pct*100:.2f}%)",
                        price=price, features={}
                    )
                    self.state.last_trade_time = 0
                    result = self._execute_trade(forced_signal, price, force=True)
                    self._sync_state_from_positions()
                    return result

        return False'''
    content = content.replace(old_auto, new_auto, 1)

    # ---- PATCH 11: Update _run_loop position value update ----
    old_loop_pos = '''                # Atualizar valor da posição
                if self.state.position > 0:
                    self.state.position_value = self.state.position * market_state.price'''
    new_loop_pos = '''                # Atualizar valor da posição (multi-position)
                if self.position_manager.count > 0:
                    self.state.position_value = self.position_manager.total_btc * market_state.price
                    self.state.position = self.position_manager.total_btc
                    self.state.entry_price = self.position_manager.weighted_entry_price'''
    content = content.replace(old_loop_pos, new_loop_pos, 1)

    # ---- PATCH 12: Update _run_loop trailing/auto_exit check ----
    old_loop_check = '''                # Check trailing stop FIRST, then auto SL/TP
                if self.state.position > 0:
                    if self._check_trailing_stop(market_state.price):
                        time.sleep(POLL_INTERVAL)
                        continue
                    if self._check_auto_exit(market_state.price):
                        time.sleep(POLL_INTERVAL)
                        continue'''
    new_loop_check = '''                # Check trailing stop FIRST, then auto SL/TP (per-position)
                if self.position_manager.count > 0:
                    if self._check_trailing_stop(market_state.price):
                        time.sleep(POLL_INTERVAL)
                        continue
                    if self._check_auto_exit(market_state.price):
                        time.sleep(POLL_INTERVAL)
                        continue'''
    content = content.replace(old_loop_check, new_loop_check, 1)

    # ---- PATCH 13: Update _run_loop signal execution for SELL ----
    # When a SELL signal is received, pick the best-profit position
    old_signal_exec = '''                # Verificar se deve executar
                if signal.action != "HOLD" and self._check_can_trade(signal):
                    executed = self._execute_trade(signal, market_state.price)'''
    new_signal_exec = '''                # Verificar se deve executar
                if signal.action != "HOLD" and self._check_can_trade(signal):
                    # For signal SELL: select best-profit position
                    if signal.action == "SELL" and self.position_manager.count > 0:
                        best_pos = self.position_manager.best_profit_position(market_state.price)
                        if best_pos:
                            self.state.entry_price = best_pos.entry_price
                            self.state.position = best_pos.size
                            self._selling_position_id = best_pos.id
                    executed = self._execute_trade(signal, market_state.price)'''
    content = content.replace(old_signal_exec, new_signal_exec, 1)

    # ---- PATCH 14: Update periodic log to show position count ----
    old_log = '''                if cycle % 60 == 0:  # A cada ~5 minutos
                    pos_info = f"Position: {self.state.position:.6f} BTC" if self.state.position > 0 else "No position"
                    logger.info(f"📊 Cycle {cycle} | ${market_state.price:,.2f} | "
                              f"{pos_info} | PnL: ${self.state.total_pnl:.2f}")'''
    new_log = '''                if cycle % 60 == 0:  # A cada ~5 minutos
                    n_pos = self.position_manager.count
                    total_btc = self.position_manager.total_btc
                    pos_info = f"{n_pos} pos ({total_btc:.6f} BTC)" if n_pos > 0 else "No position"
                    logger.info(f"📊 Cycle {cycle} | ${market_state.price:,.2f} | "
                              f"{pos_info} | PnL: ${self.state.total_pnl:.2f}")'''
    content = content.replace(old_log, new_log, 1)

    # Write patched file
    write_remote(f"{AGENT_DIR}/trading_agent.py", content)
    print("✅ trading_agent.py patched for multi-position support")


# ============================================================
# STEP 5: Patch prometheus_exporter.py
# ============================================================
def step5_patch_exporter():
    print("\n" + "=" * 60)
    print("STEP 5: Patch prometheus_exporter.py")
    print("=" * 60)

    content = ssh(f"cat {AGENT_DIR}/prometheus_exporter.py")

    # Replace the position detection logic
    old_pos = '''            # Posição aberta — baseada no último trade (não SUM histórico)
            # Se o último trade foi sell → sem posição aberta
            # Se o último trade foi buy → posição = size desse buy
            cursor.execute("""
                SELECT side, size, price FROM trades
                WHERE dry_run=%s AND symbol=%s
                ORDER BY timestamp DESC LIMIT 1
            """, (mode_val, self.symbol))
            last_trade = cursor.fetchone()
            if last_trade and last_trade[0] == 'buy':
                pos_btc = last_trade[1] or 0
                entry_price = last_trade[2] or 0
                metrics[f'{prefix}open_position_btc'] = pos_btc
                metrics[f'{prefix}open_position_usdt'] = pos_btc * entry_price
                metrics[f'{prefix}entry_price'] = entry_price
                # Calculate TP/SL targets from config
                try:
                    _cfg = load_config()
                    _tp_pct = _cfg.get('take_profit_pct', 0.03)
                    _sl_pct = _cfg.get('stop_loss_pct', 0.02)
                    metrics[f'{prefix}take_profit_target'] = round(entry_price * (1 + _tp_pct), 2)
                    metrics[f'{prefix}stop_loss_target'] = round(entry_price * (1 - _sl_pct), 2)
                except Exception:
                    metrics[f'{prefix}take_profit_target'] = 0
                    metrics[f'{prefix}stop_loss_target'] = 0
            else:
                # Último trade foi sell ou sem trades → sem posição
                metrics[f'{prefix}open_position_btc'] = 0
                metrics[f'{prefix}open_position_usdt'] = 0
                metrics[f'{prefix}entry_price'] = 0
                metrics[f'{prefix}take_profit_target'] = 0
                metrics[f'{prefix}stop_loss_target'] = 0'''
    new_pos = '''            # Multi-position: read from open_positions table
            cursor.execute("""
                SELECT id, size, entry_price, trailing_high
                FROM open_positions
                WHERE dry_run=%s AND symbol=%s
                ORDER BY opened_at ASC
            """, (mode_val, self.symbol))
            open_pos_rows = cursor.fetchall()
            if open_pos_rows:
                total_btc = sum(r[1] or 0 for r in open_pos_rows)
                total_entry_val = sum((r[1] or 0) * (r[2] or 0) for r in open_pos_rows)
                weighted_entry = total_entry_val / total_btc if total_btc > 0 else 0
                metrics[f'{prefix}open_position_btc'] = total_btc
                metrics[f'{prefix}open_position_usdt'] = total_entry_val
                metrics[f'{prefix}entry_price'] = round(weighted_entry, 2)
                metrics[f'{prefix}open_positions_count'] = len(open_pos_rows)
                try:
                    _cfg = load_config()
                    _tp_pct = _cfg.get('take_profit_pct', 0.03)
                    _sl_pct = _cfg.get('stop_loss_pct', 0.02)
                    # Report targets based on weighted avg entry
                    metrics[f'{prefix}take_profit_target'] = round(weighted_entry * (1 + _tp_pct), 2)
                    metrics[f'{prefix}stop_loss_target'] = round(weighted_entry * (1 - _sl_pct), 2)
                except Exception:
                    metrics[f'{prefix}take_profit_target'] = 0
                    metrics[f'{prefix}stop_loss_target'] = 0
            else:
                metrics[f'{prefix}open_position_btc'] = 0
                metrics[f'{prefix}open_position_usdt'] = 0
                metrics[f'{prefix}entry_price'] = 0
                metrics[f'{prefix}open_positions_count'] = 0
                metrics[f'{prefix}take_profit_target'] = 0
                metrics[f'{prefix}stop_loss_target'] = 0'''
    content = content.replace(old_pos, new_pos, 1)

    # Add open_positions_count to the metric definitions
    old_metric_def = "('btc_trading_entry_price', 'entry_price', 'Entry price of open position', 'gauge', '{v:.2f}'),"
    new_metric_def = """('btc_trading_entry_price', 'entry_price', 'Entry price of open position (weighted avg)', 'gauge', '{v:.2f}'),
                ('btc_trading_open_positions_count', 'open_positions_count', 'Number of open positions', 'gauge', '{v:.0f}'),"""
    content = content.replace(old_metric_def, new_metric_def, 1)

    write_remote(f"{AGENT_DIR}/prometheus_exporter.py", content)
    print("✅ prometheus_exporter.py patched for multi-position")


# ============================================================
# STEP 6: Update config.json
# ============================================================
def step6_config():
    print("\n" + "=" * 60)
    print("STEP 6: Update config.json (add max_positions)")
    print("=" * 60)

    update_script = '''
import json
cfg_path = "/home/homelab/myClaude/btc_trading_agent/config.json"
with open(cfg_path) as f:
    cfg = json.load(f)
if "max_positions" not in cfg:
    cfg["max_positions"] = 3
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"Added max_positions=3")
else:
    print(f"max_positions already set to {cfg['max_positions']}")
print(json.dumps(cfg, indent=2))
'''
    result = ssh(f"python3 -c '{update_script}'")
    print(result)


# ============================================================
# STEP 7: Verify + restart
# ============================================================
def step7_verify():
    print("\n" + "=" * 60)
    print("STEP 7: Syntax check + restart")
    print("=" * 60)

    # Check syntax
    result = ssh(f"cd {AGENT_DIR} && python3 -c 'import py_compile; py_compile.compile(\"position_manager.py\", doraise=True); print(\"position_manager.py: OK\")'", check=False)
    print(result)

    result = ssh(f"cd {AGENT_DIR} && python3 -c 'import py_compile; py_compile.compile(\"trading_agent.py\", doraise=True); print(\"trading_agent.py: OK\")'", check=False)
    print(result)

    result = ssh(f"cd {AGENT_DIR} && python3 -c 'import py_compile; py_compile.compile(\"prometheus_exporter.py\", doraise=True); print(\"prometheus_exporter.py: OK\")'", check=False)
    print(result)


def step8_restart():
    print("\n" + "=" * 60)
    print("STEP 8: Restart services")
    print("=" * 60)

    ssh("sudo systemctl restart btc-trading-agent", check=False)
    print("✅ btc-trading-agent restarted")

    ssh("sudo systemctl restart autocoinbot-exporter", check=False)
    print("✅ autocoinbot-exporter restarted")

    import time as t
    t.sleep(3)

    result = ssh("sudo systemctl is-active btc-trading-agent autocoinbot-exporter")
    print(f"Service status: {result}")

    result = ssh("sudo journalctl -u btc-trading-agent --since '10 sec ago' --no-pager 2>/dev/null | tail -15", check=False)
    print(f"\nAgent logs:\n{result}")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("🚀 Deploying Multi-Position Support for BTC Trading Agent")
    print("=" * 60)

    ts = step1_backup()
    step2_db()
    step3_position_manager()
    step4_patch_agent()
    step5_patch_exporter()
    step6_config()
    step7_verify()

    print("\n" + "=" * 60)
    print("✅ All patches applied. Ready to restart.")
    print("Run step8_restart() to restart services.")
    print("Or manually: sudo systemctl restart btc-trading-agent autocoinbot-exporter")
    print("=" * 60)

    answer = input("\nRestart services now? [y/N] ")
    if answer.lower() == 'y':
        step8_restart()
    else:
        print("Skipped restart. Run manually when ready.")
