#!/usr/bin/env python3
"""Rotina completa de fine-tuning do eddie-sentiment.

Executa pipeline completo:
  1. Reclassifica artigos existentes no DB com phi4-mini (substituindo qwen3:1.7b)
  2. Coleta novos artigos dos feeds RSS
  3. Correlaciona todos com dados de preço (btc.candles)
  4. Treina eddie-sentiment:latest com os melhores exemplos
  5. Valida o modelo com predict

Uso:
  python3 scripts/run_sentiment_finetune.py

Parâmetros via env:
  OLLAMA_HOST          GPU0 (default: http://192.168.15.2:11434)
  OLLAMA_HOST_GPU1     GPU1 (default: http://192.168.15.2:11435)
  DATABASE_URL         PostgreSQL (default: postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/btc_trading)
  MIN_DATE             Data mínima dos artigos (default: 2026-02-01)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Adicionar o diretório raiz ao path para importar o trainer
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 não instalado.")
    sys.exit(1)

# ── Configuração ───────────────────────────────────────────────────────────────

OLLAMA_HOST_GPU1 = os.environ.get("OLLAMA_HOST_GPU1", "http://192.168.15.2:11435")
OLLAMA_HOST_GPU0 = os.environ.get("OLLAMA_HOST", "http://192.168.15.2:11434")
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/btc_trading",
)
CLASSIFIER_MODEL = os.environ.get("OLLAMA_CLASSIFIER_MODEL", "phi4-mini")
MIN_DATE = os.environ.get("MIN_DATE", "2026-02-01")

log = logging.getLogger("finetune")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)


# ── Funções auxiliares ─────────────────────────────────────────────────────────

def get_db_connection() -> psycopg2.extensions.connection:
    """Conecta ao PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def ollama_classify(
    host: str, model: str, title: str, description: str, coin: str, timeout: int = 30
) -> Tuple[float, float, str, str]:
    """Classifica sentimento de um artigo via Ollama API.

    Returns:
        (sentiment, confidence, direction, category)
    """
    prompt = f"""Analyze this crypto news and classify sentiment for trading.
Reply ONLY in this exact format (no extra text, no thinking):
SENTIMENT: <-1.0 to 1.0> | CONFIDENCE: <0.0 to 1.0> | DIRECTION: <BULLISH|BEARISH|NEUTRAL> | CATEGORY: <regulation|adoption|hack|price|macro|defi|technical|general>

Coin: {coin}
Title: {title}
Summary: {description[:300]}"""

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.05, "num_predict": 100},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{host}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            text = data.get("response", "")
            return _parse_response(text)
    except Exception as exc:
        log.debug("Ollama erro (%s): %s", host, exc)
        return 0.0, 0.5, "NEUTRAL", "general"


def _parse_response(response: str) -> Tuple[float, float, str, str]:
    """Parseia resposta do Ollama."""
    sentiment = 0.0
    confidence = 0.5
    direction = "NEUTRAL"
    category = "general"

    try:
        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
        response = re.sub(r"^\s*</think>\s*", "", response).strip()

        sent_m = re.search(r"SENTIMENT:\s*([-+]?\d*\.?\d+)", response, re.IGNORECASE)
        if sent_m:
            sentiment = max(-1.0, min(1.0, float(sent_m.group(1))))

        conf_m = re.search(r"CONFIDENCE:\s*(\d*\.?\d+)", response, re.IGNORECASE)
        if conf_m:
            confidence = max(0.0, min(1.0, float(conf_m.group(1))))

        dir_m = re.search(r"DIRECTION:\s*(BULLISH|BEARISH|NEUTRAL)", response, re.IGNORECASE)
        if dir_m:
            direction = dir_m.group(1).upper()

        cat_m = re.search(r"CATEGORY:\s*(\w+)", response, re.IGNORECASE)
        valid_cats = {"regulation", "adoption", "hack", "price", "macro", "defi", "technical", "general"}
        if cat_m and cat_m.group(1).lower() in valid_cats:
            category = cat_m.group(1).lower()
    except Exception:
        pass

    return sentiment, confidence, direction, category


