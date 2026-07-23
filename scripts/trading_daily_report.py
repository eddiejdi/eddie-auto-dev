#!/usr/bin/env python3
"""Relatório diário de trading — multi-símbolo (BTC + ETH + SOL + DOGE) com análise Ollama.

Coleta dados do PostgreSQL btc_trading para cada símbolo operado, monta um
relatório determinístico e consistente para o Telegram e usa o modelo
trading-analyst (Ollama GPU0) apenas para uma análise curta de rodapé.
O resultado é salvo em btc.daily_reports e enviado no Telegram.

Uso:
    python3 scripts/trading_daily_report.py             # Executa e envia
    python3 scripts/trading_daily_report.py --dry-run   # Apenas imprime, não salva nem envia
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import date, datetime, timezone

import psycopg2
import psycopg2.extras

# Garantir que o projeto está no sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.ollama_mcp_bridge import OllamaMCPBridge

logger = logging.getLogger("trading.daily_report")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

OPERATIONAL_PROFILES = ("conservative", "aggressive", "shadow")

# Símbolos reportados. A ordem define a ordem das seções no relatório.
SYMBOLS = ("BTC-USDT", "ETH-USDT", "SOL-USDT", "DOGE-USDT")

# Perfis que possuem serviço systemd próprio (shadow é virtual, não tem serviço).
SERVICE_PROFILES = ("aggressive", "conservative")

# Ícone por ativo para o cabeçalho de cada seção.
ASSET_ICONS = {"BTC": "₿", "ETH": "Ξ", "SOL": "◎", "DOGE": "Ð"}

# ── Configuração ─────────────────────────────────────────────────────────────

# DATABASE_URL é injetada pelo systemd via EnvironmentFile=/etc/default/eddie-common
# (fonte canônica). O fallback é montado a partir de env — nunca com segredo
# embutido no código-fonte.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    _db_host = os.getenv("BTC_TRADING_DB_HOST", "192.168.15.2")
    _db_port = os.getenv("BTC_TRADING_DB_PORT", "5433")
    _db_user = os.getenv("BTC_TRADING_DB_USER", "postgres")
    _db_pass = os.getenv("BTC_TRADING_DB_PASSWORD", "")
    _db_name = os.getenv("BTC_TRADING_DB_NAME", "btc_trading")
    _auth = f"{_db_user}:{_db_pass}@" if _db_pass else f"{_db_user}@"
    DATABASE_URL = f"postgresql://{_auth}{_db_host}:{_db_port}/{_db_name}"


# ── PostgreSQL ────────────────────────────────────────────────────────────────

def _get_conn() -> psycopg2.extensions.connection:
    """Obtém conexão PostgreSQL com autocommit."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def _collect_symbol(cur: psycopg2.extensions.cursor, symbol: str) -> dict:
    """Coleta preço, trades 24h, histórico e posições abertas de um símbolo."""
    # Preço atual
    cur.execute(
        """
        SELECT ROUND(price::numeric, 2) AS price
        FROM btc.market_states
        WHERE symbol = %s
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (symbol,),
    )
    row = cur.fetchone()
    current_price = float(row["price"]) if row else 0.0

    # Trades últimas 24h — resumo por perfil
    cur.execute(
        """
        SELECT
            profile,
            COUNT(CASE WHEN side='buy' THEN 1 END)  AS buys,
            COUNT(CASE WHEN side='sell' THEN 1 END) AS sells,
            COUNT(CASE WHEN side='sell' AND pnl > 0 THEN 1 END) AS wins,
            COUNT(CASE WHEN side='sell' AND pnl < 0 THEN 1 END) AS losses,
            ROUND(SUM(CASE WHEN side='sell' THEN COALESCE(pnl,0) ELSE 0 END)::numeric, 4) AS pnl_24h
        FROM btc.trades
        WHERE dry_run = false
          AND symbol = %s
          AND profile IN ('conservative', 'aggressive', 'shadow')
          AND to_timestamp(timestamp) >= NOW() - INTERVAL '24 hours'
        GROUP BY profile
        ORDER BY profile
        """,
        (symbol,),
    )
    trades_24h = [dict(r) for r in cur.fetchall()]

    # PnL acumulado histórico
    cur.execute(
        """
        SELECT
            profile,
            COUNT(CASE WHEN side='sell' THEN 1 END) AS total_sells,
            COUNT(CASE WHEN side='sell' AND pnl > 0 THEN 1 END) AS total_wins,
            ROUND(SUM(CASE WHEN side='sell' THEN COALESCE(pnl,0) ELSE 0 END)::numeric, 4) AS pnl_total
        FROM btc.trades
        WHERE dry_run = false AND symbol = %s
          AND profile IN ('conservative', 'aggressive', 'shadow')
        GROUP BY profile
        ORDER BY profile
        """,
        (symbol,),
    )
    history = [dict(r) for r in cur.fetchall()]

    # Posições abertas por perfil, reconstruídas a partir do último SELL de cada
    # perfil. Isso evita reportar BUY antigo como posição aberta depois de a
    # estratégia já ter zerado o perfil.
    cur.execute(
        """
        WITH profiles AS (
            SELECT DISTINCT profile
            FROM btc.trades
            WHERE symbol = %s
              AND dry_run = false
              AND profile IN ('conservative', 'aggressive', 'shadow')
              AND profile IS NOT NULL
        ),
        latest_sell AS (
            SELECT profile, MAX(timestamp) AS last_sell_ts
            FROM btc.trades
            WHERE dry_run = false
              AND symbol = %s
              AND profile IN ('conservative', 'aggressive', 'shadow')
              AND side = 'sell'
            GROUP BY profile
        ),
        open_buys AS (
            SELECT t.*
            FROM btc.trades t
            LEFT JOIN latest_sell s ON s.profile = t.profile
            WHERE t.dry_run = false
              AND t.symbol = %s
              AND t.profile IN ('conservative', 'aggressive', 'shadow')
              AND t.side = 'buy'
              AND COALESCE(t.metadata->>'source', '') != 'external_deposit'
              AND t.timestamp > COALESCE(s.last_sell_ts, 0)
        )
        SELECT
            p.profile,
            COALESCE(COUNT(o.*), 0) AS n_entries,
            COALESCE(ROUND(SUM(o.size)::numeric, 8), 0) AS total_qty,
            COALESCE(
                ROUND((SUM(COALESCE(NULLIF(o.funds, 0), o.size * o.price)) / NULLIF(SUM(o.size), 0))::numeric, 2),
                0
            ) AS avg_entry
        FROM profiles p
        LEFT JOIN open_buys o ON o.profile = p.profile
        GROUP BY p.profile
        HAVING COALESCE(SUM(o.size), 0) > 0
        ORDER BY p.profile
        """,
        (symbol, symbol, symbol),
    )
    open_pos = [dict(r) for r in cur.fetchall()]

    # Agregados 24h do símbolo
    realized_24h = sum(float(t["pnl_24h"]) for t in trades_24h)
    n_trades_24h = sum(int(t["buys"]) + int(t["sells"]) for t in trades_24h)
    unrealized = 0.0
    for p in open_pos:
        avg = float(p["avg_entry"])
        qty = float(p["total_qty"])
        unrealized += (current_price - avg) * qty

    return {
        "symbol": symbol,
        "current_price": current_price,
        "trades_24h": trades_24h,
        "history": history,
        "open_positions": open_pos,
        "realized_24h": round(realized_24h, 4),
        "unrealized": round(unrealized, 4),
        "n_trades_24h": n_trades_24h,
    }


def collect_context_data() -> dict:
    """Coleta dados de contexto do banco para todos os símbolos operados.

    Returns:
        Dicionário com métricas por símbolo, balanço de contas e agregados.
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            symbols = {sym: _collect_symbol(cur, sym) for sym in SYMBOLS}

            # Balanço de contas KuCoin (main/trade) do último snapshot — global,
            # não é por símbolo.
            cur.execute("""
                WITH latest AS (
                    SELECT MAX(synced_at) AS s FROM btc.exchange_balance_snapshots
                )
                SELECT account_type, currency, balance, price_usdt, synced_at
                FROM btc.exchange_balance_snapshots, latest
                WHERE synced_at = latest.s
            """)
            snapshot_rows = [dict(r) for r in cur.fetchall()]
            balance = _build_balance_summary(snapshot_rows)

        total_trades_24h = sum(s["n_trades_24h"] for s in symbols.values())
        total_pnl_24h = sum(s["realized_24h"] for s in symbols.values())
        total_unrealized = sum(s["unrealized"] for s in symbols.values())

        return {
            "balance": balance,
            "symbols": symbols,
            "total_trades_24h": total_trades_24h,
            "total_pnl_24h": round(total_pnl_24h, 4),
            "total_unrealized": round(total_unrealized, 4),
            "report_date": date.today().isoformat(),
        }
    finally:
        conn.close()


def _build_balance_summary(rows: list[dict]) -> dict:
    """Resume o último snapshot de saldos em totais por conta e por moeda.

    Subcontas KuCoin não são sincronizadas — apenas main/trade da conta master.
    """
    def to_usdt(row: dict) -> float:
        price = row.get("price_usdt")
        if price is None:
            price = 1.0 if row["currency"] == "USDT" else 0.0
        return float(row["balance"]) * float(price)

    per_account: dict[str, float] = {}
    per_currency: dict[str, dict] = {}
    brl_rate = 0.0
    synced_at = None
    for r in rows:
        per_account[r["account_type"]] = per_account.get(r["account_type"], 0.0) + to_usdt(r)
        cur_entry = per_currency.setdefault(r["currency"], {"qty": 0.0, "usdt": 0.0})
        cur_entry["qty"] += float(r["balance"])
        cur_entry["usdt"] += to_usdt(r)
        if r["currency"] == "BRL" and r.get("price_usdt"):
            brl_rate = float(r["price_usdt"])
        synced_at = r.get("synced_at") or synced_at

    total_usdt = sum(per_account.values())
    return {
        "brl_rate": brl_rate or None,
        "per_account": {k: round(v, 2) for k, v in sorted(per_account.items())},
        "per_account_brl": {
            k: round(v / brl_rate, 2) for k, v in sorted(per_account.items())
        } if brl_rate else {},
        "per_currency": {
            k: {"qty": round(v["qty"], 8), "usdt": round(v["usdt"], 2)}
            for k, v in sorted(per_currency.items())
            if v["usdt"] >= 0.01
        },
        "total_usdt": round(total_usdt, 2),
        "total_brl": round(total_usdt / brl_rate, 2) if brl_rate else None,
        "synced_at": synced_at.isoformat() if synced_at else None,
    }


def format_balance_block(balance: dict) -> str:
    """Formata o balanço de contas em texto para o relatório e o prompt."""
    if not balance or not balance.get("per_account"):
        return "  Snapshot de saldos indisponível"
    lines = []
    per_brl = balance.get("per_account_brl") or {}
    for account, usdt in balance["per_account"].items():
        brl = per_brl.get(account)
        brl_txt = f" (≈ R$ {brl:,.2f})" if brl is not None else ""
        lines.append(f"  • {account}: ${usdt:,.2f} USDT{brl_txt}")
    for currency, v in balance.get("per_currency", {}).items():
        lines.append(f"  • {currency}: {v['qty']:g} (≈ ${v['usdt']:,.2f} USDT)")
    total_line = f"  • TOTAL: ${balance['total_usdt']:,.2f} USDT"
    if balance.get("total_brl"):
        total_line += f" (≈ R$ {balance['total_brl']:,.2f})"
    lines.append(total_line)
    return "\n".join(lines)


def save_report(
    report_text: str,
    pnl_24h: float,
    profiles: list[str],
    metadata: dict,
    model_used: str,
) -> None:
    """Salva relatório em btc.daily_reports (upsert por data)."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO btc.daily_reports
                    (report_date, report_text, pnl_24h, profiles, metadata, model_used)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (report_date)
                DO UPDATE SET
                    report_text = EXCLUDED.report_text,
                    pnl_24h     = EXCLUDED.pnl_24h,
                    profiles    = EXCLUDED.profiles,
                    metadata    = EXCLUDED.metadata,
                    model_used  = EXCLUDED.model_used,
                    created_at  = NOW()
            """, (
                date.today(),
                report_text,
                pnl_24h,
                profiles,
                json.dumps(metadata, default=str),
                model_used,
            ))
        logger.info("Relatório salvo em btc.daily_reports para %s", date.today())
    finally:
        conn.close()


