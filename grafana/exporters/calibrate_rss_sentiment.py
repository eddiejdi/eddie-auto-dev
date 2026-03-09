#!/usr/bin/env python3
"""Calibração e validação do RSS Sentiment Exporter.

Executa a classificação de sentimento com cenários passados,
coleta feeds RSS para dados históricos, e valida a qualidade
das predições do Ollama.

Uso:
  python3 calibrate_rss_sentiment.py --mode full --feeds 500
  python3 calibrate_rss_sentiment.py --mode validate --coins BTC ETH
  python3 calibrate_rss_sentiment.py --mode report --window 7
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import feedparser
except ImportError:
    print("ERROR: feedparser not installed. Run: pip install feedparser")
    sys.exit(1)

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [calibrate] %(message)s",
)
log = logging.getLogger("calibrate")

# ── Configuração ───────────────────────────────────────────────────────

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/btc_trading"
)
OLLAMA_HOST = "http://192.168.15.2:11434"
OLLAMA_SENTIMENT_MODEL = "qwen2.5-coder:7b"

RSS_FEEDS: List[Dict[str, str]] = [
    {"name": "coindesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "cointelegraph", "url": "https://cointelegraph.com/rss"},
    {"name": "decrypt", "url": "https://decrypt.co/feed"},
    {"name": "bitcoinmagazine", "url": "https://bitcoinmagazine.com/.rss/full/"},
    {"name": "cryptonews", "url": "https://cryptonews.com/news/feed/"},
    {"name": "theblock", "url": "https://www.theblock.co/rss.xml"},
]

TRACKED_COINS = ["BTC", "ETH", "XRP", "SOL", "DOGE", "ADA"]

# Exemplos de validação manual (especialista humano)
VALIDATION_EXAMPLES: Dict[str, Tuple[float, str]] = {
    # URL: (expected_sentiment, category)
    "bitcoin-etf-approval": (0.9, "adoption"),  # Extremamente bullish
    "crypto-ban-china": (-0.85, "regulation"),  # Extremamente bearish
    "defi-hack-millions": (-0.8, "hack"),  # Muito bearish
    "ethereum-staking": (0.75, "adoption"),  # Bullish
    "ripple-sec-settlement": (0.7, "regulation"),  # Bullish (settlement positivo)
    "luna-crash": (-0.95, "price"),  # Crash total
    "institutional-buying": (0.8, "price"),  # Bullish
    "fed-rate-increase": (-0.5, "macro"),  # Bearish (macro)
    "nft-market-growth": (0.6, "adoption"),  # Bullish (adoção)
    "exchange-hack": (-0.85, "hack"),  # Muito bearish
}


# ── Coleta de Articles ─────────────────────────────────────────────────


def fetch_rss_articles(feed_url: str, feed_name: str, limit: int = 50) -> List[Dict]:
    """Busca artigos de um feed RSS."""
    try:
        feed = feedparser.parse(feed_url)
        articles = []

        for entry in feed.entries[:limit]:
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            if not title or not url:
                continue

            description = entry.get("description", "") or entry.get("summary", "")
            articles.append({
                "title": title,
                "url": url,
                "source": feed_name,
                "description": description[:500],
                "published": datetime.now(timezone.utc).isoformat(),
            })

        log.info("Feed %s: %d artigos coletados", feed_name, len(articles))
        return articles

    except Exception as e:
        log.error("Erro ao buscar feed %s: %s", feed_name, e)
        return []


def collect_all_feeds(limit_per_feed: int = 50) -> List[Dict]:
    """Coleta artigos de todos os feeds."""
    all_articles = []
    for feed_def in RSS_FEEDS:
        articles = fetch_rss_articles(feed_def["url"], feed_def["name"], limit_per_feed)
        all_articles.extend(articles)
        time.sleep(1)  # Rate limiting
    return all_articles


# ── Ollama Sentiment Classification ─────────────────────────────────────


def classify_sentiment(title: str, description: str) -> Tuple[float, float, str]:
    """Classifica sentimento via Ollama. Retorna (sentiment, confidence, category)."""
    import urllib.request
    import urllib.error

    prompt = f"""Classify sentiment (crypto trading) -1 to 1 scale.
