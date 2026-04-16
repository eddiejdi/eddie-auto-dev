#!/usr/bin/env python3
"""Pipeline de Treinamento LLM para Sentimento Cripto via RSS.

Coleta artigos RSS históricos, correlaciona com movimentação real de preço
(btc.candles), gera dataset de treinamento e cria o modelo `trading-sentiment`
no Ollama via API /api/create.

Fluxo:
  1. Coleta RSS → artigos com timestamp
  2. Busca preço BTC no momento T e T+4h (btc.candles)
  3. Calcula Δprice % → label ground-truth (BULLISH/BEARISH/NEUTRAL)
  4. Classifica artigo via Ollama (phi4-mini — GPU0 primário, always warm)
  5. Salva pairs (artigo, sentimento_previsto, variação_real) em btc.training_samples
  6. Seleciona melhores exemplos (alta confiança + label correto)
  7. Gera Modelfile para trading-sentiment com few-shot examples
  8. Cria trading-sentiment:latest via Ollama API /api/create

Uso:
  python3 rss_llm_trainer.py --mode collect    # Coleta e classifica artigos
  python3 rss_llm_trainer.py --mode train      # Gera Modelfile + cria modelo
  python3 rss_llm_trainer.py --mode full       # Coleta + treina
  python3 rss_llm_trainer.py --mode report     # Relatório de acurácia
  python3 rss_llm_trainer.py --mode predict    # Testa modelo trading-sentiment
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
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
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [trainer] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("rss_llm_trainer")

# ── Configuração ───────────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/btc_trading",
)
OLLAMA_HOST_GPU1 = os.environ.get("OLLAMA_HOST_GPU1", "http://192.168.15.2:11435")
OLLAMA_HOST_GPU0 = os.environ.get("OLLAMA_HOST", "http://192.168.15.2:11434")

# Modelo para classificar durante coleta
CLASSIFIER_MODEL = os.environ.get("OLLAMA_CLASSIFIER_MODEL", "phi4-mini")

# Modelo sentimento customizado (resultado do treinamento)
SENTIMENT_MODEL_NAME = "trading-sentiment"
SENTIMENT_MODEL_TAG = "latest"

# Base model para o Modelfile
BASE_MODEL = os.environ.get("OLLAMA_BASE_MODEL", "phi4-mini")

# Limiar de variação de preço para considerar como bullish/bearish
PRICE_CHANGE_THRESHOLD_PCT = float(os.environ.get("PRICE_THRESHOLD_PCT", "1.5"))

# Janela de tempo após artigo para medir impacto no preço
PRICE_IMPACT_HOURS = int(os.environ.get("PRICE_IMPACT_HOURS", "4"))

# Número de exemplos few-shot no Modelfile
MAX_FEW_SHOT_EXAMPLES = int(os.environ.get("MAX_FEW_SHOT_EXAMPLES", "20"))

RSS_FEEDS: List[Dict[str, str]] = [
    {"name": "coindesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "cointelegraph", "url": "https://cointelegraph.com/rss"},
    {"name": "decrypt", "url": "https://decrypt.co/feed"},
    {"name": "cryptonews", "url": "https://cryptonews.com/news/feed/"},
    {"name": "bitcoinmagazine", "url": "https://bitcoinmagazine.com/.rss/full/"},
    {"name": "theblock", "url": "https://www.theblock.co/rss.xml"},
    {"name": "beincrypto", "url": "https://beincrypto.com/feed/"},
]

# Mapeamento coin → symbol no DB
COIN_SYMBOL_MAP: Dict[str, str] = {
    "BTC": "BTC-USDT",
    "ETH": "ETH-USDT",
    "SOL": "SOL-USDT",
    "XRP": "XRP-USDT",
    "DOGE": "DOGE-USDT",
    "ADA": "ADA-USDT",
}

# Pasta de saída para artefatos de treinamento
OUTPUT_DIR = Path(os.environ.get("TRAINING_OUTPUT_DIR", "/tmp/trading-sentiment-training"))


# ── Data Classes ───────────────────────────────────────────────────────────────

@dataclass
class ArticleSample:
    """Representa um artigo RSS com metadados de sentimento e preço."""

    url: str
    title: str
    description: str
    source: str
    published_ts: float  # unix timestamp
    coin: str  # BTC, ETH, etc.
    price_at_publish: Optional[float] = None      # preço no momento do artigo
    price_at_impact: Optional[float] = None       # preço T + PRICE_IMPACT_HOURS
    price_change_pct: Optional[float] = None      # Δ%
    ground_truth_label: Optional[str] = None      # BULLISH/BEARISH/NEUTRAL (real)
    ollama_sentiment: Optional[float] = None      # saída do modelo (-1 a +1)
    ollama_confidence: Optional[float] = None
    ollama_direction: Optional[str] = None        # BULLISH/BEARISH/NEUTRAL
    ollama_category: Optional[str] = None
    prediction_correct: Optional[bool] = None     # ollama_direction == ground_truth_label


@dataclass
class TrainingStats:
    """Estatísticas acumuladas do ciclo de treinamento."""

    total_articles: int = 0
    with_price_data: int = 0
    bullish_correct: int = 0
    bearish_correct: int = 0
    neutral_correct: int = 0
    total_correct: int = 0
    avg_confidence: float = 0.0
    label_distribution: Dict[str, int] = field(default_factory=dict)


# ── Database ───────────────────────────────────────────────────────────────────

def get_db_connection() -> psycopg2.extensions.connection:
    """Conecta ao PostgreSQL e retorna conexão com autocommit ativo."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def ensure_training_table(conn: psycopg2.extensions.connection) -> None:
    """Cria tabela btc.training_samples caso não exista."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS btc.training_samples (
                id             SERIAL PRIMARY KEY,
                created_at     TIMESTAMPTZ DEFAULT NOW(),
                url            TEXT NOT NULL,
                title          TEXT,
                description    TEXT,
                source         VARCHAR(100),
                coin           VARCHAR(20),
                published_ts   BIGINT,
                price_at_pub   FLOAT,
                price_at_impact FLOAT,
                price_change_pct FLOAT,
                ground_truth   VARCHAR(20),
                ollama_sentiment FLOAT,
                ollama_confidence FLOAT,
                ollama_direction VARCHAR(20),
                ollama_category VARCHAR(50),
                prediction_correct BOOLEAN,
                model_version  VARCHAR(100),
                CONSTRAINT uq_training_samples_url UNIQUE(url)
            )
        """)
    log.debug("Tabela btc.training_samples verificada.")