def compute_ground_truth(price_pub: float, price_impact: float, threshold: float = 1.5) -> str:
    """Computa ground truth baseado em variação de preço."""
    if price_pub <= 0:
        return "NEUTRAL"
    change = ((price_impact - price_pub) / price_pub) * 100
    if change >= threshold:
        return "BULLISH"
    if change <= -threshold:
        return "BEARISH"
    return "NEUTRAL"


def get_price_at_ts(
    conn: psycopg2.extensions.connection,
    symbol: str,
    ts: float,
    window_min: int = 60,
) -> Optional[float]:
    """Busca preço de fechamento mais próximo de um timestamp."""
    ts_sec = int(ts)
    window_sec = window_min * 60
    with conn.cursor() as cur:
        cur.execute("""
            SELECT close FROM btc.candles
            WHERE symbol = %s
              AND timestamp BETWEEN %s AND %s
            ORDER BY ABS(timestamp - %s)
            LIMIT 1
        """, (symbol, ts_sec - window_sec, ts_sec + window_sec, ts_sec))
        row = cur.fetchone()
        return float(row[0]) if row else None


COIN_SYMBOL_MAP: Dict[str, str] = {
    "BTC": "BTC-USDT", "ETH": "ETH-USDT", "SOL": "SOL-USDT",
    "XRP": "XRP-USDT", "DOGE": "DOGE-USDT", "ADA": "ADA-USDT",
}

PRICE_IMPACT_HOURS = 4


# ── Etapa 1: Reclassificar existentes ─────────────────────────────────────────

