#!/usr/bin/env python3
"""Constrói o dataset de fine-tuning do trading-analyst a partir de btc.llm_calls.

Junta cada chamada logada ao Ollama (controls | window | plan) com os trades reais
que aconteceram na sua janela de validade (do timestamp da chamada até a próxima
chamada do mesmo call_type/symbol/profile) e mantém apenas os exemplos cujo PnL
realizado subsequente foi bom — ou seja, exemplos em que os parâmetros/plano
sugeridos pelo modelo levaram a um resultado positivo.

Saída: um JSONL por call_type em OUTPUT_DIR, no formato instruction/input/output
consumido por scripts/trading_analyst_finetune_batch.py (Unsloth SFT).

Pré-requisito: a Fase 1 (log em btc.llm_calls) precisa estar rodando em produção
há tempo suficiente para acumular amostras. Nas primeiras semanas é esperado que
não haja dados suficientes — o script reporta isso e encerra com sucesso (exit 0).

Uso:
  python3 scripts/trading_analyst_finetune_dataset_builder.py
  python3 scripts/trading_analyst_finetune_dataset_builder.py --days 30 --min-samples 50
  python3 scripts/trading_analyst_finetune_dataset_builder.py --out /tmp/eddie-finetune --stats-only

Este script é SÓ-LEITURA no schema btc.* (apenas SELECT). Não altera trading.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Reusa o resolvedor de DSN e o pool do próprio agente.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))
from training_db import TrainingDatabase  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("finetune-dataset")

CALL_TYPES = ("controls", "window", "plan")
DEFAULT_OUTPUT_DIR = Path("/tmp/eddie-finetune")

# Só treina em exemplos cujo PnL realizado na janela ficou acima deste piso.
# 0.0 = qualquer resultado não-negativo. Ajustável via --min-pnl.
DEFAULT_MIN_PNL = 0.0
DEFAULT_MIN_SAMPLES = 50
DEFAULT_DAYS = 45


def _pnl_in_window(
    trades: List[Dict[str, Any]], start_ts: float, end_ts: float,
) -> tuple[float, int]:
    """Soma o PnL realizado dos trades com timestamp em [start_ts, end_ts)."""
    total = 0.0
    n = 0
    for t in trades:
        ts = t.get("timestamp")
        pnl = t.get("pnl")
        if ts is None or pnl is None:
            continue
        if start_ts <= ts < end_ts:
            total += float(pnl)
            n += 1
    return total, n


def _build_example(call: Dict[str, Any], call_type: str) -> Optional[Dict[str, str]]:
    """Converte uma linha de btc.llm_calls num exemplo SFT instruction/input/output.

    O prompt logado JÁ é o formato exato de produção; a resposta bruta do modelo é
    o alvo. Para controls/window preferimos a resposta canônica em JSON quando
    presente (response_json), senão o texto bruto.
    """
    prompt = call.get("prompt")
    if not prompt:
        return None

    response_text = call.get("response_text")
    response_json = call.get("response_json")
    if call_type in ("controls", "window") and response_json:
        # Normaliza para JSON compacto e determinístico como alvo de treino.
        if isinstance(response_json, str):
            try:
                response_json = json.loads(response_json)
            except Exception:
                response_json = None
        if isinstance(response_json, dict):
            output = json.dumps(response_json, ensure_ascii=False, sort_keys=True)
        else:
            output = (response_text or "").strip()
    else:
        output = (response_text or "").strip()

    if not output:
        return None

    return {"instruction": prompt, "input": "", "output": output}


def build_for_call_type(
    db: TrainingDatabase,
    call_type: str,
    *,
    since: float,
    min_pnl: float,
    max_calls: int = 20000,
) -> tuple[List[Dict[str, str]], Dict[str, int]]:
    """Gera exemplos SFT para um call_type, filtrando por PnL realizado positivo."""
    calls = db.get_llm_calls(call_type=call_type, since=since, limit=max_calls)
    stats = {"calls": len(calls), "kept": 0, "no_output": 0, "bad_pnl": 0, "no_trades": 0}

    # Agrupa por (symbol, profile) para calcular a janela de validade de cada chamada
    # (até a próxima chamada do mesmo grupo) e o PnL realizado nessa janela.
    by_group: Dict[tuple, List[Dict[str, Any]]] = {}
    for c in calls:
        by_group.setdefault((c["symbol"], c["profile"]), []).append(c)

    examples: List[Dict[str, str]] = []
    now = time.time()
    for (symbol, profile), group in by_group.items():
        group.sort(key=lambda c: c["timestamp"])
        trades = db.get_recent_trades(
            symbol=symbol, limit=5000, include_dry=False, profile=profile,
        )
        for i, call in enumerate(group):
            start_ts = call["timestamp"]
            end_ts = group[i + 1]["timestamp"] if i + 1 < len(group) else now
            pnl, n_trades = _pnl_in_window(trades, start_ts, end_ts)
            if n_trades == 0:
                stats["no_trades"] += 1
                continue
            if pnl < min_pnl:
                stats["bad_pnl"] += 1
                continue
            example = _build_example(call, call_type)
            if not example:
                stats["no_output"] += 1
                continue
            examples.append(example)
            stats["kept"] += 1

    return examples, stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Dataset builder do fine-tuning trading-analyst")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="Diretório de saída dos JSONL")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS,
                        help="Janela de histórico a considerar (dias)")
    parser.add_argument("--min-pnl", type=float, default=DEFAULT_MIN_PNL,
                        help="PnL mínimo realizado na janela para manter o exemplo")
    parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES,
                        help="Mínimo de exemplos por call_type para gerar o arquivo")
    parser.add_argument("--stats-only", action="store_true",
                        help="Só imprime estatísticas, não escreve arquivos")
    args = parser.parse_args()

    since = time.time() - args.days * 86400
    db = TrainingDatabase()
    args.out.mkdir(parents=True, exist_ok=True)

    total_kept = 0
    manifest: Dict[str, Any] = {"generated_at": time.time(), "days": args.days,
                                "min_pnl": args.min_pnl, "call_types": {}}

    for call_type in CALL_TYPES:
        examples, stats = build_for_call_type(
            db, call_type, since=since, min_pnl=args.min_pnl,
        )
        log.info(
            "call_type=%s: %d chamadas → %d exemplos "
            "(sem_trades=%d, pnl_ruim=%d, sem_output=%d)",
            call_type, stats["calls"], stats["kept"],
            stats["no_trades"], stats["bad_pnl"], stats["no_output"],
        )
        enough = len(examples) >= args.min_samples
        manifest["call_types"][call_type] = {
            **stats, "enough": enough, "min_samples": args.min_samples,
        }

        if not enough:
            log.warning(
                "call_type=%s: %d < %d exemplos — INSUFICIENTE, arquivo não gerado. "
                "Aguarde mais dados da Fase 1.",
                call_type, len(examples), args.min_samples,
            )
            continue

        total_kept += len(examples)
        if args.stats_only:
            continue

        out_path = args.out / f"trading_analyst_{call_type}.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        log.info("Escrito %s (%d exemplos)", out_path, len(examples))

    if not args.stats_only:
        (args.out / "dataset_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8",
        )

    if total_kept == 0:
        log.warning(
            "Nenhum call_type atingiu o mínimo de amostras. "
            "Isso é esperado nas primeiras semanas após a Fase 1 ir ao ar."
        )
    else:
        log.info("Total de exemplos gerados: %d", total_kept)

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