def upsert_sample(
    conn: psycopg2.extensions.connection,
    sample: ArticleSample,
    model_version: str = "phi4-mini",
) -> None:
    """Insere ou atualiza um sample de treinamento."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO btc.training_samples (
                url, title, description, source, coin, published_ts,
                price_at_pub, price_at_impact, price_change_pct, ground_truth,
                ollama_sentiment, ollama_confidence, ollama_direction,
                ollama_category, prediction_correct, model_version
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (url) DO UPDATE SET
                ollama_sentiment    = EXCLUDED.ollama_sentiment,
                ollama_confidence   = EXCLUDED.ollama_confidence,
                ollama_direction    = EXCLUDED.ollama_direction,
                ollama_category     = EXCLUDED.ollama_category,
                ground_truth        = EXCLUDED.ground_truth,
                price_change_pct    = EXCLUDED.price_change_pct,
                prediction_correct  = EXCLUDED.prediction_correct,
                model_version       = EXCLUDED.model_version
        """, (
            sample.url,
            sample.title[:500] if sample.title else None,
            sample.description[:1000] if sample.description else None,
            sample.source,
            sample.coin,
            int(sample.published_ts) if sample.published_ts else None,
            sample.price_at_publish,
            sample.price_at_impact,
            sample.price_change_pct,
            sample.ground_truth_label,
            sample.ollama_sentiment,
            sample.ollama_confidence,
            sample.ollama_direction,
            sample.ollama_category,
            sample.prediction_correct,
            model_version,
        ))


def get_price_at_ts(
    conn: psycopg2.extensions.connection,
    symbol: str,
    ts: float,
    window_min: int = 30,
) -> Optional[float]:
    """Retorna preço de fechamento mais próximo do timestamp dado.

    Args:
        conn: Conexão PostgreSQL.
        symbol: Par (ex.: BTC-USDT).
        ts: Timestamp Unix em SEGUNDOS.
        window_min: Janela de tolerância em minutos.

    Note:
        btc.candles.timestamp está em SEGUNDOS (10 dígitos, ex: 1772652120).
    """
    ts_sec = int(ts)  # garante segundos
    window_sec = window_min * 60

    with conn.cursor() as cur:
        cur.execute("""
            SELECT close
            FROM btc.candles
            WHERE symbol = %s
              AND ABS(timestamp - %s) <= %s
            ORDER BY ABS(timestamp - %s)
            LIMIT 1
        """, (symbol, ts_sec, window_sec, ts_sec))
        row = cur.fetchone()
        return float(row[0]) if row else None


def get_best_training_examples(
    conn: psycopg2.extensions.connection,
    limit: int = MAX_FEW_SHOT_EXAMPLES,
) -> List[Dict]:
    """Retorna os melhores exemplos de treinamento para few-shot.

    Seleciona amostras em que:
    - prediction_correct = TRUE
    - ollama_confidence >= 0.7
    - ground_truth é BULLISH ou BEARISH (exemplos mais úteis)
    """
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT title, description, coin, ground_truth,
                   ollama_sentiment, ollama_confidence, ollama_direction, ollama_category,
                   price_change_pct
            FROM btc.training_samples
            WHERE prediction_correct = TRUE
              AND ollama_confidence >= 0.40
              AND ground_truth IN ('BULLISH', 'BEARISH')
            ORDER BY ABS(ollama_sentiment) DESC, ollama_confidence DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def get_training_stats(conn: psycopg2.extensions.connection) -> TrainingStats:
    """Calcula estatísticas do dataset de treinamento."""
    stats = TrainingStats()

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM btc.training_samples")
        stats.total_articles = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM btc.training_samples WHERE ground_truth IS NOT NULL")
        stats.with_price_data = cur.fetchone()[0] or 0

        cur.execute("""
            SELECT ground_truth, COUNT(*) FROM btc.training_samples
            WHERE ground_truth IS NOT NULL
            GROUP BY ground_truth
        """)
        for row in cur.fetchall():
            stats.label_distribution[row[0]] = row[1]

        cur.execute("""
            SELECT COUNT(*) FROM btc.training_samples
            WHERE prediction_correct = TRUE
        """)
        stats.total_correct = cur.fetchone()[0] or 0

        cur.execute("""
            SELECT AVG(ollama_confidence) FROM btc.training_samples
            WHERE ollama_confidence IS NOT NULL
        """)
        avg_c = cur.fetchone()[0]
        stats.avg_confidence = float(avg_c) if avg_c else 0.0

    return stats