Reply ONLY: SENTIMENT: <number> | CONFIDENCE: <0-1> | CATEGORY: <word>

Title: {title}
Text: {description[:300]}"""

    try:
        req_data = json.dumps({
            "model": OLLAMA_SENTIMENT_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 64, "temperature": 0.1},
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=req_data,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            response = result.get("response", "").strip()

            # Parse response
            sentiment, confidence, category = _parse_response(response)
            return sentiment, confidence, category

    except Exception as e:
        log.warning("Ollama error: %s", e)
        return 0.0, 0.5, "general"


def _parse_response(response: str) -> Tuple[float, float, str]:
    """Parseia resposta do Ollama."""
    import re

    sentiment = 0.0
    confidence = 0.5
    category = "general"

    try:
        sent_match = re.search(r"SENTIMENT:\s*([-+]?\d*\.?\d+)", response, re.IGNORECASE)
        if sent_match:
            sentiment = float(sent_match.group(1))
            sentiment = max(-1.0, min(1.0, sentiment))

        conf_match = re.search(r"CONFIDENCE:\s*([-+]?\d*\.?\d+)", response, re.IGNORECASE)
        if conf_match:
            confidence = float(conf_match.group(1))
            confidence = max(0.0, min(1.0, confidence))

        cat_match = re.search(r"CATEGORY:\s*(\w+)", response, re.IGNORECASE)
        valid_cats = {"regulation", "adoption", "hack", "price", "macro", "defi"}
        if cat_match and cat_match.group(1).lower() in valid_cats:
            category = cat_match.group(1).lower()

    except Exception as e:
        log.debug("Parse error: %s", e)

    return sentiment, confidence, category


# ── Database Operations ────────────────────────────────────────────────


def get_db_connection():
    """Retorna conexão PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def insert_calibration_result(
    conn: psycopg2.extensions.connection,
    article: Dict,
    sentiment: float,
    confidence: float,
    category: str,
    manual_validation: Optional[Tuple[float, str]] = None,
) -> None:
    """Insere resultado de classificação na tabela de calibração."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS btc.sentiment_calibration (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ DEFAULT NOW(),
                url TEXT NOT NULL UNIQUE,
                title TEXT,
                source VARCHAR(50),
                ollama_sentiment FLOAT,
                ollama_confidence FLOAT,
                ollama_category VARCHAR(50),
                manual_sentiment FLOAT,
                manual_category VARCHAR(50),
                accuracy_score FLOAT,
                notes TEXT
            )
        """)

        accuracy = None
        if manual_validation:
            expected_sentiment, expected_category = manual_validation
            # Medir acurácia
            accuracy = 1.0 - abs(sentiment - expected_sentiment)

        cur.execute("""
            INSERT INTO btc.sentiment_calibration
            (url, title, source, ollama_sentiment, ollama_confidence,
             ollama_category, manual_sentiment, manual_category, accuracy_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE SET
                ollama_sentiment = EXCLUDED.ollama_sentiment,
                ollama_confidence = EXCLUDED.ollama_confidence,
                ollama_category = EXCLUDED.ollama_category,
                accuracy_score = EXCLUDED.accuracy_score
        """, (
            article["url"],
            article["title"][:200],
            article["source"],
            sentiment,
            confidence,
            category,
            manual_validation[0] if manual_validation else None,
            manual_validation[1] if manual_validation else None,
            accuracy,
        ))


