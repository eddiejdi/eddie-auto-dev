#!/usr/bin/env python3
"""Compara desempenho de trading entre versoes v-1 e v0."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg2


@dataclass
class Window:
    label: str
    start: datetime
    end: datetime


@dataclass
class TradeMetrics:
    trades_total: int
    buys: int
    sells: int
    realized_pnl_usd: float
    avg_sell_pnl_pct: float
    win_rate_sell_pct: float
    profit_factor: float | None
    sells_per_hour: float


@dataclass
class DecisionMetrics:
    decisions_total: int
    decisions_buy: int
    decisions_sell: int
    decisions_hold: int
    executed_total: int
    executed_sell: int
    exec_rate_total_pct: float
    exec_rate_sell_pct: float


VERSION_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_dt(value: str) -> datetime:
    v = value.strip()
    if v.lower() == "now":
        return datetime.now(timezone.utc)
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dsn", required=True, help="DSN PostgreSQL para btc_trading")
    p.add_argument("--symbol", default="BTC-USDT")
    p.add_argument(
        "--mode",
        choices=["time", "tag"],
        default="time",
        help="Modo time (janela) ou tag (versao em JSON).",
    )
    p.add_argument(
        "--profiles",
        default="aggressive,conservative",
        help="Lista separada por virgula. Ex: aggressive,conservative",
    )
    p.add_argument(
        "--cutover",
        help="Timestamp de corte da versao v0 (ISO8601). Ex: 2026-03-19T21:28:31Z",
    )
    p.add_argument(
        "--duration-hours",
        type=float,
        default=None,
        help="Duracao de cada janela. Se omitido, v0 vai de cutover ate now.",
    )
    p.add_argument("--vminus1-start", help="Inicio explicito da janela v-1")
    p.add_argument("--vminus1-end", help="Fim explicito da janela v-1")
    p.add_argument("--v0-start", help="Inicio explicito da janela v0")
    p.add_argument("--v0-end", help="Fim explicito da janela v0")
    p.add_argument("--vminus1-tag", default="-1", help="Tag da versao -1 em metadata/features.")
    p.add_argument("--v0-tag", default="0", help="Tag da versao 0 em metadata/features.")
    p.add_argument(
        "--version-keys",
        default="version,agent_version,config_version,release_version",
        help="Chaves JSON candidatas para versao.",
    )
    p.add_argument("--since", help="Filtro opcional de inicio para modo tag (ISO8601).")
    p.add_argument("--until", help="Filtro opcional de fim para modo tag (ISO8601).")
    p.add_argument("--json", action="store_true", help="Saida em JSON")
    return p.parse_args()


def resolve_windows(args: argparse.Namespace) -> tuple[Window, Window]:
    explicit = all([args.vminus1_start, args.vminus1_end, args.v0_start, args.v0_end])
    if explicit:
        v_minus_1 = Window("v-1", parse_dt(args.vminus1_start), parse_dt(args.vminus1_end))
        v0 = Window("v0", parse_dt(args.v0_start), parse_dt(args.v0_end))
        return v_minus_1, v0

    if not args.cutover:
        raise SystemExit(
            "Informe --cutover ou os quatro parametros explicitos de janela "
            "(--vminus1-start --vminus1-end --v0-start --v0-end)."
        )

    cutover = parse_dt(args.cutover)
    if args.duration_hours is not None:
        duration = timedelta(hours=args.duration_hours)
        v_minus_1 = Window("v-1", cutover - duration, cutover)
        v0 = Window("v0", cutover, cutover + duration)
    else:
        now = datetime.now(timezone.utc)
        if cutover >= now:
            raise SystemExit("--cutover deve ser anterior ao horario atual.")
        duration = now - cutover
        v_minus_1 = Window("v-1", cutover - duration, cutover)
        v0 = Window("v0", cutover, now)
    return v_minus_1, v0


def parse_version_keys(raw: str) -> list[str]:
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        raise SystemExit("version-keys vazio.")
    invalid = [k for k in keys if not VERSION_KEY_RE.match(k)]
    if invalid:
        raise SystemExit(f"version-keys invalidas: {', '.join(invalid)}")
    return keys


def build_version_expr(alias: str, json_col: str, keys: list[str]) -> str:
    parts = [f"NULLIF({alias}.{json_col}->>'{k}', '')" for k in keys]
    return f"COALESCE({', '.join(parts)}, '')"


def q_metrics_time(
    conn: Any,
    symbol: str,
    profiles: list[str],
    start: datetime,
    end: datetime,
) -> tuple[TradeMetrics, DecisionMetrics]:
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH scoped AS (
              SELECT side, pnl, pnl_pct
              FROM btc.trades
              WHERE symbol = %s
                AND profile = ANY(%s)
                AND created_at >= %s
                AND created_at < %s
            ),
            sells AS (
              SELECT pnl, pnl_pct FROM scoped WHERE lower(side) = 'sell'
            )
            SELECT
              COUNT(*)::int AS trades_total,
              COUNT(*) FILTER (WHERE lower(side)='buy')::int AS buys,
              COUNT(*) FILTER (WHERE lower(side)='sell')::int AS sells,
              COALESCE(SUM(pnl) FILTER (WHERE lower(side)='sell'), 0)::float8 AS realized_pnl_usd,
              COALESCE(AVG(pnl_pct) FILTER (WHERE lower(side)='sell'), 0)::float8 AS avg_sell_pnl_pct,
              COALESCE(
                100.0 * (COUNT(*) FILTER (WHERE lower(side)='sell' AND pnl > 0))
                / NULLIF(COUNT(*) FILTER (WHERE lower(side)='sell'), 0),
                0
              )::float8 AS win_rate_sell_pct,
              CASE
                WHEN COALESCE(SUM(CASE WHEN pnl < 0 THEN -pnl ELSE 0 END), 0) = 0 THEN NULL
                ELSE (
                  COALESCE(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END), 0)
                  / NULLIF(COALESCE(SUM(CASE WHEN pnl < 0 THEN -pnl ELSE 0 END), 0), 0)
                )::float8
              END AS profit_factor
            FROM scoped;
            """,
            (symbol, profiles, start, end),
        )
        t = cur.fetchone()

        hours = max((end - start).total_seconds() / 3600.0, 1e-9)
        trade_metrics = TradeMetrics(
            trades_total=t[0],
            buys=t[1],
            sells=t[2],
            realized_pnl_usd=float(t[3]),
            avg_sell_pnl_pct=float(t[4]),
            win_rate_sell_pct=float(t[5]),
            profit_factor=(None if t[6] is None else float(t[6])),
            sells_per_hour=float(t[2]) / hours,
        )

        cur.execute(
            """
            WITH scoped AS (
              SELECT action, executed
              FROM btc.decisions
              WHERE symbol = %s
                AND profile = ANY(%s)
                AND to_timestamp(timestamp) >= %s
                AND to_timestamp(timestamp) < %s
            )
            SELECT
              COUNT(*)::int AS decisions_total,
              COUNT(*) FILTER (WHERE upper(action)='BUY')::int AS decisions_buy,
              COUNT(*) FILTER (WHERE upper(action)='SELL')::int AS decisions_sell,
              COUNT(*) FILTER (WHERE upper(action)='HOLD')::int AS decisions_hold,
              COUNT(*) FILTER (WHERE executed)::int AS executed_total,
              COUNT(*) FILTER (WHERE upper(action)='SELL' AND executed)::int AS executed_sell,
              COALESCE(100.0 * COUNT(*) FILTER (WHERE executed) / NULLIF(COUNT(*),0), 0)::float8 AS exec_rate_total_pct,
              COALESCE(
                100.0 * COUNT(*) FILTER (WHERE upper(action)='SELL' AND executed)
                / NULLIF(COUNT(*) FILTER (WHERE upper(action)='SELL'),0),
                0
              )::float8 AS exec_rate_sell_pct
            FROM scoped;
            """,
            (symbol, profiles, start, end),
        )
        d = cur.fetchone()
        decision_metrics = DecisionMetrics(
            decisions_total=d[0],
            decisions_buy=d[1],
            decisions_sell=d[2],
            decisions_hold=d[3],
            executed_total=d[4],
            executed_sell=d[5],
            exec_rate_total_pct=float(d[6]),
            exec_rate_sell_pct=float(d[7]),
        )

    return trade_metrics, decision_metrics


