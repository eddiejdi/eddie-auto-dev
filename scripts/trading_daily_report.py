#!/usr/bin/env python3
"""Relatório diário de trading — Ollama MCP Orchestration.

Coleta dados do PostgreSQL btc_trading, orquestra análise via Ollama (trading-analyst GPU0)
com MCP tools ativas, salva resultado em btc.daily_reports e envia no Telegram.

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

# ── Configuração ─────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/btc_trading",
)


# ── PostgreSQL ────────────────────────────────────────────────────────────────

def _get_conn() -> psycopg2.extensions.connection:
    """Obtém conexão PostgreSQL com autocommit."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def collect_context_data() -> dict:
    """Coleta dados de contexto do banco para alimentar o prompt do LLM.

    Returns:
        Dicionário com métricas pré-coletadas para o prompt inicial.
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Preço atual
            cur.execute("""
                SELECT ROUND(price::numeric, 2) AS price
                FROM btc.market_states
                WHERE symbol = 'BTC-USDT'
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            current_price = float(row["price"]) if row else 0.0

            # Trades últimas 24h — resumo por perfil
            cur.execute("""
                SELECT
                    profile,
                    COUNT(CASE WHEN side='buy' THEN 1 END)  AS buys,
                    COUNT(CASE WHEN side='sell' THEN 1 END) AS sells,
                    COUNT(CASE WHEN side='sell' AND pnl > 0 THEN 1 END) AS wins,
                    COUNT(CASE WHEN side='sell' AND pnl < 0 THEN 1 END) AS losses,
                    ROUND(SUM(CASE WHEN side='sell' THEN COALESCE(pnl,0) ELSE 0 END)::numeric, 4) AS pnl_24h
                FROM btc.trades
                WHERE dry_run = false
                  AND symbol = 'BTC-USDT'
                  AND to_timestamp(timestamp) >= NOW() - INTERVAL '24 hours'
                GROUP BY profile
                ORDER BY profile
            """)
            trades_24h = [dict(r) for r in cur.fetchall()]

            # PnL acumulado histórico
            cur.execute("""
                SELECT
                    profile,
                    COUNT(CASE WHEN side='sell' THEN 1 END) AS total_sells,
                    COUNT(CASE WHEN side='sell' AND pnl > 0 THEN 1 END) AS total_wins,
                    ROUND(SUM(CASE WHEN side='sell' THEN COALESCE(pnl,0) ELSE 0 END)::numeric, 4) AS pnl_total
                FROM btc.trades
                WHERE dry_run = false AND symbol = 'BTC-USDT'
                GROUP BY profile
                ORDER BY profile
            """)
            history = [dict(r) for r in cur.fetchall()]

            # Posições abertas (buy sem sell emparelhado — aproximação por perfil)
            cur.execute("""
                SELECT
                    profile,
                    COUNT(*) AS n_entries,
                    ROUND(SUM(size)::numeric, 8) AS total_btc,
                    ROUND(AVG(price)::numeric, 2) AS avg_entry
                FROM btc.trades
                WHERE dry_run = false
                  AND symbol = 'BTC-USDT'
                  AND side = 'buy'
                  AND to_timestamp(timestamp) >= NOW() - INTERVAL '30 days'
                GROUP BY profile
                ORDER BY profile
            """)
            open_pos = [dict(r) for r in cur.fetchall()]

            # Total de trades hoje
            total_24h = sum(r["buys"] + r["sells"] for r in trades_24h)
            total_pnl_24h = sum(float(r["pnl_24h"]) for r in trades_24h)

            return {
                "current_price": current_price,
                "trades_24h": trades_24h,
                "history": history,
                "open_positions": open_pos,
                "total_trades_24h": total_24h,
                "total_pnl_24h": round(total_pnl_24h, 4),
                "report_date": date.today().isoformat(),
            }
    finally:
        conn.close()


def save_report(
    report_text: str,
    pnl_24h: float,
    profiles: list[str],
    metadata: dict,
    model_used: str,
) -> None:
    """Salva relatório em btc.daily_reports (upsert por data).

    Args:
        report_text: Texto do relatório gerado pelo LLM.
        pnl_24h: PnL realizado nas últimas 24h (soma de todos os perfis).
        profiles: Lista de perfis analisados.
        metadata: Metadados adicionais (preço, n_trades, etc.).
        model_used: Nome do modelo Ollama utilizado.
    """
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
                json.dumps(metadata),
                model_used,
            ))
        logger.info("Relatório salvo em btc.daily_reports para %s", date.today())
    finally:
        conn.close()