def reclassify_existing(conn: psycopg2.extensions.connection) -> int:
    """Reclassifica todos os artigos que foram classificados com modelo antigo.

    Usa phi4-mini para reclassificar artigos previamente classificados por qwen3:1.7b.
    Também recalcula ground_truth e prediction_correct.

    Returns:
        Número de artigos reclassificados.
    """
    min_ts = int(datetime.strptime(MIN_DATE, "%Y-%m-%d").timestamp())

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT id, url, title, description, coin, published_ts,
                   model_version, ground_truth
            FROM btc.training_samples
            WHERE model_version != %s
              AND published_ts >= %s
            ORDER BY published_ts ASC
        """, (CLASSIFIER_MODEL, min_ts))
        rows = cur.fetchall()

    if not rows:
        log.info("Nenhum artigo para reclassificar (todos já usam %s).", CLASSIFIER_MODEL)
        return 0

    log.info("=" * 60)
    log.info("ETAPA 1: Reclassificar %d artigos com %s", len(rows), CLASSIFIER_MODEL)
    log.info("=" * 60)

    reclassified = 0
    for i, row in enumerate(rows, 1):
        title = row["title"] or ""
        desc = row["description"] or ""
        coin = row["coin"] or "BTC"
        symbol = COIN_SYMBOL_MAP.get(coin, "BTC-USDT")
        pub_ts = row["published_ts"]

        log.info("[%d/%d] Reclassificando: %s", i, len(rows), title[:60])

        # GPU0 primeiro (phi4-mini ~2.5GB, NÃO cabe em GPU1 2GB), fallback GPU1
        sentiment, confidence, direction, category = ollama_classify(
            OLLAMA_HOST_GPU0, CLASSIFIER_MODEL, title, desc, coin, timeout=30
        )
        if direction == "NEUTRAL" and sentiment == 0.0 and confidence == 0.5:
            # GPU0 pode ter falhado, tentar GPU1
            sentiment, confidence, direction, category = ollama_classify(
                OLLAMA_HOST_GPU1, CLASSIFIER_MODEL, title, desc, coin, timeout=15
            )

        # Recalcular ground truth com timestamp correto
        price_pub = get_price_at_ts(conn, symbol, pub_ts, window_min=60)
        price_impact = get_price_at_ts(conn, symbol, pub_ts + PRICE_IMPACT_HOURS * 3600, window_min=60)

        ground_truth = None
        price_change_pct = None
        prediction_correct = None

        if price_pub and price_impact and price_pub > 0:
            price_change_pct = ((price_impact - price_pub) / price_pub) * 100
            ground_truth = compute_ground_truth(price_pub, price_impact)
            prediction_correct = (direction == ground_truth)

        with conn.cursor() as cur:
            cur.execute("""
                UPDATE btc.training_samples SET
                    ollama_sentiment = %s,
                    ollama_confidence = %s,
                    ollama_direction = %s,
                    ollama_category = %s,
                    model_version = %s,
                    price_at_pub = %s,
                    price_at_impact = %s,
                    price_change_pct = %s,
                    ground_truth = %s,
                    prediction_correct = %s
                WHERE id = %s
            """, (
                sentiment, confidence, direction, category,
                CLASSIFIER_MODEL,
                price_pub, price_impact, price_change_pct,
                ground_truth, prediction_correct,
                row["id"],
            ))

        status = ""
        if ground_truth:
            icon = "✅" if prediction_correct else "❌"
            status = f" | GT={ground_truth} {icon}"
        log.info("       → %s %.2f (conf=%.0f%%) [%s]%s",
                 direction, sentiment, confidence * 100, category, status)

        reclassified += 1
        time.sleep(0.3)

    log.info("✅ Reclassificação concluída: %d artigos atualizados com %s", reclassified, CLASSIFIER_MODEL)
    return reclassified


# ── Etapa 2: Coletar novos artigos ────────────────────────────────────────────

def collect_new_articles(conn: psycopg2.extensions.connection) -> int:
    """Coleta novos artigos dos feeds RSS, classifica e salva.

    Importa e usa as funções existentes do rss_llm_trainer.py.

    Returns:
        Número de novos artigos coletados.
    """
    log.info("=" * 60)
    log.info("ETAPA 2: Coletar novos artigos dos feeds RSS")
    log.info("=" * 60)

    # Import dinâmico do trainer
    import importlib.util
    trainer_path = ROOT_DIR / "grafana" / "exporters" / "rss_llm_trainer.py"
    spec = importlib.util.spec_from_file_location("rss_llm_trainer", trainer_path)
    trainer = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["rss_llm_trainer"] = trainer
    spec.loader.exec_module(trainer)  # type: ignore[union-attr]

    # Coleta
    articles = trainer.collect_all_feeds(limit_per_feed=100)
    if not articles:
        log.info("Nenhum artigo novo coletado.")
        return 0

    # Filtrar artigos desde MIN_DATE
    min_ts = int(datetime.strptime(MIN_DATE, "%Y-%m-%d").timestamp())
    articles = [a for a in articles if a.get("published_ts", 0) >= min_ts]
    log.info("Artigos desde %s: %d", MIN_DATE, len(articles))

    # Verificar quais já existem no DB
    with conn.cursor() as cur:
        cur.execute("SELECT url FROM btc.training_samples")
        existing_urls = {r[0] for r in cur.fetchall()}

    new_articles = [a for a in articles if a.get("url") not in existing_urls]
    log.info("Artigos novos (não duplicados): %d", len(new_articles))

    if not new_articles:
        log.info("Todos os artigos já estão no DB.")
        return 0

    impact_seconds = PRICE_IMPACT_HOURS * 3600
    inserted = 0
    with_price = 0

    for i, art in enumerate(new_articles, 1):
        title = art.get("title", "")
        description = art.get("description", "")
        coin = trainer.detect_primary_coin(title, description)
        symbol = COIN_SYMBOL_MAP.get(coin, "BTC-USDT")
        pub_ts = art["published_ts"]

        log.info("[%d/%d] %s | %s", i, len(new_articles), art["source"], title[:55])

        # Classifica com phi4-mini (GPU0 → GPU1 fallback)
        sentiment, confidence, direction, category = ollama_classify(
            OLLAMA_HOST_GPU0, CLASSIFIER_MODEL, title, description, coin, timeout=30
        )
        if direction == "NEUTRAL" and sentiment == 0.0 and confidence == 0.5:
            sentiment, confidence, direction, category = ollama_classify(
                OLLAMA_HOST_GPU1, CLASSIFIER_MODEL, title, description, coin, timeout=15
            )

        # Correlação com preço
        price_pub = get_price_at_ts(conn, symbol, pub_ts, window_min=60)
        price_impact = get_price_at_ts(conn, symbol, pub_ts + impact_seconds, window_min=60)

        ground_truth = None
        price_change_pct = None
        prediction_correct = None

        if price_pub and price_impact and price_pub > 0:
            price_change_pct = ((price_impact - price_pub) / price_pub) * 100
            ground_truth = compute_ground_truth(price_pub, price_impact)
            prediction_correct = (direction == ground_truth)
            with_price += 1

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO btc.training_samples (
                    url, title, description, source, coin, published_ts,
                    price_at_pub, price_at_impact, price_change_pct, ground_truth,
                    ollama_sentiment, ollama_confidence, ollama_direction,
                    ollama_category, prediction_correct, model_version
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (url) DO NOTHING
            """, (
                art["url"], title, description, art["source"], coin, int(pub_ts),
                price_pub, price_impact, price_change_pct, ground_truth,
                sentiment, confidence, direction, category,
                prediction_correct, CLASSIFIER_MODEL,
            ))

        inserted += 1
        time.sleep(0.3)

    log.info("✅ Coleta concluída: %d novos | %d com preço", inserted, with_price)
    return inserted