# ── RSS Collection ─────────────────────────────────────────────────────────────

def parse_entry_timestamp(entry: Dict) -> Optional[float]:
    """Extrai timestamp Unix de um entry do feedparser."""
    # feedparser popula `published_parsed` como time.struct_time
    published = getattr(entry, "published_parsed", None) or entry.get("published_parsed")
    if published:
        try:
            return float(datetime(*published[:6], tzinfo=timezone.utc).timestamp())
        except Exception:
            pass

    # Fallback: tentar campo published como string
    pub_str = entry.get("published", "") or entry.get("updated", "")
    if pub_str:
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(pub_str).timestamp()
        except Exception:
            pass

    return None


def detect_primary_coin(title: str, description: str) -> str:
    """Detecta a cripto principal mencionada no artigo."""
    text = f"{title} {description}".lower()
    coin_patterns = {
        "BTC": [r"\b(bitcoin|btc)\b", "₿"],
        "ETH": [r"\b(ethereum|eth|ether)\b"],
        "SOL": [r"\b(solana|sol)\b"],
        "XRP": [r"\b(ripple|xrp)\b"],
        "DOGE": [r"\b(dogecoin|doge)\b"],
        "ADA": [r"\b(cardano|ada)\b"],
    }
    for coin, patterns in coin_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return coin
    return "BTC"  # padrão: BTC é o mais correlacionado


def fetch_rss_feed(feed_url: str, feed_name: str, limit: int = 50) -> List[Dict]:
    """Busca e parseia artigos de um feed RSS.

    Returns:
        Lista de dicts com title, url, description, source, published_ts.
    """
    try:
        parsed = feedparser.parse(feed_url)
        articles = []
        for entry in parsed.entries[:limit]:
            title = (entry.get("title") or "").strip()
            url = (entry.get("link") or entry.get("id") or "").strip()
            if not title or not url:
                continue

            desc = (
                entry.get("description")
                or entry.get("summary")
                or entry.get("content", [{}])[0].get("value", "")
            )
            # Remove HTML tags
            desc = re.sub(r"<[^>]+>", " ", desc or "")
            desc = re.sub(r"\s+", " ", desc).strip()[:600]

            ts = parse_entry_timestamp(entry) or datetime.now(timezone.utc).timestamp()

            articles.append({
                "title": title,
                "url": url,
                "source": feed_name,
                "description": desc,
                "published_ts": ts,
            })

        log.info("Feed %-20s → %3d artigos", feed_name, len(articles))
        return articles

    except Exception as exc:
        log.warning("Erro ao buscar feed %s: %s", feed_name, exc)
        return []


def collect_all_feeds(limit_per_feed: int = 50) -> List[Dict]:
    """Coleta artigos de todos os feeds configurados."""
    articles: List[Dict] = []
    for feed_def in RSS_FEEDS:
        batch = fetch_rss_feed(feed_def["url"], feed_def["name"], limit_per_feed)
        articles.extend(batch)
        time.sleep(1.0)
    # Remove duplicatas por URL
    seen: set = set()
    unique = []
    for a in articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)
    log.info("Total artigos únicos coletados: %d", len(unique))
    return unique


# ── Ollama Communication ───────────────────────────────────────────────────────

def _ollama_request(
    host: str, model: str, prompt: str, timeout: int = 20,
    use_chat_api: bool = False,
) -> Tuple[bool, str]:
    """Faz requisição POST para o Ollama e retorna (success, response_text).

    Args:
        host: URL do Ollama (ex: http://192.168.15.2:11434).
        model: Nome do modelo (ex: trading-sentiment:latest).
        prompt: Texto do prompt.
        timeout: Timeout em segundos.
        use_chat_api: Se True, usa /api/chat com think=false (ideal para modelos
            com system prompt embutido como trading-sentiment).
    """
    if use_chat_api:
        # /api/chat respeita o system prompt e few-shot do Modelfile
        body: Dict = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
        }
        endpoint = "/api/chat"
    else:
        body = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 120,
                "temperature": 0.05,
                "top_p": 0.9,
            },
        }
        endpoint = "/api/generate"

    payload = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        f"{host}{endpoint}",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            if use_chat_api:
                return True, data.get("message", {}).get("content", "").strip()
            return True, data.get("response", "").strip()
    except Exception as exc:
        return False, str(exc)