def q_hours_for_tag(
    conn: Any,
    symbol: str,
    profiles: list[str],
    tag: str,
    keys: list[str],
    since: datetime | None,
    until: datetime | None,
) -> float:
    trade_expr = build_version_expr("t", "metadata", keys)
    decision_expr = build_version_expr("d", "features", keys)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH ts_union AS (
              SELECT t.created_at AS ts
              FROM btc.trades t
              WHERE t.symbol = %s
                AND t.profile = ANY(%s)
                AND {trade_expr} = %s
                AND (%s::timestamptz IS NULL OR t.created_at >= %s::timestamptz)
                AND (%s::timestamptz IS NULL OR t.created_at < %s::timestamptz)
              UNION ALL
              SELECT to_timestamp(d.timestamp) AS ts
              FROM btc.decisions d
              WHERE d.symbol = %s
                AND d.profile = ANY(%s)
                AND {decision_expr} = %s
                AND (%s::timestamptz IS NULL OR to_timestamp(d.timestamp) >= %s::timestamptz)
                AND (%s::timestamptz IS NULL OR to_timestamp(d.timestamp) < %s::timestamptz)
            )
            SELECT
              EXTRACT(EPOCH FROM (MAX(ts) - MIN(ts)))::float8 AS span_seconds
            FROM ts_union;
            """,
            (
                symbol,
                profiles,
                tag,
                since,
                since,
                until,
                until,
                symbol,
                profiles,
                tag,
                since,
                since,
                until,
                until,
            ),
        )
        row = cur.fetchone()
    span_seconds = float(row[0]) if row and row[0] is not None else 0.0
    return max(span_seconds / 3600.0, 1e-9)


def q_metrics_tag(
    conn: Any,
    symbol: str,
    profiles: list[str],
    tag: str,
    keys: list[str],
    since: datetime | None,
    until: datetime | None,
) -> tuple[TradeMetrics, DecisionMetrics]:
    trade_expr = build_version_expr("t", "metadata", keys)
    decision_expr = build_version_expr("d", "features", keys)
    hours = q_hours_for_tag(conn, symbol, profiles, tag, keys, since, until)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH scoped AS (
              SELECT t.side, t.pnl, t.pnl_pct
              FROM btc.trades t
              WHERE t.symbol = %s
                AND t.profile = ANY(%s)
                AND {trade_expr} = %s
                AND (%s::timestamptz IS NULL OR t.created_at >= %s::timestamptz)
                AND (%s::timestamptz IS NULL OR t.created_at < %s::timestamptz)
            )
            SELECT
              COUNT(*)::int AS trades_total,
              COUNT(*) FILTER (WHERE lower(side)='buy')::int AS buys,
              COUNT(*) FILTER (WHERE lower(side)='sell')::int AS sells,
              COALESCE(SUM(pnl) FILTER (WHERE lower(side)='sell'), 0)::float8 AS realized_pnl_usd,
              COALESCE(AVG(pnl_pct) FILTER (WHERE lower(side)='sell'), 0)::float8 AS avg_sell_pnl_pct,
              COALESCE(
                100.0 * (COUNT(*) FILTER (WHERE lower(side)='sell' AND pnl > 0))
                / NULLIF(COUNT(*) FILTER (WHERE lower(side)='sell'), 0),
                0
              )::float8 AS win_rate_sell_pct,
              CASE
                WHEN COALESCE(SUM(CASE WHEN pnl < 0 THEN -pnl ELSE 0 END), 0) = 0 THEN NULL
                ELSE (
                  COALESCE(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END), 0)
                  / NULLIF(COALESCE(SUM(CASE WHEN pnl < 0 THEN -pnl ELSE 0 END), 0), 0)
                )::float8
              END AS profit_factor
            FROM scoped;
            """,
            (symbol, profiles, tag, since, since, until, until),
        )
        t = cur.fetchone()

        trade_metrics = TradeMetrics(
            trades_total=t[0],
            buys=t[1],
            sells=t[2],
            realized_pnl_usd=float(t[3]),
            avg_sell_pnl_pct=float(t[4]),
            win_rate_sell_pct=float(t[5]),
            profit_factor=(None if t[6] is None else float(t[6])),
            sells_per_hour=float(t[2]) / hours,
        )

        cur.execute(
            f"""
            WITH scoped AS (
              SELECT d.action, d.executed
              FROM btc.decisions d
              WHERE d.symbol = %s
                AND d.profile = ANY(%s)
                AND {decision_expr} = %s
                AND (%s::timestamptz IS NULL OR to_timestamp(d.timestamp) >= %s::timestamptz)
                AND (%s::timestamptz IS NULL OR to_timestamp(d.timestamp) < %s::timestamptz)
            )
            SELECT
              COUNT(*)::int AS decisions_total,
              COUNT(*) FILTER (WHERE upper(action)='BUY')::int AS decisions_buy,
              COUNT(*) FILTER (WHERE upper(action)='SELL')::int AS decisions_sell,
              COUNT(*) FILTER (WHERE upper(action)='HOLD')::int AS decisions_hold,
              COUNT(*) FILTER (WHERE executed)::int AS executed_total,
              COUNT(*) FILTER (WHERE upper(action)='SELL' AND executed)::int AS executed_sell,
              COALESCE(100.0 * COUNT(*) FILTER (WHERE executed) / NULLIF(COUNT(*),0), 0)::float8 AS exec_rate_total_pct,
              COALESCE(
                100.0 * COUNT(*) FILTER (WHERE upper(action)='SELL' AND executed)
                / NULLIF(COUNT(*) FILTER (WHERE upper(action)='SELL'),0),
                0
              )::float8 AS exec_rate_sell_pct
            FROM scoped;
            """,
            (symbol, profiles, tag, since, since, until, until),
        )
        d = cur.fetchone()
        decision_metrics = DecisionMetrics(
            decisions_total=d[0],
            decisions_buy=d[1],
            decisions_sell=d[2],
            decisions_hold=d[3],
            executed_total=d[4],
            executed_sell=d[5],
            exec_rate_total_pct=float(d[6]),
            exec_rate_sell_pct=float(d[7]),
        )
    return trade_metrics, decision_metrics


