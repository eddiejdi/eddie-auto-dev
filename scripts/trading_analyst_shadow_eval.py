#!/usr/bin/env python3
"""Shadow evaluator do trading-analyst-candidate — SEM nunca executar ordem.

Consome (SÓ-LEITURA) as chamadas de LLM que a produção já logou em btc.llm_calls,
reenvia o MESMO prompt para o modelo candidato (trading-analyst-candidate) servido
na NAS, e grava a resposta do candidato em btc.llm_shadow_results. Isso permite
comparar candidato vs. produção sem colocar um centavo em risco: o candidato nunca
entra no caminho de decisão do agente.

O modo --report junta btc.llm_shadow_results com o resultado real dos trades (mesma
janela de PnL do dataset builder) e reporta concordância, divergência e correlação
com PnL — insumo para a decisão HUMANA de promover ou não o candidato.

Este script NÃO altera trading, NÃO troca modelo de produção e NÃO escreve em
nenhuma tabela além de btc.llm_shadow_results (que ele mesmo cria).

Uso:
  python3 scripts/trading_analyst_shadow_eval.py            # avalia chamadas novas
  python3 scripts/trading_analyst_shadow_eval.py --limit 200
  python3 scripts/trading_analyst_shadow_eval.py --report   # relatório comparativo
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))
from secrets_helper import get_database_url  # noqa: E402

SCHEMA = "btc"
OLLAMA_NAS_HOST = os.environ.get("OLLAMA_NAS_HOST", "http://192.168.15.4:11436")
CANDIDATE_MODEL = os.environ.get("FT_TARGET_MODEL", "trading-analyst-candidate")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("shadow-eval")


def _connect():
    # autocommit=True: writes são inserts independentes (convenção dos scripts de
    # trading; transação explícita fica só no training_db.py). SÓ-LEITURA no schema
    # exceto a própria tabela llm_shadow_results.
    conn = psycopg2.connect(get_database_url())
    conn.autocommit = True
    return conn


def ensure_shadow_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.llm_shadow_results (
                id SERIAL PRIMARY KEY,
                llm_call_id INTEGER NOT NULL REFERENCES {SCHEMA}.llm_calls(id),
                timestamp DOUBLE PRECISION NOT NULL,
                call_type TEXT NOT NULL,
                symbol TEXT NOT NULL,
                profile TEXT NOT NULL,
                candidate_model TEXT NOT NULL,
                candidate_response TEXT,
                candidate_json JSONB,
                latency_ms DOUBLE PRECISION,
                error TEXT,
                UNIQUE(llm_call_id, candidate_model)
            )
        """)
        cur.execute(
            f"CREATE INDEX IF NOT EXISTS idx_btc_llm_shadow_call "
            f"ON {SCHEMA}.llm_shadow_results(call_type, symbol, profile, timestamp DESC)"
        )


def fetch_pending(conn, limit: int) -> List[Dict[str, Any]]:
    """Chamadas de produção ainda não avaliadas para o candidato atual."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"""
            SELECT c.id, c.call_type, c.symbol, c.profile, c.prompt
            FROM {SCHEMA}.llm_calls c
            LEFT JOIN {SCHEMA}.llm_shadow_results s
                   ON s.llm_call_id = c.id AND s.candidate_model = %s
            WHERE s.id IS NULL
            ORDER BY c.timestamp ASC
            LIMIT %s
        """, (CANDIDATE_MODEL, limit))
        return [dict(r) for r in cur.fetchall()]


def ask_candidate(prompt: str, call_type: str, timeout: float = 120.0) -> Dict[str, Any]:
    """Reenvia o prompt de produção ao candidato na NAS. Só leitura de modelo."""
    # controls/window pedem JSON; plan é texto livre.
    body: Dict[str, Any] = {
        "model": CANDIDATE_MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.0, "num_ctx": 4096, "num_predict": 1024},
    }
    if call_type in ("controls", "window"):
        body["format"] = "json"
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_NAS_HOST}/api/generate", data=payload,
        headers={"Content-Type": "application/json"},
    )
    started = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    latency_ms = (time.time() - started) * 1000.0
    text = (data.get("response") or "").strip()
    parsed: Optional[dict] = None
    if call_type in ("controls", "window") and text:
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None
    return {"text": text, "json": parsed, "latency_ms": latency_ms}


def record_result(conn, call: Dict[str, Any], result: Optional[Dict[str, Any]],
                  error: Optional[str]) -> None:
    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO {SCHEMA}.llm_shadow_results (
                llm_call_id, timestamp, call_type, symbol, profile,
                candidate_model, candidate_response, candidate_json, latency_ms, error
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (llm_call_id, candidate_model) DO NOTHING
        """, (
            call["id"], time.time(), call["call_type"], call["symbol"], call["profile"],
            CANDIDATE_MODEL,
            (result or {}).get("text"),
            json.dumps((result or {}).get("json")) if (result or {}).get("json") else None,
            (result or {}).get("latency_ms"),
            error,
        ))