def classify_with_ollama(title: str, description: str, coin: str) -> Tuple[float, float, str, str]:
    """Classifica sentimento usando GPU0 (phi4-mini always warm) → GPU1 como fallback.

    GPU0 (RTX 2060 8GB) é primário — phi4-mini (~2.5GB) cabe com folga.
    GPU1 (GTX 1050 2GB) é fallback leve — phi4-mini NÃO cabe nesta GPU.

    Returns:
        (sentiment: float, confidence: float, direction: str, category: str)
    """
    prompt = f"""Analyze this crypto news and classify sentiment for trading.
Reply ONLY in this exact format (no extra text, no thinking):
SENTIMENT: <-1.0 to 1.0> | CONFIDENCE: <0.0 to 1.0> | DIRECTION: <BULLISH|BEARISH|NEUTRAL> | CATEGORY: <regulation|adoption|hack|price|macro|defi|technical>

Coin: {coin}
Title: {title}
Summary: {description[:300]}"""

    # Tenta GPU0 primeiro (RTX 2060 — phi4-mini always warm)
    ok, text = _ollama_request(OLLAMA_HOST_GPU0, CLASSIFIER_MODEL, prompt, timeout=30)
    if not ok:
        log.debug("GPU0 falhou, tentando GPU1: %s", text[:60])
        ok, text = _ollama_request(OLLAMA_HOST_GPU1, CLASSIFIER_MODEL, prompt, timeout=15)

    if not ok:
        log.warning("Ambas GPUs falharam. Returning neutral.")
        return 0.0, 0.3, "NEUTRAL", "general"

    return _parse_ollama_response(text)


def _parse_ollama_response(response: str) -> Tuple[float, float, str, str]:
    """Parseia resposta do Ollama no formato padronizado.

    Args:
        response: Texto retornado pelo modelo.
    Returns:
        (sentiment, confidence, direction, category)
    """
    sentiment = 0.0
    confidence = 0.5
    direction = "NEUTRAL"
    category = "general"

    try:
        # Remove thinking tags se presentes (qwen3 pode incluir)
        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
        # Remove </think> residual quando <think> foi consumido no stream
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

    except Exception as exc:
        log.debug("Parse error: %s (response: %s)", exc, response[:120])

    return sentiment, confidence, direction, category


# ── Price Correlation ──────────────────────────────────────────────────────────

def compute_ground_truth(price_at_pub: float, price_at_impact: float) -> str:
    """Computa label ground-truth baseado na variação real de preço.

    Args:
        price_at_pub: Preço no momento da publicação do artigo.
        price_at_impact: Preço após PRICE_IMPACT_HOURS horas.
    Returns:
        'BULLISH', 'BEARISH' ou 'NEUTRAL'
    """
    if price_at_pub <= 0:
        return "NEUTRAL"
    change_pct = ((price_at_impact - price_at_pub) / price_at_pub) * 100
    if change_pct >= PRICE_CHANGE_THRESHOLD_PCT:
        return "BULLISH"
    if change_pct <= -PRICE_CHANGE_THRESHOLD_PCT:
        return "BEARISH"
    return "NEUTRAL"


# ── Collection Mode ────────────────────────────────────────────────────────────