# ── Etapa 3: Relatório + Treino ────────────────────────────────────────────────

def report_and_train(conn: psycopg2.extensions.connection) -> bool:
    """Gera relatório do dataset e executa treinamento.

    Returns:
        True se o modelo foi criado com sucesso.
    """
    log.info("=" * 60)
    log.info("ETAPA 3: Relatório + Treinamento")
    log.info("=" * 60)

    min_ts = int(datetime.strptime(MIN_DATE, "%Y-%m-%d").timestamp())

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM btc.training_samples WHERE published_ts >= %s", (min_ts,))
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM btc.training_samples
            WHERE published_ts >= %s AND ground_truth IS NOT NULL
        """, (min_ts,))
        with_gt = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM btc.training_samples
            WHERE published_ts >= %s AND prediction_correct = TRUE
        """, (min_ts,))
        correct = cur.fetchone()[0]

        cur.execute("""
            SELECT ground_truth, COUNT(*) FROM btc.training_samples
            WHERE published_ts >= %s AND ground_truth IS NOT NULL
            GROUP BY ground_truth ORDER BY ground_truth
        """, (min_ts,))
        dist = cur.fetchall()

        cur.execute("""
            SELECT model_version, COUNT(*) FROM btc.training_samples
            WHERE published_ts >= %s
            GROUP BY model_version ORDER BY model_version
        """, (min_ts,))
        models = cur.fetchall()

        # Exemplos qualificados para few-shot
        cur.execute("""
            SELECT COUNT(*) FROM btc.training_samples
            WHERE published_ts >= %s
              AND prediction_correct = TRUE
              AND ollama_confidence >= 0.40
              AND ground_truth IN ('BULLISH', 'BEARISH')
        """, (min_ts,))
        qualified = cur.fetchone()[0]

    accuracy = (correct / max(1, with_gt)) * 100

    log.info("─" * 50)
    log.info("📊 DATASET (desde %s):", MIN_DATE)
    log.info("   Total artigos:     %d", total)
    log.info("   Com ground truth:  %d", with_gt)
    log.info("   Corretos:          %d (%.1f%%)", correct, accuracy)
    log.info("   Distribuição:      %s", dict(dist))
    log.info("   Modelos usados:    %s", dict(models))
    log.info("   Exemplos few-shot: %d (qualificados)", qualified)
    log.info("─" * 50)

    # Importar e executar modo train
    import importlib.util
    trainer_path = ROOT_DIR / "grafana" / "exporters" / "rss_llm_trainer.py"
    spec = importlib.util.spec_from_file_location("rss_llm_trainer", trainer_path)
    trainer = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["rss_llm_trainer"] = trainer
    spec.loader.exec_module(trainer)  # type: ignore[union-attr]

    trainer.mode_train()
    return True


# ── Etapa 4: Validação do modelo ───────────────────────────────────────────────

