#!/usr/bin/env python3
"""Testes unitários para o RSS Sentiment Exporter.

Valida as funções de detecção de moedas, parsing de feeds RSS,
classificação de sentimento via Ollama (mockado), persistência
PostgreSQL (mockada) e setup de métricas Prometheus.

Cobertura alvo: ≥ 80% do código em rss_sentiment_exporter.py.
"""

from __future__ import annotations

import importlib.util
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ── Import direto (bypass __init__.py) ──────────────────────────────

_EXPORTER_PATH = (
    Path(__file__).parent.parent
    / "grafana"
    / "exporters"
    / "rss_sentiment_exporter.py"
)
_MOD_NAME = "rss_sentiment_exporter"
_spec = importlib.util.spec_from_file_location(_MOD_NAME, str(_EXPORTER_PATH))
_mod = importlib.util.module_from_spec(_spec)

# Registrar o módulo em sys.modules ANTES de exec_module
# (necessário para dataclass funcionar com __module__)
sys.modules[_MOD_NAME] = _mod

# Mock módulos opcionais antes de carregar o exporter
sys.modules.setdefault("feedparser", MagicMock())
sys.modules.setdefault("psycopg2", MagicMock())
sys.modules.setdefault("psycopg2.extensions", MagicMock())
_prom_mock = MagicMock()
sys.modules.setdefault("prometheus_client", _prom_mock)

_spec.loader.exec_module(_mod)

# Referências diretas ao módulo
detect_coins = _mod.detect_coins
fetch_rss_feed = _mod.fetch_rss_feed
classify_sentiment_ollama = _mod.classify_sentiment_ollama
_parse_sentiment_response = _mod._parse_sentiment_response
_parse_date = _mod._parse_date
process_articles = _mod.process_articles
setup_prometheus_metrics = _mod.setup_prometheus_metrics
update_prometheus_metrics = _mod.update_prometheus_metrics
NewsArticle = _mod.NewsArticle
SentimentResult = _mod.SentimentResult
NewsDatabase = _mod.NewsDatabase
COIN_PATTERNS = _mod.COIN_PATTERNS
RSS_FEEDS = _mod.RSS_FEEDS
TRACKED_COINS = _mod.TRACKED_COINS


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sample_article() -> NewsArticle:
    """Artigo de exemplo para testes."""
    return NewsArticle(
        title="Bitcoin hits $100k as institutional adoption surges",
        url="https://example.com/btc-100k",
        source="coindesk",
        published=datetime.now(timezone.utc),
        description="Bitcoin reached a new all-time high amid ETF inflows.",
        coins=["BTC"],
    )


@pytest.fixture
def eth_article() -> NewsArticle:
    """Artigo de exemplo sobre Ethereum."""
    return NewsArticle(
        title="Ethereum's Dencun upgrade reduces Layer 2 fees by 90%",
        url="https://example.com/eth-dencun",
        source="decrypt",
        published=datetime.now(timezone.utc),
        description="The Dencun upgrade on Ethereum significantly reduces gas fees for layer 2 solutions.",
        coins=["ETH"],
    )


@pytest.fixture
def multi_coin_article() -> NewsArticle:
    """Artigo mencionando múltiplas moedas."""
    return NewsArticle(
        title="Crypto market rally: Bitcoin, Ethereum, and Solana lead gains",
        url="https://example.com/multi-rally",
        source="cointelegraph",
        published=datetime.now(timezone.utc),
        description="Bitcoin and Ethereum rally together as Solana hits new highs.",
        coins=["BTC", "ETH", "SOL"],
    )


@pytest.fixture
def general_article() -> NewsArticle:
    """Artigo genérico sobre crypto sem moeda específica."""
    return NewsArticle(
        title="SEC announces new cryptocurrency regulation framework",
        url="https://example.com/sec-regulation",
        source="theblock",
        published=datetime.now(timezone.utc),
        description="New regulation framework for crypto exchanges.",
        coins=["GENERAL"],
    )


@pytest.fixture
def mock_db() -> MagicMock:
    """Mock do NewsDatabase."""
    db = MagicMock(spec=NewsDatabase)
    db.url_exists.return_value = False
    db.insert_sentiment.return_value = True
    db.get_sentiment_stats.return_value = {
        "avg_sentiment": 0.5,
        "count": 10,
        "bullish_pct": 60.0,
        "bearish_pct": 20.0,
        "avg_confidence": 0.8,
        "latest_sentiment": 0.7,
    }
    return db


@pytest.fixture
def mock_metrics() -> Dict:
    """Mock das métricas Prometheus."""
    gauge_mock = MagicMock()
    gauge_mock.labels.return_value = gauge_mock
    counter_mock = MagicMock()

    return {
        "sentiment": gauge_mock,
        "count": MagicMock(labels=MagicMock(return_value=gauge_mock)),
        "bullish_pct": MagicMock(labels=MagicMock(return_value=gauge_mock)),
        "bearish_pct": MagicMock(labels=MagicMock(return_value=gauge_mock)),
        "latest_sentiment": MagicMock(labels=MagicMock(return_value=gauge_mock)),
        "confidence": MagicMock(labels=MagicMock(return_value=gauge_mock)),
        "fetch_errors": counter_mock,
        "articles_processed": counter_mock,
    }


# ═══════════════════════════════════════════════════════════════════════
# Testes: detect_coins
# ═══════════════════════════════════════════════════════════════════════


