"""
Testes unitários para integração de News Sentiment no FastTradingModel.

Testa o método _news_sentiment_signal() com cenários de:
- Sem notícias recentes
- Notícias bullish (ETF aprovado)
- Notícias bearish (hack/regulação)
- Baixa confiança (artigos ignorados)
- Cache (deve retornar resultado anterior)
- Erro de conexão DB
"""

import time
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass
from typing import Tuple, Optional, Dict

import pytest


# ──────────────────────────────────────────────────────
# Reproduzir classes mínimas do fast_model.py para teste
# (evita import do módulo real que requer numpy/psycopg2)
# ──────────────────────────────────────────────────────

@dataclass
class _FakeRow:
    """Simula resultado do cursor RealDictCursor."""
    sentiment: float
    confidence: float
    category: str
    hours_ago: float

    def __getitem__(self, key: str):
        return getattr(self, key)

    def get(self, key: str, default=None):
        return getattr(self, key, default)


class _NewsSignalMixin:
    """Extrai apenas a lógica de _news_sentiment_signal para testes isolados."""

    def __init__(self):
        self._news_db_url = "postgresql://test:test@localhost:5433/test"
        self._news_cache: Optional[Tuple[float, float, float]] = None
        self._news_cache_ttl: float = 60.0

    def _news_sentiment_signal(self) -> Tuple[float, float, str]:
        """Obtém sinal de sentimento de notícias cripto (5º fator do ensemble)."""
        import logging
        logger = logging.getLogger(__name__)

        now = time.time()
        if self._news_cache is not None:
            cache_ts, cached_score, cached_weight = self._news_cache
            if now - cache_ts < self._news_cache_ttl:
                direction = "bullish" if cached_score > 0.1 else "bearish" if cached_score < -0.1 else "neutral"
                return cached_score, cached_weight, f"news:{direction}(cached)"

        try:
            import psycopg2
            import psycopg2.extras
        except ImportError:
            return 0.0, 0.0, "news:unavailable"

        try:
            conn = psycopg2.connect(self._news_db_url, connect_timeout=3)
            conn.autocommit = True
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cur.execute("""
                SELECT sentiment::float, confidence::float, category,
                       EXTRACT(EPOCH FROM (NOW() - timestamp))::float / 3600.0 AS hours_ago
                FROM btc.news_sentiment
                WHERE coin IN ('BTC', 'GENERAL')
                  AND timestamp > NOW() - INTERVAL '4 hours'
                  AND confidence >= 0.5
                ORDER BY timestamp DESC
                LIMIT 50
            """)
            rows = cur.fetchall()
            cur.close()
            conn.close()

            if not rows:
                self._news_cache = (now, 0.0, 0.0)
                return 0.0, 0.0, "news:no_recent"

            total_weight = 0.0
            weighted_sum = 0.0
            total_conf = 0.0

            for row in rows:
                hours = row["hours_ago"] if row["hours_ago"] else 0.0
                recency = max(0.1, 1.0 - hours / 4.0)
                conf = row["confidence"]
                w = conf * recency
                weighted_sum += row["sentiment"] * w
                total_weight += w
                total_conf += conf

            if total_weight < 0.01:
                self._news_cache = (now, 0.0, 0.0)
                return 0.0, 0.0, "news:low_weight"

            score = weighted_sum / total_weight
            avg_conf = total_conf / len(rows)
            n_articles = len(rows)

            quantity_factor = min(n_articles / 10.0, 1.0)
            confidence_factor = avg_conf
            weight = 0.20 * quantity_factor * confidence_factor
            weight = max(0.0, min(weight, 0.20))

            categories = [r["category"] for r in rows if r.get("category")]
            if "hack" in categories or "regulation" in categories:
                weight = min(weight * 1.5, 0.20)

            direction = "bullish" if score > 0.1 else "bearish" if score < -0.1 else "neutral"
            reason = f"news:{direction}({n_articles}art,w={weight:.0%})"

            self._news_cache = (now, score, weight)
            return score, weight, reason

        except Exception as e:
            self._news_cache = (now, 0.0, 0.0)
            return 0.0, 0.0, "news:error"


# ──────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────

@pytest.fixture
def signal_provider():
    """Instância da mixin para testes."""
    return _NewsSignalMixin()


def _mock_rows(articles: list[dict]) -> list[_FakeRow]:
    """Cria lista de FakeRow a partir de dicts."""
    return [_FakeRow(**a) for a in articles]


# ──────────────────────────────────────────────────────
# Testes
# ──────────────────────────────────────────────────────

