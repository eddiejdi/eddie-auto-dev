#!/usr/bin/env python3
"""Validação + veredito de rollout do trading-analyst-candidate + relatório Telegram.

Compara o candidato contra a produção usando os resultados do shadow-eval
(btc.llm_shadow_results) de duas formas:

  1. Concordância (clone check): quão parecido o candidato é da produção nos
     parâmetros de window (target_sell idêntico %, divergência média).
  2. EDGE contrafactual: para cada window avaliada, aplica o MESMO scorer por
     preço real (candles) à sugestão da PRODUÇÃO e à do CANDIDATO, e compara
     win-rate e PnL% estimado. Isso mede se o candidato produz janelas melhores
     sem depender de trades executados (raros).

Veredito de rollout (conservador — dinheiro real):
  READY só se: n >= MIN_N, 0 erros, e o candidato supera a produção em PnL% médio
  por uma margem >= EDGE_MARGIN_PCT. Caso contrário NOT_READY (com os números).
  NUNCA promove sozinho — só DETECTA e RECOMENDA; a troca em produção é humana.

Sempre envia um relatório no Telegram (resultado do treino + veredito).

Uso:
  python3 scripts/trading_analyst_rollout_report.py                 # avalia + envia
  python3 scripts/trading_analyst_rollout_report.py --no-telegram   # só imprime
  python3 scripts/trading_analyst_rollout_report.py --days 8 --loss "<loss>"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import psycopg2

# Reusa o scorer contrafactual do backfill.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from trading_analyst_backfill_window_dataset import score_price_path  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("rollout-report")

CANDIDATE_MODEL = os.environ.get("FT_TARGET_MODEL", "trading-analyst-candidate")
HORIZON_SEC = int(os.environ.get("FT_HORIZON_MIN", "60")) * 60
STOP_PCT = float(os.environ.get("FT_STOP_PCT", "0.02"))
# Gates do veredito (conservadores).
MIN_N = int(os.environ.get("ROLLOUT_MIN_N", "50"))
EDGE_MARGIN_PCT = float(os.environ.get("ROLLOUT_EDGE_MARGIN_PCT", "0.05"))


def _db():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL não configurado")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    return conn


def _parse(obj: str) -> dict | None:
    try:
        d = json.loads(obj)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def evaluate(conn, days: int) -> dict:
    """Coleta shadow windows recentes e computa concordância + edge contrafactual."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT c.timestamp, c.symbol, c.response_text, s.candidate_response, s.error
        FROM btc.llm_shadow_results s
        JOIN btc.llm_calls c ON c.id = s.llm_call_id
        WHERE s.candidate_model = %s AND s.call_type = 'window'
          AND s.timestamp >= extract(epoch from now()) - %s
        """,
        (CANDIDATE_MODEL, days * 86400),
    )
    rows = cur.fetchall()

    n = target_ident = errors = 0
    prod_win = cand_win = 0
    prod_pnls: list[float] = []
    cand_pnls: list[float] = []

    def _score(sym, ts, d):
        cur2 = conn.cursor()
        cur2.execute(
            "SELECT high, low, close FROM btc.candles WHERE symbol=%s AND ktype='1min' "
            "AND timestamp >= %s AND timestamp < %s ORDER BY timestamp ASC",
            (sym, int(ts), int(ts + HORIZON_SEC)),
        )
        bars = [(float(h), float(l), float(c)) for h, l, c in cur2.fetchall()]
        cur2.close()
        return score_price_path(bars, float(d["entry_low"]), float(d["entry_high"]),
                                float(d["target_sell"]), STOP_PCT)

    for ts, sym, prod_text, cand_text, err in rows:
        if err:
            errors += 1
            continue
        prod = _parse(prod_text or "")
        cand = _parse(cand_text or "")
        if not prod or not cand:
            continue
        need = {"entry_low", "entry_high", "target_sell"}
        if not (need <= prod.keys() and need <= cand.keys()):
            continue
        n += 1
        if float(prod.get("target_sell", 0)) == float(cand.get("target_sell", -1)):
            target_ident += 1
        pl, pd = _score(sym, ts, prod)
        cl, cd = _score(sym, ts, cand)
        if pl == "win":
            prod_win += 1
        if cl == "win":
            cand_win += 1
        prod_pnls.append(float(pd.get("pnl_pct", 0.0)))
        cand_pnls.append(float(cd.get("pnl_pct", 0.0)))

    prod_avg = round(sum(prod_pnls) / len(prod_pnls), 4) if prod_pnls else 0.0
    cand_avg = round(sum(cand_pnls) / len(cand_pnls), 4) if cand_pnls else 0.0
    return {
        "n": n, "errors": errors,
        "target_identical_pct": round(100.0 * target_ident / n, 0) if n else 0,
        "prod_win_rate": round(100.0 * prod_win / n, 1) if n else 0,
        "cand_win_rate": round(100.0 * cand_win / n, 1) if n else 0,
        "prod_avg_pnl_pct": prod_avg,
        "cand_avg_pnl_pct": cand_avg,
        "edge_pnl_pct": round(cand_avg - prod_avg, 4),
    }


def verdict(m: dict) -> tuple[str, str]:
    """Decide READY/NOT_READY de forma conservadora."""
    if m["n"] < MIN_N:
        return "NOT_READY", f"amostra insuficiente (n={m['n']} < {MIN_N})"
    if m["errors"] > 0:
        return "NOT_READY", f"{m['errors']} erros no shadow"
    if m["edge_pnl_pct"] >= EDGE_MARGIN_PCT:
        return "READY", (f"candidato supera produção em PnL contrafactual "
                         f"(+{m['edge_pnl_pct']:.3f}% ≥ {EDGE_MARGIN_PCT}%)")
    return "NOT_READY", (f"sem edge suficiente (candidato {m['edge_pnl_pct']:+.3f}% vs "
                         f"margem {EDGE_MARGIN_PCT}%); candidato ≈ produção")


def build_report(m: dict, loss: str | None, dataset_n: int | None) -> str:
    v, reason = verdict(m)
    icon = "🟢" if v == "READY" else "🟡"
    lines = [
        "🤖 *Retreino trading-analyst-candidate*",
        "",
        "🏋️ *Treino*",
        f"  • Dataset: {dataset_n if dataset_n is not None else '?'} exemplos (window BTC)",
        f"  • Loss final: {loss or 'n/d'}",
        "",
        f"🔬 *Shadow (últimos dias, n={m['n']}, {m['errors']} erros)*",
        f"  • target idêntico à prod: {m['target_identical_pct']:.0f}%",
        f"  • win-rate contrafactual: cand {m['cand_win_rate']:.1f}% vs prod {m['prod_win_rate']:.1f}%",
        f"  • PnL% médio: cand {m['cand_avg_pnl_pct']:+.3f} vs prod {m['prod_avg_pnl_pct']:+.3f} "
        f"(edge {m['edge_pnl_pct']:+.3f})",
        "",
        f"{icon} *Rollout: {v}*",
        f"  {reason}",
    ]
    if v == "READY":
        lines += ["", "⚠️ Promoção é decisão HUMANA — responda para aprovar a troca em produção."]
    return "\n".join(lines)


async def send_telegram(text: str) -> None:
    try:
        from telegram import Bot
        from telegram.request import HTTPXRequest
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not token:
            try:
                sys.path.insert(0, "/apps/crypto-trader/trading/btc_trading_agent")
                from secrets_helper import get_telegram_token  # type: ignore
                token = get_telegram_token()
            except Exception:
                pass
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN não configurado")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "-1004434951297")
        req = HTTPXRequest(connect_timeout=30, read_timeout=30, write_timeout=20, pool_timeout=30)
        bot = Bot(token=token, request=req)
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        except Exception:
            await bot.send_message(chat_id=chat_id, text=text)
        log.info("Relatório enviado no Telegram")
    except Exception:
        log.exception("Falha ao enviar Telegram")


def main() -> int:
    ap = argparse.ArgumentParser(description="Veredito de rollout + relatório do candidato")
    ap.add_argument("--days", type=int, default=8)
    ap.add_argument("--loss", default=None, help="Loss final do treino (para o relatório)")
    ap.add_argument("--dataset-n", type=int, default=None)
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args()

    conn = _db()
    try:
        m = evaluate(conn, args.days)
    finally:
        conn.close()

    report = build_report(m, args.loss, args.dataset_n)
    print("\n" + "=" * 60 + "\n" + report + "\n" + "=" * 60 + "\n")
    log.info("Métricas: %s", json.dumps(m))
    if not args.no_telegram:
        asyncio.run(send_telegram(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
