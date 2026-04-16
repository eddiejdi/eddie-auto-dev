#!/usr/bin/env python3
"""Consulta rápida de dados do Grafana/PostgreSQL para o frontend.

Uso:
  python3 tools/grafana_query.py news           # últimas notícias analisadas
  python3 tools/grafana_query.py trades         # trades recentes BTC-USDT
  python3 tools/grafana_query.py position       # posição aberta atual
  python3 tools/grafana_query.py pnl            # PnL por perfil
  python3 tools/grafana_query.py sentiment      # sentimento médio do mercado
  python3 tools/grafana_query.py panels         # lista painéis do dashboard
  python3 tools/grafana_query.py sql "SELECT …" # query SQL arbitrária

Variáveis de ambiente:
  GRAFANA_URL   — URL do Grafana     (padrão: http://localhost:3002)
  GRAFANA_USER  — Usuário admin      (padrão: admin)
  GRAFANA_PASS  — Senha admin
  DATABASE_URL  — postgres://…       (acesso direto ao PostgreSQL)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger("grafana_query")

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3002")
GRAFANA_USER = os.getenv("GRAFANA_USER", "admin")
GRAFANA_PASS = os.getenv("GRAFANA_PASS", "")
# Banco principal de trading (contém news_sentiment, trades, etc.)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:eddie_memory_2026@localhost:5433/btc_trading")
GRAFANA_DS_UID = os.getenv("GRAFANA_DS_UID", "btc-trading-pg")

# ---------------------------------------------------------------------------
# Queries pré-definidas — fáceis de estender
# ---------------------------------------------------------------------------

QUERIES: dict[str, str] = {
    "news": """
        SELECT
            TO_CHAR(timestamp AT TIME ZONE 'America/Sao_Paulo', 'DD/MM HH24:MI') AS "Hora",
            source AS "Fonte",
            LEFT(title, 80) AS "Título",
            CASE WHEN sentiment > 0.1 THEN 'BULLISH' WHEN sentiment < -0.1 THEN 'BEARISH' ELSE 'NEUTRAL' END AS "Sentimento",
            ROUND(sentiment::numeric, 2) AS "Score",
            ROUND(confidence::numeric, 2) AS "Confiança"
        FROM btc.news_sentiment
        WHERE coin = 'BTC'
        ORDER BY timestamp DESC
        LIMIT 15
    """,
    "trades": """
        SELECT
            TO_CHAR(created_at AT TIME ZONE 'America/Sao_Paulo', 'DD/MM HH24:MI:SS') AS "Hora",
            side AS "Lado",
            profile AS "Perfil",
            ROUND(price::numeric, 2) AS "Preço",
            ROUND(size::numeric, 6) AS "Size",
            ROUND(COALESCE(pnl, 0)::numeric, 4) AS "PnL",
            ROUND(COALESCE(pnl_pct, 0)::numeric, 2) AS "PnL%",
            dry_run AS "Dry"
        FROM btc.trades
        WHERE symbol = 'BTC-USDT'
        ORDER BY created_at DESC
        LIMIT 20
    """,
    "position": """
        SELECT
            symbol AS "Par",
            regime AS "Regime",
            ROUND(conservative_pct::numeric, 1) AS "Conservador%",
            ROUND(aggressive_pct::numeric, 1) AS "Agressivo%",
            reason AS "Motivo",
            TO_CHAR(created_at AT TIME ZONE 'America/Sao_Paulo', 'DD/MM HH24:MI:SS') AS "Atualizado"
        FROM btc.profile_allocations
        ORDER BY created_at DESC
        LIMIT 5
    """,
    "pnl": """
        SELECT
            profile AS "Perfil",
            COUNT(*) FILTER (WHERE side='sell') AS "Sells",
            ROUND(SUM(COALESCE(pnl, 0))::numeric, 4) AS "PnL Total",
            ROUND(SUM(COALESCE(pnl, 0)) FILTER (WHERE dry_run=false)::numeric, 4) AS "PnL Live",
            COUNT(*) FILTER (WHERE dry_run=false) AS "Live",
            COUNT(*) FILTER (WHERE dry_run=true) AS "Dry",
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE pnl > 0 AND side='sell') /
                NULLIF(COUNT(*) FILTER (WHERE side='sell' AND pnl IS NOT NULL), 0),
                1
            ) AS "Win Rate %"
        FROM btc.trades
        WHERE symbol = 'BTC-USDT'
        GROUP BY profile
        ORDER BY profile
    """,
    "sentiment": """
        SELECT
            coin AS "Moeda",
            ROUND(AVG(sentiment)::numeric, 3) AS "Sentimento Médio",
            ROUND(AVG(confidence)::numeric, 3) AS "Confiança Média",
            COUNT(*) FILTER (WHERE sentiment > 0.1) AS "Bullish",
            COUNT(*) FILTER (WHERE sentiment < -0.1) AS "Bearish",
            COUNT(*) FILTER (WHERE sentiment BETWEEN -0.1 AND 0.1) AS "Neutral",
            COUNT(*) AS "Total",
            TO_CHAR(MAX(timestamp) AT TIME ZONE 'America/Sao_Paulo', 'DD/MM HH24:MI') AS "Último"
        FROM btc.news_sentiment
        WHERE timestamp >= NOW() - INTERVAL '24 hours'
        GROUP BY coin
        ORDER BY coin
    """,
}


# ---------------------------------------------------------------------------
# Execução de queries
# ---------------------------------------------------------------------------


def _run_via_psycopg2(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Executa SQL direto no PostgreSQL via psycopg2.

    Args:
        sql: Query SQL a executar.
        params: Parâmetros posicionais (%s).

    Returns:
        Lista de dicionários com os resultados.
    """
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        log.error("psycopg2 não instalado. Instale com: pip install psycopg2-binary")
        sys.exit(1)

    if not DATABASE_URL:
        log.error("DATABASE_URL não configurada.")
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SET search_path TO btc, public")
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _run_via_grafana_api(sql: str, ds_uid: str = GRAFANA_DS_UID) -> list[dict[str, Any]]:
    """Executa SQL via API de datasource do Grafana.

    Args:
        sql: Query SQL a executar.
        ds_uid: UID do datasource PostgreSQL no Grafana.

    Returns:
        Lista de dicionários com os resultados.
    """
    if not GRAFANA_PASS:
        log.error("GRAFANA_PASS não configurado.")
        sys.exit(1)

    import base64

    token = base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASS}".encode()).decode()
    payload = {
        "queries": [
            {
                "refId": "A",
                "datasourceId": ds_uid,
                "rawSql": sql,
                "format": "table",
            }
        ],
        "from": "now-24h",
        "to": "now",
    }
    url = f"{GRAFANA_URL.rstrip('/')}/api/ds/query"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        log.error("Grafana API erro %d: %s", exc.code, exc.read().decode()[:200])
        sys.exit(1)
    except urllib.error.URLError as exc:
        log.error("Não conectou ao Grafana: %s", exc.reason)
        sys.exit(1)

    # Transforma resposta frame → lista de dicts
    results: list[dict[str, Any]] = []
    for frame in data.get("results", {}).values():
        for df in frame.get("frames", []):
            schema = df.get("schema", {})
            fdata = df.get("data", {})
            fields = [f.get("name", f"col{i}") for i, f in enumerate(schema.get("fields", []))]
            values = fdata.get("values", [])
            if not fields or not values:
                continue
            for i in range(len(values[0])):
                row = {fields[j]: (values[j][i] if j < len(values) else None) for j in range(len(fields))}
                results.append(row)
    return results