class TestDetectCoins:
    """Testes para a função detect_coins()."""

    def test_detecta_bitcoin_por_nome(self) -> None:
        """Deve detectar BTC quando 'bitcoin' aparece no texto."""
        assert "BTC" in detect_coins("Bitcoin surges past $100k")

    def test_detecta_bitcoin_por_sigla(self) -> None:
        """Deve detectar BTC quando 'btc' aparece no texto."""
        assert "BTC" in detect_coins("BTC price analysis for today")

    def test_detecta_ethereum(self) -> None:
        """Deve detectar ETH quando 'ethereum' ou 'eth' aparece."""
        assert "ETH" in detect_coins("Ethereum layer 2 scaling update")
        assert "ETH" in detect_coins("ETH hits new high")

    def test_detecta_xrp_ripple(self) -> None:
        """Deve detectar XRP quando 'xrp' ou 'ripple' aparece."""
        assert "XRP" in detect_coins("Ripple wins SEC lawsuit")
        assert "XRP" in detect_coins("XRP price prediction 2025")

    def test_detecta_solana(self) -> None:
        """Deve detectar SOL quando 'solana' ou 'sol' aparece."""
        assert "SOL" in detect_coins("Solana DeFi ecosystem growing rapidly")

    def test_detecta_dogecoin(self) -> None:
        """Deve detectar DOGE quando 'dogecoin' ou 'doge' aparece."""
        assert "DOGE" in detect_coins("Dogecoin meme coin returns")

    def test_detecta_cardano(self) -> None:
        """Deve detectar ADA quando 'cardano' ou 'ada' aparece."""
        assert "ADA" in detect_coins("Cardano Hydra scaling solution launched")

    def test_detecta_multiplas_moedas(self) -> None:
        """Deve retornar múltiplas moedas se mencionadas no mesmo texto."""
        coins = detect_coins("Bitcoin and Ethereum lead crypto market rally")
        assert "BTC" in coins
        assert "ETH" in coins

    def test_texto_generico_crypto_retorna_general(self) -> None:
        """Texto sobre crypto sem moeda específica deve retornar GENERAL."""
        coins = detect_coins("New crypto exchange regulation announced")
        assert coins == ["GENERAL"]

    def test_texto_irrelevante_retorna_vazio(self) -> None:
        """Texto sem relação com crypto retorna lista vazia."""
        coins = detect_coins("Weather forecast for tomorrow in São Paulo")
        assert coins == []

    def test_case_insensitive(self) -> None:
        """Detecção deve ser case-insensitive."""
        assert "BTC" in detect_coins("BITCOIN all caps")
        assert "BTC" in detect_coins("bitcoin lowercase")
        assert "BTC" in detect_coins("Bitcoin mixed case")

    def test_nao_detecta_substring_parcial(self) -> None:
        """Não deve detectar moeda em substrings parciais (word boundary)."""
        # 'sol' dentro de 'solution' não deveria detectar SOL idealmente,
        # mas o regex usa word boundary, então 'sol' in 'solution' vai
        # detectar se 'sol' for seguido por 'ution' sem boundary.
        # Na prática o regex \bsol\b não matcha 'solution'
        coins = detect_coins("This is not a solution for anything")
        assert "SOL" not in coins

    def test_simbolo_btc_unicode(self) -> None:
        """Deve detectar símbolo Unicode ₿."""
        assert "BTC" in detect_coins("Price of ₿ is rising fast")

    def test_texto_vazio(self) -> None:
        """Texto vazio retorna lista vazia."""
        assert detect_coins("") == []


# ═══════════════════════════════════════════════════════════════════════
# Testes: _parse_sentiment_response
# ═══════════════════════════════════════════════════════════════════════


class TestParseSentimentResponse:
    """Testes para _parse_sentiment_response()."""

    def test_formato_correto_completo(self) -> None:
        """Parseia resposta completa no formato esperado."""
        response = "SENTIMENT: 0.7 | CONFIDENCE: 0.85 | CATEGORY: adoption"
        result = _parse_sentiment_response(response)
        assert result.sentiment == pytest.approx(0.7, abs=0.01)
        assert result.confidence == pytest.approx(0.85, abs=0.01)
        assert result.category == "adoption"

    def test_sentimento_negativo(self) -> None:
        """Parseia sentimento negativo corretamente."""
        response = "SENTIMENT: -0.8 | CONFIDENCE: 0.9 | CATEGORY: hack"
        result = _parse_sentiment_response(response)
        assert result.sentiment == pytest.approx(-0.8, abs=0.01)
        assert result.category == "hack"

    def test_sentimento_limiteado_maximo(self) -> None:
        """Sentimento acima de 1.0 deve ser clampado para 1.0."""
        response = "SENTIMENT: 1.5 | CONFIDENCE: 0.9 | CATEGORY: price"
        result = _parse_sentiment_response(response)
        assert result.sentiment == 1.0

    def test_sentimento_limiteado_minimo(self) -> None:
        """Sentimento abaixo de -1.0 deve ser clampado para -1.0."""
        response = "SENTIMENT: -2.0 | CONFIDENCE: 0.9 | CATEGORY: regulation"
        result = _parse_sentiment_response(response)
        assert result.sentiment == -1.0

    def test_confianca_limiteada_maxima(self) -> None:
        """Confiança acima de 1.0 deve ser clampada para 1.0."""
        response = "SENTIMENT: 0.5 | CONFIDENCE: 1.5 | CATEGORY: macro"
        result = _parse_sentiment_response(response)
        assert result.confidence == 1.0

    def test_confianca_limiteada_minima(self) -> None:
        """Confiança negativa deve ser clampada para 0.0."""
        response = "SENTIMENT: 0.5 | CONFIDENCE: -0.3 | CATEGORY: defi"
        result = _parse_sentiment_response(response)
        assert result.confidence == 0.0

    def test_categoria_invalida_mantida_default(self) -> None:
        """Categoria não reconhecida deve manter o default 'general'."""
        response = "SENTIMENT: 0.5 | CONFIDENCE: 0.8 | CATEGORY: unknown_cat"
        result = _parse_sentiment_response(response)
        assert result.category == "general"

    def test_resposta_vazia(self) -> None:
        """Resposta vazia retorna valores padrão."""
        result = _parse_sentiment_response("")
        assert result.sentiment == 0.0
        assert result.confidence == 0.0
        assert result.category == "general"

    def test_resposta_malformada(self) -> None:
        """Resposta sem formato esperado retorna padrão."""
        result = _parse_sentiment_response("This is a random response without format")
        assert result.sentiment == 0.0
        assert result.confidence == 0.0

    def test_resposta_parcial_somente_sentimento(self) -> None:
        """Resposta com apenas sentimento parseia corretamente."""
        response = "SENTIMENT: 0.6"
        result = _parse_sentiment_response(response)
        assert result.sentiment == pytest.approx(0.6, abs=0.01)
        assert result.confidence == 0.0
        assert result.category == "general"

    def test_categorias_validas(self) -> None:
        """Todas as categorias válidas devem ser reconhecidas."""
        valid_cats = ["regulation", "adoption", "hack", "price", "macro", "defi"]
        for cat in valid_cats:
            response = f"SENTIMENT: 0.5 | CONFIDENCE: 0.8 | CATEGORY: {cat}"
            result = _parse_sentiment_response(response)
            assert result.category == cat, f"Categoria {cat} não reconhecida"

    def test_case_insensitive_labels(self) -> None:
        """Labels SENTIMENT/CONFIDENCE/CATEGORY devem ser case-insensitive."""
        response = "sentiment: 0.4 | confidence: 0.7 | category: price"
        result = _parse_sentiment_response(response)
        assert result.sentiment == pytest.approx(0.4, abs=0.01)
        assert result.confidence == pytest.approx(0.7, abs=0.01)
        assert result.category == "price"


