#!/usr/bin/env python3
"""Prometheus exporter de sentimento de notícias crypto via RSS feeds.

Coleta notícias dos principais portais crypto via RSS, classifica sentimento
usando Ollama local (GPU1), persiste em PostgreSQL e expõe métricas Prometheus
para integração com o ensemble do Trading Agent e dashboards Grafana.

Usage:
  python3 rss_sentiment_exporter.py --port 9122
  python3 rss_sentiment_exporter.py --port 9122 --interval 300 --window 4

Metrics:
  btc_news_sentiment{coin}         — sentimento médio ponderado (janela configurável)
  btc_news_count{coin}             — contagem de notícias na janela
  btc_news_bullish_pct{coin}       — % notícias bullish (>0.3)
  btc_news_bearish_pct{coin}       — % notícias bearish (<-0.3)
  btc_news_latest_sentiment{coin}  — sentimento da notícia mais recente
  btc_news_confidence{coin}        — confiança média do classificador
  btc_news_fetch_errors_total      — counter de erros de fetch RSS
  btc_news_articles_processed_total — counter de artigos processados com sucesso

Systemd service: rss-sentiment-exporter.service
Ollama integration: GPU1 (:11435) para classificação leve de sentimento
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import signal
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

try:
    from prometheus_client import Counter, Gauge, start_http_server
    HAS_PROM = True
except ImportError:
    HAS_PROM = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [rss-sentiment] %(message)s",
)
log = logging.getLogger("rss-sentiment")

# ── Configuração ───────────────────────────────────────────────────────

OLLAMA_HOST_GPU1 = os.environ.get(
    "OLLAMA_HOST_GPU1", "http://192.168.15.2:11435"
)
OLLAMA_HOST_GPU0 = os.environ.get(
    "OLLAMA_HOST", "http://192.168.15.2:11434"
)
OLLAMA_SENTIMENT_MODEL = os.environ.get(
    "OLLAMA_SENTIMENT_MODEL", "eddie-sentiment:latest"
)
# Modelo de fallback caso eddie-sentiment ainda não tenha sido treinado
OLLAMA_FALLBACK_MODEL = os.environ.get(
    "OLLAMA_FALLBACK_MODEL", "qwen3:1.7b"
)
PG_DSN = os.environ.get(
    "DATABASE_URL",
    ""
)
FETCH_INTERVAL = int(os.environ.get("RSS_FETCH_INTERVAL", "300"))  # 5 min
SENTIMENT_WINDOW_HOURS = int(os.environ.get("RSS_SENTIMENT_WINDOW", "4"))

# Moedas monitoradas pelo trading agent
TRACKED_COINS = ["BTC", "ETH", "XRP", "SOL", "DOGE", "ADA"]

# ── RSS Feed Definitions ──────────────────────────────────────────────

RSS_FEEDS: List[Dict[str, str]] = [
    {"name": "coindesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "cointelegraph", "url": "https://cointelegraph.com/rss"},
    {"name": "decrypt", "url": "https://decrypt.co/feed"},
    {"name": "bitcoinmagazine", "url": "https://bitcoinmagazine.com/.rss/full/"},
    {"name": "cryptonews", "url": "https://cryptonews.com/news/feed/"},
    {"name": "theblock", "url": "https://www.theblock.co/rss.xml"},
]

# ── Coin Detection ─────────────────────────────────────────────────────

# Padrões regex para detectar menções a moedas no texto
COIN_PATTERNS: Dict[str, re.Pattern] = {
    "BTC": re.compile(
        r"\b(bitcoin|btc)\b|₿", re.IGNORECASE
    ),
    "ETH": re.compile(
        r"\b(ethereum|ether|eth)\b", re.IGNORECASE
    ),
    "XRP": re.compile(
        r"\b(xrp|ripple)\b", re.IGNORECASE
    ),
    "SOL": re.compile(
        r"\b(solana|sol)\b", re.IGNORECASE
    ),
    "DOGE": re.compile(
        r"\b(dogecoin|doge)\b", re.IGNORECASE
    ),
    "ADA": re.compile(
        r"\b(cardano|ada)\b", re.IGNORECASE
    ),
}

# Palavras-chave gerais crypto (notícia sem menção a moeda específica)
GENERAL_CRYPTO_PATTERN = re.compile(
    r"\b(crypto|cryptocurrency|blockchain|defi|stablecoin|altcoin|nft|web3"
    r"|exchange|mining|halving|etf|sec|regulation)\b",
    re.IGNORECASE,
)


@dataclass
class NewsArticle:
    """Representa um artigo de notícia RSS."""

    title: str
    url: str
    source: str
    published: datetime
    description: str = ""
    coins: List[str] = None

    def __post_init__(self) -> None:
        """Inicializa lista de moedas se não fornecida."""
        if self.coins is None:
            self.coins = []


@dataclass
class SentimentResult:
    """Resultado da classificação de sentimento."""

    sentiment: float = 0.0  # -1.0 a 1.0
    confidence: float = 0.0  # 0.0 a 1.0
    category: str = "general"  # regulation, adoption, hack, price, macro, defi


# ── Coin Detection ─────────────────────────────────────────────────────


def detect_coins(text: str) -> List[str]:
    """Detecta moedas mencionadas no texto.

    Retorna lista de symbols encontrados (ex: ['BTC', 'ETH']).
    Se nenhuma moeda específica for encontrada mas o texto menciona
    termos crypto genéricos, retorna ['GENERAL'].
    """
    found: List[str] = []
    for coin, pattern in COIN_PATTERNS.items():
        if pattern.search(text):
            found.append(coin)
    if not found and GENERAL_CRYPTO_PATTERN.search(text):
        found.append("GENERAL")
    return found


# ── RSS Fetching ───────────────────────────────────────────────────────


def fetch_rss_feed(feed_url: str, feed_name: str) -> List[NewsArticle]:
    """Busca e parseia um feed RSS retornando lista de artigos.

    Requer feedparser instalado. Retorna lista vazia em caso de erro.
    """
    if not HAS_FEEDPARSER:
        log.error("feedparser não instalado — pip install feedparser")
        return []

    try:
        feed = feedparser.parse(feed_url)
        if feed.bozo and not feed.entries:
            log.warning("Feed %s retornou erro: %s", feed_name, feed.bozo_exception)
            return []

        articles: List[NewsArticle] = []
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            if not title or not url:
                continue

            description = entry.get("description", "") or entry.get("summary", "")
            # Limpar HTML básico
            description = re.sub(r"<[^>]+>", " ", description)
            description = re.sub(r"\s+", " ", description).strip()[:1000]

            # Parsear data de publicação
            pub_date = _parse_date(entry)

            # Detectar moedas
            combined_text = f"{title} {description}"
            coins = detect_coins(combined_text)

            if coins:  # Só processar se relevante para crypto
                articles.append(
                    NewsArticle(
                        title=title,
                        url=url,
                        source=feed_name,
                        published=pub_date,
                        description=description[:500],
                        coins=coins,
                    )
                )
        return articles

    except Exception as e:
        log.error("Erro ao buscar feed %s: %s", feed_name, e)
        return []


def _parse_date(entry: dict) -> datetime:
    """Parseia data de publicação de um entry RSS."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime(
                    *parsed[:6], tzinfo=timezone.utc
                )
            except (ValueError, TypeError):
                continue
    return datetime.now(timezone.utc)


