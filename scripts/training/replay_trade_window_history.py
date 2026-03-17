#!/usr/bin/env python3
"""Replay historical BUY gate events against the fresh AI trade-window model."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import statistics
import sys
import time
import types
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

import requests


ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = ROOT / "btc_trading_agent"


def _bootstrap_agent_import() -> None:
    os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
    sys.path.insert(0, str(AGENT_DIR))
    sys.modules.setdefault("httpx", types.SimpleNamespace())
    sys.modules.setdefault(
        "kucoin_api",
        types.SimpleNamespace(
            get_price=None,
            get_price_fast=None,
            get_orderbook=None,
            get_candles=None,
            get_recent_trades=None,
            get_balances=None,
            get_balance=None,
            place_market_order=None,
            analyze_orderbook=None,
            analyze_trade_flow=None,
            inner_transfer=None,
            _has_keys=lambda: False,
        ),
    )
    sys.modules.setdefault(
        "fast_model",
        types.SimpleNamespace(
            FastTradingModel=object,
            MarketState=object,
            Signal=object,
        ),
    )


_bootstrap_agent_import()
from trading_agent import BitcoinTradingAgent  # type: ignore  # noqa: E402


KUCOIN_BASE = "https://api.kucoin.com"
DEFAULT_LOG = ROOT / "btc_trading_agent" / "logs" / "agent.log"


@dataclass
class GateEvent:
    ts: float
    status: str
    price: float
    target: float
    tolerance_pct: float
    reason: str
    raw: str


@dataclass
class Candle:
    ts: int
    open: float
    close: float
    high: float
    low: float
    volume: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-file", default=str(DEFAULT_LOG))
    parser.add_argument("--symbol", default="BTC-USDT")
    parser.add_argument("--profiles", nargs="+", default=["aggressive", "conservative"])
    parser.add_argument("--ollama-host", default=os.getenv("OLLAMA_TRADE_WINDOW_HOST", "http://192.168.15.2:11434"))
    parser.add_argument("--ollama-model", default=os.getenv("OLLAMA_TRADE_WINDOW_MODEL", "phi4-mini:latest"))
    parser.add_argument("--fallback-model", default=os.getenv("OLLAMA_TRADE_WINDOW_FALLBACK_MODEL", "qwen3:0.6b"))
    parser.add_argument("--output", default=str(ROOT / "analysis_results" / "trade_window_history_replay.json"))
    return parser.parse_args()


def _parse_ts(text: str) -> float:
    dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S,%f")
    return dt.timestamp()


def parse_events(log_file: Path) -> list[GateEvent]:
    allow_re = re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}).*BUY permitido pela IA: "
        r"preço \$(?P<price>[\d,]+\.\d+) <= .*?alvo \$?(?P<target>[\d,]+\.\d+)"
        r"(?: \+ tolerância (?P<tol>[\d.]+)%)? \((?P<reason>.*)\)$"
    )
    blocked_re = re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}).*BUY blocked \(AI target\): "
        r"preço \$(?P<price>[\d,]+\.\d+) > alvo \$?(?P<target>[\d,]+\.\d+).*?"
        r"\[tol (?P<tol>[\d.]+)%.*\] — (?P<reason>.*)$"
    )

    events: list[GateEvent] = []
    with open(log_file) as fh:
        for line in fh:
            line = line.strip()
            match = allow_re.search(line)
            if match:
                events.append(
                    GateEvent(
                        ts=_parse_ts(match.group("ts")),
                        status="allowed",
                        price=float(match.group("price").replace(",", "")),
                        target=float(match.group("target").replace(",", "")),
                        tolerance_pct=float(match.group("tol") or 0.0) / 100.0,
                        reason=match.group("reason").strip(),
                        raw=line,
                    )
                )
                continue
            match = blocked_re.search(line)
            if match:
                events.append(
                    GateEvent(
                        ts=_parse_ts(match.group("ts")),
                        status="blocked",
                        price=float(match.group("price").replace(",", "")),
                        target=float(match.group("target").replace(",", "")),
                        tolerance_pct=float(match.group("tol") or 0.0) / 100.0,
                        reason=match.group("reason").strip(),
                        raw=line,
                    )
                )

    dedup: dict[str, GateEvent] = {}
    for event in events:
        key = f"{event.status}|{event.price:.2f}|{event.target:.2f}|{event.reason}"
        dedup.setdefault(key, event)
    return sorted(dedup.values(), key=lambda item: item.ts)


def fetch_candles(symbol: str, start_ts: int, end_ts: int, ktype: str = "1min") -> list[Candle]:
    url = f"{KUCOIN_BASE}/api/v1/market/candles"
    resp = requests.get(
        url,
        params={"symbol": symbol, "type": ktype, "startAt": start_ts, "endAt": end_ts},
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != "200000":
        raise RuntimeError(f"KuCoin error: {payload}")
    candles = [
        Candle(
            ts=int(row[0]),
            open=float(row[1]),
            close=float(row[2]),
            high=float(row[3]),
            low=float(row[4]),
            volume=float(row[5]),
        )
        for row in payload.get("data", [])
        if len(row) >= 6
    ]
    return sorted(candles, key=lambda item: item.ts)


def _infer_regime(reason: str) -> str:
    reason_l = reason.lower()
    if "bear" in reason_l:
        return "BEARISH"
    if "bull" in reason_l:
        return "BULLISH"
    return "RANGING"


def _rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains: list[float] = []
    losses: list[float] = []
    for idx in range(-period, 0):
        change = closes[idx] - closes[idx - 1]
        if change >= 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _find_event_index(candles: list[Candle], event_ts: float) -> int | None:
    selected = None
    for idx, candle in enumerate(candles):
        if candle.ts <= int(event_ts):
            selected = idx
        else:
            break
    return selected


def _feature_block(candles: list[Candle], idx: int) -> dict[str, float]:
    closes = [c.close for c in candles[: idx + 1]]
    if not closes:
        raise ValueError("empty candle window")
    returns = []
    for a, b in zip(closes[-16:-1], closes[-15:]):
        if a > 0:
            returns.append((b / a) - 1.0)
    close = closes[-1]
    close_5 = closes[-6] if len(closes) >= 6 else closes[0]
    close_15 = closes[-16] if len(closes) >= 16 else closes[0]
    close_30 = closes[-31] if len(closes) >= 31 else closes[0]
    return {
        "price": close,
        "rsi": _rsi(closes),
        "momentum_5m": ((close / close_5) - 1.0) if close_5 > 0 else 0.0,
        "momentum_15m": ((close / close_15) - 1.0) if close_15 > 0 else 0.0,
        "trend_30m": ((close / close_30) - 1.0) if close_30 > 0 else 0.0,
        "volatility_15m": statistics.pstdev(returns) if len(returns) >= 2 else 0.0,
    }


def _forward_metrics(candles: list[Candle], idx: int, price: float) -> dict[str, float | None]:
    results: dict[str, float | None] = {}
    for minutes in (15, 30, 60):
        future = candles[idx + 1 : idx + 1 + minutes]
        if not future:
            results[f"up_{minutes}m"] = None
            results[f"dn_{minutes}m"] = None
            continue
        max_high = max(c.high for c in future)
        min_low = min(c.low for c in future)
        results[f"up_{minutes}m"] = ((max_high / price) - 1.0) * 100.0
        results[f"dn_{minutes}m"] = ((min_low / price) - 1.0) * 100.0
    return results


def _make_agent(profile: str) -> BitcoinTradingAgent:
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent.state = SimpleNamespace(profile=profile)
    agent._load_live_config = lambda: {"profile": profile}
    return agent


def _build_prompt(event: GateEvent, profile: str, features: dict[str, float], regime: str, ttl_seconds: int) -> str:
    return (
        "Voce gera uma janela operacional curta para um bot de trading de BTC.\n"
        "Retorne apenas JSON valido, sem markdown, com as chaves:\n"
        "entry_low, entry_high, target_sell, min_confidence, min_trade_interval, ttl_seconds, rationale.\n\n"
        "Contexto historico de replay:\n"
        f"- profile={profile}\n"
        f"- regime={regime}\n"
        f"- price={event.price:.2f}\n"
        f"- previous_buy_target={event.target:.2f}\n"
        f"- rsi={features['rsi']:.2f}\n"
        f"- momentum_5m={features['momentum_5m']:.6f}\n"
        f"- momentum_15m={features['momentum_15m']:.6f}\n"
        f"- trend_30m={features['trend_30m']:.6f}\n"
        f"- volatility_15m={features['volatility_15m']:.6f}\n"
        f"- historical_reason={event.reason[:180]}\n\n"
        "Objetivo: manter entry_high perto do preco atual quando a leitura justificar entrada fresca, sem chase excessivo, e sugerir target_sell acima do custo total estimado.\n"
        "Use numeros simples e rationale curta em pt-BR.\n"
        f"Use ttl_seconds perto de {ttl_seconds}.\n"
    )


def _call_ollama(host: str, model: str, fallback_model: str, prompt: str) -> tuple[str, str, float]:
    attempts = [
        (model, 45),
        (fallback_model, 30),
    ]
    last_error: Exception | None = None
    for attempt_model, timeout_sec in attempts:
        started = time.time()
        try:
            resp = requests.post(
                f"{host.rstrip('/')}/api/generate",
                json={
                    "model": attempt_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.0,
                        "num_predict": 96,
                        "num_ctx": 2048,
                        "repeat_penalty": 1.10,
                        "top_k": 24,
                        "top_p": 0.80,
                    },
                },
                timeout=timeout_sec,
            )
            resp.raise_for_status()
            return str(resp.json().get("response", "")).strip(), attempt_model, (time.time() - started) * 1000.0
        except Exception as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def _parse_trade_window_suggestion(
    agent: BitcoinTradingAgent,
    raw: str,
    *,
    price: float,
    target: float,
    regime: str,
    controls: Any,
):
    try:
        return agent._parse_ai_trade_window(
            raw,
            SimpleNamespace(price=price),
            SimpleNamespace(ai_buy_target_price=target, ai_take_profit_pct=0.004, suggested_regime=regime),
            controls,
        )
    except Exception:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        candidate = match.group(0) if match else raw
        parsed = ast.literal_eval(candidate)
        repaired = json.dumps(parsed, ensure_ascii=True)
        return agent._parse_ai_trade_window(
            repaired,
            SimpleNamespace(price=price),
            SimpleNamespace(ai_buy_target_price=target, ai_take_profit_pct=0.004, suggested_regime=regime),
            controls,
        )


def _safe_mean(values: Iterable[float | None]) -> float | None:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "count": 0,
            "avg_up_15m": None,
            "avg_up_30m": None,
            "avg_up_60m": None,
            "avg_dn_15m": None,
            "avg_dn_30m": None,
            "avg_dn_60m": None,
            "hit_0_20_60m_pct": None,
            "hit_0_30_60m_pct": None,
        }
    hits_020 = sum(1 for row in rows if (row.get("up_60m") or -999) >= 0.20)
    hits_030 = sum(1 for row in rows if (row.get("up_60m") or -999) >= 0.30)
    return {
        "count": len(rows),
        "avg_up_15m": _safe_mean(row.get("up_15m") for row in rows),
        "avg_up_30m": _safe_mean(row.get("up_30m") for row in rows),
        "avg_up_60m": _safe_mean(row.get("up_60m") for row in rows),
        "avg_dn_15m": _safe_mean(row.get("dn_15m") for row in rows),
        "avg_dn_30m": _safe_mean(row.get("dn_30m") for row in rows),
        "avg_dn_60m": _safe_mean(row.get("dn_60m") for row in rows),
        "hit_0_20_60m_pct": round((hits_020 / len(rows)) * 100.0, 2),
        "hit_0_30_60m_pct": round((hits_030 / len(rows)) * 100.0, 2),
    }


def replay_profile(
    *,
    events: list[GateEvent],
    candles: list[Candle],
    profile: str,
    host: str,
    model: str,
    fallback_model: str,
) -> dict[str, Any]:
    agent = _make_agent(profile)
    controls = SimpleNamespace(min_confidence=0.61, min_trade_interval=150)
    settings = agent._get_trade_window_settings()
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for event in events:
        idx = _find_event_index(candles, event.ts)
        if idx is None or idx < 15:
            continue
        features = _feature_block(candles, idx)
        regime = _infer_regime(event.reason)
        prompt = _build_prompt(event, profile, features, regime, int(settings["ttl_seconds"]))
        try:
            raw, model_used, latency_ms = _call_ollama(host, model, fallback_model, prompt)
        except Exception as exc:
            errors.append(f"{event.price:.2f}|{event.target:.2f}|{event.reason[:80]} => {type(exc).__name__}: {exc}")
            continue
        try:
            suggestion = _parse_trade_window_suggestion(
                agent,
                raw,
                price=event.price,
                target=event.target,
                regime=regime,
                controls=controls,
            )
        except Exception as exc:
            errors.append(
                f"{event.price:.2f}|{event.target:.2f}|{event.reason[:80]} => parse {type(exc).__name__}: {str(exc)[:180]}"
            )
            continue
        old_ceiling = event.target * (1 + event.tolerance_pct) if event.tolerance_pct > 0 else event.target
        new_ceiling = max(old_ceiling, suggestion.entry_high)
        new_allowed = event.price <= new_ceiling
        row = {
            "ts": event.ts,
            "status_old": event.status,
            "price": event.price,
            "target": event.target,
            "old_ceiling": old_ceiling,
            "new_entry_low": suggestion.entry_low,
            "new_entry_high": suggestion.entry_high,
            "new_target_sell": suggestion.target_sell,
            "new_min_confidence": suggestion.min_confidence,
            "new_min_trade_interval": suggestion.min_trade_interval,
            "new_ttl_seconds": suggestion.ttl_seconds,
            "new_allowed": new_allowed,
            "newly_unlocked": event.status == "blocked" and new_allowed,
            "reason": event.reason,
            "regime": regime,
            "rationale": suggestion.rationale,
            "latency_ms": round(latency_ms, 2),
            "model_used": model_used,
        }
        row.update(_forward_metrics(candles, idx, event.price))
        rows.append(row)

    old_allowed = [row for row in rows if row["status_old"] == "allowed"]
    old_blocked = [row for row in rows if row["status_old"] == "blocked"]
    new_allowed = [row for row in rows if row["new_allowed"]]
    newly_unlocked = [row for row in rows if row["newly_unlocked"]]
    still_blocked = [row for row in rows if row["status_old"] == "blocked" and not row["new_allowed"]]

    return {
        "profile": profile,
        "summary": {
            "rows": len(rows),
            "old_allowed": len(old_allowed),
            "old_blocked": len(old_blocked),
            "new_allowed": len(new_allowed),
            "newly_unlocked": len(newly_unlocked),
            "still_blocked": len(still_blocked),
            "errors": len(errors),
            "avg_latency_ms": _safe_mean(row.get("latency_ms") for row in rows),
            "old_allowed_stats": _summarize(old_allowed),
            "new_allowed_stats": _summarize(new_allowed),
            "newly_unlocked_stats": _summarize(newly_unlocked),
            "still_blocked_stats": _summarize(still_blocked),
        },
        "details": rows,
        "errors": errors,
    }


def main() -> None:
    args = parse_args()
    log_file = Path(args.log_file)
    events = parse_events(log_file)
    if not events:
        raise SystemExit(f"No BUY gate events found in {log_file}")

    min_ts = int(min(event.ts for event in events)) - (90 * 60)
    max_ts = int(max(event.ts for event in events)) + (60 * 60)
    candles = fetch_candles(args.symbol, min_ts, max_ts)
    if not candles:
        raise SystemExit("No candles returned from KuCoin")

    result = {
        "symbol": args.symbol,
        "event_count": len(events),
        "window": {
            "from": min_ts,
            "to": max_ts,
        },
        "profiles": [],
    }
    for profile in args.profiles:
        result["profiles"].append(
            replay_profile(
                events=events,
                candles=candles,
                profile=profile,
                host=args.ollama_host,
                model=args.ollama_model,
                fallback_model=args.fallback_model,
            )
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
