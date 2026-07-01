#!/usr/bin/env python3
"""Backfill restauravel do dashboard BTC em OpenMetrics/TSDB.

Reconstrói a maior parte das métricas Prometheus do dashboard BTC a partir das
fontes persistidas no PostgreSQL:
- btc.market_states
- btc.decisions
- btc.trades
- btc.exchange_balance_snapshots
- btc.profile_config

Escopo deliberadamente limitado:
- Restaura preço, indicadores técnicos, contagens/PNL/posição, decisões,
  atividade do agente e saldos/equity reconstruídos.
- Não tenta reconstruir as métricas RAG exportadas apenas pelos JSONs "current"
  do market_rag, porque essa família não tem histórico persistido fiel.

Uso típico:
  python3 tools/backfill_btc_prometheus_history.py \\
    --dsn postgresql://btc-trading:...@localhost:5433/btc_trading \\
    --start 2026-06-10T19:38:00Z \\
    --end   2026-06-12T16:44:00Z \\
    --output /tmp/btc-gap.om

  promtool tsdb create-blocks-from openmetrics /tmp/btc-gap.om /tmp/btc-gap-blocks
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg2


PROFILES = ("aggressive", "conservative")
ACTIONS = ("BUY", "SELL", "HOLD")

METRIC_META: dict[str, tuple[str, str]] = {
    "btc_price": ("gauge", "BTC price in USDT"),
    "btc_trading_total_trades": ("counter", "Total trades active mode"),
    "btc_trading_winning_trades": ("counter", "Winning trades active mode"),
    "btc_trading_losing_trades": ("counter", "Losing trades active mode"),
    "btc_trading_win_rate": ("gauge", "Win rate 0-1 active mode"),
    "btc_trading_total_pnl": ("gauge", "Total PnL active mode"),
    "btc_trading_avg_pnl": ("gauge", "Average PnL active mode"),
    "btc_trading_best_trade_pnl": ("gauge", "Best trade PnL active mode"),
    "btc_trading_worst_trade_pnl": ("gauge", "Worst trade PnL active mode"),
    "btc_trading_cumulative_pnl": ("gauge", "Cumulative PnL all time active mode"),
    "btc_trading_cumulative_pnl_24h": ("gauge", "Cumulative PnL 24h active mode"),
    "btc_trading_trades_24h": ("gauge", "Trades 24h active mode"),
    "btc_trading_trades_1h": ("gauge", "Trades 1h active mode"),
    "btc_trading_open_position_btc": ("gauge", "Open BTC position active mode"),
    "btc_trading_open_position_usdt": ("gauge", "Open USDT position active mode"),
    "btc_trading_open_position_count": ("gauge", "Open position raw count active mode"),
    "btc_trading_open_position_raw_entries": ("gauge", "Open position raw entries active mode"),
    "btc_trading_open_position_logical_slots": ("gauge", "Open position logical slots active mode"),
    "btc_trading_avg_entry_price": ("gauge", "Average entry price active mode"),
    "btc_trading_decisions_total": ("counter", "Total decisions by action"),
    "btc_trading_decisions_1h": ("gauge", "Decisions 1h by action"),
    "btc_trading_rsi": ("gauge", "RSI"),
    "btc_trading_momentum": ("gauge", "Momentum"),
    "btc_trading_volatility": ("gauge", "Volatility"),
    "btc_trading_trend": ("gauge", "Trend"),
    "btc_trading_orderbook_imbalance": ("gauge", "Orderbook imbalance"),
    "btc_trading_trade_flow": ("gauge", "Trade flow"),
    "btc_trading_bid_volume": ("gauge", "Bid proxy"),
    "btc_trading_ask_volume": ("gauge", "Ask proxy"),
    "btc_trading_spread": ("gauge", "Spread"),
    "btc_trading_final_score": ("gauge", "Latest final score"),
    "btc_trading_agent_running": ("gauge", "Agent running"),
    "btc_trading_last_activity_timestamp": ("gauge", "Last activity timestamp"),
    "btc_trading_equity_usdt": ("gauge", "Equity USDT"),
    "btc_trading_equity_btc": ("gauge", "Equity BTC"),
    "btc_trading_initial_capital": ("gauge", "Initial capital"),
    "btc_trading_unrealized_pnl": ("gauge", "Unrealized PnL"),
    "btc_trading_exchange_usdt_balance": ("gauge", "Exchange USDT balance"),
    "btc_trading_exchange_btc_balance": ("gauge", "Exchange BTC balance"),
}


@dataclass
class MarketRow:
    ts: float
    price: float
    bid: float
    ask: float
    spread: float
    orderbook_imbalance: float
    trade_flow: float
    rsi: float
    momentum: float
    volatility: float
    trend: float
    volume: float


@dataclass
class DecisionRow:
    ts: float
    profile: str
    action: str
    features: dict[str, Any]


@dataclass
class TradeRow:
    ts: float
    profile: str
    side: str
    size: float
    price: float
    funds: float
    pnl: float | None
    metadata: dict[str, Any]


@dataclass
class BalanceRow:
    ts: float
    currency: str
    available: float


@dataclass
class TradeState:
    total_sells: int = 0
    winning: int = 0
    losing: int = 0
    pnl_sum: float = 0.0
    pnl_count: int = 0
    best_pnl: float | None = None
    worst_pnl: float | None = None
    trade_times_24h: deque[float] = field(default_factory=deque)
    trade_times_1h: deque[float] = field(default_factory=deque)
    pnl_24h: deque[tuple[float, float]] = field(default_factory=deque)
    open_buys: list[tuple[float, float, float]] = field(default_factory=list)

    def apply_trade(self, row: TradeRow) -> None:
        self.trade_times_24h.append(row.ts)
        self.trade_times_1h.append(row.ts)
        if row.pnl is not None:
            self.pnl_sum += row.pnl
            self.pnl_count += 1
            if row.pnl > 0:
                self.winning += 1
            else:
                self.losing += 1
            self.best_pnl = row.pnl if self.best_pnl is None else max(self.best_pnl, row.pnl)
            self.worst_pnl = row.pnl if self.worst_pnl is None else min(self.worst_pnl, row.pnl)
            self.pnl_24h.append((row.ts, row.pnl))

        side = (row.side or "").lower()
        if side in ("sell", "sell_reconciled"):
            self.total_sells += 1

        if side == "buy":
            self.open_buys.append((row.size, row.price, round(row.price, 2)))
            return

        if side not in ("sell", "sell_reconciled"):
            return

        metadata = row.metadata or {}
        slot_exit_reason = metadata.get("slot_exit_reason")
        if slot_exit_reason in (None, ""):
            self.open_buys.clear()
            return

        slot_entry_price = metadata.get("slot_entry_price")
        if slot_entry_price is None:
            return

        rounded = round(float(slot_entry_price), 2)
        for idx, buy in enumerate(self.open_buys):
            if buy[2] == rounded:
                del self.open_buys[idx]
                break

    def trim_windows(self, now_ts: float) -> None:
        cutoff_24h = now_ts - 86400
        cutoff_1h = now_ts - 3600
        while self.trade_times_24h and self.trade_times_24h[0] <= cutoff_24h:
            self.trade_times_24h.popleft()
        while self.trade_times_1h and self.trade_times_1h[0] <= cutoff_1h:
            self.trade_times_1h.popleft()
        while self.pnl_24h and self.pnl_24h[0][0] <= cutoff_24h:
            self.pnl_24h.popleft()

    def snapshot(self) -> dict[str, float]:
        total_btc = sum(size for size, _price, _round_px in self.open_buys)
        total_cost = sum(size * price for size, price, _round_px in self.open_buys)
        avg_entry = total_cost / total_btc if total_btc > 0 else 0.0
        return {
            "total_trades": float(self.total_sells),
            "winning_trades": float(self.winning),
            "losing_trades": float(self.losing),
            "win_rate": (self.winning / self.total_sells) if self.total_sells > 0 else 0.0,
            "total_pnl": self.pnl_sum,
            "avg_pnl": (self.pnl_sum / self.pnl_count) if self.pnl_count > 0 else 0.0,
            "best_trade_pnl": self.best_pnl if self.best_pnl is not None else 0.0,
            "worst_trade_pnl": self.worst_pnl if self.worst_pnl is not None else 0.0,
            "cumulative_pnl": self.pnl_sum,
            "cumulative_pnl_24h": sum(pnl for _ts, pnl in self.pnl_24h),
            "trades_24h": float(len(self.trade_times_24h)),
            "trades_1h": float(len(self.trade_times_1h)),
            "open_position_btc": total_btc,
            "open_position_usdt": total_btc * avg_entry,
            "open_position_count": float(len(self.open_buys)),
            "open_position_raw_entries": float(len(self.open_buys)),
            "open_position_logical_slots": float(len(self.open_buys)),
            "avg_entry_price": avg_entry,
        }


@dataclass
class DecisionState:
    counts_total: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    actions_1h: deque[tuple[float, str]] = field(default_factory=deque)
    final_score: float = 0.0

    def apply_decision(self, row: DecisionRow) -> None:
        action = (row.action or "HOLD").upper()
        self.counts_total[action] += 1
        self.actions_1h.append((row.ts, action))
        if isinstance(row.features, dict):
            try:
                self.final_score = float(row.features.get("final_score", self.final_score) or self.final_score)
            except (TypeError, ValueError):
                pass

    def trim_windows(self, now_ts: float) -> None:
        cutoff_1h = now_ts - 3600
        while self.actions_1h and self.actions_1h[0][0] <= cutoff_1h:
            self.actions_1h.popleft()

    def counts_1h(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for _ts, action in self.actions_1h:
            counts[action] += 1
        return counts


def parse_dt(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def format_labels(labels: dict[str, Any]) -> str:
    parts = []
    for key in sorted(labels):
        value = str(labels[key]).replace("\\", "\\\\").replace("\"", "\\\"")
        parts.append(f'{key}="{value}"')
    return ",".join(parts)


def format_value(value: float) -> str:
    if math.isinf(value) or math.isnan(value):
        return "0"
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.10f}".rstrip("0").rstrip(".")


def load_profile_config(cur: psycopg2.extensions.cursor) -> dict[str, float]:
    cur.execute("SELECT profile, initial_capital FROM btc.profile_config WHERE profile = ANY(%s)", (list(PROFILES),))
    result = {profile: float(capital) for profile, capital in cur.fetchall()}
    for profile in PROFILES:
        result.setdefault(profile, 100.0)
    return result


def load_market_rows(cur: psycopg2.extensions.cursor, symbol: str, end_ts: float) -> list[MarketRow]:
    cur.execute(
        """
        SELECT timestamp, price, bid, ask, spread, orderbook_imbalance, trade_flow,
               rsi, momentum, volatility, trend, volume
        FROM btc.market_states
        WHERE symbol = %s AND timestamp <= %s
        ORDER BY timestamp
        """,
        (symbol, end_ts),
    )
    return [
        MarketRow(
            ts=float(ts),
            price=float(price or 0),
            bid=float(bid or 0),
            ask=float(ask or 0),
            spread=float(spread or 0),
            orderbook_imbalance=float(orderbook_imbalance or 0),
            trade_flow=float(trade_flow or 0),
            rsi=float(rsi or 50),
            momentum=float(momentum or 0),
            volatility=float(volatility or 0),
            trend=float(trend or 0),
            volume=float(volume or 0),
        )
        for ts, price, bid, ask, spread, orderbook_imbalance, trade_flow, rsi, momentum, volatility, trend, volume in cur.fetchall()
    ]


def load_decision_rows(cur: psycopg2.extensions.cursor, symbol: str, end_ts: float) -> list[DecisionRow]:
    cur.execute(
        """
        SELECT timestamp, profile, action, features
        FROM btc.decisions
        WHERE symbol = %s
          AND profile = ANY(%s)
          AND timestamp <= %s
        ORDER BY timestamp
        """,
        (symbol, list(PROFILES), end_ts),
    )
    rows = []
    for ts, profile, action, features in cur.fetchall():
        if isinstance(features, str):
            try:
                features = json.loads(features)
            except json.JSONDecodeError:
                features = {}
        rows.append(
            DecisionRow(
                ts=float(ts),
                profile=profile,
                action=action,
                features=features or {},
            )
        )
    return rows


def load_trade_rows(cur: psycopg2.extensions.cursor, symbol: str, end_ts: float) -> list[TradeRow]:
    cur.execute(
        """
        SELECT timestamp, profile, side, size, price, funds, pnl, metadata
        FROM btc.trades
        WHERE symbol = %s
          AND profile = ANY(%s)
          AND dry_run = false
          AND timestamp <= %s
        ORDER BY timestamp
        """,
        (symbol, list(PROFILES), end_ts),
    )
    rows = []
    for ts, profile, side, size, price, funds, pnl, metadata in cur.fetchall():
        rows.append(
            TradeRow(
                ts=float(ts),
                profile=profile,
                side=side,
                size=float(size or 0),
                price=float(price or 0),
                funds=float(funds or 0),
                pnl=float(pnl) if pnl is not None else None,
                metadata=metadata or {},
            )
        )
    return rows


def load_balance_rows(cur: psycopg2.extensions.cursor, end_ts: float) -> list[BalanceRow]:
    cur.execute(
        """
        SELECT EXTRACT(EPOCH FROM synced_at), currency, available
        FROM btc.exchange_balance_snapshots
        WHERE account_type = 'trade'
          AND currency IN ('USDT', 'BTC')
          AND synced_at <= to_timestamp(%s)
        ORDER BY synced_at
        """,
        (end_ts,),
    )
    return [BalanceRow(ts=float(ts), currency=currency, available=float(available or 0)) for ts, currency, available in cur.fetchall()]


def apply_balance_trade(account_balances: dict[str, float], row: TradeRow) -> None:
    source = (row.metadata or {}).get("source")
    if source == "external_deposit":
        return
    side = (row.side or "").lower()
    if side == "buy":
        account_balances["USDT"] -= float(row.funds or (row.size * row.price))
        account_balances["BTC"] += float(row.size or 0)
    elif side in ("sell", "sell_reconciled"):
        account_balances["USDT"] += float(row.funds or (row.size * row.price))
        account_balances["BTC"] -= float(row.size or 0)


def write_headers(handle: Any) -> None:
    for metric, (mtype, help_text) in METRIC_META.items():
        handle.write(f"# HELP {metric} {help_text}\n")
        handle.write(f"# TYPE {metric} {mtype}\n")


def emit_sample(handle: Any, metric: str, labels: dict[str, Any], value: float, ts: float) -> None:
    handle.write(f"{metric}{{{format_labels(labels)}}} {format_value(value)} {format_value(ts)}\n")


def maybe_run_promtool(promtool: str, om_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [promtool, "tsdb", "create-blocks-from", "openmetrics", str(om_path), str(out_dir)],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True, help="DSN PostgreSQL do schema btc")
    parser.add_argument("--symbol", default="BTC-USDT")
    parser.add_argument("--start", required=True, help="Inicio ISO8601 UTC")
    parser.add_argument("--end", required=True, help="Fim ISO8601 UTC")
    parser.add_argument("--step-seconds", type=int, default=60)
    parser.add_argument("--output", required=True, help="Arquivo OpenMetrics de saida")
    parser.add_argument("--promtool", help="Se informado junto com --block-output, gera blocos TSDB")
    parser.add_argument("--block-output", help="Diretorio de saida dos blocos TSDB")
    args = parser.parse_args()

    start_dt = parse_dt(args.start)
    end_dt = parse_dt(args.end)
    if end_dt <= start_dt:
        raise SystemExit("--end deve ser maior que --start")

    start_ts = start_dt.timestamp()
    end_ts = end_dt.timestamp()

    conn = psycopg2.connect(args.dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET search_path TO btc, public")

    profile_capitals = load_profile_config(cur)
    market_rows = load_market_rows(cur, args.symbol, end_ts)
    decision_rows = load_decision_rows(cur, args.symbol, end_ts)
    trade_rows = load_trade_rows(cur, args.symbol, end_ts)
    balance_rows = load_balance_rows(cur, end_ts)
    cur.close()
    conn.close()

    market_idx = 0
    decision_idx = 0
    trade_idx = 0
    balance_idx = 0

    latest_market: MarketRow | None = None
    trade_states = {profile: TradeState() for profile in PROFILES}
    decision_states = {profile: DecisionState() for profile in PROFILES}
    account_balances = {"USDT": 0.0, "BTC": 0.0}

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        write_headers(handle)

        ts = start_ts
        while ts <= end_ts:
            while market_idx < len(market_rows) and market_rows[market_idx].ts <= ts:
                latest_market = market_rows[market_idx]
                market_idx += 1

            while balance_idx < len(balance_rows) and balance_rows[balance_idx].ts <= ts:
                row = balance_rows[balance_idx]
                account_balances[row.currency] = row.available
                balance_idx += 1

            while trade_idx < len(trade_rows) and trade_rows[trade_idx].ts <= ts:
                row = trade_rows[trade_idx]
                trade_states[row.profile].apply_trade(row)
                apply_balance_trade(account_balances, row)
                trade_idx += 1

            while decision_idx < len(decision_rows) and decision_rows[decision_idx].ts <= ts:
                row = decision_rows[decision_idx]
                decision_states[row.profile].apply_decision(row)
                decision_idx += 1

            for profile in PROFILES:
                trade_states[profile].trim_windows(ts)
                decision_states[profile].trim_windows(ts)

            price = latest_market.price if latest_market else 0.0
            market_age = (ts - latest_market.ts) if latest_market else float("inf")

            for profile in PROFILES:
                base_labels = {"coin": args.symbol, "profile": profile}
                trade_snapshot = trade_states[profile].snapshot()
                decision_state = decision_states[profile]
                decisions_1h = decision_state.counts_1h()

                emit_sample(handle, "btc_price", {**base_labels, "symbol": args.symbol}, price, ts)

                for metric, key in (
                    ("btc_trading_total_trades", "total_trades"),
                    ("btc_trading_winning_trades", "winning_trades"),
                    ("btc_trading_losing_trades", "losing_trades"),
                    ("btc_trading_win_rate", "win_rate"),
                    ("btc_trading_total_pnl", "total_pnl"),
                    ("btc_trading_avg_pnl", "avg_pnl"),
                    ("btc_trading_best_trade_pnl", "best_trade_pnl"),
                    ("btc_trading_worst_trade_pnl", "worst_trade_pnl"),
                    ("btc_trading_cumulative_pnl", "cumulative_pnl"),
                    ("btc_trading_cumulative_pnl_24h", "cumulative_pnl_24h"),
                    ("btc_trading_trades_24h", "trades_24h"),
                    ("btc_trading_trades_1h", "trades_1h"),
                    ("btc_trading_open_position_btc", "open_position_btc"),
                    ("btc_trading_open_position_usdt", "open_position_usdt"),
                    ("btc_trading_open_position_count", "open_position_count"),
                    ("btc_trading_open_position_raw_entries", "open_position_raw_entries"),
                    ("btc_trading_open_position_logical_slots", "open_position_logical_slots"),
                    ("btc_trading_avg_entry_price", "avg_entry_price"),
                ):
                    emit_sample(handle, metric, base_labels, trade_snapshot[key], ts)

                for action in ACTIONS:
                    emit_sample(
                        handle,
                        "btc_trading_decisions_total",
                        {**base_labels, "action": action},
                        float(decision_state.counts_total.get(action, 0)),
                        ts,
                    )
                    emit_sample(
                        handle,
                        "btc_trading_decisions_1h",
                        {**base_labels, "action": action},
                        float(decisions_1h.get(action, 0)),
                        ts,
                    )

                emit_sample(handle, "btc_trading_final_score", base_labels, decision_state.final_score, ts)
                emit_sample(handle, "btc_trading_initial_capital", base_labels, profile_capitals[profile], ts)

                if latest_market:
                    emit_sample(handle, "btc_trading_rsi", base_labels, latest_market.rsi, ts)
                    emit_sample(handle, "btc_trading_momentum", base_labels, latest_market.momentum, ts)
                    emit_sample(handle, "btc_trading_volatility", base_labels, latest_market.volatility, ts)
                    emit_sample(handle, "btc_trading_trend", base_labels, latest_market.trend, ts)
                    emit_sample(handle, "btc_trading_orderbook_imbalance", base_labels, latest_market.orderbook_imbalance, ts)
                    emit_sample(handle, "btc_trading_trade_flow", base_labels, latest_market.trade_flow, ts)
                    emit_sample(handle, "btc_trading_bid_volume", base_labels, latest_market.bid, ts)
                    emit_sample(handle, "btc_trading_ask_volume", base_labels, latest_market.ask, ts)
                    emit_sample(handle, "btc_trading_spread", base_labels, latest_market.spread, ts)
                    emit_sample(handle, "btc_trading_last_activity_timestamp", base_labels, latest_market.ts, ts)
                else:
                    for metric in (
                        "btc_trading_rsi",
                        "btc_trading_momentum",
                        "btc_trading_volatility",
                        "btc_trading_trend",
                        "btc_trading_orderbook_imbalance",
                        "btc_trading_trade_flow",
                        "btc_trading_bid_volume",
                        "btc_trading_ask_volume",
                        "btc_trading_spread",
                        "btc_trading_last_activity_timestamp",
                    ):
                        emit_sample(handle, metric, base_labels, 0.0, ts)

                agent_running = 1.0 if latest_market and market_age <= 180 else 0.0
                emit_sample(handle, "btc_trading_agent_running", base_labels, agent_running, ts)

                usdt_bal = account_balances["USDT"]
                btc_bal = account_balances["BTC"]
                avg_entry = trade_snapshot["avg_entry_price"]
                equity_usdt = usdt_bal + (btc_bal * price)
                equity_btc = (equity_usdt / price) if price > 0 else 0.0
                unrealized = btc_bal * (price - avg_entry) if btc_bal > 0 and price > 0 else 0.0

                emit_sample(handle, "btc_trading_exchange_usdt_balance", base_labels, usdt_bal, ts)
                emit_sample(handle, "btc_trading_exchange_btc_balance", base_labels, btc_bal, ts)
                emit_sample(handle, "btc_trading_equity_usdt", base_labels, equity_usdt, ts)
                emit_sample(handle, "btc_trading_equity_btc", base_labels, equity_btc, ts)
                emit_sample(handle, "btc_trading_unrealized_pnl", base_labels, unrealized, ts)

            ts += args.step_seconds

        handle.write("# EOF\n")

    if args.promtool and args.block_output:
        maybe_run_promtool(args.promtool, output_path, Path(args.block_output))

    print(
        json.dumps(
            {
                "output": str(output_path),
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "step_seconds": args.step_seconds,
                "profiles": list(PROFILES),
                "restored_metric_families": sorted(METRIC_META),
                "not_restored_metric_families": [
                    "btc_rag_*",
                    "btc_trade_window_*",
                ],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