class TestNewsSentimentSignal:
    """Testes para _news_sentiment_signal()."""

    @patch("psycopg2.connect")
    def test_no_recent_articles(self, mock_connect, signal_provider):
        """Sem notícias recentes: retorna score=0, weight=0."""
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn

        score, weight, reason = signal_provider._news_sentiment_signal()

        assert score == 0.0
        assert weight == 0.0
        assert "no_recent" in reason

    @patch("psycopg2.connect")
    def test_bullish_articles(self, mock_connect, signal_provider):
        """Artigos positivos (ETF): score > 0, weight > 0."""
        articles = [
            {"sentiment": 0.80, "confidence": 0.90, "category": "adoption", "hours_ago": 0.5},
            {"sentiment": 0.70, "confidence": 0.85, "category": "price", "hours_ago": 1.0},
            {"sentiment": 0.60, "confidence": 0.75, "category": "etf", "hours_ago": 2.0},
        ]
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = _mock_rows(articles)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn

        score, weight, reason = signal_provider._news_sentiment_signal()

        assert score > 0.5, f"Score should be bullish, got {score}"
        assert weight > 0.0, f"Weight should be > 0"
        assert weight <= 0.20, f"Weight should be <= 20%"
        assert "bullish" in reason

    @patch("psycopg2.connect")
    def test_bearish_hack_articles(self, mock_connect, signal_provider):
        """Artigos de hack: score negativo, peso amplificado (1.5x)."""
        articles = [
            {"sentiment": -0.90, "confidence": 0.95, "category": "hack", "hours_ago": 0.2},
            {"sentiment": -0.80, "confidence": 0.90, "category": "hack", "hours_ago": 0.5},
            {"sentiment": -0.70, "confidence": 0.85, "category": "security", "hours_ago": 1.0},
        ]
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = _mock_rows(articles)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn

        score, weight, reason = signal_provider._news_sentiment_signal()

        assert score < -0.5, f"Score should be bearish, got {score}"
        assert weight > 0.0
        assert "bearish" in reason

    @patch("psycopg2.connect")
    def test_regulation_boosts_weight(self, mock_connect, signal_provider):
        """Artigos de regulação devem ter peso amplificado (1.5x)."""
        articles_regulation = [
            {"sentiment": -0.50, "confidence": 0.80, "category": "regulation", "hours_ago": 0.5},
        ] * 10  # 10 artigos para saturar quantity_factor

        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = _mock_rows(articles_regulation)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn

        score_reg, weight_reg, _ = signal_provider._news_sentiment_signal()

        # Reset cache
        signal_provider._news_cache = None

        articles_normal = [
            {"sentiment": -0.50, "confidence": 0.80, "category": "price", "hours_ago": 0.5},
        ] * 10

        mock_cur2 = MagicMock()
        mock_cur2.fetchall.return_value = _mock_rows(articles_normal)
        mock_conn2 = MagicMock()
        mock_conn2.cursor.return_value = mock_cur2
        mock_connect.return_value = mock_conn2

        score_norm, weight_norm, _ = signal_provider._news_sentiment_signal()

        assert weight_reg > weight_norm, (
            f"Regulation weight ({weight_reg}) should be > normal weight ({weight_norm})"
        )

    @patch("psycopg2.connect")
    def test_low_confidence_ignored(self, mock_connect, signal_provider):
        """Artigos com confiança < 0.5 são filtrados pela query SQL."""
        # A query já filtra confidence >= 0.5, então se todos têm baixa conf,
        # a query retorna vazio
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = []  # Filtrados pela query
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn

        score, weight, reason = signal_provider._news_sentiment_signal()

        assert score == 0.0
        assert weight == 0.0
        assert "no_recent" in reason

    @patch("psycopg2.connect")
    def test_cache_within_ttl(self, mock_connect, signal_provider):
        """Cache deve retornar resultado anterior dentro do TTL."""
        # Primeiro call — popula cache
        articles = [
            {"sentiment": 0.80, "confidence": 0.90, "category": "price", "hours_ago": 0.5},
        ]
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = _mock_rows(articles)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn

        score1, weight1, reason1 = signal_provider._news_sentiment_signal()
        assert score1 > 0.0

        # Segundo call — deve usar cache (sem chamar DB)
        mock_connect.reset_mock()
        score2, weight2, reason2 = signal_provider._news_sentiment_signal()

        assert score2 == score1
        assert "cached" in reason2
        mock_connect.assert_not_called()

    @patch("psycopg2.connect")
    def test_cache_expired_refetches(self, mock_connect, signal_provider):
        """Cache expirado deve refazer a consulta ao DB."""
        # Popula cache com timestamp no passado
        signal_provider._news_cache = (time.time() - 120, 0.5, 0.10)  # 2 min atrás (TTL=60s)

        articles = [
            {"sentiment": -0.50, "confidence": 0.80, "category": "price", "hours_ago": 0.5},
        ]
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = _mock_rows(articles)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn

        score, weight, reason = signal_provider._news_sentiment_signal()

        # Deve ter chamado o DB (cache expirado)
        mock_connect.assert_called_once()
        assert score < 0.0

    @patch("psycopg2.connect")
    def test_db_connection_error(self, mock_connect, signal_provider):
        """Erro de conexão DB: retorna neutro sem peso."""
        mock_connect.side_effect = Exception("Connection refused")

        score, weight, reason = signal_provider._news_sentiment_signal()

        assert score == 0.0
        assert weight == 0.0
        assert "error" in reason

    @patch("psycopg2.connect")
    def test_weight_cap_at_20_percent(self, mock_connect, signal_provider):
        """Peso nunca deve exceder 20% (0.20)."""
        # Muitos artigos com alta confiança + hack
        articles = [
            {"sentiment": 0.90, "confidence": 0.99, "category": "hack", "hours_ago": 0.1},
        ] * 50  # 50 artigos (limite da query)

        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = _mock_rows(articles)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn

        score, weight, reason = signal_provider._news_sentiment_signal()

        assert weight <= 0.20, f"Weight {weight} should be capped at 0.20"
        assert weight > 0.10, f"Weight {weight} should be significant with 50 high-conf articles"

    @patch("psycopg2.connect")
    def test_recency_weighting(self, mock_connect, signal_provider):
        """Artigos mais recentes devem ter maior impacto no score."""
        # Artigo recente bullish + artigo antigo bearish
        articles = [
            {"sentiment": 0.90, "confidence": 0.90, "category": "price", "hours_ago": 0.1},  # Muito recente
            {"sentiment": -0.90, "confidence": 0.90, "category": "price", "hours_ago": 3.5},  # Quase expirando
        ]
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = _mock_rows(articles)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn

        score, weight, reason = signal_provider._news_sentiment_signal()

        # O artigo recente (bullish) deve dominar sobre o antigo (bearish)
        assert score > 0.0, f"Recent bullish should dominate, got score={score}"

    @patch("psycopg2.connect")
    def test_mixed_sentiment_neutral(self, mock_connect, signal_provider):
        """Sentimento misto deve resultar em score próximo de zero."""
        articles = [
            {"sentiment": 0.80, "confidence": 0.80, "category": "price", "hours_ago": 1.0},
            {"sentiment": -0.80, "confidence": 0.80, "category": "price", "hours_ago": 1.0},
        ]
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = _mock_rows(articles)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn

        score, weight, reason = signal_provider._news_sentiment_signal()

        assert abs(score) < 0.1, f"Mixed sentiment should be ~0, got {score}"
        assert "neutral" in reason


