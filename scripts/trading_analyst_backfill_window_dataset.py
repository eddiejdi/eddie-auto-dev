#!/usr/bin/env python3
"""Backfill do dataset de fine-tuning do contrato `window` a partir do histórico.

Motivação
---------
O dataset builder online (`trading_analyst_finetune_dataset_builder.py`) rotula cada
chamada ao LLM pela existência de uma VENDA executada numa janela curta logo depois.
Vendas reais são raras (guardrail só-vender-no-lucro) e esparsas: mesmo com 3 meses de
histórico isso rende ~15 exemplos — insuficiente para treinar.

Este script troca a fonte do rótulo: em vez de exigir um trade executado, avalia cada
sugestão `window` já persistida em `btc.ai_trade_windows` **contra o preço que de fato
ocorreu** (candles 1min de `btc.candles`), de forma contrafactual — "se você tivesse
entrado na banda sugerida, o preço teria atingido o `target_sell` antes de furar um
stop?". Preço é dado abundante, então isso gera rótulo para ~todas as janelas históricas.

Isso é o *reward shaping* do design (docs/TRADING_FINE_TUNING_DESIGN.md §5) e destrava a
Fase 2 com o histórico existente, em vez de esperar semanas de `btc.llm_calls`.

Saída: JSONL instruction/input/output (compatível com `trading_analyst_finetune_batch.py`),
contendo só os exemplos com desfecho POSITIVO (a sugestão "teria funcionado"), mais um
manifesto com a distribuição de rótulos.

Fidelidade (LER):
- O ALVO (completion) é EXATO: os parâmetros da janela já estão salvos em
  `btc.ai_trade_windows`.
- O RÓTULO é EXATO: derivado do preço real (candles), sem depender de trades executados.
- O PROMPT (input) é uma RECONSTRUÇÃO APROXIMADA — o prompt exato de produção nunca foi
  persistido (é o motivo da Fase 1/`btc.llm_calls`). Reconstruímos o formato de produção
  (`LIMITS=...\nCONTEXT=...`) com os campos recuperáveis (indicadores de `btc.market_states`,
  controls de `btc.ai_trade_controls`, performance 7d point-in-time de `btc.trades`,
  settings do perfil). Campos internos do RAG e o estado exato de posição são aproximados.
  Por isso o candidato treinado aqui é um BOOTSTRAP v0 e SÓ pode ser promovido após o
  shadow-eval reenviar os PROMPTS REAIS logados na Fase 1
  (`scripts/trading_analyst_shadow_eval.py`).

Este script é SÓ-LEITURA no schema btc.* (apenas SELECT). Não altera trading.

Uso:
  python3 scripts/trading_analyst_backfill_window_dataset.py --stats-only
  python3 scripts/trading_analyst_backfill_window_dataset.py --days 90 --horizon-min 30 --out /tmp/eddie-finetune
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Reusa o resolvedor de DSN e o pool do próprio agente.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))
from training_db import TrainingDatabase  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backfill-window")

# Constantes de janela por perfil, espelhando trading_agent._get_trade_window_settings.
# Usadas para reconstruir o bloco LIMITS do prompt de produção.
WINDOW_SETTINGS = {
    "aggressive": {"window_depth_pct": 0.0028, "max_chase_pct": 0.0012, "target_cap_pct": 0.0100, "ttl_seconds": 60},
    "conservative": {"window_depth_pct": 0.0025, "max_chase_pct": 0.0009, "target_cap_pct": 0.0090, "ttl_seconds": 90},
    "default": {"window_depth_pct": 0.0030, "max_chase_pct": 0.0012, "target_cap_pct": 0.0100, "ttl_seconds": 60},
}

# Preâmbulo idêntico ao de produção (trading_agent._generate_ai_trade_window).
WINDOW_PROMPT_PREAMBLE = (
    "Retorne somente um objeto JSON válido, sem markdown, com as chaves "
    "entry_low,entry_high,target_sell,min_confidence,min_trade_interval,ttl_seconds.\n"
    "Use apenas números. Não inclua texto livre. "
    "Mantenha a janela curta e fresca. Se houver dúvida, fique perto do preço atual e do buy_target.\n"
)

DEFAULT_DAYS = 90
DEFAULT_HORIZON_MIN = 30
DEFAULT_STOP_PCT = 0.02
DEFAULT_MIN_SAMPLES = 50
DEFAULT_OUTPUT_DIR = Path("/tmp/eddie-finetune")
POSITIVE_LABELS = ("win", "flat_pos")


# ── Scorer contrafactual (função pura, testável) ─────────────────────────────

def score_price_path(
    bars: Sequence[Tuple[float, float, float]],
    entry_low: float,
    entry_high: float,
    target_sell: float,
    stop_pct: float,
) -> Tuple[str, Dict[str, Any]]:
    """Avalia contrafactualmente uma sugestão de janela contra o caminho de preço.

    Modelo conservador: assume uma ordem de compra no TOPO da banda (`entry_high`,
    o pior preço dentro da banda). A entrada "enche" no primeiro bar cujo mínimo
    toca a banda (low <= entry_high). A partir daí:
      - WIN  se o preço atinge `target_sell` (high >= target_sell) antes de furar o
        stop (`entry_high*(1-stop_pct)`);
      - LOSS se fura o stop antes do target;
      - se um mesmo bar toca target E stop, assume LOSS (conservador);
      - TIMEOUT (flat_pos/flat_neg) se encheu mas nem target nem stop no horizonte —
        classifica pelo sinal do PnL no fim do horizonte;
      - NO_ENTRY se a banda nunca foi tocada no horizonte.

    Args:
        bars: candles cronológicos como tuplas (high, low, close).
        entry_low, entry_high: banda de entrada sugerida.
        target_sell: alvo de saída sugerido.
        stop_pct: excursão adversa máxima tolerada (fração, ex. 0.02 = 2%).

    Returns:
        (label, detalhes) onde label ∈ {win, loss, flat_pos, flat_neg, no_entry, invalid}.
    """
    if not bars or entry_high <= 0 or target_sell <= 0 or entry_high < entry_low:
        return "invalid", {"reason": "input inválido"}
    if target_sell <= entry_high:
        # Alvo abaixo/na entrada: sugestão degenerada, não treina.
        return "invalid", {"reason": "target_sell <= entry_high"}

    fill_price = entry_high
    stop_level = entry_high * (1.0 - stop_pct)
    filled = False
    for high, low, _close in bars:
        if not filled:
            if low <= entry_high:  # preço entrou na banda (a partir de cima)
                filled = True
            else:
                continue
        # Já dentro (mesmo bar do fill conta para target/stop).
        hit_target = high >= target_sell
        hit_stop = low <= stop_level
        if hit_target and hit_stop:
            return "loss", {"exit": "stop_and_target_same_bar", "fill": fill_price}
        if hit_target:
            return "win", {"exit": "target", "fill": fill_price,
                           "pnl_pct": round((target_sell / fill_price - 1) * 100, 4)}
        if hit_stop:
            return "loss", {"exit": "stop", "fill": fill_price,
                            "pnl_pct": round((stop_level / fill_price - 1) * 100, 4)}

    if not filled:
        return "no_entry", {"reason": "banda não tocada no horizonte"}

    last_close = bars[-1][2]
    pnl_pct = round((last_close / fill_price - 1) * 100, 4)
    return ("flat_pos" if pnl_pct >= 0 else "flat_neg"), {"exit": "timeout", "fill": fill_price, "pnl_pct": pnl_pct}


# ── Acesso a dados (só-leitura) ──────────────────────────────────────────────

def _fetchall(conn, sql: str, params: tuple) -> List[tuple]:
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()


def fetch_windows(conn, symbol: str, profiles: Sequence[str], since_ts: float) -> List[Dict[str, Any]]:
    """Carrega sugestões de janela válidas (model=trading-analyst) do histórico."""
    rows = _fetchall(
        conn,
        """
        SELECT id, timestamp, profile, regime, reference_price,
               entry_low, entry_high, target_sell,
               min_confidence, min_trade_interval, ttl_seconds, trigger
        FROM btc.ai_trade_windows
        WHERE symbol = %s
          AND profile = ANY(%s)
          AND model = 'trading-analyst'
          AND timestamp >= %s
          AND entry_low > 0 AND entry_high > 0 AND target_sell > 0
        ORDER BY timestamp ASC
        """,
        (symbol, list(profiles), since_ts),
    )
    cols = ("id", "timestamp", "profile", "regime", "reference_price", "entry_low",
            "entry_high", "target_sell", "min_confidence", "min_trade_interval",
            "ttl_seconds", "trigger")
    return [dict(zip(cols, r)) for r in rows]


def fetch_bars(conn, symbol: str, start_ts: float, end_ts: float) -> List[Tuple[float, float, float]]:
    """Candles 1min (high, low, close) no intervalo, cronológicos."""
    rows = _fetchall(
        conn,
        """
        SELECT high, low, close FROM btc.candles
        WHERE symbol = %s AND ktype = '1min'
          AND timestamp >= %s AND timestamp < %s
        ORDER BY timestamp ASC
        """,
        (symbol, int(start_ts), int(end_ts)),
    )
    return [(float(h), float(l), float(c)) for h, l, c in rows]


def nearest_market_state(conn, symbol: str, ts: float) -> Optional[Dict[str, float]]:
    """Estado de mercado mais recente <= ts (indicadores para o CONTEXT)."""
    rows = _fetchall(
        conn,
        """
        SELECT price, rsi, momentum, volatility, orderbook_imbalance, spread, trade_flow
        FROM btc.market_states
        WHERE symbol = %s AND timestamp <= %s
        ORDER BY timestamp DESC LIMIT 1
        """,
        (symbol, ts),
    )
    if not rows:
        return None
    keys = ("price", "rsi", "momentum", "volatility", "orderbook_imbalance", "spread", "trade_flow")
    return {k: (float(v) if v is not None else 0.0) for k, v in zip(keys, rows[0])}


def perf_context_at(conn, symbol: str, profile: str, ts: float) -> Dict[str, Any]:
    """Reconstrói o bloco de performance 7d point-in-time (sem leakage: só trades < ts)."""
    row = _fetchall(
        conn,
        """
        SELECT
            COUNT(*) FILTER (WHERE side='sell') AS sells,
            COUNT(*) FILTER (WHERE side='sell' AND pnl > 0) AS wins,
            COALESCE(SUM(CASE WHEN side='sell' THEN pnl ELSE 0 END), 0) AS pnl
        FROM btc.trades
        WHERE symbol = %s AND dry_run = false
          AND timestamp >= %s AND timestamp < %s
        """,
        (symbol, ts - 7 * 86400, ts),
    )[0]
    sells, wins, pnl = int(row[0]), int(row[1]), float(row[2])
    return {
        "perf_7d_wr": round(wins / sells, 3) if sells else 0.0,
        "perf_7d_pnl": round(pnl, 4),
        "perf_7d_trades": sells,
    }


def controls_at(conn, symbol: str, profile: str, ts: float) -> Optional[Dict[str, float]]:
    """Últimos controls aplicados <= ts (min_confidence/min_trade_interval)."""
    rows = _fetchall(
        conn,
        """
        SELECT applied_min_confidence, applied_min_trade_interval
        FROM btc.ai_trade_controls
        WHERE symbol = %s AND profile = %s AND timestamp <= %s
        ORDER BY timestamp DESC LIMIT 1
        """,
        (symbol, profile, ts),
    )
    if not rows or rows[0][0] is None:
        return None
    return {"min_confidence": float(rows[0][0]), "min_trade_interval": int(rows[0][1] or 0)}


# ── Reconstrução do prompt (aproximada, formato de produção) ─────────────────

def _compact(payload: Dict[str, Any]) -> str:
    """Serialização compacta idêntica a trading_agent._compact_prompt_json."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