def pct_delta(base: float, new: float) -> float | None:
    if abs(base) < 1e-12:
        return None
    return ((new - base) / abs(base)) * 100.0


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]
    keys = parse_version_keys(args.version_keys)
    since = parse_dt(args.since) if args.since else None
    until = parse_dt(args.until) if args.until else None
    conn = psycopg2.connect(args.dsn)
    try:
        if args.mode == "time":
            w_prev, w_now = resolve_windows(args)
            t_prev, d_prev = q_metrics_time(conn, args.symbol, profiles, w_prev.start, w_prev.end)
            t_now, d_now = q_metrics_time(conn, args.symbol, profiles, w_now.start, w_now.end)
            windows_payload = {
                "v-1": {"start": w_prev.start.isoformat(), "end": w_prev.end.isoformat()},
                "v0": {"start": w_now.start.isoformat(), "end": w_now.end.isoformat()},
            }
        else:
            t_prev, d_prev = q_metrics_tag(
                conn,
                args.symbol,
                profiles,
                args.vminus1_tag,
                keys,
                since,
                until,
            )
            t_now, d_now = q_metrics_tag(
                conn,
                args.symbol,
                profiles,
                args.v0_tag,
                keys,
                since,
                until,
            )
            windows_payload = {
                "v-1": {"tag": args.vminus1_tag, "since": args.since, "until": args.until},
                "v0": {"tag": args.v0_tag, "since": args.since, "until": args.until},
            }
    finally:
        conn.close()

    deltas = {
        "realized_pnl_usd_delta": t_now.realized_pnl_usd - t_prev.realized_pnl_usd,
        "realized_pnl_usd_delta_pct": pct_delta(t_prev.realized_pnl_usd, t_now.realized_pnl_usd),
        "win_rate_sell_pp": t_now.win_rate_sell_pct - t_prev.win_rate_sell_pct,
        "exec_rate_sell_pp": d_now.exec_rate_sell_pct - d_prev.exec_rate_sell_pct,
        "sells_per_hour_delta": t_now.sells_per_hour - t_prev.sells_per_hour,
    }

    return {
        "mode": args.mode,
        "symbol": args.symbol,
        "profiles": profiles,
        "version_keys": keys,
        "windows": windows_payload,
        "v-1": {"trades": asdict(t_prev), "decisions": asdict(d_prev)},
        "v0": {"trades": asdict(t_now), "decisions": asdict(d_now)},
        "delta": deltas,
    }