# ── Telegram ──────────────────────────────────────────────────────────────────

async def send_telegram_report(text: str) -> None:
    """Envia relatório via Telegram."""
    try:
        from telegram import Bot

        # Tentar env var primeiro, depois secrets agent
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not token:
            try:
                from tools.secrets_loader import get_telegram_token
                token = get_telegram_token()
            except Exception:
                pass
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN não configurado")

        chat_id = os.getenv("TELEGRAM_CHAT_ID", "948686300")
        # Aumentar timeouts para compensar Happy Eyeballs IPv6→IPv4 (~10s no homelab)
        from telegram.request import HTTPXRequest
        request = HTTPXRequest(
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=20.0,
            pool_timeout=30.0,
        )
        bot = Bot(token=token, request=request)
        # Dividir se muito longo (Telegram limit: 4096 chars)
        max_len = 4000
        chunks = [text[i : i + max_len] for i in range(0, len(text), max_len)]
        for chunk in chunks:
            try:
                await bot.send_message(chat_id=chat_id, text=chunk, parse_mode="Markdown")
            except Exception:
                # Fallback sem parse_mode (Markdown inválido no relatório)
                await bot.send_message(chat_id=chat_id, text=chunk)
        logger.info("Relatório diário de trading enviado no Telegram")
    except ImportError:
        logger.warning("python-telegram-bot não instalado — pulando envio Telegram")
    except Exception:
        logger.exception("Falha ao enviar relatório no Telegram")