# ═══════════════════════════════════════════════════════════════════════
# Testes: _parse_date
# ═══════════════════════════════════════════════════════════════════════


class TestParseDate:
    """Testes para _parse_date()."""

    def test_data_published_parsed(self) -> None:
        """Deve parsear campo published_parsed corretamente."""
        entry = {
            "published_parsed": (2025, 1, 15, 10, 30, 0, 0, 0, 0),
        }
        dt = _parse_date(entry)
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 15
        assert dt.hour == 10
        assert dt.minute == 30
        assert dt.tzinfo == timezone.utc

    def test_data_updated_parsed_fallback(self) -> None:
        """Deve usar updated_parsed quando published_parsed não existe."""
        entry = {
            "updated_parsed": (2024, 12, 25, 8, 0, 0, 0, 0, 0),
        }
        dt = _parse_date(entry)
        assert dt.year == 2024
        assert dt.month == 12
        assert dt.day == 25

    def test_sem_data_retorna_now(self) -> None:
        """Quando nenhum campo existe, retorna datetime atual."""
        entry = {}
        dt = _parse_date(entry)
        now = datetime.now(timezone.utc)
        assert abs((now - dt).total_seconds()) < 5

    def test_published_parsed_none(self) -> None:
        """Campo published_parsed=None deve cair no fallback."""
        entry = {
            "published_parsed": None,
            "updated_parsed": (2024, 6, 1, 12, 0, 0, 0, 0, 0),
        }
        dt = _parse_date(entry)
        assert dt.year == 2024
        assert dt.month == 6


# ═══════════════════════════════════════════════════════════════════════
# Testes: NewsArticle dataclass
# ═══════════════════════════════════════════════════════════════════════


class TestNewsArticle:
    """Testes para o dataclass NewsArticle."""

    def test_criacao_com_todos_campos(self) -> None:
        """Deve criar artigo com todos os campos preenchidos."""
        article = NewsArticle(
            title="Test Title",
            url="https://example.com",
            source="test",
            published=datetime.now(timezone.utc),
            description="Test description",
            coins=["BTC", "ETH"],
        )
        assert article.title == "Test Title"
        assert article.coins == ["BTC", "ETH"]

    def test_coins_default_lista_vazia(self) -> None:
        """Coins deve ser lista vazia se não fornecido."""
        article = NewsArticle(
            title="Test",
            url="https://example.com",
            source="test",
            published=datetime.now(timezone.utc),
        )
        assert article.coins == []

    def test_description_default_vazio(self) -> None:
        """Description deve ser string vazia por padrão."""
        article = NewsArticle(
            title="Test",
            url="https://example.com",
            source="test",
            published=datetime.now(timezone.utc),
        )
        assert article.description == ""


# ═══════════════════════════════════════════════════════════════════════
# Testes: SentimentResult dataclass
# ═══════════════════════════════════════════════════════════════════════


class TestSentimentResult:
    """Testes para o dataclass SentimentResult."""

    def test_defaults(self) -> None:
        """Resultado padrão deve ser neutro com confiança zero."""
        result = SentimentResult()
        assert result.sentiment == 0.0
        assert result.confidence == 0.0
        assert result.category == "general"

    def test_criacao_com_valores(self) -> None:
        """Deve criar resultado com valores customizados."""
        result = SentimentResult(
            sentiment=0.8, confidence=0.95, category="adoption"
        )
        assert result.sentiment == 0.8
        assert result.confidence == 0.95
        assert result.category == "adoption"


# ═══════════════════════════════════════════════════════════════════════
# Testes: classify_sentiment_ollama
# ═══════════════════════════════════════════════════════════════════════


class TestClassifySentimentOllama:
    """Testes para classify_sentiment_ollama()."""

    @patch.object(_mod, "_query_ollama_with_timeout")
    def test_sucesso_gpu1(
        self, mock_query: MagicMock, sample_article: NewsArticle
    ) -> None:
        """Deve usar GPU1 com sucesso na primeira tentativa."""
        mock_query.return_value = (
            True,
            "SENTIMENT: 0.8 | CONFIDENCE: 0.9 | CATEGORY: adoption",
            "GPU1",
        )
        result = _mod.classify_sentiment_ollama(sample_article)
        assert result.sentiment == pytest.approx(0.8, abs=0.01)
        assert result.confidence == pytest.approx(0.9, abs=0.01)
        assert result.category == "adoption"
        mock_query.assert_called_once()

    @patch.object(_mod, "_query_ollama_with_timeout")
    def test_fallback_gpu0_quando_gpu1_falha(
        self, mock_query: MagicMock, sample_article: NewsArticle
    ) -> None:
        """Deve cair para GPU0 quando GPU1 falha."""
        mock_query.side_effect = [
            (False, "", "GPU1"),  # GPU1 falha
            (True, "SENTIMENT: 0.5 | CONFIDENCE: 0.7 | CATEGORY: price", "GPU0"),  # GPU0 OK
        ]
        result = _mod.classify_sentiment_ollama(sample_article)
        assert result.sentiment == pytest.approx(0.5, abs=0.01)
        assert mock_query.call_count == 2

    @patch.object(_mod, "_query_ollama_with_timeout")
    def test_ambas_gpus_falham(
        self, mock_query: MagicMock, sample_article: NewsArticle
    ) -> None:
        """Deve retornar resultado padrão quando ambas GPUs falham."""
        mock_query.return_value = (False, "", "GPU?")
        result = _mod.classify_sentiment_ollama(sample_article)
        assert result.sentiment == 0.0
        assert result.confidence == 0.0
        assert result.category == "general"

    @patch.object(_mod, "_query_ollama_with_timeout")
    def test_gpu1_timeout_usa_gpu0(
        self, mock_query: MagicMock, sample_article: NewsArticle
    ) -> None:
        """GPU1 com timeout deve disparar fallback para GPU0."""
        mock_query.side_effect = [
            (False, "", "GPU1"),  # GPU1 timeout/falha
            (True, "SENTIMENT: 0.3 | CONFIDENCE: 0.65 | CATEGORY: regulation", "GPU0"),
        ]
        result = _mod.classify_sentiment_ollama(sample_article)
        assert result.sentiment == pytest.approx(0.3, abs=0.01)
        assert mock_query.call_count == 2