# ── Telegram ──────────────────────────────────────────────────────────────────

async def send_telegram_report(text: str) -> None:
    """Envia relatório via Telegram.

    Args:
        text: Texto do relatório (suporta Markdown do Telegram).
    """
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
    """Coleta saldo KuCoin e status dos agents via SSH.

    Returns:
        Dicionário com kucoin_balance e agent_status.
    """
    import subprocess

    HOMELAB = "homelab@192.168.15.2"
    AGENT_PATH = "/apps/crypto-trader/trading/btc_trading_agent"

    # Saldo KuCoin
    kucoin_balance = "INDISPONÍVEL"
    try:
        py_cmd = (
            f"cd {AGENT_PATH} && "
            "python3 -c \""
            "import sys, os; sys.path.insert(0, os.getcwd()); "
            "from dotenv import load_dotenv; load_dotenv(); "
            "import kucoin_api as api; "
            "b = api.get_balances('trade'); "
            "relevant = [x for x in b if x['currency'] in ['USDT','BTC','BRL']]; "
            "[print(f\\\"{x['currency']}: {x['available']}\\\") for x in relevant]"
            "\""
        )
        r = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", HOMELAB, py_cmd],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            kucoin_balance = r.stdout.strip()
    except Exception as exc:
        logger.warning("Falha ao coletar saldo KuCoin: %s", exc)

    # Status dos agents
    agents_status = {}
    for svc in ["BTC_USDT_aggressive", "BTC_USDT_conservative", "USDT_BRL_aggressive", "USDT_BRL_conservative"]:
        try:
            r = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", HOMELAB,
                 f"systemctl is-active crypto-agent@{svc} 2>/dev/null"],
                capture_output=True, text=True, timeout=8,
            )
            agents_status[svc] = "✅ ACTIVE" if r.returncode == 0 else "❌ INACTIVE"
        except Exception:
            agents_status[svc] = "⚠️ ERRO"

    return {
        "kucoin_balance": kucoin_balance,
        "agents_status": agents_status,
    }


# ── Geração via Ollama ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Você é o Trading Analyst do sistema Eddie Auto-Dev.
Sua tarefa é analisar dados de trading e gerar um relatório diário formatado para o Telegram.

Regras:
- Relatório em PT-BR, estruturado com emojis
- Se PnL for positivo: destaque como vitória; se negativo: mencione cautela
- Analise tendências: se avg_entry > preço_atual, posições estão no negativo (underwater)
- Identifique alertas críticos: agentes parados, perda > -5%, posições muito abertas
- Seja objetivo e baseado somente nos dados fornecidos
- NUNCA invente dados ou métricas que não foram fornecidas"""


def generate_report(context: dict, live_data: dict, model: str) -> str:
    """Gera relatório usando Ollama com todos os dados já coletados.

    Args:
        context: Dados do PostgreSQL (trades 24h, posições, histórico).
        live_data: Dados live (saldo KuCoin, status agents).
        model: Nome do modelo Ollama a usar.

    Returns:
        Texto do relatório gerado.
    """
    today = context["report_date"]
    price = context["current_price"]

    # Formatar trades 24h
    trades_str = ""
    for t in context["trades_24h"]:
        trades_str += (
            f"  - {t['profile']}: {t['buys']} buys, {t['sells']} sells | "
            f"wins={t['wins']}, losses={t['losses']} | PnL={float(t['pnl_24h']):+.4f}\n"
        )
    if not trades_str:
        trades_str = "  Nenhum trade nas últimas 24h\n"

    # Formatar histórico
    history_str = ""
    for h in context["history"]:
        total = h["total_sells"]
        wins = h["total_wins"]
        rate = round(100.0 * wins / total, 1) if total > 0 else 0
        history_str += (
            f"  - {h['profile']}: {total} sells | {wins} wins ({rate}%) | "
            f"PnL total={float(h['pnl_total']):+.4f}\n"
        )

    # Formatar posições abertas
    pos_str = ""
    for p in context["open_positions"]:
        avg = float(p["avg_entry"])
        unrealized = round((price - avg) * float(p["total_btc"]), 4)
        pct = round((price / avg - 1) * 100, 2) if avg > 0 else 0
        pos_str += (
            f"  - {p['profile']}: {p['n_entries']} entradas | "
            f"avg=${avg:,.2f} | BTC={float(p['total_btc']):.6f} | "
            f"PnL não realizado: ${unrealized:+.4f} ({pct:+.2f}%)\n"
        )
    if not pos_str:
        pos_str = "  Nenhuma posição aberta no período\n"

    # Formatar saldo KuCoin
    kucoin_str = live_data.get("kucoin_balance", "INDISPONÍVEL")

    # Formatar status agents
    agents_str = "\n".join(
        f"  - {k}: {v}" for k, v in live_data.get("agents_status", {}).items()
    )

    user_msg = f"""Gere o relatório diário de trading para {today}.