def fetch_all_feeds() -> List[NewsArticle]:
    """Busca todos os feeds RSS configurados e retorna artigos consolidados."""
    all_articles: List[NewsArticle] = []
    for feed_def in RSS_FEEDS:
        articles = fetch_rss_feed(feed_def["url"], feed_def["name"])
        all_articles.extend(articles)
        log.info("Feed %s: %d artigos relevantes", feed_def["name"], len(articles))
    return all_articles


# ── Ollama Sentiment Classification ───────────────────────────────────

# Prompt para eddie-sentiment (modelo especializado) e modelos genéricos
# Formato: SENTIMENT | CONFIDENCE | DIRECTION | CATEGORY
SENTIMENT_PROMPT_TEMPLATE = """Coin: {coin}
Title: {title}
Summary: {description}"""

# Prompt completo para modelos genéricos sem system prompt especializado
SENTIMENT_GENERIC_PROMPT = """Classify the sentiment of this cryptocurrency news for trading (next 4h price direction).

Reply ONLY in this exact format (no extra text, no thinking):
SENTIMENT: <-1.0 to 1.0> | CONFIDENCE: <0.0 to 1.0> | DIRECTION: <BULLISH|BEARISH|NEUTRAL> | CATEGORY: <regulation|adoption|hack|price|macro|defi|technical>

Coin: {coin}
Title: {title}
Summary: {description}"""