# ── Coleta de dados adicionais via SSH ───────────────────────────────────────

def collect_live_data() -> dict:
    """Coleta status dos agents systemd de todos os símbolos via SSH."""
    import subprocess

    HOMELAB = "homelab@192.168.15.2"

    # Serviços derivados de SYMBOLS × SERVICE_PROFILES (ex.: BTC_USDT_aggressive).
    services = [
        f"{sym.replace('-', '_')}_{prof}"
        for sym in SYMBOLS
        for prof in SERVICE_PROFILES
    ]

    agents_status = {}
    for svc in services:
        try:
            r = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", HOMELAB,
                 f"systemctl is-active crypto-agent@{svc} 2>/dev/null"],
                capture_output=True, text=True, timeout=8,
            )
            agents_status[svc] = "✅ ACTIVE" if r.returncode == 0 else "❌ INACTIVE"
        except Exception:
            agents_status[svc] = "⚠️ ERRO"

    return {"agents_status": agents_status}


# ── Análise via Ollama (rodapé curto) ─────────────────────────────────────────

ANALYSIS_SYSTEM_PROMPT = """Você é o Trading Analyst do sistema Eddie Auto-Dev.
Com base nos dados fornecidos, escreva uma análise CURTA do dia de trading.

Regras:
- Máximo 4 linhas, em PT-BR, sem tabelas nem listas longas
- Leia o cenário: tendência do PnL, posições underwater, agentes parados
- Se houver posições no negativo, explique que o guardrail de "só vender no lucro"
  segura a venda até o preço voltar acima da entrada — isso é esperado, não é falha
- Termine com um alerta acionável somente se houver algo relevante
- NUNCA invente dados ou métricas que não foram fornecidas"""