## DADOS COLETADOS

### Preço BTC-USDT Atual
${price:,.2f}

### Trades Últimas 24h (apenas reais, dry_run=false)
{trades_str}
PnL total 24h: ${context['total_pnl_24h']:+.4f}
Total execuções: {context['total_trades_24h']}

### Posições Abertas (últimos 30 dias, sem sell emparelhado)
{pos_str}

### Performance Histórica Acumulada
{history_str}

### Saldo KuCoin Live
{kucoin_str}

### Status dos Agentes
{agents_str}

---
Com base nesses dados, gere o relatório completo formatado com emojis para Telegram em PT-BR."""

    with OllamaMCPBridge(model=model) as bridge:
        # Enviar sem tools — apenas formatação/análise dos dados já coletados
        report = bridge.run_with_tools(
            system=SYSTEM_PROMPT,
            user_msg=user_msg,
            tools=[],  # Sem MCP tools — dados já foram coletados
        )

    return report


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
    args = parser.parse_args()

    logger.info("Iniciando relatório diário de trading (dry_run=%s, model=%s)", args.dry_run, args.model)

    # 1. Coletar contexto do banco
    try:
        context = collect_context_data()
        logger.info(
            "Contexto coletado: preço=$%s, trades_24h=%d, pnl_24h=$%s",
            context["current_price"],
            context["total_trades_24h"],
            context["total_pnl_24h"],
        )
    except Exception:
        logger.exception("Falha ao coletar contexto — usando contexto vazio")
        context = {
            "current_price": 0.0,
            "trades_24h": [],
            "history": [],
            "open_positions": [],
            "total_trades_24h": 0,
            "total_pnl_24h": 0.0,
            "report_date": date.today().isoformat(),
        }

    # 2. Coletar dados live (saldo KuCoin, status agents)
    try:
        live_data = collect_live_data()
    except Exception:
        logger.warning("Falha ao coletar dados live — usando valores padrão")
        live_data = {"kucoin_balance": "INDISPONÍVEL", "agents_status": {}}

    # 3. Gerar relatório via Ollama + MCP
    try:
        report_text = generate_report(context, live_data, model=args.model)
    except Exception:
        logger.exception("Falha ao gerar relatório via Ollama")
        report_text = (
            f"⚠️ *TRADING REPORT — {context['report_date']}*\n\n"
            f"❌ Falha na geração automática via Ollama MCP.\n"
            f"Preço BTC: ${context['current_price']:,.2f} | "
            f"Trades 24h: {context['total_trades_24h']} | "
            f"PnL: ${context['total_pnl_24h']:+.4f}"
        )

    # Exibir sempre
    print("\n" + "=" * 60)
    print(report_text)
    print("=" * 60 + "\n")

    if args.dry_run:
        logger.info("--dry-run: relatório não salvo nem enviado")
        return

    # 3. Salvar no banco
    profiles = [r["profile"] for r in context["trades_24h"]]
    metadata = {
        "current_price": context["current_price"],
        "total_trades_24h": context["total_trades_24h"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        save_report(
            report_text=report_text,
            pnl_24h=context["total_pnl_24h"],
            profiles=profiles or ["conservative", "aggressive"],
            metadata=metadata,
            model_used=args.model,
        )
    except Exception:
        logger.exception("Falha ao salvar relatório no banco")

    # 4. Enviar Telegram
    asyncio.run(send_telegram_report(report_text))


if __name__ == "__main__":
    main()
