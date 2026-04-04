#!/usr/bin/env python3
"""Relatório diário de marketing — Telegram.

Coleta métricas do PostgreSQL e envia resumo diário no Telegram.
Executar via cron: 0 8 * * * /path/.venv/bin/python3 marketing/daily_report.py

Uso:
    python3 marketing/daily_report.py            # Envia relatório
    python3 marketing/daily_report.py --dry-run  # Apenas imprime
"""

import argparse
import asyncio
import logging
import os
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

logger = logging.getLogger("marketing.daily_report")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@192.168.15.2:5433/shared",
)


def _get_conn():
    """Obtém conexão PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def collect_metrics() -> dict:
    """Coleta métricas de marketing do banco."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Total de leads
            cur.execute("SELECT COUNT(*) as total FROM marketing.leads")
            total = cur.fetchone()["total"]

            # Leads hoje
            cur.execute(
                "SELECT COUNT(*) as hoje FROM marketing.leads "
                "WHERE created_at::date = CURRENT_DATE"
            )
            hoje = cur.fetchone()["hoje"]

            # Leads ontem (para comparação)
            cur.execute(
                "SELECT COUNT(*) as ontem FROM marketing.leads "
                "WHERE created_at::date = CURRENT_DATE - 1"
            )
            ontem = cur.fetchone()["ontem"]

            # Leads semana
            cur.execute(
                "SELECT COUNT(*) as semana FROM marketing.leads "
                "WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'"
            )
            semana = cur.fetchone()["semana"]

            # Leads mês
            cur.execute(
                "SELECT COUNT(*) as mes FROM marketing.leads "
                "WHERE created_at >= date_trunc('month', CURRENT_DATE)"
            )
            mes = cur.fetchone()["mes"]

            # Por origem (top 5)
            cur.execute("""
                SELECT COALESCE(origem, 'direto') as origem, COUNT(*) as qtd
                FROM marketing.leads
                WHERE created_at >= date_trunc('month', CURRENT_DATE)
                GROUP BY origem ORDER BY qtd DESC LIMIT 5
            """)
            por_origem = cur.fetchall()

            # Por UTM source (top 5)
            cur.execute("""
                SELECT COALESCE(utm_source, 'direto') as src, COUNT(*) as qtd
                FROM marketing.leads
                WHERE created_at >= date_trunc('month', CURRENT_DATE)
                GROUP BY utm_source ORDER BY qtd DESC LIMIT 5
            """)
            por_utm = cur.fetchall()

            # Status dos leads
            cur.execute("""
                SELECT status, COUNT(*) as qtd
                FROM marketing.leads
                GROUP BY status ORDER BY qtd DESC
            """)
            por_status = cur.fetchall()

            # Drip stats
            cur.execute("""
                SELECT drip_step, COUNT(*) as qtd
                FROM marketing.leads
                WHERE status = 'novo'
                GROUP BY drip_step ORDER BY drip_step
            """)
            drip_stats = cur.fetchall()

            return {
                "total": total,
                "hoje": hoje,
                "ontem": ontem,
                "semana": semana,
                "mes": mes,
                "por_origem": por_origem,
                "por_utm": por_utm,
                "por_status": por_status,
                "drip_stats": drip_stats,
            }
    finally:
        conn.close()


def format_report(metrics: dict) -> str:
    """Formata relatório em texto para Telegram."""
    delta = metrics["hoje"] - metrics["ontem"]
    delta_icon = "📈" if delta > 0 else ("📉" if delta < 0 else "➡️")
    delta_str = f"+{delta}" if delta > 0 else str(delta)

    report = (
        f"📊 *MARKETING RPA4ALL — Relatório Diário*\n"
        f"📅 {datetime.now().strftime('%d/%m/%Y')}\n"
        f"{'─' * 30}\n\n"
        f"🎯 *LEADS*\n"
        f"  Total acumulado: *{metrics['total']}*\n"
        f"  Hoje: *{metrics['hoje']}* {delta_icon} ({delta_str} vs ontem)\n"
        f"  Últimos 7 dias: *{metrics['semana']}*\n"
        f"  Mês atual: *{metrics['mes']}*\n\n"
    )

    if metrics["por_origem"]:
        report += "🏷️ *POR ORIGEM (mês)*\n"
        for r in metrics["por_origem"]:
            report += f"  • {r['origem']}: {r['qtd']}\n"
        report += "\n"

    if metrics["por_utm"]:
        report += "📡 *POR UTM SOURCE (mês)*\n"
        for r in metrics["por_utm"]:
            report += f"  • {r['src']}: {r['qtd']}\n"
        report += "\n"

    if metrics["por_status"]:
        report += "📋 *STATUS DOS LEADS*\n"
        for r in metrics["por_status"]:
            icon = {"novo": "🆕", "nutrido": "📧", "qualificado": "⭐", "convertido": "✅"}.get(
                r["status"], "⚪"
            )
            report += f"  {icon} {r['status']}: {r['qtd']}\n"
        report += "\n"

    if metrics["drip_stats"]:
        report += "💧 *DRIP SEQUENCE*\n"
        for r in metrics["drip_stats"]:
            report += f"  Step {r['drip_step']}: {r['qtd']} leads\n"
        report += "\n"

    report += f"{'─' * 30}\n🤖 Gerado automaticamente pelo Marketing Agent"
    return report


async def send_telegram_report(text: str) -> None:
    """Envia relatório via Telegram."""
    try:
        from tools.secrets_loader import get_telegram_token

        from telegram import Bot

        token = get_telegram_token()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "948686300")
        bot = Bot(token=token)
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        logger.info("Relatório diário enviado no Telegram")
    except Exception:
        logger.exception("Falha ao enviar relatório no Telegram")


def save_daily_metrics(metrics: dict) -> None:
    """Persiste métricas diárias no banco."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO marketing.daily_metrics (data, leads_total, leads_novos)
                VALUES (CURRENT_DATE, %s, %s)
                ON CONFLICT (data)
                DO UPDATE SET
                    leads_total = EXCLUDED.leads_total,
                    leads_novos = EXCLUDED.leads_novos
            """, (metrics["total"], metrics["hoje"]))
    finally:
        conn.close()


def main() -> None:
    """Entrypoint CLI."""
    parser = argparse.ArgumentParser(description="Marketing Daily Report — RPA4ALL")
    parser.add_argument("--dry-run", action="store_true", help="Apenas imprime, não envia")
    args = parser.parse_args()

    try:
        metrics = collect_metrics()
    except Exception:
        logger.exception("Falha ao coletar métricas (tabela pode não existir ainda)")
        metrics = {
            "total": 0, "hoje": 0, "ontem": 0, "semana": 0, "mes": 0,
            "por_origem": [], "por_utm": [], "por_status": [], "drip_stats": [],
        }

    report = format_report(metrics)

    if args.dry_run:
        print(report)
        return

    save_daily_metrics(metrics)
    asyncio.run(send_telegram_report(report))
    print("✅ Relatório enviado")


if __name__ == "__main__":
    main()