def _analysis_digest(context: dict, live_data: dict) -> str:
    """Monta um resumo compacto dos dados para o prompt de análise."""
    parts = [f"Data: {context['report_date']}"]
    for symbol in SYMBOLS:
        s = context["symbols"].get(symbol)
        if not s:
            continue
        parts.append(
            f"\n{symbol}: preço ${s['current_price']:,.2f} | "
            f"PnL realizado 24h ${s['realized_24h']:+.4f} | "
            f"PnL não realizado ${s['unrealized']:+.4f} | "
            f"{s['n_trades_24h']} trades"
        )
        for p in s["open_positions"]:
            avg = float(p["avg_entry"])
            pct = round((s["current_price"] / avg - 1) * 100, 2) if avg > 0 else 0
            parts.append(
                f"  - {p['profile']}: {p['n_entries']} lotes, avg ${avg:,.2f}, {pct:+.2f}%"
            )
    stopped = [k for k, v in live_data.get("agents_status", {}).items() if "ACTIVE" not in v]
    if stopped:
        parts.append("\nAgentes parados: " + ", ".join(stopped))
    else:
        parts.append("\nTodos os agentes ativos.")
    return "\n".join(parts)


def generate_analysis(context: dict, live_data: dict, model: str) -> str:
    """Gera a análise textual curta via Ollama. Retorna '' em caso de falha."""
    user_msg = (
        "Dados do dia de trading:\n\n"
        + _analysis_digest(context, live_data)
        + "\n\nEscreva a análise curta (máx 4 linhas)."
    )
    # O coordinator (11437) não serve /api/generate; a análise usa o Ollama
    # direto (GPU0/11434). Independente do OLLAMA_HOST do serviço.
    host = os.getenv(
        "OLLAMA_GENERATE_HOST",
        "http://192.168.15.2:11434",
    )
    try:
        with OllamaMCPBridge(model=model, host=host, num_predict=1024) as bridge:
            analysis = bridge.run_with_tools(
                system=ANALYSIS_SYSTEM_PROMPT,
                user_msg=user_msg,
                tools=[],
            )
    except Exception:
        logger.exception("Falha ao gerar análise via Ollama")
        return ""

    import re as _re
    analysis = _re.sub(r"<think>.*?</think>", "", analysis or "", flags=_re.DOTALL)
    return analysis.strip()