def run_query(sql: str) -> list[dict[str, Any]]:
    """Executa query SQL usando a melhor estratégia disponível.

    Tenta psycopg2 primeiro (mais rápido), fallback para API do Grafana.

    Args:
        sql: Query SQL.

    Returns:
        Lista de dicionários com os resultados.
    """
    if DATABASE_URL:
        return _run_via_psycopg2(sql)
    return _run_via_grafana_api(sql)


# ---------------------------------------------------------------------------
# Formatação de saída
# ---------------------------------------------------------------------------


def _print_table(rows: list[dict[str, Any]]) -> None:
    """Imprime lista de dicionários como tabela ASCII alinhada."""
    if not rows:
        print("(sem resultados)")
        return

    cols = list(rows[0].keys())
    widths = {c: max(len(str(c)), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}

    sep = "+-" + "-+-".join("-" * widths[c] for c in cols) + "-+"
    header = "| " + " | ".join(str(c).ljust(widths[c]) for c in cols) + " |"
    print(sep)
    print(header)
    print(sep)
    for row in rows:
        line = "| " + " | ".join(str(row.get(c, "")).ljust(widths[c]) for c in cols) + " |"
        print(line)
    print(sep)
    print(f"({len(rows)} linhas)")


def cmd_panels() -> None:
    """Lista painéis do dashboard BTC Trading Monitor."""
    import base64

    if not GRAFANA_PASS:
        log.error("GRAFANA_PASS não configurado.")
        sys.exit(1)
    token = base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASS}".encode()).decode()
    url = f"{GRAFANA_URL.rstrip('/')}/api/dashboards/uid/btc-trading-monitor"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    panels = data.get("dashboard", {}).get("panels", [])
    print(f"{'ID':<6} {'Tipo':<10} Título")
    print("─" * 70)
    for p in panels:
        print(f"{p.get('id',''):<6} {p.get('type',''):<10} {p.get('title','')}")
    print(f"\nTotal: {len(panels)} painéis")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Consulta rápida de dados Grafana/PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--url", default=GRAFANA_URL, help="URL do Grafana")
    parser.add_argument("--user", default=GRAFANA_USER, help="Usuário Grafana")
    parser.add_argument("--pass", dest="password", default=GRAFANA_PASS, help="Senha Grafana")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Saída em JSON")
    parser.add_argument("--db", default=DATABASE_URL, help="DATABASE_URL para acesso direto ao PostgreSQL")

    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("news", help="Últimas notícias analisadas (BTC)")
    sub.add_parser("trades", help="Trades recentes BTC-USDT")
    sub.add_parser("position", help="Posição aberta atual (live)")
    sub.add_parser("pnl", help="PnL por perfil")
    sub.add_parser("sentiment", help="Sentimento médio por moeda (últimas 24h)")
    sub.add_parser("panels", help="Lista painéis do dashboard BTC Trading Monitor")

    p_sql = sub.add_parser("sql", help="Query SQL arbitrária")
    p_sql.add_argument("query", help="SQL a executar")

    return parser


def main() -> None:
    """Ponto de entrada principal."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    parser = _build_parser()
    args = parser.parse_args()

    global GRAFANA_URL, GRAFANA_USER, GRAFANA_PASS, DATABASE_URL
    GRAFANA_URL = args.url
    GRAFANA_USER = args.user
    GRAFANA_PASS = args.password
    if args.db:
        DATABASE_URL = args.db

    if args.cmd == "panels":
        cmd_panels()
        return

    sql = QUERIES.get(args.cmd) if args.cmd != "sql" else args.query
    rows = run_query(sql)

    if args.as_json:
        print(json.dumps(rows, indent=2, ensure_ascii=False, default=str))
    else:
        _print_table(rows)


if __name__ == "__main__":
    main()
