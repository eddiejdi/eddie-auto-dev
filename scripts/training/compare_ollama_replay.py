#!/usr/bin/env python3
"""Compare real trading decisions against qmodel and Ollama replay."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import psycopg2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True, help="PostgreSQL DSN for btc_trading")
    parser.add_argument("--symbol", default="BTC-USDT")
    parser.add_argument("--profile", default="aggressive")
    parser.add_argument("--hours", type=int, default=6)
    parser.add_argument("--limit", type=int, default=20, help="Max executed decisions to compare")
    parser.add_argument("--ollama-host", default=os.getenv("OLLAMA_PLAN_HOST", "http://127.0.0.1:11434"))
    parser.add_argument("--ollama-model", default=os.getenv("OLLAMA_PLAN_MODEL", "phi4-mini:latest"))
    parser.add_argument(
        "--agent-dir",
        default="/apps/crypto-trader/trading/btc_trading_agent",
        help="Directory containing fast_model.py",
    )
    return parser.parse_args()


def load_fast_model(agent_dir: str):
    sys.path.insert(0, agent_dir)
    from fast_model import FastTradingModel, MarketState  # type: ignore

    return FastTradingModel, MarketState


def fetch_rows(dsn: str, symbol: str, profile: str, hours: int, limit: int) -> list[dict[str, Any]]:
    sql = """
    with recent_decisions as (
      select
        d.id,
        d.timestamp,
        d.action as actual_action,
        d.confidence as actual_confidence,
        d.price as decision_price,
        d.executed,
        d.reason,
        d.features,
        d.trade_id,
        t.id as trade_row_id,
        t.side as trade_side,
        t.price as trade_price,
        t.pnl,
        t.pnl_pct,
        t.order_id
      from btc.decisions d
      left join btc.trades t on t.id = d.trade_id
      where d.symbol = %s
        and d.profile = %s
        and d.timestamp > extract(epoch from now() - make_interval(hours => %s))
        and d.executed = true
      order by d.timestamp asc
      limit %s
    ), paired as (
      select
        d.*,
        ms.timestamp as state_ts,
        ms.price,
        ms.bid,
        ms.ask,
        ms.spread,
        ms.orderbook_imbalance,
        ms.trade_flow,
        ms.rsi,
        ms.momentum,
        ms.volatility,
        ms.trend,
        ms.volume
      from recent_decisions d
      join lateral (
        select *
        from btc.market_states ms
        where ms.symbol = %s
          and ms.timestamp between d.timestamp - 1.0 and d.timestamp + 1.0
        order by abs(ms.timestamp - d.timestamp)
        limit 1
      ) ms on true
    )
    select * from paired order by timestamp asc
    """
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (symbol, profile, hours, limit, symbol))
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def build_prompt(row: dict[str, Any]) -> str:
    features = row.get("features") or {}
    regime = features.get("regime", "UNKNOWN")
    regime_strength = features.get("regime_strength", 0.0)
    news_score = features.get("news_score", 0.0)
    news_weight = features.get("news_weight", 0.0)
    final_score = features.get("final_score", 0.0)
    q_score = features.get("q_score", 0.0)
    ob_score = features.get("orderbook_score", 0.0)
    flow_score = features.get("flow_score", 0.0)
    tech_score = features.get("technical_score", 0.0)
    return (
        "Decida a melhor ação imediata para BTC-USDT.\n"
        "Use apenas BUY, SELL ou HOLD.\n"
        "Responda apenas JSON compacto: "
        "{\"action\":\"BUY|SELL|HOLD\",\"confidence\":0.0,\"rationale\":\"frase curta\"}\n\n"
        f"symbol=BTC-USDT\n"
        f"price={float(row.get('price') or 0.0):.2f}\n"
        f"rsi={float(row.get('rsi') or 50.0):.4f}\n"
        f"momentum={float(row.get('momentum') or 0.0):.6f}\n"
        f"volatility={float(row.get('volatility') or 0.0):.6f}\n"
        f"trend={float(row.get('trend') or 0.0):.6f}\n"
        f"orderbook_imbalance={float(row.get('orderbook_imbalance') or 0.0):.6f}\n"
        f"trade_flow={float(row.get('trade_flow') or 0.0):.6f}\n"
        f"spread={float(row.get('spread') or 0.0):.6f}\n"
        f"volume={float(row.get('volume') or 0.0):.6f}\n"
        f"regime={regime}\n"
        f"regime_strength={float(regime_strength or 0.0):.6f}\n"
        f"final_score={float(final_score or 0.0):.6f}\n"
        f"q_score={float(q_score or 0.0):.6f}\n"
        f"technical_score={float(tech_score or 0.0):.6f}\n"
        f"orderbook_score={float(ob_score or 0.0):.6f}\n"
        f"flow_score={float(flow_score or 0.0):.6f}\n"
        f"news_score={float(news_score or 0.0):.6f}\n"
        f"news_weight={float(news_weight or 0.0):.6f}\n"
    )


@dataclass
class OllamaDecision:
    action: str
    confidence: float
    rationale: str
    raw: str


def call_ollama(host: str, model: str, row: dict[str, Any]) -> OllamaDecision:
    prompt = build_prompt(row)
    with httpx.Client(timeout=180.0) as client:
        resp = client.post(
            f"{host.rstrip('/')}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.0,
                    "num_predict": 64,
                    "num_ctx": 1024,
                },
            },
        )
    resp.raise_for_status()
    raw = resp.json().get("response", "").strip()
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    candidate = match.group(0) if match else cleaned
    parsed = json.loads(candidate)
    action = str(parsed.get("action", "HOLD")).upper()
    if action not in {"BUY", "SELL", "HOLD"}:
        action = "HOLD"
    confidence = float(parsed.get("confidence", 0.5) or 0.5)
    confidence = max(0.0, min(1.0, confidence))
    rationale = str(parsed.get("rationale", "")).strip()
    return OllamaDecision(action=action, confidence=confidence, rationale=rationale, raw=raw)


def compare(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    FastTradingModel, MarketState = load_fast_model(args.agent_dir)
    model = FastTradingModel(args.symbol)
    model.q_model.epsilon = 0.0

    details: list[dict[str, Any]] = []
    q_counts: Counter[str] = Counter()
    ollama_counts: Counter[str] = Counter()
    actual_counts: Counter[str] = Counter()
    q_match = 0
    ollama_match = 0

    for row in rows:
        state = MarketState(
            price=float(row.get("price") or 0.0),
            bid=float(row.get("bid") or 0.0),
            ask=float(row.get("ask") or 0.0),
            spread=float(row.get("spread") or 0.0),
            orderbook_imbalance=float(row.get("orderbook_imbalance") or 0.0),
            trade_flow=float(row.get("trade_flow") or 0.0),
            volume_ratio=float(row.get("volume") or 1.0),
            rsi=float(row.get("rsi") or 50.0),
            momentum=float(row.get("momentum") or 0.0),
            volatility=float(row.get("volatility") or 0.0),
            trend=float(row.get("trend") or 0.0),
            timestamp=float(row.get("state_ts") or row.get("timestamp") or 0.0),
        )
        q_pred = model.predict(state, explore=False)
        ollama = call_ollama(args.ollama_host, args.ollama_model, row)
        actual = str(row["actual_action"]).upper()

        actual_counts[actual] += 1
        q_counts[q_pred.action] += 1
        ollama_counts[ollama.action] += 1
        if q_pred.action == actual:
            q_match += 1
        if ollama.action == actual:
            ollama_match += 1

        details.append(
            {
                "ts": row["timestamp"],
                "actual": actual,
                "qmodel": q_pred.action,
                "q_conf": round(float(q_pred.confidence or 0.0), 3),
                "ollama": ollama.action,
                "ollama_conf": round(float(ollama.confidence), 3),
                "trade_price": round(float(row.get("trade_price") or row.get("decision_price") or 0.0), 2),
                "pnl": None if row.get("pnl") is None else round(float(row["pnl"]), 4),
                "pnl_pct": None if row.get("pnl_pct") is None else round(float(row["pnl_pct"]), 4),
                "actual_reason": (row.get("reason") or "")[:180],
                "q_reason": (q_pred.reason or "")[:180],
                "ollama_reason": (ollama.rationale or "")[:180],
                "order_id": row.get("order_id"),
            }
        )

    return {
        "summary": {
            "rows": len(rows),
            "actual_counts": dict(actual_counts),
            "qmodel_counts": dict(q_counts),
            "ollama_counts": dict(ollama_counts),
            "qmodel_agreement_pct": round(q_match / len(rows) * 100, 2) if rows else 0.0,
            "ollama_agreement_pct": round(ollama_match / len(rows) * 100, 2) if rows else 0.0,
        },
        "details": details,
    }


def main() -> None:
    args = parse_args()
    rows = fetch_rows(args.dsn, args.symbol, args.profile, args.hours, args.limit)
    result = compare(rows, args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
