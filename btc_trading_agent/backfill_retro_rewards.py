#!/usr/bin/env python3
"""Backfill retroactive rewards for BTC trading training data."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any

import psycopg2
import psycopg2.extras


SCHEMA = "btc"


@dataclass
class RetroReward:
    best_action: int
    reward: float
    price_change: float
    penalties: list[str]
    bonuses: list[str]


def retro_score_sample(state: dict[str, Any], next_state: dict[str, Any]) -> RetroReward:
    price = float(state.get("price") or 0.0)
    next_price = float(next_state.get("price") or 0.0)
    if price <= 0:
        return RetroReward(best_action=0, reward=0.0, price_change=0.0, penalties=["invalid_price"], bonuses=[])

    price_change = (next_price - price) / price
    fee_drag = 0.002
    actionable_edge = max(abs(price_change) - fee_drag, 0.0)

    rsi = float(state.get("rsi") or 50.0)
    momentum = float(state.get("momentum") or 0.0)
    imbalance = float(state.get("orderbook_imbalance") or 0.0)
    flow = float(state.get("trade_flow") or 0.0)
    trend = float(state.get("trend") or 0.0)
    volatility = float(state.get("volatility") or 0.0)

    penalties: list[str] = []
    bonuses: list[str] = []
    regime = "BULLISH" if trend > 0.12 else "BEARISH" if trend < -0.12 else "RANGING"

    def add_penalty(score: float, label: str, current_reward: float) -> float:
        penalties.append(label)
        return current_reward - score

    def add_bonus(score: float, label: str, current_reward: float) -> float:
        bonuses.append(label)
        return current_reward + score

    if price_change > fee_drag:
        best_action = 1
        reward_multiplier = 50.0 if regime == "BULLISH" else 34.0 if regime == "RANGING" else 30.0
        reward = actionable_edge * reward_multiplier
        if regime == "BULLISH":
            reward = add_bonus(0.06, "regime_aligned", reward)
        elif regime == "BEARISH":
            reward = add_penalty(0.12, "counter_regime_buy", reward)
        if actionable_edge >= 0.004:
            reward = add_bonus(0.10, "strong_edge", reward)
        elif actionable_edge < 0.0015:
            reward = add_penalty(0.12, "thin_edge", reward)
        if rsi < 35:
            reward = add_bonus(0.08, "rsi_oversold", reward)
        if imbalance > 0:
            reward = add_bonus(0.06, "bid_pressure", reward)
        if flow > 0:
            reward = add_bonus(0.06, "buying_pressure", reward)
        if momentum > 0:
            reward = add_bonus(0.05, "positive_momentum", reward)
        if trend > 0:
            reward = add_bonus(0.04, "trend_up", reward)
        if rsi > 68:
            reward = add_penalty(0.12, "rsi_overbought", reward)
        if imbalance < 0:
            reward = add_penalty(0.08, "ask_pressure", reward)
        if flow < 0:
            reward = add_penalty(0.08, "selling_pressure", reward)
        if momentum < 0:
            reward = add_penalty(0.10, "negative_momentum", reward)
        if volatility > 0.02 and regime != "BULLISH":
            reward = add_penalty(0.05, "volatile_buy", reward)
    elif price_change < -fee_drag:
        best_action = 2
        reward_multiplier = 50.0 if regime == "BEARISH" else 34.0 if regime == "RANGING" else 30.0
        reward = actionable_edge * reward_multiplier
        if regime == "BEARISH":
            reward = add_bonus(0.06, "regime_aligned", reward)
        elif regime == "BULLISH":
            reward = add_penalty(0.12, "counter_regime_sell", reward)
        if actionable_edge >= 0.004:
            reward = add_bonus(0.10, "strong_edge", reward)
        elif actionable_edge < 0.0015:
            reward = add_penalty(0.12, "thin_edge", reward)
        if rsi > 65:
            reward = add_bonus(0.08, "rsi_high_for_sell", reward)
        if imbalance < 0:
            reward = add_bonus(0.06, "ask_pressure", reward)
        if flow < 0:
            reward = add_bonus(0.06, "selling_pressure", reward)
        if momentum < 0:
            reward = add_bonus(0.05, "negative_momentum", reward)
        if trend < 0:
            reward = add_bonus(0.04, "trend_down", reward)
        if rsi < 35:
            reward = add_penalty(0.08, "rsi_oversold", reward)
        if imbalance > 0:
            reward = add_penalty(0.08, "bid_pressure", reward)
        if flow > 0:
            reward = add_penalty(0.08, "buying_pressure", reward)
        if momentum > 0:
            reward = add_penalty(0.10, "positive_momentum", reward)
        if volatility > 0.02 and regime == "BEARISH":
            reward = add_bonus(0.03, "volatile_breakdown", reward)
    else:
        best_action = 0
        reward = 0.05 if regime == "RANGING" else 0.015
        if regime == "RANGING":
            reward = add_bonus(0.02, "range_patience", reward)
        if abs(momentum) < 0.0015:
            reward = add_bonus(0.02, "flat_momentum", reward)
        if abs(imbalance) < 0.05:
            reward = add_bonus(0.02, "neutral_imbalance", reward)
        if abs(flow) < 0.05:
            reward = add_bonus(0.02, "neutral_flow", reward)
        if volatility > 0.02:
            reward = add_penalty(0.02, "high_vol_noise", reward)

    return RetroReward(
        best_action=best_action,
        reward=round(float(reward), 6),
        price_change=round(float(price_change), 6),
        penalties=penalties,
        bonuses=bonuses,
    )


def ensure_table(cur: psycopg2.extensions.cursor) -> None:
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.learning_rewards_retro (
            id SERIAL PRIMARY KEY,
            state_id INTEGER NOT NULL,
            next_state_id INTEGER NOT NULL,
            timestamp DOUBLE PRECISION NOT NULL,
            symbol TEXT NOT NULL,
            action INTEGER NOT NULL,
            reward DOUBLE PRECISION NOT NULL,
            price_change DOUBLE PRECISION NOT NULL,
            context JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(state_id, next_state_id)
        )
        """
    )
    cur.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_btc_learning_rewards_retro_symbol_ts
        ON {SCHEMA}.learning_rewards_retro(symbol, timestamp)
        """
    )


def fetch_states(cur: psycopg2.extensions.cursor, symbol: str, hours: int | None) -> list[dict[str, Any]]:
    query = f"""
        SELECT id, timestamp, symbol, price, bid, ask, spread,
               orderbook_imbalance, trade_flow, rsi, momentum,
               volatility, trend, volume
        FROM {SCHEMA}.market_states
        WHERE symbol = %s
    """
    params: list[Any] = [symbol]
    if hours is not None:
        query += " AND timestamp >= EXTRACT(EPOCH FROM NOW()) - %s"
        params.append(hours * 3600)
    query += " ORDER BY timestamp ASC, id ASC"
    cur.execute(query, params)
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def backfill(dsn: str, symbol: str, hours: int | None, replace_learning_rewards: bool) -> dict[str, Any]:
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            ensure_table(cur)
        conn.commit()

        with conn.cursor() as cur:
            states = fetch_states(cur, symbol, hours)

        processed = 0
        action_counts = {0: 0, 1: 0, 2: 0}
        reward_sum = 0.0
        rows: list[tuple[Any, ...]] = []

        for current, next_state in zip(states, states[1:]):
            scored = retro_score_sample(current, next_state)
            action_counts[scored.best_action] += 1
            reward_sum += scored.reward
            context = {
                "penalties": scored.penalties,
                "bonuses": scored.bonuses,
                "price_change": scored.price_change,
            }
            rows.append(
                (
                    current["id"],
                    next_state["id"],
                    current["timestamp"],
                    symbol,
                    scored.best_action,
                    scored.reward,
                    scored.price_change,
                    json.dumps(context),
                )
            )

        with conn.cursor() as cur:
            if rows:
                for start in range(0, len(rows), 5000):
                    batch = rows[start:start + 5000]
                    psycopg2.extras.execute_batch(
                        cur,
                        f"""
                        INSERT INTO {SCHEMA}.learning_rewards_retro
                            (state_id, next_state_id, timestamp, symbol, action, reward, price_change, context)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (state_id, next_state_id) DO UPDATE
                        SET action = EXCLUDED.action,
                            reward = EXCLUDED.reward,
                            price_change = EXCLUDED.price_change,
                            context = EXCLUDED.context,
                            timestamp = EXCLUDED.timestamp,
                            symbol = EXCLUDED.symbol
                        """,
                        batch,
                        page_size=1000,
                    )
                    conn.commit()
                    processed += len(batch)

            if replace_learning_rewards:
                cur.execute(f"DELETE FROM {SCHEMA}.learning_rewards WHERE symbol = %s", (symbol,))
                cur.execute(
                    f"""
                    INSERT INTO {SCHEMA}.learning_rewards
                        (timestamp, symbol, state_hash, action, reward, next_state_hash, episode)
                    SELECT
                        timestamp,
                        symbol,
                        state_id::text,
                        action,
                        reward,
                        next_state_id::text,
                        0
                    FROM {SCHEMA}.learning_rewards_retro
                    WHERE symbol = %s
                    """,
                    (symbol,),
                )
                conn.commit()

        return {
            "states": len(states),
            "transitions": max(len(states) - 1, 0),
            "processed": processed,
            "reward_sum": round(reward_sum, 6),
            "action_counts": action_counts,
            "replaced_learning_rewards": replace_learning_rewards,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill retroactive rewards from btc.market_states")
    parser.add_argument("--dsn", required=True, help="PostgreSQL DSN")
    parser.add_argument("--symbol", default="BTC-USDT")
    parser.add_argument("--hours", type=int, default=None)
    parser.add_argument("--replace-learning-rewards", action="store_true")
    args = parser.parse_args()

    result = backfill(
        dsn=args.dsn,
        symbol=args.symbol,
        hours=args.hours,
        replace_learning_rewards=args.replace_learning_rewards,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