def get_calibration_report(conn: psycopg2.extensions.connection, days: int = 7) -> Dict:
    """Gera relatório de cobertura e acurácia."""
    with conn.cursor() as cur:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Total de artigos classificados
        cur.execute("""
            SELECT COUNT(*) FROM btc.sentiment_calibration WHERE timestamp >= %s
        """, (cutoff,))
        total = cur.fetchone()[0]

        # Acurácia média (onde há validação manual)
        cur.execute("""
            SELECT AVG(accuracy_score) FROM btc.sentiment_calibration
            WHERE timestamp >= %s AND accuracy_score IS NOT NULL
        """, (cutoff,))
        avg_accuracy = cur.fetchone()[0] or 0.0

        # Distribuição de sentimentos
        cur.execute("""
            SELECT
                CASE
                    WHEN ollama_sentiment > 0.3 THEN 'BULLISH'
                    WHEN ollama_sentiment < -0.3 THEN 'BEARISH'
                    ELSE 'NEUTRAL'
                END as sentiment_class,
                COUNT(*) as count
            FROM btc.sentiment_calibration
            WHERE timestamp >= %s
            GROUP BY sentiment_class
        """, (cutoff,))
        distribution = dict(cur.fetchall())

        # Confiança média
        cur.execute("""
            SELECT AVG(ollama_confidence) FROM btc.sentiment_calibration
            WHERE timestamp >= %s
        """, (cutoff,))
        avg_confidence = cur.fetchone()[0] or 0.0

        # Top categorias
        cur.execute("""
            SELECT ollama_category, COUNT(*) FROM btc.sentiment_calibration
            WHERE timestamp >= %s
            GROUP BY ollama_category
            ORDER BY COUNT(*) DESC
            LIMIT 5
        """, (cutoff,))
        top_categories = dict(cur.fetchall())

    return {
        "total_articles": total,
        "avg_accuracy": round(avg_accuracy * 100, 2),
        "avg_confidence": round(avg_confidence * 100, 2),
        "sentiment_distribution": distribution,
        "top_categories": top_categories,
        "period_days": days,
    }


# ── Calibration Modes ──────────────────────────────────────────────────