def classify_sentiment_ollama(
    article: NewsArticle,
    ollama_host: str = OLLAMA_HOST_GPU1,
    model: str = OLLAMA_SENTIMENT_MODEL,
) -> SentimentResult:
    """Classifica sentimento de um artigo usando Ollama local.

    Fluxo de fallback inteligente:
    1. Tenta GPU1 (10s timeout) com eddie-sentiment:latest
    2. Se GPU1 falhar → GPU0 (30s timeout) com eddie-sentiment:latest
    3. Se eddie-sentiment não existir → repete com OLLAMA_FALLBACK_MODEL
    4. Se tudo falhar → SentimentResult neutro
    """
    coin = _detect_primary_coin(article.title, article.description)

    # eddie-sentiment usa prompt compacto (tem system prompt built-in)
    # modelos genéricos usam prompt completo com instruções
    is_eddie = "eddie-sentiment" in model
    if is_eddie:
        prompt = SENTIMENT_PROMPT_TEMPLATE.format(
            coin=coin,
            title=article.title,
            description=article.description[:500],
        )
    else:
        prompt = SENTIMENT_GENERIC_PROMPT.format(
            coin=coin,
            title=article.title,
            description=article.description[:500],
        )

    # Tenta GPU1 com timeout curto (10s)
    success, response, gpu_used = _query_ollama_with_timeout(
        ollama_host, model, prompt, timeout=10, gpu_name="GPU1"
    )
    if success and response:
        log.info("✅ [%s] Classificação via %s/%s", article.source[:15], gpu_used, model)
        return _parse_sentiment_response(response)

    # GPU1 falhou/timeout — tenta GPU0 com timeout maior (30s)
    log.warning("GPU1 indisponível para %s, tentando GPU0...", article.title[:60])
    success, response, gpu_used = _query_ollama_with_timeout(
        OLLAMA_HOST_GPU0, model, prompt, timeout=30, gpu_name="GPU0"
    )
    if success and response:
        log.info("✅ [%s] Classificação via GPU0/%s", article.source[:15], model)
        return _parse_sentiment_response(response)

    # eddie-sentiment não disponível — tenta modelo de fallback genérico
    if "eddie-sentiment" in model:
        log.warning(
            "eddie-sentiment não disponível. Executar 'python3 rss_llm_trainer.py --mode train' "
            "para criar o modelo. Usando fallback: %s",
            OLLAMA_FALLBACK_MODEL,
        )
        fallback_prompt = SENTIMENT_GENERIC_PROMPT.format(
            coin=coin,
            title=article.title,
            description=article.description[:500],
        )
        ok1, resp1, g1 = _query_ollama_with_timeout(
            OLLAMA_HOST_GPU1, OLLAMA_FALLBACK_MODEL, fallback_prompt, timeout=15, gpu_name="GPU1-fb"
        )
        if ok1 and resp1:
            log.info("✅ [%s] Fallback via %s/%s", article.source[:15], g1, OLLAMA_FALLBACK_MODEL)
            return _parse_sentiment_response(resp1)
        ok2, resp2, g2 = _query_ollama_with_timeout(
            OLLAMA_HOST_GPU0, OLLAMA_FALLBACK_MODEL, fallback_prompt, timeout=30, gpu_name="GPU0-fb"
        )
        if ok2 and resp2:
            log.info("✅ [%s] Fallback via %s/%s", article.source[:15], g2, OLLAMA_FALLBACK_MODEL)
            return _parse_sentiment_response(resp2)

    log.error("❌ Todas as GPUs/modelos falharam para: %s", article.title[:80])
    return SentimentResult()


