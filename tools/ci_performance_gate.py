#!/usr/bin/env python3
"""Gate de desempenho para CI: falha quando v0 performa pior que v-1."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from compare_trading_versions import build_report  # noqa: E402


FAIL_BANNER = "CI_CANCELED_BY_PERF_GATE"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dsn", required=True)
    p.add_argument("--symbol", default="BTC-USDT")
    p.add_argument("--profiles", default="aggressive,conservative")
    p.add_argument("--mode", choices=["time", "tag"], default="time")
    p.add_argument("--cutover", help="Obrigatorio no modo time.")
    p.add_argument("--duration-hours", type=float, default=None)
    p.add_argument("--vminus1-start")
    p.add_argument("--vminus1-end")
    p.add_argument("--v0-start")
    p.add_argument("--v0-end")
    p.add_argument("--vminus1-tag", default="-1")
    p.add_argument("--v0-tag", default="0")
    p.add_argument("--version-keys", default="version,agent_version,config_version,release_version")
    p.add_argument("--since")
    p.add_argument("--until")
    p.add_argument("--min-realized-pnl-delta", type=float, default=0.0)
    p.add_argument("--min-win-rate-sell-pp", type=float, default=0.0)
    p.add_argument("--min-exec-rate-sell-pp", type=float, default=0.0)
    p.add_argument("--min-v0-sells", type=int, default=0)
    p.add_argument("--json-report-out", help="Salva o report JSON completo neste caminho.")
    return p.parse_args()


def evaluate_report(report: dict[str, Any], args: argparse.Namespace) -> list[str]:
    issues: list[str] = []
    d = report.get("delta", {})
    v0 = report.get("v0", {}).get("trades", {})
    pnl_delta = float(d.get("realized_pnl_usd_delta", 0.0) or 0.0)
    wr_delta = float(d.get("win_rate_sell_pp", 0.0) or 0.0)
    exec_delta = float(d.get("exec_rate_sell_pp", 0.0) or 0.0)
    v0_sells = int(v0.get("sells", 0) or 0)

    if pnl_delta < args.min_realized_pnl_delta:
        issues.append(
            f"realized_pnl_usd_delta={pnl_delta:.6f} < min={args.min_realized_pnl_delta:.6f}"
        )
    if wr_delta < args.min_win_rate_sell_pp:
        issues.append(
            f"win_rate_sell_pp={wr_delta:.4f} < min={args.min_win_rate_sell_pp:.4f}"
        )
    if exec_delta < args.min_exec_rate_sell_pp:
        issues.append(
            f"exec_rate_sell_pp={exec_delta:.4f} < min={args.min_exec_rate_sell_pp:.4f}"
        )
    if v0_sells < args.min_v0_sells:
        issues.append(f"v0_sells={v0_sells} < min={args.min_v0_sells}")
    return issues


def build_compare_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        dsn=args.dsn,
        symbol=args.symbol,
        profiles=args.profiles,
        mode=args.mode,
        cutover=args.cutover,
        duration_hours=args.duration_hours,
        vminus1_start=args.vminus1_start,
        vminus1_end=args.vminus1_end,
        v0_start=args.v0_start,
        v0_end=args.v0_end,
        vminus1_tag=args.vminus1_tag,
        v0_tag=args.v0_tag,
        version_keys=args.version_keys,
        since=args.since,
        until=args.until,
        json=True,
    )


def write_summary(lines: list[str]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    args = parse_args()
    try:
        report = build_report(build_compare_args(args))
    except Exception as e:
        msg = f"{FAIL_BANNER}: nao foi possivel gerar relatorio ({e})"
        print(f"::error::{msg}")
        print(f"*** {FAIL_BANNER} ***")
        print(msg)
        write_summary([f"## {FAIL_BANNER}", msg])
        raise SystemExit(2)

    if args.json_report_out:
        with open(args.json_report_out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    issues = evaluate_report(report, args)
    if issues:
        print(f"::error::{FAIL_BANNER}: regressao de desempenho detectada")
        print("")
        print("############################################")
        print(f"### {FAIL_BANNER} ###")
        print("############################################")
        for item in issues:
            print(f"- {item}")
        write_summary(
            [
                f"## {FAIL_BANNER}",
                "Regressao de desempenho detectada:",
                *[f"- {i}" for i in issues],
            ]
        )
        raise SystemExit(1)

    print("PERF_GATE_OK: sem regressao nos limites configurados.")
    write_summary(["## PERF_GATE_OK", "Sem regressao de desempenho nos limites configurados."])


if __name__ == "__main__":
    main()