def reconstruct_prompt(conn, w: Dict[str, Any], symbol: str) -> Optional[str]:
    """Reconstrói o prompt da window no formato de produção (aproximado)."""
    ms = nearest_market_state(conn, symbol, w["timestamp"])
    if not ms:
        return None
    profile = w["profile"]
    settings = WINDOW_SETTINGS.get(profile, WINDOW_SETTINGS["default"])
    ctrl = controls_at(conn, symbol, profile, w["timestamp"]) or {
        "min_confidence": float(w.get("min_confidence") or 0.6),
        "min_trade_interval": int(w.get("min_trade_interval") or 120),
    }
    price = ms["price"]

    window_limits = {
        "entry_low_min": round(price * (1 - settings["window_depth_pct"]), 2),
        "entry_low_max": round(price, 2),
        "entry_high_min": round(price * 0.9998, 2),
        "entry_high_max": round(price * (1 + settings["max_chase_pct"]), 2),
        "target_sell_max": round(price * (1 + settings["target_cap_pct"]), 2),
        "min_confidence_min": round(max(0.40, ctrl["min_confidence"] - 0.10), 3),
        "min_confidence_max": round(min(0.92, ctrl["min_confidence"] + 0.08), 3),
        "min_trade_interval_min": max(30, int(ctrl["min_trade_interval"] * 0.5)),
        "min_trade_interval_max": min(900, int(ctrl["min_trade_interval"] * 1.5)),
        "ttl_min": max(20, int(settings["ttl_seconds"] // 2)),
        "ttl_max": int(settings["ttl_seconds"] * 2),
    }
    window_context = {
        "symbol": symbol,
        "profile": profile,
        "trigger": w.get("trigger") or "periodic",
        "regime": w.get("regime") or "UNKNOWN",
        "price": round(price, 2),
        "rsi": round(ms["rsi"], 2),
        "momentum": round(ms["momentum"], 6),
        "volatility": round(ms["volatility"], 6),
        "orderbook_imbalance": round(ms["orderbook_imbalance"], 4),
        "spread": round(ms["spread"], 8),
        "trade_flow": round(ms["trade_flow"], 4),
        "rag_min_confidence": round(ctrl["min_confidence"], 3),
        "rag_min_trade_interval": int(ctrl["min_trade_interval"]),
    }
    window_context.update(perf_context_at(conn, symbol, profile, w["timestamp"]))

    return f"{WINDOW_PROMPT_PREAMBLE}LIMITS={_compact(window_limits)}\nCONTEXT={_compact(window_context)}"


def build_target(w: Dict[str, Any]) -> str:
    """Alvo canônico: JSON determinístico dos parâmetros da janela (chaves ordenadas)."""
    payload = {
        "entry_low": round(float(w["entry_low"]), 2),
        "entry_high": round(float(w["entry_high"]), 2),
        "target_sell": round(float(w["target_sell"]), 2),
        "min_confidence": round(float(w["min_confidence"] or 0), 3),
        "min_trade_interval": int(w["min_trade_interval"] or 0),
        "ttl_seconds": int(w["ttl_seconds"] or 0),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


# ── Pipeline ─────────────────────────────────────────────────────────────────

def build_dataset(
    db: TrainingDatabase, *, symbol: str, profiles: Sequence[str], since_ts: float,
    horizon_sec: int, stop_pct: float,
) -> Tuple[List[Dict[str, str]], Dict[str, int]]:
    """Gera exemplos SFT positivos + estatísticas de rótulo."""
    # db._get_conn() é um context manager (@contextmanager), não uma conexão crua.
    with db._get_conn() as conn:
        windows = fetch_windows(conn, symbol, profiles, since_ts)
        stats: Dict[str, int] = {"windows": len(windows), "kept": 0, "no_prompt": 0}
        examples: List[Dict[str, str]] = []
        for w in windows:
            bars = fetch_bars(conn, symbol, w["timestamp"], w["timestamp"] + horizon_sec)
            label, _detail = score_price_path(
                bars, float(w["entry_low"]), float(w["entry_high"]),
                float(w["target_sell"]), stop_pct,
            )
            stats[label] = stats.get(label, 0) + 1
            if label not in POSITIVE_LABELS:
                continue
            prompt = reconstruct_prompt(conn, w, symbol)
            if not prompt:
                stats["no_prompt"] += 1
                continue
            examples.append({"instruction": prompt, "input": "", "output": build_target(w)})
            stats["kept"] += 1
        return examples, stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill contrafactual do dataset window (Fase 2)")
    parser.add_argument("--symbol", default="BTC-USDT")
    parser.add_argument("--profiles", default="aggressive,conservative",
                        help="Perfis separados por vírgula")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--horizon-min", type=int, default=DEFAULT_HORIZON_MIN,
                        help="Horizonte de avaliação do contrafactual, em minutos")
    parser.add_argument("--stop-pct", type=float, default=DEFAULT_STOP_PCT,
                        help="Excursão adversa máxima tolerada (fração, ex. 0.02)")
    parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--stats-only", action="store_true")
    args = parser.parse_args()

    profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]
    since_ts = time.time() - args.days * 86400
    horizon_sec = args.horizon_min * 60

    db = TrainingDatabase()
    examples, stats = build_dataset(
        db, symbol=args.symbol, profiles=profiles, since_ts=since_ts,
        horizon_sec=horizon_sec, stop_pct=args.stop_pct,
    )
    db.close()

    dist = {k: v for k, v in sorted(stats.items()) if k not in ("windows", "kept", "no_prompt")}
    log.info("Janelas avaliadas: %d | horizonte=%dmin stop=%.1f%%",
             stats["windows"], args.horizon_min, args.stop_pct * 100)
    log.info("Distribuição de rótulos: %s", dist)
    log.info("Exemplos positivos (%s) mantidos: %d", "/".join(POSITIVE_LABELS), stats["kept"])

    enough = len(examples) >= args.min_samples
    if not enough:
        log.warning("%d < %d exemplos — abaixo do mínimo para treinar.", len(examples), args.min_samples)

    if not args.stats_only and examples:
        args.out.mkdir(parents=True, exist_ok=True)
        out_path = args.out / "trading_analyst_window_backfill.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        manifest = {
            "generated_at": time.time(), "symbol": args.symbol, "profiles": profiles,
            "days": args.days, "horizon_min": args.horizon_min, "stop_pct": args.stop_pct,
            "label_distribution": dist, "kept": stats["kept"],
            "source": "counterfactual price backfill (bootstrap v0)",
            "fidelity": "target+label exatos; prompt reconstruído aproximado — validar em shadow com prompts reais",
        }
        (args.out / "window_backfill_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("Escrito %s (%d exemplos) + manifesto", out_path, len(examples))

    return 0


if __name__ == "__main__":
    sys.exit(main())