# ── Montagem do relatório ─────────────────────────────────────────────────────

def _fmt_price(symbol: str, value: float) -> str:
    """Formata preço com casas decimais adequadas ao ativo (BTC/ETH: 2 casas)."""
    return f"${value:,.2f}"


def build_report(context: dict, live_data: dict, analysis: str = "") -> str:
    """Monta o relatório determinístico multi-símbolo para o Telegram."""
    today = context["report_date"]
    lines = [f"📊 *Relatório Diário de Trading* — {today}", ""]

    for symbol in SYMBOLS:
        s = context["symbols"].get(symbol)
        if not s:
            continue
        asset = symbol.split("-")[0]
        icon = ASSET_ICONS.get(asset, "•")
        price = s["current_price"]

        buys = sum(int(t["buys"]) for t in s["trades_24h"])
        sells = sum(int(t["sells"]) for t in s["trades_24h"])
        wins = sum(int(t["wins"]) for t in s["trades_24h"])
        losses = sum(int(t["losses"]) for t in s["trades_24h"])

        lines.append("━━━━━━━━━━━━━━━━")
        lines.append(f"{icon} *{symbol}* · {_fmt_price(symbol, price)}")
        lines.append(
            f"📈 PnL 24h: ${s['realized_24h']:+.4f}  ·  "
            f"{buys + sells} trades ({buys}⬆ {sells}⬇ · {wins}🟢/{losses}🔴)"
        )

        if s["open_positions"]:
            lines.append(f"📦 Posições abertas · não realizado ${s['unrealized']:+.4f}")
            for p in s["open_positions"]:
                avg = float(p["avg_entry"])
                qty = float(p["total_qty"])
                unreal = round((price - avg) * qty, 4)
                pct = round((price / avg - 1) * 100, 2) if avg > 0 else 0
                mark = "🟢" if unreal >= 0 else "🔴"
                lines.append(
                    f"  • {p['profile']}: {p['n_entries']} lotes · "
                    f"avg {_fmt_price(symbol, avg)} · {mark} ${unreal:+.4f} ({pct:+.2f}%)"
                )
        else:
            lines.append("📦 Sem posições abertas")
        lines.append("")

    # Consolidado
    lines.append("━━━━━━━━━━━━━━━━")
    total_pnl = context["total_pnl_24h"]
    trophy = "🏆" if total_pnl > 0 else ("⚠️" if total_pnl < 0 else "➖")
    lines.append(f"{trophy} *Consolidado 24h*")
    lines.append(
        f"  • PnL realizado: ${total_pnl:+.4f}  ·  "
        f"não realizado: ${context['total_unrealized']:+.4f}"
    )
    lines.append(f"  • Execuções: {context['total_trades_24h']}")
    lines.append("")

    # Alertas
    lines.append("🚨 *Alertas*")
    alerts = []
    stopped = [k for k, v in live_data.get("agents_status", {}).items() if "ACTIVE" not in v]
    if stopped:
        pretty = ", ".join(sv.replace("_", " ") for sv in stopped)
        alerts.append(f"  • ❌ Agente(s) parado(s): {pretty}")
    for symbol in SYMBOLS:
        s = context["symbols"].get(symbol) or {}
        price = s.get("current_price", 0.0)
        for p in s.get("open_positions", []):
            avg = float(p["avg_entry"])
            pct = (price / avg - 1) * 100 if avg > 0 else 0
            if pct <= -5:
                alerts.append(
                    f"  • 🔻 {symbol} {p['profile']} em {pct:+.2f}% (> -5%)"
                )
    if alerts:
        lines.extend(alerts)
    else:
        lines.append("  • ✅ Nenhum agente parado · nenhuma perda > -5%")
    lines.append("")

    # Balanço
    lines.append("💰 *Balanço de Contas*")
    lines.append(format_balance_block(context.get("balance") or {}))
    if context.get("balance", {}).get("synced_at"):
        lines.append(f"  _snapshot: {context['balance']['synced_at']}_")
    lines.append("")

    # Análise (opcional, gerada pelo LLM)
    if analysis:
        lines.append("📝 *Análise*")
        lines.append(analysis)

    return "\n".join(lines).rstrip()


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    """Entrypoint CLI."""
    parser = argparse.ArgumentParser(description="Trading Daily Report — Eddie Auto-Dev")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas imprime o relatório, não salva no banco nem envia Telegram",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OLLAMA_TRADING_MODEL", "trading-analyst:latest"),
        help="Modelo Ollama a usar (default: trading-analyst:latest)",
    )
    parser.add_argument(
        "--no-analysis",
        action="store_true",
        help="Não gerar a análise textual via Ollama (apenas o relatório determinístico)",
    )
    args = parser.parse_args()

    logger.info("Iniciando relatório diário de trading (dry_run=%s, model=%s)", args.dry_run, args.model)

    # 1. Coletar contexto do banco — falha hard (nunca enviar relatório zerado)
    try:
        context = collect_context_data()
        logger.info(
            "Contexto coletado: símbolos=%s, trades_24h=%d, pnl_24h=$%s",
            ",".join(context["symbols"].keys()),
            context["total_trades_24h"],
            context["total_pnl_24h"],
        )
    except Exception:
        logger.exception(
            "Falha ao coletar contexto do PostgreSQL — abortando sem enviar "
            "Telegram nem gravar relatório (evita zeros enganosos)"
        )
        sys.exit(1)

    if not context.get("symbols"):
        logger.error(
            "Contexto sem símbolos — abortando. Verifique DATABASE_URL e btc.trades."
        )
        sys.exit(1)

    # 2. Coletar dados live (status agents)
    try:
        live_data = collect_live_data()
    except Exception:
        logger.exception("Falha ao coletar dados live — usando valores padrão")
        live_data = {"agents_status": {}}

    # 3. Gerar análise curta via Ollama (opcional)
    analysis = ""
    if not args.no_analysis:
        analysis = generate_analysis(context, live_data, model=args.model)

    # 4. Montar relatório determinístico
    report_text = build_report(context, live_data, analysis)

    # Exibir sempre
    print("\n" + "=" * 60)
    print(report_text)
    print("=" * 60 + "\n")

    if args.dry_run:
        logger.info("--dry-run: relatório não salvo nem enviado")
        return

    # 5. Salvar no banco
    profiles = sorted({
        r["profile"]
        for s in context["symbols"].values()
        for rows in (s["trades_24h"], s["open_positions"])
        for r in rows
        if r.get("profile")
    })
    metadata = {
        "symbols": {
            sym: {
                "current_price": s["current_price"],
                "realized_24h": s["realized_24h"],
                "unrealized": s["unrealized"],
                "n_trades_24h": s["n_trades_24h"],
                "open_positions": s["open_positions"],
            }
            for sym, s in context["symbols"].items()
        },
        "total_trades_24h": context["total_trades_24h"],
        "total_unrealized": context["total_unrealized"],
        "balance": context.get("balance"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        save_report(
            report_text=report_text,
            pnl_24h=context["total_pnl_24h"],
            profiles=profiles or ["conservative", "aggressive"],
            metadata=metadata,
            model_used=(args.model if analysis else "deterministic"),
        )
    except Exception:
        logger.exception("Falha ao salvar relatório no banco — abortando envio Telegram")
        sys.exit(1)

    # 6. Enviar Telegram
    asyncio.run(send_telegram_report(report_text))


if __name__ == "__main__":
    main()