def _detect_primary_coin(title: str, description: str) -> str:
    """Detecta a criptomoeda principal mencionada no texto."""
    text = f"{title} {description}".lower()
    patterns = {
        "BTC": [r"\b(bitcoin|btc)\b", "₿"],
        "ETH": [r"\b(ethereum|eth|ether)\b"],
        "SOL": [r"\b(solana|sol)\b"],
        "XRP": [r"\b(ripple|xrp)\b"],
        "DOGE": [r"\b(dogecoin|doge)\b"],
        "ADA": [r"\b(cardano|ada)\b"],
    }
    for coin, pats in patterns.items():
        for p in pats:
            if re.search(p, text, re.IGNORECASE):
                return coin
    return "BTC"


def _query_ollama_with_timeout(
    host: str, model: str, prompt: str, timeout: int = 30, gpu_name: str = "GPU?"
) -> Tuple[bool, str, str]:
    """Envia prompt ao Ollama com timeout configurável.

    Retorna (success, response_text, gpu_used_name).
    """
    try:
        req_data = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "3600s",
            "options": {
                "num_predict": 64,
                "temperature": 0.1,
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{host}/api/generate",
            data=req_data,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
            response_text = result.get("response", "").strip()
            return True, response_text, gpu_name

    except urllib.error.URLError as e:
        log.debug("Conexão recusada em %s (%s): %s", host, gpu_name, e.reason)
        return False, "", gpu_name
    except socket.timeout:
        log.warning("%s timed out após %ds", gpu_name, timeout)
        return False, "", gpu_name
    except Exception as e:
        log.debug("Ollama query em %s (%s) falhou: %s", host, gpu_name, e)
        return False, "", gpu_name


def _query_ollama(host: str, model: str, prompt: str) -> Tuple[bool, str]:
    """Envia prompt ao Ollama e retorna (success, response_text).

    Versão legada para compatibilidade. Use _query_ollama_with_timeout em novo código.
    """
    success, response, _ = _query_ollama_with_timeout(host, model, prompt, timeout=30)
    return success, response


def _parse_sentiment_response(response: str) -> SentimentResult:
    """Parseia resposta do Ollama no formato padronizado.

    Formato esperado:
    SENTIMENT: <n> | CONFIDENCE: <n> | DIRECTION: <word> | CATEGORY: <word>

    Compatível com o formato do eddie-sentiment e com modelos genéricos.
    Remove tags <think>...</think> do qwen3 antes de parsear.
    """
    result = SentimentResult()

    try:
        # Remove thinking tags (qwen3 pode incluir)
        clean = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
        if not clean:
            clean = response  # fallback se todo o conteúdo era thinking

        # Extrair sentimento
        sent_match = re.search(r"SENTIMENT:\s*([-+]?\d*\.?\d+)", clean, re.IGNORECASE)
        if sent_match:
            result.sentiment = max(-1.0, min(1.0, float(sent_match.group(1))))

        # Extrair confiança
        conf_match = re.search(r"CONFIDENCE:\s*([-+]?\d*\.?\d+)", clean, re.IGNORECASE)
        if conf_match:
            result.confidence = max(0.0, min(1.0, float(conf_match.group(1))))

        # DIRECTION (campo adicionado pelo eddie-sentiment) — atualiza sentimento se inconsistente
        dir_match = re.search(r"DIRECTION:\s*(BULLISH|BEARISH|NEUTRAL)", clean, re.IGNORECASE)
        if dir_match:
            direction = dir_match.group(1).upper()
            # Garante consistência: se DIRECTION e SENTIMENT discordarem, ajusta sinal
            if direction == "BULLISH" and result.sentiment < 0:
                result.sentiment = abs(result.sentiment)
            elif direction == "BEARISH" and result.sentiment > 0:
                result.sentiment = -abs(result.sentiment)

        # Extrair categoria
        cat_match = re.search(r"CATEGORY:\s*(\w+)", clean, re.IGNORECASE)
        valid_categories = {
            "regulation", "adoption", "hack", "price", "macro", "defi", "technical", "general",
        }
        if cat_match and cat_match.group(1).lower() in valid_categories:
            result.category = cat_match.group(1).lower()

    except (ValueError, AttributeError) as exc:
        log.warning("Erro ao parsear resposta Ollama: %s — response: %s", exc, response[:200])

    return result


# ── PostgreSQL Persistence ─────────────────────────────────────────────


class NewsDatabase:
    """Gerencia persistência de notícias e sentimento no PostgreSQL."""

    def __init__(self, dsn: str) -> None:
        """Inicializa conexão com o banco de dados."""
        self.dsn = dsn
        self._conn: Optional[psycopg2.extensions.connection] = None

    def _get_conn(self) -> psycopg2.extensions.connection:
        """Retorna conexão ativa, reconectando se necessário."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.dsn)
            self._conn.autocommit = True
        return self._conn

    def ensure_table(self) -> None:
        """Cria tabela btc.news_sentiment se não existir."""
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("SET search_path TO btc;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS btc.news_sentiment (
                    id              SERIAL PRIMARY KEY,
                    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    source          VARCHAR(50) NOT NULL,
                    title           TEXT NOT NULL,
                    url             TEXT NOT NULL,
                    coin            VARCHAR(10) NOT NULL,
                    sentiment       FLOAT NOT NULL DEFAULT 0.0,
                    confidence      FLOAT NOT NULL DEFAULT 0.0,
                    category        VARCHAR(50),
                    summary         TEXT,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_news_url_coin UNIQUE (url, coin)
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_news_sentiment_coin_ts
                    ON btc.news_sentiment (coin, timestamp DESC);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_news_sentiment_ts
                    ON btc.news_sentiment (timestamp DESC);
            """)
        log.info("Tabela btc.news_sentiment verificada/criada.")

    def url_exists(self, url: str, coin: str) -> bool:
        """Verifica se URL+coin já foi processada (deduplicação)."""
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM btc.news_sentiment WHERE url = %s AND coin = %s LIMIT 1",
                    (url, coin),
                )
                return cur.fetchone() is not None
        except Exception as e:
            log.warning("Erro ao verificar URL: %s", e)
            return False

    def insert_sentiment(
        self,
        article: NewsArticle,
        coin: str,
        result: SentimentResult,
    ) -> bool:
        """Insere registro de sentimento no banco. Retorna True se inserido."""
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO btc.news_sentiment
                        (timestamp, source, title, url, coin, sentiment,
                         confidence, category, summary)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (url, coin) DO NOTHING
                    """,
                    (
                        article.published,
                        article.source,
                        article.title[:500],
                        article.url,
                        coin,
                        result.sentiment,
                        result.confidence,
                        result.category,
                        article.description[:500],
                    ),
                )
                return cur.rowcount > 0
        except Exception as e:
            log.error("Erro ao inserir sentimento: %s", e)
            self._conn = None  # forçar reconexão
            return False

    def get_sentiment_stats(
        self, coin: str, window_hours: int = SENTIMENT_WINDOW_HOURS
    ) -> Dict:
        """Calcula estatísticas de sentimento para uma moeda na janela de tempo.

        Retorna dict com: avg_sentiment, count, bullish_pct, bearish_pct,
        avg_confidence, latest_sentiment.
        """
        defaults = {
            "avg_sentiment": 0.0,
            "count": 0,
            "bullish_pct": 0.0,
            "bearish_pct": 0.0,
            "avg_confidence": 0.0,
            "latest_sentiment": 0.0,
        }
        try:
            conn = self._get_conn()
            cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
            with conn.cursor() as cur:
                # Estatísticas agregadas
                cur.execute(
                    """SELECT
                        COALESCE(AVG(sentiment), 0.0),
                        COUNT(*),
                        COALESCE(AVG(confidence), 0.0),
                        COALESCE(
                            100.0 * COUNT(*) FILTER (WHERE sentiment > 0.3) / NULLIF(COUNT(*), 0),
                            0.0
                        ),
                        COALESCE(
                            100.0 * COUNT(*) FILTER (WHERE sentiment < -0.3) / NULLIF(COUNT(*), 0),
                            0.0
                        )
                       FROM btc.news_sentiment
                       WHERE coin = %s AND timestamp >= %s
                    """,
                    (coin, cutoff),
                )
                row = cur.fetchone()
                if row:
                    defaults["avg_sentiment"] = float(row[0])
                    defaults["count"] = int(row[1])
                    defaults["avg_confidence"] = float(row[2])
                    defaults["bullish_pct"] = float(row[3])
                    defaults["bearish_pct"] = float(row[4])

                # Sentimento mais recente
                cur.execute(
                    """SELECT sentiment FROM btc.news_sentiment
                       WHERE coin = %s
                       ORDER BY timestamp DESC LIMIT 1
                    """,
                    (coin,),
                )
                latest = cur.fetchone()
                if latest:
                    defaults["latest_sentiment"] = float(latest[0])

        except Exception as e:
            log.error("Erro ao buscar stats de sentimento para %s: %s", coin, e)
            self._conn = None
        return defaults


# ── Prometheus Metrics ─────────────────────────────────────────────────


def setup_prometheus_metrics() -> Optional[Dict]:
    """Cria objetos de métricas Prometheus."""
    if not HAS_PROM:
        return None

    metrics = {
        "sentiment": Gauge(
            "btc_news_sentiment",
            "Sentimento médio ponderado de notícias crypto (janela configurável)",
            ["coin"],
        ),
        "count": Gauge(
            "btc_news_count",
            "Contagem de notícias na janela de tempo",
            ["coin"],
        ),
        "bullish_pct": Gauge(
            "btc_news_bullish_pct",
            "Percentual de notícias bullish (sentiment > 0.3)",
            ["coin"],
        ),
        "bearish_pct": Gauge(
            "btc_news_bearish_pct",
            "Percentual de notícias bearish (sentiment < -0.3)",
            ["coin"],
        ),
        "latest_sentiment": Gauge(
            "btc_news_latest_sentiment",
            "Sentimento da notícia mais recente",
            ["coin"],
        ),
        "confidence": Gauge(
            "btc_news_confidence",
            "Confiança média do classificador",
            ["coin"],
        ),
        "fetch_errors": Counter(
            "btc_news_fetch_errors_total",
            "Total de erros ao buscar feeds RSS",
        ),
        "articles_processed": Counter(
            "btc_news_articles_processed_total",
            "Total de artigos processados com sucesso",
        ),
    }
    return metrics


def update_prometheus_metrics(
    db: NewsDatabase,
    metrics: Optional[Dict],
    coins: List[str],
) -> None:
    """Atualiza métricas Prometheus com dados do banco."""
    if not metrics:
        return
    all_coins = coins + ["GENERAL"]
    for coin in all_coins:
        stats = db.get_sentiment_stats(coin)
        metrics["sentiment"].labels(coin=coin).set(stats["avg_sentiment"])
        metrics["count"].labels(coin=coin).set(stats["count"])
        metrics["bullish_pct"].labels(coin=coin).set(stats["bullish_pct"])
        metrics["bearish_pct"].labels(coin=coin).set(stats["bearish_pct"])
        metrics["latest_sentiment"].labels(coin=coin).set(stats["latest_sentiment"])
        metrics["confidence"].labels(coin=coin).set(stats["avg_confidence"])


# ── Main Processing Pipeline ──────────────────────────────────────────


def process_articles(
    articles: List[NewsArticle],
    db: Optional[NewsDatabase],
    metrics: Optional[Dict],
) -> int:
    """Processa lista de artigos: deduplicação → classificação → persistência.

    Retorna número de artigos novos processados.
    """
    new_count = 0

    for article in articles:
        for coin in article.coins:
            # Deduplicação
            if db and db.url_exists(article.url, coin):
                continue

            # Classificação de sentimento via Ollama
            result = classify_sentiment_ollama(article)

            log.info(
                "📰 [%s] %s → sent=%.2f conf=%.2f cat=%s | %s",
                coin,
                article.source,
                result.sentiment,
                result.confidence,
                result.category,
                article.title[:80],
            )

            # Persistir
            if db:
                inserted = db.insert_sentiment(article, coin, result)
                if inserted:
                    new_count += 1
                    if metrics:
                        metrics["articles_processed"].inc()
            else:
                new_count += 1
                if metrics:
                    metrics["articles_processed"].inc()

            # Pequena pausa entre classificações para não sobrecarregar Ollama
            time.sleep(0.5)

    return new_count


# ── Main Loop ──────────────────────────────────────────────────────────


def main() -> None:
    """Loop principal do RSS Sentiment Exporter."""
    parser = argparse.ArgumentParser(
        description="RSS Sentiment Exporter — notícias crypto → Prometheus"
    )
    parser.add_argument(
        "--port", type=int, default=9122, help="Porta do Prometheus metrics"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=FETCH_INTERVAL,
        help="Intervalo entre coletas em segundos (default: 300)",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=SENTIMENT_WINDOW_HOURS,
        help="Janela de agregação em horas (default: 4)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Não persiste no banco, só mostra no log",
    )
    args = parser.parse_args()

    # Validações
    if not HAS_FEEDPARSER:
        log.error("feedparser não instalado. Execute: pip install feedparser")
        sys.exit(1)

    if not args.dry_run and not PG_DSN:
        log.error(
            "DATABASE_URL não definido. Defina a variável de ambiente ou use --dry-run"
        )
        sys.exit(1)

    # Inicializar DB
    db: Optional[NewsDatabase] = None
    if not args.dry_run and HAS_PSYCOPG2 and PG_DSN:
        try:
            db = NewsDatabase(PG_DSN)
            db.ensure_table()
        except Exception as e:
            log.error("Erro ao conectar ao PostgreSQL: %s", e)
            sys.exit(1)

    # Prometheus
    prom_metrics: Optional[Dict] = None
    if HAS_PROM:
        prom_metrics = setup_prometheus_metrics()
        start_http_server(args.port)
        log.info("Prometheus metrics em :%d", args.port)
    else:
        log.warning("prometheus_client não instalado — métricas desabilitadas")

    # Signal handling
    running = True

    def shutdown(sig: int, frame: object) -> None:
        nonlocal running
        log.info("Encerrando (signal %s)...", sig)
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log.info(
        "Iniciando RSS Sentiment Exporter (interval=%ds, window=%dh, dry_run=%s)",
        args.interval,
        args.window,
        args.dry_run,
    )
    log.info("Feeds: %s", [f["name"] for f in RSS_FEEDS])
    log.info("Moedas monitoradas: %s", TRACKED_COINS)
    log.info(
        "Ollama: GPU1=%s GPU0=%s model=%s",
        OLLAMA_HOST_GPU1,
        OLLAMA_HOST_GPU0,
        OLLAMA_SENTIMENT_MODEL,
    )

    while running:
        try:
            # 1. Buscar todos os feeds
            articles = fetch_all_feeds()
            log.info("Total de artigos coletados: %d", len(articles))

            # 2. Processar (deduplica + classifica + persiste)
            new_count = process_articles(articles, db, prom_metrics)
            log.info("Artigos novos processados: %d", new_count)

            # 3. Atualizar métricas Prometheus
            if db and prom_metrics:
                update_prometheus_metrics(db, prom_metrics, TRACKED_COINS)

        except Exception as e:
            log.error("Erro no loop principal: %s", e)
            if prom_metrics:
                prom_metrics["fetch_errors"].inc()

        # Aguardar próximo ciclo
        for _ in range(args.interval):
            if not running:
                break
            time.sleep(1)

    log.info("Shutdown completo.")


if __name__ == "__main__":
    main()