def validate_model() -> None:
    """Testa o modelo eddie-sentiment com artigos de exemplo."""
    log.info("=" * 60)
    log.info("ETAPA 4: Validação do eddie-sentiment")
    log.info("=" * 60)

    test_cases = [
        ("BTC", "Bitcoin surges 15% as institutional demand hits record high",
         "Major ETFs report unprecedented inflows pushing BTC above $100K"),
        ("ETH", "Ethereum upgrade causes network instability",
         "Post-merge upgrade leads to validator issues, gas fees spike 10x"),
        ("BTC", "Major exchange hacked, $500M in user funds stolen",
         "Security breach compromises hot wallets, withdrawals halted"),
        ("XRP", "Ripple wins SEC lawsuit definitively",
         "Court rules XRP is not a security, price jumps 25%"),
        ("BTC", "Bitcoin pizza day anniversary: community celebrates",
         "Crypto enthusiasts mark the 16th year of the famous pizza transaction"),
    ]

    # Testar com eddie-sentiment via chat API
    correct = 0
    expected = ["BULLISH", "BEARISH", "BEARISH", "BULLISH", "NEUTRAL"]

    for idx, (coin, title, desc) in enumerate(test_cases):
        # Usar a chat API para eddie-sentiment
        payload = json.dumps({
            "model": "eddie-sentiment:latest",
            "messages": [{"role": "user", "content": f"Coin: {coin}\nTitle: {title}\nSummary: {desc}"}],
            "stream": False,
            "options": {"temperature": 0.05, "num_predict": 100},
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_HOST_GPU0}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                text = data.get("message", {}).get("content", "")
                sentiment, confidence, direction, category = _parse_response(text)

                is_correct = direction == expected[idx]
                if is_correct:
                    correct += 1
                icon = "✅" if is_correct else "❌"
                log.info("  %s [%s] %s → %s (exp=%s) s=%.2f c=%.0f%%",
                         icon, coin, title[:45], direction, expected[idx],
                         sentiment, confidence * 100)
        except Exception as e:
            log.error("  ❌ [%s] %s → ERRO: %s", coin, title[:45], e)

    accuracy = correct * 100 // len(test_cases)
    log.info("\n📊 Validação eddie-sentiment: %d/%d (%d%%)", correct, len(test_cases), accuracy)

    if accuracy >= 60:
        log.info("✅ Modelo aprovado para produção.")
    else:
        log.warning("⚠️ Modelo com acurácia baixa. Considere mais dados de treinamento.")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    """Pipeline completo de fine-tuning."""
    start = time.time()

    log.info("🚀 Pipeline de Fine-Tuning eddie-sentiment")
    log.info("   GPU0: %s (primário, phi4-mini warm)  |  GPU1: %s (fallback leve)", OLLAMA_HOST_GPU0, OLLAMA_HOST_GPU1)
    log.info("   Classificador: %s", CLASSIFIER_MODEL)
    log.info("   Dados desde: %s", MIN_DATE)
    log.info("   Database: %s", DATABASE_URL.split("@")[1] if "@" in DATABASE_URL else "configured")

    # Verificar GPUs
    for name, host in [("GPU0", OLLAMA_HOST_GPU0), ("GPU1", OLLAMA_HOST_GPU1)]:
        try:
            req = urllib.request.Request(f"{host}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
                models = [m["name"] for m in data.get("models", [])]
                has_phi = "phi4-mini" in " ".join(models).lower() or "phi4-mini:latest" in models
                log.info("   %s: ✅ online (%d modelos, phi4-mini=%s)", name, len(models), "✅" if has_phi else "❌")
        except Exception as e:
            log.error("   %s: ❌ OFFLINE (%s)", name, e)

    conn = get_db_connection()

    # Etapa 1: Reclassificar existentes
    reclassified = reclassify_existing(conn)

    # Etapa 2: Coletar novos
    new_collected = collect_new_articles(conn)

    # Etapa 3: Relatório + Treino
    report_and_train(conn)

    conn.close()

    # Etapa 4: Validação
    validate_model()

    elapsed = time.time() - start
    log.info("=" * 60)
    log.info("🏁 Pipeline concluído em %.1f minutos", elapsed / 60)
    log.info("   Reclassificados: %d | Novos: %d", reclassified, new_collected)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