# ═══════════════════════════════════════════════════════════════════════
# Testes: _query_ollama_with_timeout
# ═══════════════════════════════════════════════════════════════════════


class TestQueryOllamaWithTimeout:
    """Testes para _query_ollama_with_timeout()."""

    @patch("urllib.request.urlopen")
    def test_query_sucesso_gpu1(self, mock_urlopen: MagicMock) -> None:
        """Deve retornar (True, response, 'GPU1') em caso de sucesso."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"response": "SENTIMENT: 0.5 | CONFIDENCE: 0.8 | CATEGORY: price"}
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        success, text, gpu = _mod._query_ollama_with_timeout(
            "http://localhost:11435", "qwen2.5-coder:7b", "test prompt", timeout=10, gpu_name="GPU1"
        )
        assert success is True
        assert "SENTIMENT" in text
        assert gpu == "GPU1"

    @patch("urllib.request.urlopen")
    def test_query_timeout(self, mock_urlopen: MagicMock) -> None:
        """Deve retornar (False, '', gpu_name) em caso de timeout."""
        mock_urlopen.side_effect = socket.timeout("Timeout")

        success, text, gpu = _mod._query_ollama_with_timeout(
            "http://localhost:11435", "model", "prompt", timeout=10, gpu_name="GPU1"
        )
        assert success is False
        assert text == ""
        assert gpu == "GPU1"

    @patch("urllib.request.urlopen")
    def test_query_url_error(self, mock_urlopen: MagicMock) -> None:
        """Deve retornar (False, '', gpu_name) em caso de URLError."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        success, text, gpu = _mod._query_ollama_with_timeout(
            "http://localhost:11435", "model", "prompt", timeout=10, gpu_name="GPU0"
        )
        assert success is False
        assert text == ""
        assert gpu == "GPU0"

    @patch("urllib.request.urlopen")
    def test_query_json_decode_error(self, mock_urlopen: MagicMock) -> None:
        """Deve retornar (False, '', gpu_name) se resposta não for JSON válido."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"invalid json {{"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        success, text, gpu = _mod._query_ollama_with_timeout(
            "http://localhost:11435", "model", "prompt", gpu_name="GPU1"
        )
        assert success is False
        assert gpu == "GPU1"


# ═══════════════════════════════════════════════════════════════════════
# Testes: _query_ollama (legada)
# ═══════════════════════════════════════════════════════════════════════


class TestQueryOllamaLegacy:
    """Testes para _query_ollama() — função legada."""

    @patch.object(_mod, "_query_ollama_with_timeout")
    def test_query_legada_chama_nova(
        self, mock_new_query: MagicMock
    ) -> None:
        """Versão legada deve chamar _query_ollama_with_timeout."""
        mock_new_query.return_value = (True, "response_text", "GPU1")

        success, text = _mod._query_ollama(
            "http://localhost:11435", "model", "prompt"
        )
        assert success is True
        assert text == "response_text"
        mock_new_query.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════
# Testes antigos: _query_ollama (mantém compatibilidade)
# ═══════════════════════════════════════════════════════════════════════


class TestQueryOllama:
    """Testes legados para _query_ollama()."""

    @patch("urllib.request.urlopen")
    def test_query_sucesso(self, mock_urlopen: MagicMock) -> None:
        """Deve retornar (True, response) em caso de sucesso."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"response": "SENTIMENT: 0.5 | CONFIDENCE: 0.8 | CATEGORY: price"}
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        success, text = _mod._query_ollama(
            "http://localhost:11435", "qwen2.5-coder:7b", "test prompt"
        )
        assert success is True
        assert "SENTIMENT" in text

    @patch("urllib.request.urlopen")
    def test_query_falha_conexao(self, mock_urlopen: MagicMock) -> None:
        """Deve retornar (False, '') em caso de erro de conexão."""
        mock_urlopen.side_effect = ConnectionError("Connection refused")

        success, text = _mod._query_ollama(
            "http://localhost:11435", "model", "prompt"
        )
        assert success is False
        assert text == ""

    @patch("urllib.request.urlopen")
    def test_query_timeout(self, mock_urlopen: MagicMock) -> None:
        """Deve retornar (False, '') em caso de timeout."""
        mock_urlopen.side_effect = TimeoutError("Timeout")

        success, text = _mod._query_ollama(
            "http://localhost:11435", "model", "prompt"
        )
        assert success is False
        assert text == ""


# ═══════════════════════════════════════════════════════════════════════
# Testes: process_articles
# ═══════════════════════════════════════════════════════════════════════