def mode_collect(limit_per_feed: int = 50) -> None:
    """Coleta RSS, classifica com Ollama e correlaciona com preço real.

    Persiste resultados em btc.training_samples.
    """
    log.info("=" * 60)
    log.info("MODO: COLETAR → Feeds RSS + Sentimento + Correlação de Preço")
    log.info("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    articles = collect_all_feeds(limit_per_feed=limit_per_feed)
    if not articles:
        log.error("Nenhum artigo coletado. Verifique conectividade.")
        return

    conn = get_db_connection()
    ensure_training_table(conn)

    impact_seconds = PRICE_IMPACT_HOURS * 3600
    processed = 0
    with_price = 0

    for i, art in enumerate(articles, 1):
        title = art.get("title", "")
        description = art.get("description", "")
        coin = detect_primary_coin(title, description)
        symbol = COIN_SYMBOL_MAP.get(coin, "BTC-USDT")
        pub_ts = art["published_ts"]

        log.info("[%d/%d] %-20s | %s", i, len(articles), art["source"], title[:60])

        sample = ArticleSample(
            url=art["url"],
            title=title,
            description=description,
            source=art["source"],
            published_ts=pub_ts,
            coin=coin,
        )

        # Busca preço no momento da publicação e T+4h
        price_pub = get_price_at_ts(conn, symbol, pub_ts, window_min=60)
        price_impact = get_price_at_ts(conn, symbol, pub_ts + impact_seconds, window_min=60)

        if price_pub and price_impact and price_pub > 0:
            sample.price_at_publish = price_pub
            sample.price_at_impact = price_impact
            sample.price_change_pct = ((price_impact - price_pub) / price_pub) * 100
            sample.ground_truth_label = compute_ground_truth(price_pub, price_impact)
            with_price += 1
            log.info(
                "       Preço: $%.0f → $%.0f (%.2f%%) = %s",
                price_pub, price_impact, sample.price_change_pct, sample.ground_truth_label,
            )
        else:
            log.debug("       Sem dados de preço para ts=%.0f (%s)", pub_ts, symbol)

        # Classifica com Ollama
        sentiment, confidence, direction, category = classify_with_ollama(
            title, description, coin
        )
        sample.ollama_sentiment = sentiment
        sample.ollama_confidence = confidence
        sample.ollama_direction = direction
        sample.ollama_category = category

        # Compara com ground truth se disponível
        if sample.ground_truth_label:
            sample.prediction_correct = (direction == sample.ground_truth_label)
            status = "✅" if sample.prediction_correct else "❌"
            log.info(
                "       Ollama: %s %.2f (%.0f%% conf) → %s | GT: %s %s",
                direction, sentiment, confidence * 100,
                sample.ollama_category,
                sample.ground_truth_label,
                status,
            )

        upsert_sample(conn, sample, model_version=CLASSIFIER_MODEL)
        processed += 1

        # Rate limiting gentil
        time.sleep(0.5)

    conn.close()

    log.info("─" * 60)
    log.info("✅ Coleta concluída: %d artigos | %d com dados de preço", processed, with_price)


# ── Modelfile Generation ───────────────────────────────────────────────────────

# Exemplos base (hardcoded) para garantir mínimo de qualidade
BASE_FEW_SHOT_EXAMPLES: List[Tuple[str, str]] = [
    # (user_message, assistant_message)
    (
        "Coin: BTC\nTitle: SEC approves first spot Bitcoin ETF in the United States\n"
        "Summary: The Securities and Exchange Commission has officially approved the first spot Bitcoin ETF, "
        "opening institutional investors to direct Bitcoin exposure.",
        "SENTIMENT: 0.95 | CONFIDENCE: 0.98 | DIRECTION: BULLISH | CATEGORY: regulation",
    ),
    (
        "Coin: BTC\nTitle: Major cryptocurrency exchange hacked, $500M stolen\n"
        "Summary: A leading exchange suffered a sophisticated security breach, resulting in the theft of "
        "approximately $500 million in various cryptocurrencies.",
        "SENTIMENT: -0.90 | CONFIDENCE: 0.95 | DIRECTION: BEARISH | CATEGORY: hack",
    ),
    (
        "Coin: ETH\nTitle: Ethereum completes successful network upgrade to reduce gas fees\n"
        "Summary: The Ethereum network successfully implemented the latest upgrade, significantly reducing "
        "transaction costs and improving scalability.",
        "SENTIMENT: 0.80 | CONFIDENCE: 0.90 | DIRECTION: BULLISH | CATEGORY: technical",
    ),
    (
        "Coin: BTC\nTitle: China bans all cryptocurrency transactions and mining\n"
        "Summary: Chinese authorities have announced a sweeping ban on all cryptocurrency activities, "
        "including trading and mining operations throughout the country.",
        "SENTIMENT: -0.85 | CONFIDENCE: 0.92 | DIRECTION: BEARISH | CATEGORY: regulation",
    ),
    (
        "Coin: ETH\nTitle: DeFi protocol loses $100M in smart contract exploit\n"
        "Summary: A major decentralized finance protocol lost approximately $100 million following "
        "a sophisticated smart contract vulnerability exploit.",
        "SENTIMENT: -0.75 | CONFIDENCE: 0.88 | DIRECTION: BEARISH | CATEGORY: hack",
    ),
    (
        "Coin: BTC\nTitle: BlackRock increases Bitcoin holdings to $10 billion\n"
        "Summary: Asset management giant BlackRock has significantly increased its Bitcoin position, "
        "now holding over $10 billion in the cryptocurrency.",
        "SENTIMENT: 0.85 | CONFIDENCE: 0.91 | DIRECTION: BULLISH | CATEGORY: adoption",
    ),
    (
        "Coin: BTC\nTitle: Federal Reserve keeps interest rates unchanged\n"
        "Summary: The Federal Reserve decided to maintain current interest rates, citing stable inflation "
        "and employment data, with no indication of near-term changes.",
        "SENTIMENT: 0.10 | CONFIDENCE: 0.55 | DIRECTION: NEUTRAL | CATEGORY: macro",
    ),
    (
        "Coin: SOL\nTitle: Solana network experiences major outage lasting 12 hours\n"
        "Summary: The Solana blockchain went offline for 12 hours following a critical bug, "
        "disrupting thousands of DeFi protocols and NFT platforms.",
        "SENTIMENT: -0.80 | CONFIDENCE: 0.93 | DIRECTION: BEARISH | CATEGORY: technical",
    ),
    (
        "Coin: XRP\nTitle: Ripple wins landmark legal battle against SEC\n"
        "Summary: A federal judge ruled in favor of Ripple Labs in its case against the SEC, "
        "declaring that XRP sold on exchanges is not a security.",
        "SENTIMENT: 0.90 | CONFIDENCE: 0.95 | DIRECTION: BULLISH | CATEGORY: regulation",
    ),
    (
        "Coin: BTC\nTitle: El Salvador expands Bitcoin legal tender law to all private businesses\n"
        "Summary: El Salvador has expanded its Bitcoin legal tender requirements, now mandating "
        "all businesses accept Bitcoin as payment.",
        "SENTIMENT: 0.70 | CONFIDENCE: 0.82 | DIRECTION: BULLISH | CATEGORY: adoption",
    ),
]

SENTIMENT_SYSTEM_PROMPT = """Você é trading-sentiment, especialista em análise de sentimento de mercado para criptomoedas.

Sua função: Analisar notícias de cripto e prever o impacto no preço nas próximas 4 horas.

FORMATO DE RESPOSTA OBRIGATÓRIO (apenas isso, sem texto extra):
SENTIMENT: <-1.0 a +1.0> | CONFIDENCE: <0.0 a 1.0> | DIRECTION: <BULLISH|BEARISH|NEUTRAL> | CATEGORY: <categoria>

ESCALA DE SENTIMENTO:
+0.8 a +1.0 = Extremamente bullish (ETF aprovado, Regulatory win, Institutional adoption)
+0.5 a +0.8 = Bullish (partnerships, upgrades, positive news)
+0.2 a +0.5 = Levemente bullish
-0.2 a +0.2 = Neutro (Fed mantém juros, relatórios neutros)
-0.5 a -0.2 = Levemente bearish
-0.5 a -0.8 = Bearish (restrições regulatórias, problemas técnicos)
-0.8 a -1.0 = Extremamente bearish (hacks, banimentos, crashes)

REGRAS:
- DIRECTION deve ser consistente com SENTIMENT (positivo → BULLISH, negativo → BEARISH)
- CONFIDENCE reflete certeza baseada na clareza da notícia
- CATEGORY: regulation | adoption | hack | price | macro | defi | technical | general
- Ignore ruído de mercado. Foque em fundamentais."""


def generate_modelfile(examples: List[Dict]) -> str:
    """Gera conteúdo do Modelfile para o modelo trading-sentiment.

    Combina exemplos base (hardcoded) com os melhores do DB.
    """
    lines = [
        f"FROM {BASE_MODEL}",
        "",
        f'SYSTEM """{SENTIMENT_SYSTEM_PROMPT}"""',
        "",
        "PARAMETER temperature 0.05",
        "PARAMETER top_p 0.9",
        "PARAMETER num_predict 80",
        "PARAMETER repeat_penalty 1.1",
        "",
        "# ── Few-shot examples base ────────────────────────────────────",
    ]

    # Exemplos hardcoded
    for user_msg, assistant_msg in BASE_FEW_SHOT_EXAMPLES:
        lines.append(f'MESSAGE user """{user_msg}"""')
        lines.append(f'MESSAGE assistant """{assistant_msg}"""')
        lines.append("")

    # Exemplos derivados do DB (calibrados com preço real)
    if examples:
        lines.append("# ── Exemplos calibrados com dados reais de preço ─────────────")
        for ex in examples[:MAX_FEW_SHOT_EXAMPLES]:
            title = (ex.get("title") or "").replace('"""', "'")
            desc = (ex.get("description") or "").replace('"""', "'")[:200]
            coin = ex.get("coin", "BTC")
            gt = ex.get("ground_truth", "NEUTRAL")
            sentiment = ex.get("ollama_sentiment", 0.0)
            confidence = ex.get("ollama_confidence", 0.5)
            direction = ex.get("ollama_direction", "NEUTRAL")
            category = ex.get("ollama_category", "general")
            change = ex.get("price_change_pct", 0.0) or 0.0

            user_msg = f"Coin: {coin}\nTitle: {title}\nSummary: {desc}"
            assistant_msg = (
                f"SENTIMENT: {sentiment:.2f} | CONFIDENCE: {confidence:.2f} | "
                f"DIRECTION: {direction} | CATEGORY: {category}"
            )
            note = f"# Preço real: {change:+.2f}% → {gt}"

            lines.append(note)
            lines.append(f'MESSAGE user """{user_msg}"""')
            lines.append(f'MESSAGE assistant """{assistant_msg}"""')
            lines.append("")

    return "\n".join(lines)


# ── Model Creation via Ollama API ──────────────────────────────────────────────


def _parse_modelfile_to_api_payload(modelfile_content: str, model_full_name: str) -> Dict:
    """Converte conteúdo de Modelfile para payload da API nova do Ollama (>= 0.6).

    A API nova usa: {"model": ..., "from": ..., "system": ...,
                    "messages": [...], "parameters": {...}}
    em vez do campo legado "modelfile".
    """
    import re

    api_payload: Dict = {"model": model_full_name, "stream": True}

    # FROM — modelo base
    m = re.search(r"^FROM\s+(\S+)", modelfile_content, re.MULTILINE)
    if m:
        api_payload["from"] = m.group(1)

    # SYSTEM — bloco triple-quoted
    m = re.search(r'SYSTEM\s+"""(.*?)"""', modelfile_content, re.DOTALL)
    if m:
        api_payload["system"] = m.group(1).strip()

    # PARAMETER — linhas simples
    params: Dict = {}
    for pm in re.finditer(r"^PARAMETER\s+(\w+)\s+(\S+)", modelfile_content, re.MULTILINE):
        key, val = pm.group(1), pm.group(2)
        try:
            params[key] = int(val)
        except ValueError:
            try:
                params[key] = float(val)
            except ValueError:
                params[key] = val
    if params:
        api_payload["parameters"] = params

    # MESSAGE — pares user/assistant triple-quoted
    messages: List[Dict] = []
    for mm in re.finditer(
        r'MESSAGE\s+(user|assistant)\s+"""(.*?)"""', modelfile_content, re.DOTALL
    ):
        messages.append({"role": mm.group(1), "content": mm.group(2).strip()})
    if messages:
        api_payload["messages"] = messages

    return api_payload


def create_ollama_model(modelfile_content: str, target_host: str = OLLAMA_HOST_GPU0) -> bool:
    """Cria modelo customizado via API Ollama /api/create.

    Usa a API nova do Ollama (>= 0.6) com campos "from", "system",
    "messages" e "parameters" em vez do campo legado "modelfile".

    Args:
        modelfile_content: Conteúdo do Modelfile.
        target_host: Host do Ollama onde criar o modelo.
    Returns:
        True se criado com sucesso.
    """
    model_full_name = f"{SENTIMENT_MODEL_NAME}:{SENTIMENT_MODEL_TAG}"
    log.info("Criando modelo %s em %s ...", model_full_name, target_host)

    api_payload = _parse_modelfile_to_api_payload(modelfile_content, model_full_name)
    payload = json.dumps(api_payload).encode("utf-8")

    req = urllib.request.Request(
        f"{target_host}/api/create",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            while True:
                line = resp.readline()
                if not line:
                    break
                try:
                    event = json.loads(line)
                    status = event.get("status", "")
                    if status:
                        log.info("  [create] %s", status)
                    if event.get("error"):
                        log.error("  Erro na criação: %s", event["error"])
                        return False
                except json.JSONDecodeError:
                    pass
        log.info("✅ Modelo %s criado com sucesso!", model_full_name)
        return True

    except urllib.error.URLError as exc:
        log.error("Falha na conexão com Ollama (%s): %s", target_host, exc)
        return False
    except Exception as exc:
        log.error("Erro inesperado ao criar modelo: %s", exc)
        return False


# ── Training Mode ──────────────────────────────────────────────────────────────

def mode_train() -> None:
    """Gera Modelfile com exemplos calibrados e cria trading-sentiment no Ollama."""
    log.info("=" * 60)
    log.info("MODO: TREINAR → Gerar Modelfile + Criar trading-sentiment")
    log.info("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_db_connection()
    ensure_training_table(conn)

    # Busca melhores exemplos do DB
    db_examples = get_best_training_examples(conn, limit=MAX_FEW_SHOT_EXAMPLES)
    stats = get_training_stats(conn)
    conn.close()

    log.info("Dataset: %d amostras | %d com preço | Acurácia: %.1f%%",
             stats.total_articles, stats.with_price_data,
             (stats.total_correct / max(1, stats.with_price_data)) * 100)
    log.info("Exemplos qualificados do DB: %d", len(db_examples))
    log.info("Distribuição: %s", stats.label_distribution)

    # Gera Modelfile
    modelfile_content = generate_modelfile(db_examples)
    modelfile_path = OUTPUT_DIR / "Modelfile.trading-sentiment"
    modelfile_path.write_text(modelfile_content, encoding="utf-8")
    log.info("Modelfile salvo em: %s (%d chars)", modelfile_path, len(modelfile_content))

    # Salva também no diretório do exporter para referência
    local_modelfile = Path(__file__).parent / "Modelfile.trading-sentiment"
    local_modelfile.write_text(modelfile_content, encoding="utf-8")
    log.info("Cópia local do Modelfile: %s", local_modelfile)

    # Cria o modelo no Ollama (tenta GPU0 primeiro para persistência compartilhada)
    success = create_ollama_model(modelfile_content, OLLAMA_HOST_GPU0)
    if not success:
        log.warning("GPU0 falhou, tentando GPU1...")
        success = create_ollama_model(modelfile_content, OLLAMA_HOST_GPU1)

    if success:
        log.info("✅ trading-sentiment:latest disponível para uso!")
        log.info("   Atualize OLLAMA_SENTIMENT_MODEL=trading-sentiment:latest no .env")
    else:
        log.error("❌ Falha ao criar modelo. Modelfile salvo em %s", modelfile_path)
        log.error("   Execute manualmente: ollama create trading-sentiment -f %s", modelfile_path)


# ── Prediction Test Mode ───────────────────────────────────────────────────────

def mode_predict() -> None:
    """Testa o modelo trading-sentiment com artigos de exemplo."""
    log.info("=" * 60)
    log.info("MODO: PREDICT → Testar trading-sentiment:latest")
    log.info("=" * 60)

    test_news = [
        {
            "coin": "BTC",
            "title": "Bitcoin surges 15% as institutional demand hits record high",
            "description": "Major hedge funds and pension funds have increased Bitcoin allocations to all-time highs.",
        },
        {
            "coin": "ETH",
            "title": "Ethereum upgrade causes network instability and failed transactions",
            "description": "Users report widespread failed transactions and high fees following the latest protocol upgrade.",
        },
        {
            "coin": "XRP",
            "title": "G20 nations agree on unified cryptocurrency regulation framework",
            "description": "Leaders from G20 nations agreed to implement consistent global crypto regulations.",
        },
        {
            "coin": "BTC",
            "title": "Bitcoin pizza day anniversary: community celebrates",
            "description": "The crypto community celebrates the 15th anniversary of the first Bitcoin transaction for pizza.",
        },
    ]

    model_name = f"{SENTIMENT_MODEL_NAME}:{SENTIMENT_MODEL_TAG}"
    is_specialized_model = SENTIMENT_MODEL_NAME in model_name
    log.info("Usando modelo: %s (chat_api=%s)", model_name, is_specialized_model)

    for news in test_news:
        prompt = f"Coin: {news['coin']}\nTitle: {news['title']}\nSummary: {news['description']}"

        # Tenta com trading-sentiment via chat API, depois fallback
        ok, text = _ollama_request(OLLAMA_HOST_GPU0, model_name, prompt, timeout=20, use_chat_api=is_specialized_model)
        if not ok:
            ok, text = _ollama_request(OLLAMA_HOST_GPU1, model_name, prompt, timeout=20, use_chat_api=is_specialized_model)

        if ok:
            sentiment, confidence, direction, category = _parse_ollama_response(text)
            icon = "🟢" if direction == "BULLISH" else ("🔴" if direction == "BEARISH" else "⚪")
            log.info(
                "%s [%s] %s\n       → %s %.2f (conf: %.0f%%) [%s]\n       raw: %s",
                icon, news["coin"], news["title"][:60],
                direction, sentiment, confidence * 100, category,
                text[:100],
            )
        else:
            log.warning("Falha ao classificar: %s", news["title"][:60])

        time.sleep(0.5)


# ── Report Mode ────────────────────────────────────────────────────────────────

def mode_report() -> None:
    """Exibe relatório detalhado do dataset de treinamento."""
    log.info("=" * 60)
    log.info("MODO: RELATÓRIO → Estatísticas do Dataset")
    log.info("=" * 60)

    conn = get_db_connection()
    ensure_training_table(conn)
    stats = get_training_stats(conn)

    accuracy_pct = (stats.total_correct / max(1, stats.with_price_data)) * 100

    log.info("📊 DATASET DE TREINAMENTO — btc.training_samples")
    log.info("─" * 50)
    log.info("  Total de artigos classificados  : %d", stats.total_articles)
    log.info("  Com correlação de preço         : %d", stats.with_price_data)
    log.info("  Predições corretas              : %d (%.1f%%)", stats.total_correct, accuracy_pct)
    log.info("  Confiança média do Ollama       : %.0f%%", stats.avg_confidence * 100)
    log.info("")
    log.info("  Distribuição de labels (ground-truth):")
    total_labeled = sum(stats.label_distribution.values())
    for label, count in sorted(stats.label_distribution.items()):
        pct = (count / max(1, total_labeled)) * 100
        log.info("    %s: %d (%.1f%%)", label, count, pct)

    # Amostras recentes
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT title, coin, ground_truth, ollama_direction,
                   ollama_sentiment, price_change_pct, prediction_correct
            FROM btc.training_samples
            WHERE ground_truth IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 10
        """)
        rows = cur.fetchall()

    conn.close()

    if rows:
        log.info("")
        log.info("  Últimas 10 amostras com preço:")
        for row in rows:
            ok = "✅" if row["prediction_correct"] else "❌"
            log.info(
                "    %s [%s] %s → GT:%s | Ollama:%s (%.2f) | Δprice:%.2f%%",
                ok, row["coin"], (row["title"] or "")[:50],
                row["ground_truth"], row["ollama_direction"],
                row["ollama_sentiment"] or 0.0,
                row["price_change_pct"] or 0.0,
            )

    # Salva JSON report
    report = {
        "total_articles": stats.total_articles,
        "with_price_data": stats.with_price_data,
        "accuracy_pct": round(accuracy_pct, 2),
        "avg_confidence_pct": round(stats.avg_confidence * 100, 2),
        "label_distribution": stats.label_distribution,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    report_path = OUTPUT_DIR / "training_report.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    log.info("  Relatório salvo em: %s", report_path)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    """Ponto de entrada do trainer."""
    parser = argparse.ArgumentParser(
        description="Treinamento LLM trading-sentiment para sentimento cripto via RSS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Exemplos:
  python3 rss_llm_trainer.py --mode collect --feeds 100
  python3 rss_llm_trainer.py --mode train
  python3 rss_llm_trainer.py --mode full --feeds 200
  python3 rss_llm_trainer.py --mode report
  python3 rss_llm_trainer.py --mode predict
""",
    )
    parser.add_argument(
        "--mode",
        choices=["collect", "train", "full", "report", "predict"],
        default="full",
        help="Modo de operação (default: full)",
    )
    parser.add_argument(
        "--feeds",
        type=int,
        default=50,
        help="Artigos por feed (modo collect/full, default: 50)",
    )
    args = parser.parse_args()

    log.info("🚀 RSS LLM Trainer — GPU1=%s (rápido) | GPU0=%s (fallback) | Classifier=%s",
             OLLAMA_HOST_GPU1, OLLAMA_HOST_GPU0, CLASSIFIER_MODEL)

    if args.mode == "collect":
        mode_collect(limit_per_feed=args.feeds)
    elif args.mode == "train":
        mode_train()
    elif args.mode == "full":
        mode_collect(limit_per_feed=args.feeds)
        mode_train()
    elif args.mode == "report":
        mode_report()
    elif args.mode == "predict":
        mode_predict()


if __name__ == "__main__":
    main()