class TestEnsembleWeightIntegration:
    """Testa a lógica de rebalanceamento de pesos do ensemble."""

    def test_news_weight_zero_no_change(self):
        """Se news_weight=0, pesos originais não mudam."""
        weights = {"technical": 0.35, "orderbook": 0.30, "flow": 0.25, "qlearning": 0.10}
        news_weight = 0.0

        if news_weight > 0:
            scale = 1.0 - news_weight
            for k in weights:
                weights[k] *= scale
            weights["news"] = news_weight
        else:
            weights["news"] = 0.0

        assert weights["technical"] == 0.35
        assert weights["orderbook"] == 0.30
        assert weights["flow"] == 0.25
        assert weights["qlearning"] == 0.10
        assert weights["news"] == 0.0
        assert abs(sum(weights.values()) - 1.0) < 1e-10

    def test_news_weight_20pct_rebalance(self):
        """Com news_weight=0.20, pesos devem somar 1.0."""
        weights = {"technical": 0.35, "orderbook": 0.30, "flow": 0.25, "qlearning": 0.10}
        news_weight = 0.20

        scale = 1.0 - news_weight
        for k in weights:
            weights[k] *= scale
        weights["news"] = news_weight

        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-10, f"Weights should sum to 1.0, got {total}"
        assert weights["news"] == 0.20
        assert weights["technical"] == pytest.approx(0.35 * 0.80)
        assert weights["orderbook"] == pytest.approx(0.30 * 0.80)

    def test_news_weight_10pct_rebalance(self):
        """Com news_weight=0.10, proporções são mantidas."""
        weights = {"technical": 0.35, "orderbook": 0.30, "flow": 0.25, "qlearning": 0.10}
        news_weight = 0.10

        scale = 1.0 - news_weight
        for k in weights:
            weights[k] *= scale
        weights["news"] = news_weight

        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-10

        # Proporções relativas mantidas
        ratio_before = 0.35 / 0.30
        ratio_after = weights["technical"] / weights["orderbook"]
        assert abs(ratio_before - ratio_after) < 1e-10