class TestProcessArticles:
    """Testes para process_articles()."""

    @patch.object(_mod, "classify_sentiment_ollama")
    @patch.object(_mod, "time")
    def test_processa_artigo_novo(
        self,
        mock_time: MagicMock,
        mock_classify: MagicMock,
        sample_article: NewsArticle,
        mock_db: MagicMock,
        mock_metrics: Dict,
    ) -> None:
        """Deve processar artigo novo e persistir no banco."""
        mock_classify.return_value = SentimentResult(
            sentiment=0.8, confidence=0.9, category="adoption"
        )
        mock_time.sleep = MagicMock()

        count = process_articles([sample_article], mock_db, mock_metrics)
        assert count == 1
        mock_db.insert_sentiment.assert_called_once()

    @patch.object(_mod, "classify_sentiment_ollama")
    @patch.object(_mod, "time")
    def test_pula_artigo_duplicado(
        self,
        mock_time: MagicMock,
        mock_classify: MagicMock,
        sample_article: NewsArticle,
        mock_db: MagicMock,
        mock_metrics: Dict,
    ) -> None:
        """Deve pular artigo já existente no banco (deduplicação)."""
        mock_db.url_exists.return_value = True
        mock_time.sleep = MagicMock()

        count = process_articles([sample_article], mock_db, mock_metrics)
        assert count == 0
        mock_classify.assert_not_called()

    @patch.object(_mod, "classify_sentiment_ollama")
    @patch.object(_mod, "time")
    def test_multi_coin_processa_cada_coin(
        self,
        mock_time: MagicMock,
        mock_classify: MagicMock,
        multi_coin_article: NewsArticle,
        mock_db: MagicMock,
        mock_metrics: Dict,
    ) -> None:
        """Artigo com múltiplas moedas gera um registro por moeda."""
        mock_classify.return_value = SentimentResult(
            sentiment=0.6, confidence=0.8, category="price"
        )
        mock_time.sleep = MagicMock()

        count = process_articles([multi_coin_article], mock_db, mock_metrics)
        assert count == 3  # BTC, ETH, SOL
        assert mock_db.insert_sentiment.call_count == 3

    @patch.object(_mod, "classify_sentiment_ollama")
    @patch.object(_mod, "time")
    def test_sem_db_ainda_conta(
        self,
        mock_time: MagicMock,
        mock_classify: MagicMock,
        sample_article: NewsArticle,
        mock_metrics: Dict,
    ) -> None:
        """Sem banco de dados, ainda processa e conta artigos."""
        mock_classify.return_value = SentimentResult(
            sentiment=0.5, confidence=0.7, category="price"
        )
        mock_time.sleep = MagicMock()

        count = process_articles([sample_article], None, mock_metrics)
        assert count == 1

    @patch.object(_mod, "classify_sentiment_ollama")
    @patch.object(_mod, "time")
    def test_artigo_vazio(
        self,
        mock_time: MagicMock,
        mock_classify: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """Lista vazia de artigos retorna 0."""
        mock_time.sleep = MagicMock()
        count = process_articles([], mock_db, None)
        assert count == 0
        mock_classify.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# Testes: update_prometheus_metrics
# ═══════════════════════════════════════════════════════════════════════


class TestUpdatePrometheusMetrics:
    """Testes para update_prometheus_metrics()."""

    def test_atualiza_metricas_para_cada_coin(
        self, mock_db: MagicMock, mock_metrics: Dict
    ) -> None:
        """Deve atualizar métricas para cada moeda + GENERAL."""
        update_prometheus_metrics(mock_db, mock_metrics, TRACKED_COINS)

        expected_coins = TRACKED_COINS + ["GENERAL"]
        assert mock_db.get_sentiment_stats.call_count == len(expected_coins)

    def test_sem_metricas_nao_faz_nada(self, mock_db: MagicMock) -> None:
        """Sem métricas Prometheus, não deve fazer nada."""
        update_prometheus_metrics(mock_db, None, TRACKED_COINS)
        mock_db.get_sentiment_stats.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# Testes: setup_prometheus_metrics
# ═══════════════════════════════════════════════════════════════════════


class TestSetupPrometheusMetrics:
    """Testes para setup_prometheus_metrics()."""

    def test_cria_metricas_quando_prometheus_disponivel(self) -> None:
        """Deve criar dict de métricas quando prometheus_client está disponível."""
        metrics = setup_prometheus_metrics()
        # Com HAS_PROM=True (mockado), deve retornar dict ou None dependendo do mock
        # O módulo seta HAS_PROM na inicialização; como mockamos prometheus_client,
        # ele será True e retornará um dict
        if metrics is not None:
            expected_keys = {
                "sentiment", "count", "bullish_pct", "bearish_pct",
                "latest_sentiment", "confidence", "fetch_errors",
                "articles_processed",
            }
            assert set(metrics.keys()) == expected_keys


# ═══════════════════════════════════════════════════════════════════════
# Testes: fetch_rss_feed
# ═══════════════════════════════════════════════════════════════════════


class TestFetchRssFeed:
    """Testes para fetch_rss_feed()."""

    @patch.object(_mod, "feedparser")
    def test_feed_com_artigos_crypto(self, mock_fp: MagicMock) -> None:
        """Deve retornar artigos que mencionam crypto."""
        mock_entry = {
            "title": "Bitcoin hits new high after ETF approval",
            "link": "https://example.com/btc-etf",
            "description": "Bitcoin price surges following SEC ETF approval.",
            "published_parsed": (2025, 1, 15, 10, 0, 0, 0, 0, 0),
        }
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [mock_entry]
        mock_fp.parse.return_value = mock_feed

        # Precisa que HAS_FEEDPARSER seja True
        original = _mod.HAS_FEEDPARSER
        _mod.HAS_FEEDPARSER = True
        try:
            articles = fetch_rss_feed("https://example.com/rss", "test")
            assert len(articles) == 1
            assert articles[0].title == "Bitcoin hits new high after ETF approval"
            assert "BTC" in articles[0].coins
        finally:
            _mod.HAS_FEEDPARSER = original

    @patch.object(_mod, "feedparser")
    def test_feed_sem_artigos_crypto(self, mock_fp: MagicMock) -> None:
        """Deve ignorar artigos sem menção a crypto."""
        mock_entry = {
            "title": "Weather forecast for tomorrow",
            "link": "https://example.com/weather",
            "description": "Sunny day expected across the country.",
            "published_parsed": (2025, 1, 15, 10, 0, 0, 0, 0, 0),
        }
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [mock_entry]
        mock_fp.parse.return_value = mock_feed

        original = _mod.HAS_FEEDPARSER
        _mod.HAS_FEEDPARSER = True
        try:
            articles = fetch_rss_feed("https://example.com/rss", "test")
            assert len(articles) == 0
        finally:
            _mod.HAS_FEEDPARSER = original

    def test_sem_feedparser_retorna_vazio(self) -> None:
        """Sem feedparser instalado, retorna lista vazia."""
        original = _mod.HAS_FEEDPARSER
        _mod.HAS_FEEDPARSER = False
        try:
            articles = fetch_rss_feed("https://example.com/rss", "test")
            assert articles == []
        finally:
            _mod.HAS_FEEDPARSER = original

    @patch.object(_mod, "feedparser")
    def test_feed_bozo_sem_entries(self, mock_fp: MagicMock) -> None:
        """Feed com erro (bozo) e sem entries retorna vazio."""
        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.entries = []
        mock_feed.bozo_exception = "XML parse error"
        mock_fp.parse.return_value = mock_feed

        original = _mod.HAS_FEEDPARSER
        _mod.HAS_FEEDPARSER = True
        try:
            articles = fetch_rss_feed("https://example.com/rss", "test")
            assert articles == []
        finally:
            _mod.HAS_FEEDPARSER = original

    @patch.object(_mod, "feedparser")
    def test_entry_sem_titulo_ignorado(self, mock_fp: MagicMock) -> None:
        """Entries sem título devem ser ignoradas."""
        mock_entry = {
            "title": "",
            "link": "https://example.com/btc",
            "description": "Bitcoin article",
        }
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [mock_entry]
        mock_fp.parse.return_value = mock_feed

        original = _mod.HAS_FEEDPARSER
        _mod.HAS_FEEDPARSER = True
        try:
            articles = fetch_rss_feed("https://example.com/rss", "test")
            assert len(articles) == 0
        finally:
            _mod.HAS_FEEDPARSER = original

    @patch.object(_mod, "feedparser")
    def test_limpa_html_da_description(self, mock_fp: MagicMock) -> None:
        """Deve remover tags HTML da description."""
        mock_entry = {
            "title": "Bitcoin news",
            "link": "https://example.com/btc",
            "description": "<p>Bitcoin <b>price</b> is <a href='#'>rising</a></p>",
            "published_parsed": (2025, 1, 15, 10, 0, 0, 0, 0, 0),
        }
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [mock_entry]
        mock_fp.parse.return_value = mock_feed

        original = _mod.HAS_FEEDPARSER
        _mod.HAS_FEEDPARSER = True
        try:
            articles = fetch_rss_feed("https://example.com/rss", "test")
            assert len(articles) == 1
            assert "<p>" not in articles[0].description
            assert "<b>" not in articles[0].description
        finally:
            _mod.HAS_FEEDPARSER = original


# ═══════════════════════════════════════════════════════════════════════
# Testes: NewsDatabase
# ═══════════════════════════════════════════════════════════════════════


class TestNewsDatabase:
    """Testes para a classe NewsDatabase."""

    @patch.object(_mod, "psycopg2")
    def test_get_conn_cria_conexao(self, mock_pg: MagicMock) -> None:
        """Deve criar nova conexão quando não existe."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pg.connect.return_value = mock_conn

        db = NewsDatabase("postgresql://test:test@localhost/test")
        conn = db._get_conn()
        assert conn is not None
        mock_pg.connect.assert_called_once()

    @patch.object(_mod, "psycopg2")
    def test_get_conn_reutiliza_conexao(self, mock_pg: MagicMock) -> None:
        """Deve reutilizar conexão existente se não estiver fechada."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_pg.connect.return_value = mock_conn

        db = NewsDatabase("postgresql://test:test@localhost/test")
        conn1 = db._get_conn()
        conn2 = db._get_conn()
        assert conn1 is conn2
        assert mock_pg.connect.call_count == 1

    @patch.object(_mod, "psycopg2")
    def test_get_conn_reconecta_se_fechada(self, mock_pg: MagicMock) -> None:
        """Deve reconectar se a conexão estiver fechada."""
        mock_conn1 = MagicMock()
        mock_conn1.closed = False
        mock_conn2 = MagicMock()
        mock_conn2.closed = False
        mock_pg.connect.side_effect = [mock_conn1, mock_conn2]

        db = NewsDatabase("postgresql://test:test@localhost/test")
        conn1 = db._get_conn()
        mock_conn1.closed = True  # Simula desconexão
        conn2 = db._get_conn()
        assert conn1 is not conn2
        assert mock_pg.connect.call_count == 2

    @patch.object(_mod, "psycopg2")
    def test_url_exists_true(self, mock_pg: MagicMock) -> None:
        """Deve retornar True quando URL+coin existe."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pg.connect.return_value = mock_conn

        db = NewsDatabase("postgresql://test:test@localhost/test")
        assert db.url_exists("https://example.com", "BTC") is True

    @patch.object(_mod, "psycopg2")
    def test_url_exists_false(self, mock_pg: MagicMock) -> None:
        """Deve retornar False quando URL+coin não existe."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pg.connect.return_value = mock_conn

        db = NewsDatabase("postgresql://test:test@localhost/test")
        assert db.url_exists("https://example.com", "BTC") is False

    @patch.object(_mod, "psycopg2")
    def test_insert_sentiment_sucesso(
        self, mock_pg: MagicMock, sample_article: NewsArticle
    ) -> None:
        """Deve inserir sentimento com sucesso."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pg.connect.return_value = mock_conn

        db = NewsDatabase("postgresql://test:test@localhost/test")
        result_obj = SentimentResult(
            sentiment=0.8, confidence=0.9, category="adoption"
        )
        inserted = db.insert_sentiment(sample_article, "BTC", result_obj)
        assert inserted is True

    @patch.object(_mod, "psycopg2")
    def test_insert_sentiment_conflito(
        self, mock_pg: MagicMock, sample_article: NewsArticle
    ) -> None:
        """Deve retornar False em caso de conflito (duplicata)."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0  # ON CONFLICT DO NOTHING
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pg.connect.return_value = mock_conn

        db = NewsDatabase("postgresql://test:test@localhost/test")
        result_obj = SentimentResult(sentiment=0.5, confidence=0.7)
        inserted = db.insert_sentiment(sample_article, "BTC", result_obj)
        assert inserted is False

    @patch.object(_mod, "psycopg2")
    def test_get_sentiment_stats_com_dados(self, mock_pg: MagicMock) -> None:
        """Deve retornar estatísticas corretas com dados disponíveis."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_cursor = MagicMock()
        # Primeira query: stats agregadas
        # Segunda query: latest sentiment
        mock_cursor.fetchone.side_effect = [
            (0.6, 15, 0.85, 70.0, 10.0),  # avg, count, conf, bull%, bear%
            (0.8,),  # latest
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pg.connect.return_value = mock_conn

        db = NewsDatabase("postgresql://test:test@localhost/test")
        stats = db.get_sentiment_stats("BTC")
        assert stats["avg_sentiment"] == 0.6
        assert stats["count"] == 15
        assert stats["avg_confidence"] == 0.85
        assert stats["bullish_pct"] == 70.0
        assert stats["bearish_pct"] == 10.0
        assert stats["latest_sentiment"] == 0.8

    @patch.object(_mod, "psycopg2")
    def test_get_sentiment_stats_sem_dados(self, mock_pg: MagicMock) -> None:
        """Deve retornar defaults quando não há dados."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [None, None]
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pg.connect.return_value = mock_conn

        db = NewsDatabase("postgresql://test:test@localhost/test")
        stats = db.get_sentiment_stats("BTC")
        assert stats["avg_sentiment"] == 0.0
        assert stats["count"] == 0
        assert stats["latest_sentiment"] == 0.0


# ═══════════════════════════════════════════════════════════════════════
# Testes: Configuração e constantes
# ═══════════════════════════════════════════════════════════════════════


class TestConfiguracao:
    """Testes para constantes e configuração."""

    def test_rss_feeds_configurados(self) -> None:
        """Deve ter pelo menos 5 feeds RSS configurados."""
        assert len(RSS_FEEDS) >= 5
        for feed in RSS_FEEDS:
            assert "name" in feed
            assert "url" in feed
            assert feed["url"].startswith("https://")

    def test_tracked_coins(self) -> None:
        """Deve ter as 6 moedas rastreadas."""
        expected = {"BTC", "ETH", "XRP", "SOL", "DOGE", "ADA"}
        assert set(TRACKED_COINS) == expected

    def test_coin_patterns_completo(self) -> None:
        """Deve ter padrões regex para cada moeda rastreada."""
        for coin in TRACKED_COINS:
            assert coin in COIN_PATTERNS, f"Falta padrão regex para {coin}"

    def test_feeds_conhecidos(self) -> None:
        """Feeds devem incluir os portais principais."""
        feed_names = {f["name"] for f in RSS_FEEDS}
        assert "coindesk" in feed_names
        assert "cointelegraph" in feed_names
        assert "decrypt" in feed_names

    def test_sentiment_prompt_template_existe(self) -> None:
        """Template de prompt deve existir e conter placeholders obrigatórios."""
        assert hasattr(_mod, "SENTIMENT_PROMPT_TEMPLATE")
        template = _mod.SENTIMENT_PROMPT_TEMPLATE
        assert "{title}" in template
        assert "{description}" in template
        assert "{coin}" in template
        # Prompt genérico completo deve conter palavras-chave de classificação
        assert hasattr(_mod, "SENTIMENT_GENERIC_PROMPT")
        generic = _mod.SENTIMENT_GENERIC_PROMPT
        assert "SENTIMENT" in generic
        assert "CONFIDENCE" in generic
        assert "CATEGORY" in generic


# ═══════════════════════════════════════════════════════════════════════
# Testes: fetch_all_feeds
# ═══════════════════════════════════════════════════════════════════════


class TestFetchAllFeeds:
    """Testes para fetch_all_feeds()."""

    @patch.object(_mod, "fetch_rss_feed")
    def test_consolida_artigos_de_todos_feeds(
        self, mock_fetch: MagicMock
    ) -> None:
        """Deve consolidar artigos de todos os feeds configurados."""
        article = NewsArticle(
            title="Test",
            url="https://test.com",
            source="test",
            published=datetime.now(timezone.utc),
            coins=["BTC"],
        )
        mock_fetch.return_value = [article]

        all_articles = _mod.fetch_all_feeds()
        assert len(all_articles) == len(RSS_FEEDS)
        assert mock_fetch.call_count == len(RSS_FEEDS)

    @patch.object(_mod, "fetch_rss_feed")
    def test_feeds_vazios_retorna_vazio(self, mock_fetch: MagicMock) -> None:
        """Feeds sem artigos devem retornar lista vazia."""
        mock_fetch.return_value = []
        all_articles = _mod.fetch_all_feeds()
        assert len(all_articles) == 0


# ═══════════════════════════════════════════════════════════════════════
# Testes: NewsDatabase.ensure_table
# ═══════════════════════════════════════════════════════════════════════


class TestNewsDatabaseEnsureTable:
    """Testes para NewsDatabase.ensure_table()."""

    @patch.object(_mod, "psycopg2")
    def test_ensure_table_cria_tabela(self, mock_pg: MagicMock) -> None:
        """Deve executar SQL de criação da tabela."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pg.connect.return_value = mock_conn

        db = NewsDatabase("postgresql://test:test@localhost/test")
        db.ensure_table()

        # Deve executar pelo menos 3 SQLs (SET search_path, CREATE TABLE, 2x CREATE INDEX)
        assert mock_cursor.execute.call_count >= 3

    @patch.object(_mod, "psycopg2")
    def test_url_exists_erro_retorna_false(self, mock_pg: MagicMock) -> None:
        """Em caso de erro na query, deve retornar False."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            side_effect=Exception("DB Error")
        )
        mock_pg.connect.return_value = mock_conn

        db = NewsDatabase("postgresql://test:test@localhost/test")
        result = db.url_exists("https://example.com", "BTC")
        assert result is False

    @patch.object(_mod, "psycopg2")
    def test_insert_sentiment_erro_reseta_conexao(
        self, mock_pg: MagicMock, sample_article: NewsArticle
    ) -> None:
        """Em caso de erro de insert, deve resetar conexão (_conn = None)."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            side_effect=Exception("Insert Error")
        )
        mock_pg.connect.return_value = mock_conn

        db = NewsDatabase("postgresql://test:test@localhost/test")
        result_obj = SentimentResult(sentiment=0.5)
        inserted = db.insert_sentiment(sample_article, "BTC", result_obj)
        assert inserted is False
        assert db._conn is None

    @patch.object(_mod, "psycopg2")
    def test_get_sentiment_stats_erro_reseta_conexao(
        self, mock_pg: MagicMock
    ) -> None:
        """Em caso de erro, deve resetar conexão e retornar defaults."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            side_effect=Exception("Query Error")
        )
        mock_pg.connect.return_value = mock_conn

        db = NewsDatabase("postgresql://test:test@localhost/test")
        stats = db.get_sentiment_stats("BTC")
        assert stats["avg_sentiment"] == 0.0
        assert stats["count"] == 0
        assert db._conn is None