def fmt(v: Any) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def print_human(report: dict[str, Any]) -> None:
    w_prev = report["windows"]["v-1"]
    w_now = report["windows"]["v0"]
    print("Comparativo de desempenho: v-1 vs v0")
    print(f"Modo: {report['mode']}")
    print(f"Symbol: {report['symbol']} | Profiles: {', '.join(report['profiles'])}")
    if report["mode"] == "time":
        print(f"v-1: {w_prev['start']} -> {w_prev['end']}")
        print(f"v0 : {w_now['start']} -> {w_now['end']}")
    else:
        print(f"v-1 tag: {w_prev['tag']} | since={w_prev['since']} | until={w_prev['until']}")
        print(f"v0  tag: {w_now['tag']} | since={w_now['since']} | until={w_now['until']}")
    print("")
    print(f"{'Metrica':34} {'v-1':>14} {'v0':>14} {'Delta':>14}")
    print("-" * 80)

    rows = [
        ("Trades total", report["v-1"]["trades"]["trades_total"], report["v0"]["trades"]["trades_total"]),
        ("Sells", report["v-1"]["trades"]["sells"], report["v0"]["trades"]["sells"]),
        ("Sells/hora", report["v-1"]["trades"]["sells_per_hour"], report["v0"]["trades"]["sells_per_hour"]),
        ("PnL realizado USD", report["v-1"]["trades"]["realized_pnl_usd"], report["v0"]["trades"]["realized_pnl_usd"]),
        ("Win rate SELL (%)", report["v-1"]["trades"]["win_rate_sell_pct"], report["v0"]["trades"]["win_rate_sell_pct"]),
        ("Profit factor", report["v-1"]["trades"]["profit_factor"], report["v0"]["trades"]["profit_factor"]),
        ("Decisions total", report["v-1"]["decisions"]["decisions_total"], report["v0"]["decisions"]["decisions_total"]),
        ("Decisions SELL", report["v-1"]["decisions"]["decisions_sell"], report["v0"]["decisions"]["decisions_sell"]),
        ("Exec rate total (%)", report["v-1"]["decisions"]["exec_rate_total_pct"], report["v0"]["decisions"]["exec_rate_total_pct"]),
        ("Exec rate SELL (%)", report["v-1"]["decisions"]["exec_rate_sell_pct"], report["v0"]["decisions"]["exec_rate_sell_pct"]),
    ]

    for name, a, b in rows:
        delta = None
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            delta = b - a
        print(f"{name:34} {fmt(a):>14} {fmt(b):>14} {fmt(delta):>14}")

    d = report["delta"]
    print("-" * 80)
    print(f"{'Delta PnL (%)':34} {fmt(d['realized_pnl_usd_delta_pct']):>14}")
    print(f"{'Delta WinRate (pp)':34} {fmt(d['win_rate_sell_pp']):>14}")
    print(f"{'Delta Exec SELL (pp)':34} {fmt(d['exec_rate_sell_pp']):>14}")


def main() -> None:
    args = parse_args()
    report = build_report(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)


if __name__ == "__main__":
    main()