def run_shadow(limit: int) -> int:
    conn = _connect()
    try:
        ensure_shadow_table(conn)
        pending = fetch_pending(conn, limit)
        log.info("%d chamadas pendentes para o candidato %s", len(pending), CANDIDATE_MODEL)
        ok = err = 0
        for call in pending:
            try:
                result = ask_candidate(call["prompt"], call["call_type"])
                record_result(conn, call, result, None)
                ok += 1
            except Exception as e:
                record_result(conn, call, None, str(e)[:500])
                err += 1
                log.warning("Falha na chamada id=%s: %s", call["id"], e)
        log.info("Shadow concluído: %d ok, %d erros", ok, err)
        return 0
    finally:
        conn.close()


# ── Relatório (Fase 7) ───────────────────────────────────────────────────────────

def _pnl_after(conn, symbol: str, profile: str, start_ts: float,
               horizon_sec: float = 3600.0) -> float:
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT COALESCE(SUM(pnl), 0) FROM {SCHEMA}.trades
            WHERE symbol = %s AND profile = %s AND dry_run = FALSE
              AND pnl IS NOT NULL AND timestamp >= %s AND timestamp < %s
        """, (symbol, profile, start_ts, start_ts + horizon_sec))
        return float(cur.fetchone()[0])


def run_report() -> int:
    conn = _connect()
    try:
        ensure_shadow_table(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT s.*, c.response_json AS prod_json, c.response_text AS prod_text,
                       c.timestamp AS call_ts
                FROM {SCHEMA}.llm_shadow_results s
                JOIN {SCHEMA}.llm_calls c ON c.id = s.llm_call_id
                WHERE s.candidate_model = %s
                ORDER BY s.timestamp ASC
            """, (CANDIDATE_MODEL,))
            rows = [dict(r) for r in cur.fetchall()]

        if not rows:
            log.info("Sem resultados de shadow ainda. Rode o modo padrão primeiro.")
            return 0

        by_type: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            ct = r["call_type"]
            b = by_type.setdefault(ct, {
                "n": 0, "errors": 0, "agree": 0, "comparable": 0,
                "prod_pnl": 0.0, "cand_only_keys": 0,
            })
            b["n"] += 1
            if r.get("error"):
                b["errors"] += 1
                continue
            # PnL realizado após a chamada (contexto de resultado, comum a ambos).
            b["prod_pnl"] += _pnl_after(conn, r["symbol"], r["profile"], r["call_ts"])
            # Concordância (controls/window): mesma direção nos parâmetros principais.
            if ct in ("controls", "window"):
                prod = r.get("prod_json")
                cand = r.get("candidate_json")
                if isinstance(prod, str):
                    try: prod = json.loads(prod)
                    except Exception: prod = None
                if isinstance(cand, str):
                    try: cand = json.loads(cand)
                    except Exception: cand = None
                if isinstance(prod, dict) and isinstance(cand, dict):
                    b["comparable"] += 1
                    keys = set(prod) & set(cand)
                    close = sum(
                        1 for k in keys
                        if isinstance(prod[k], (int, float)) and isinstance(cand[k], (int, float))
                        and abs(float(prod[k]) - float(cand[k])) <= 0.15 * (abs(float(prod[k])) + 1e-9)
                    )
                    if keys and close / len(keys) >= 0.6:
                        b["agree"] += 1

        print("\n=== Shadow report: %s ===" % CANDIDATE_MODEL)
        for ct, b in sorted(by_type.items()):
            line = (f"[{ct}] amostras={b['n']} erros={b['errors']} "
                    f"pnl_realizado_pós_chamada={b['prod_pnl']:+.4f} USDT")
            if b["comparable"]:
                line += (f" | comparáveis={b['comparable']} "
                         f"concordância={b['agree']}/{b['comparable']} "
                         f"({100.0 * b['agree'] / b['comparable']:.0f}%)")
            print("  " + line)
        print("\nDecisão de promoção é HUMANA — este relatório é só insumo.\n")
        return 0
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Shadow evaluator do trading-analyst-candidate")
    parser.add_argument("--limit", type=int, default=200, help="Máx. de chamadas por execução")
    parser.add_argument("--report", action="store_true", help="Relatório comparativo (Fase 7)")
    args = parser.parse_args()
    return run_report() if args.report else run_shadow(args.limit)


if __name__ == "__main__":
    sys.exit(main())