# ═══════════════════════════════════════════════════════════════════════
# Testes: _parse_date edge cases
# ═══════════════════════════════════════════════════════════════════════


class TestParseDateEdgeCases:
    """Testes adicionais para _parse_date()."""

    def test_published_parsed_com_valor_invalido(self) -> None:
        """Valor inválido em published_parsed deve usar fallback."""
        entry = {
            "published_parsed": (2025, 13, 40, 25, 61, 0, 0, 0, 0),
        }
        # Meses inválidos causam ValueError; deve retornar now
        dt = _parse_date(entry)
        now = datetime.now(timezone.utc)
        assert abs((now - dt).total_seconds()) < 5


# ═══════════════════════════════════════════════════════════════════════
# Testes: fetch_rss_feed edge cases
# ═══════════════════════════════════════════════════════════════════════


class TestFetchRssFeedEdgeCases:
    """Testes adicionais de edge cases para fetch_rss_feed."""

    @patch.object(_mod, "feedparser")
    def test_feed_exception_retorna_vazio(self, mock_fp: MagicMock) -> None:
        """Exception durante parse deve retornar lista vazia."""
        mock_fp.parse.side_effect = Exception("Network error")

        original = _mod.HAS_FEEDPARSER
        _mod.HAS_FEEDPARSER = True
        try:
            articles = fetch_rss_feed("https://example.com/rss", "test")
            assert articles == []
        finally:
            _mod.HAS_FEEDPARSER = original

    @patch.object(_mod, "feedparser")
    def test_entry_sem_link_ignorada(self, mock_fp: MagicMock) -> None:
        """Entry sem link deve ser ignorada."""
        mock_entry = {
            "title": "Bitcoin news",
            "link": "",
            "description": "Bitcoin article",
        }
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [mock_entry]
        mock_fp.parse.return_value = mock_feed

        original = _mod.HAS_FEEDPARSER
        _mod.HAS_FEEDPARSER = True
        try:
            articles = fetch_rss_feed("https://example.com/rss", "test")
            assert len(articles) == 0
        finally:
            _mod.HAS_FEEDPARSER = original

    @patch.object(_mod, "feedparser")
    def test_entry_usa_summary_quando_sem_description(
        self, mock_fp: MagicMock
    ) -> None:
        """Deve usar campo summary se description não existir."""
        mock_entry = {
            "title": "Bitcoin ETF approved",
            "link": "https://example.com/btc-etf",
            "summary": "SEC approves first Bitcoin spot ETF",
            "published_parsed": (2025, 1, 15, 10, 0, 0, 0, 0, 0),
        }
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [mock_entry]
        mock_fp.parse.return_value = mock_feed

        original = _mod.HAS_FEEDPARSER
        _mod.HAS_FEEDPARSER = True
        try:
            articles = fetch_rss_feed("https://example.com/rss", "test")
            assert len(articles) == 1
        finally:
            _mod.HAS_FEEDPARSER = original