def mode_full_calibration(feeds_to_collect: int = 500) -> None:
    """Coleta feeds RSS, classifica com Ollama, persiste resultados."""
    log.info("=== FULL CALIBRATION MODE ===")
    log.info("Coletando até %d artigos de feeds RSS...", feeds_to_collect)

    articles = collect_all_feeds(limit_per_feed=feeds_to_collect // len(RSS_FEEDS) + 1)
    articles = articles[:feeds_to_collect]

    log.info("Total de artigos coletados: %d", len(articles))
    log.info("Iniciando classificação com Ollama...")

    conn = get_db_connection()

    for i, article in enumerate(articles):
        log.info("[%d/%d] Processando: %s", i + 1, len(articles), article["title"][:60])

        sentiment, confidence, category = classify_sentiment(
            article["title"],
            article["description"],
        )

        insert_calibration_result(conn, article, sentiment, confidence, category)

        # Rate limiting
        if i % 10 == 0:
            time.sleep(2)
        else:
            time.sleep(0.3)

    conn.close()
    log.info("✅ Calibração completa. %d artigos classificados.", len(articles))


def mode_validate_with_examples() -> None:
    """Valida classificações usando exemplos manuais."""
    log.info("=== VALIDATION MODE (com exemplos manuais) ===")

    conn = get_db_connection()

    correct_count = 0
    total_count = len(VALIDATION_EXAMPLES)

    for keyword, (expected_sentiment, expected_category) in VALIDATION_EXAMPLES.items():
        # Simular um artigo com o keyword
        article = {
            "title": f"Test article about {keyword}",
            "description": f"This is a test article regarding {keyword} in crypto markets.",
            "url": f"https://test.example.com/{keyword}",
            "source": "validation",
            "published": datetime.now(timezone.utc).isoformat(),
        }

        log.info("Validando: %s (esperado: %.2f %s)", keyword, expected_sentiment, expected_category)

        sentiment, confidence, category = classify_sentiment(
            article["title"],
            article["description"],
        )

        accuracy = 1.0 - abs(sentiment - expected_sentiment)

        log.info(
            "  Resultado: sentimento=%.2f conf=%.2f cat=%s | Acurácia: %.1f%%",
            sentiment,
            confidence,
            category,
            accuracy * 100,
        )

        if accuracy > 0.8:
            correct_count += 1

        insert_calibration_result(
            conn,
            article,
            sentiment,
            confidence,
            category,
            (expected_sentiment, expected_category),
        )

        time.sleep(1)

    conn.close()

    log.info(
        "✅ Validação concluída. Acertos: %d/%d (%.1f%%)",
        correct_count,
        total_count,
        (correct_count / total_count) * 100,
    )


def mode_report(window_days: int = 7) -> None:
    """Gera relatório de cobertura e acurácia."""
    log.info("=== REPORT MODE (últimos %d dias) ===", window_days)

    conn = get_db_connection()
    report = get_calibration_report(conn, days=window_days)
    conn.close()

    log.info("📊 RELATÓRIO DE CALIBRAÇÃO")
    log.info("─" * 50)
    log.info("Total de artigos: %d", report["total_articles"])
    log.info("Acurácia média: %.1f%%", report["avg_accuracy"])
    log.info("Confiança média: %.1f%%", report["avg_confidence"])
    log.info("Período: %d dias", report["period_days"])
    log.info("")
    log.info("Distribuição de sentimentos:")
    for sentiment_class, count in sorted(report["sentiment_distribution"].items()):
        pct = (count / max(1, report["total_articles"])) * 100
        log.info("  - %s: %d (%.1f%%)", sentiment_class, count, pct)
    log.info("")
    log.info("Top categorias detectadas:")
    for category, count in sorted(report["top_categories"].items(), key=lambda x: -x[1]):
        log.info("  - %s: %d", category, count)

    # Salvar JSON
    report_file = Path("/tmp/sentiment_calibration_report.json")
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    log.info("✅ Relatório salvo em: %s", report_file)


def mode_interactive() -> None:
    """Modo interativo: classifica manualmente e compara com Ollama."""
    log.info("=== INTERACTIVE MODE ===")
    log.info("Digite 'quit' para sair, 'reset' para limpar histórico.")

    conn = get_db_connection()

    while True:
        try:
            title = input("\n📰 Título do artigo (ou 'quit'): ").strip()
            if title.lower() == "quit":
                break
            if title.lower() == "reset":
                log.info("Limpando histórico (não implementado neste modo)")
                continue

            description = input("Descrição (resumo): ").strip()

            log.info("Classificando com Ollama...")
            sentiment, confidence, category = classify_sentiment(title, description)

            log.info(
                "\n✨ Resultado Ollama:\n"
                "   Sentimento: %.2f (confiança: %.2f%%)\n"
                "   Categoria: %s",
                sentiment,
                confidence * 100,
                category,
            )

            # Validação manual
            try:
                expected = float(input("Sentimento esperado (-1 a 1, ou Enter para pular): ") or "999")
                if expected != 999:
                    accuracy = 1.0 - abs(sentiment - expected)
                    log.info("Acurácia: %.1f%%", accuracy * 100)

                    article = {
                        "title": title,
                        "description": description,
                        "url": f"manual_{int(time.time())}",
                        "source": "interactive",
                        "published": datetime.now(timezone.utc).isoformat(),
                    }
                    insert_calibration_result(
                        conn,
                        article,
                        sentiment,
                        confidence,
                        category,
                        (expected, category),
                    )
            except ValueError:
                pass

        except KeyboardInterrupt:
            break
        except Exception as e:
            log.error("Erro: %s", e)

    conn.close()
    log.info("✅ Modo interativo encerrado.")


# ── Main ───────────────────────────────────────────────────────────────


def main() -> None:
    """Ponto de entrada."""
    parser = argparse.ArgumentParser(
        description="Calibração e validação do RSS Sentiment Exporter"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "validate", "report", "interactive"],
        default="report",
        help="Modo de operação",
    )
    parser.add_argument(
        "--feeds",
        type=int,
        default=500,
        help="Número de artigos a coletar (modo full)",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=7,
        help="Janela de dias para relatório (modo report)",
    )
    parser.add_argument(
        "--coins",
        nargs="+",
        default=TRACKED_COINS,
        help="Moedas a monitorar",
    )

    args = parser.parse_args()

    log.info(
        "🚀 RSS Sentiment Calibration — Ollama=%s Model=%s",
        OLLAMA_HOST,
        OLLAMA_SENTIMENT_MODEL,
    )

    if args.mode == "full":
        mode_full_calibration(args.feeds)
    elif args.mode == "validate":
        mode_validate_with_examples()
    elif args.mode == "report":
        mode_report(args.window)
    elif args.mode == "interactive":
        mode_interactive()

    log.info("✅ Calibração finalizada.")


if __name__ == "__main__":
    main()