# ═══════════════════════════════════════════════════════════════════════
# Testes: main() function
# ═══════════════════════════════════════════════════════════════════════


class TestMain:
    """Testes para a função main()."""

    @patch.object(_mod, "start_http_server", create=True)
    @patch.object(_mod, "setup_prometheus_metrics")
    @patch.object(_mod, "update_prometheus_metrics")
    @patch.object(_mod, "process_articles")
    @patch.object(_mod, "fetch_all_feeds")
    @patch.object(_mod, "NewsDatabase")
    @patch("sys.argv", ["rss_sentiment_exporter.py", "--port", "9999", "--dry-run"])
    def test_main_dry_run(
        self,
        mock_db_cls: MagicMock,
        mock_fetch: MagicMock,
        mock_process: MagicMock,
        mock_update: MagicMock,
        mock_setup_prom: MagicMock,
        mock_start_http: MagicMock,
    ) -> None:
        """Main em dry-run deve processar sem banco de dados."""
        mock_fetch.return_value = []
        mock_process.return_value = 0
        mock_setup_prom.return_value = {"fetch_errors": MagicMock()}

        # Simular running=False após 1 iteração
        original_signal = _mod.signal.signal

        call_count = 0

        def fake_signal(sig, handler):
            """Simula signal handler."""
            nonlocal call_count
            call_count += 1
            return None

        _mod.signal.signal = fake_signal

        # Simular time.sleep para que o loop de intervalo termine rápido
        original_sleep = _mod.time.sleep

        sleep_count = 0

        def fast_sleep(seconds):
            """Encurta o intervalo para sair rapidamente."""
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count > 2:
                raise KeyboardInterrupt

        _mod.time.sleep = fast_sleep

        try:
            with pytest.raises((KeyboardInterrupt, SystemExit)):
                _mod.main()
        finally:
            _mod.signal.signal = original_signal
            _mod.time.sleep = original_sleep

        # Não deve ter criado banco em dry_run
        mock_db_cls.assert_not_called()

    @patch("sys.argv", ["rss_sentiment_exporter.py", "--port", "9999"])
    def test_main_sem_feedparser_sai(self) -> None:
        """Main sem feedparser deve sair com erro."""
        original = _mod.HAS_FEEDPARSER
        _mod.HAS_FEEDPARSER = False
        try:
            with pytest.raises(SystemExit) as exc_info:
                _mod.main()
            assert exc_info.value.code == 1
        finally:
            _mod.HAS_FEEDPARSER = original

    @patch("sys.argv", ["rss_sentiment_exporter.py", "--port", "9999"])
    def test_main_sem_database_url_sai(self) -> None:
        """Main sem DATABASE_URL (e sem --dry-run) deve sair com erro."""
        original_fp = _mod.HAS_FEEDPARSER
        original_dsn = _mod.PG_DSN
        _mod.HAS_FEEDPARSER = True
        _mod.PG_DSN = ""
        try:
            with pytest.raises(SystemExit) as exc_info:
                _mod.main()
            assert exc_info.value.code == 1
        finally:
            _mod.HAS_FEEDPARSER = original_fp
            _mod.PG_DSN = original_dsn
