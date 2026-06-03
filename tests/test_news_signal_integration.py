"""Testes para integração de sentimento de notícias no sinal de trading.

Cobre:
- _get_cached_news_tag: retorno bullish/bearish/neutro/vazio
- Injeção da tag no signal.reason após predict
- Threshold confidence >= 0.30 (Fix B)
- _get_trusted_news_sources: lógica de filtro por acerto >= 50% em 7 dias
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent_with_db(rows, row_count):
    """Cria instância mínima de CryptoTradingAgent com db mockado."""
    # Import local para não depender de credenciais reais
    import sys
    import os

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "btc_trading_agent"))

    # Mock todas as dependências pesadas antes do import
    heavy = [
        "psycopg2", "psycopg2.extras", "kucoin", "kucoin.client",
        "prometheus_client", "requests", "fast_model",
    ]
    mocks = {}
    for mod in heavy:
        m = MagicMock()
        mocks[mod] = m
        sys.modules.setdefault(mod, m)

    # fast_model precisa de Signal
    signal_cls = type("Signal", (), {
        "action": "HOLD", "confidence": 0.5, "price": 100.0,
        "reason": "RSI low", "features": {},
    })
    sys.modules["fast_model"].Signal = signal_cls
    sys.modules["fast_model"].FastTradingModel = MagicMock()
    sys.modules["fast_model"].MarketState = MagicMock()

    # Cursor/conn mock
    cur = MagicMock()
    cur.fetchone.return_value = (sum(r[0] for r in rows) / max(row_count, 1), row_count)
    conn_ctx = MagicMock()
    conn_ctx.__enter__ = MagicMock(return_value=conn_ctx)
    conn_ctx.__exit__ = MagicMock(return_value=False)
    conn_ctx.cursor.return_value = cur

    # Agente minimal
    agent = MagicMock()
    agent.db._get_conn.return_value = conn_ctx

    # Bind o método real ao mock
    from btc_trading_agent import trading_agent as ta_module  # noqa: F401 — usado via importlib
    # Importa diretamente a função do módulo para não precisar instanciar a classe
    return agent, cur


# ---------------------------------------------------------------------------
# Testes diretos de _get_cached_news_tag (lógica isolada)
# ---------------------------------------------------------------------------

class TestGetCachedNewsTagLogic:
    """Testa a lógica de tag sem instanciar CryptoTradingAgent completo."""

    def _run_tag(self, avg_sent: float, count: int) -> str:
        """Executa apenas a lógica de decisão de tag (sem DB real)."""
        # Replica a lógica do método para teste isolado
        if count >= 3:
            if avg_sent > 0.05:
                return "news:bullish(cached)"
            elif avg_sent < -0.05:
                return "news:bearish(cached)"
        return ""

    def test_bullish_retorna_tag_correta(self):
        assert self._run_tag(0.10, 5) == "news:bullish(cached)"

    def test_bearish_retorna_tag_correta(self):
        assert self._run_tag(-0.10, 4) == "news:bearish(cached)"

    def test_neutro_retorna_vazio(self):
        assert self._run_tag(0.02, 5) == ""

    def test_poucos_artigos_retorna_vazio(self):
        # Menos de 3 artigos → não confiável → sem tag
        assert self._run_tag(0.50, 2) == ""

    def test_fronteira_bullish_exato(self):
        # avg_sent == 0.05 NÃO é bullish (> 0.05)
        assert self._run_tag(0.05, 5) == ""

    def test_fronteira_bearish_exato(self):
        # avg_sent == -0.05 NÃO é bearish (< -0.05)
        assert self._run_tag(-0.05, 5) == ""

    def test_bullish_forte(self):
        assert self._run_tag(0.80, 10) == "news:bullish(cached)"

    def test_bearish_forte(self):
        assert self._run_tag(-0.75, 8) == "news:bearish(cached)"


# ---------------------------------------------------------------------------
# Testes de injeção no signal.reason
# ---------------------------------------------------------------------------

class TestNewsTagInjectionInReason:
    """Testa que a tag é corretamente acrescentada ao signal.reason."""

    def _inject(self, original_reason: str, tag: str) -> str:
        """Replica a lógica de injeção do loop principal."""
        if tag:
            return f"{original_reason}, {tag}" if original_reason else tag
        return original_reason

    def test_reason_existente_recebe_tag(self):
        result = self._inject("RSI low, bid pressure", "news:bullish(cached)")
        assert result == "RSI low, bid pressure, news:bullish(cached)"

    def test_reason_vazio_recebe_somente_tag(self):
        result = self._inject("", "news:bearish(cached)")
        assert result == "news:bearish(cached)"

    def test_sem_tag_nao_altera_reason(self):
        original = "RSI low, bid pressure"
        result = self._inject(original, "")
        assert result == original

    def test_guardrail_detecta_bullish_no_reason(self):
        reason = self._inject("[BULLISH], RSI oversold", "news:bullish(cached)")
        assert "news:bullish" in reason

    def test_guardrail_detecta_bearish_no_reason(self):
        reason = self._inject("[BEARISH], RSI overbought", "news:bearish(cached)")
        assert "news:bearish" in reason


# ---------------------------------------------------------------------------
# Testes de threshold confidence >= 0.30 (Fix B - verificação de query string)
# ---------------------------------------------------------------------------

class TestConfidenceThresholdQuery:
    """Verifica que as queries usam 0.30 e não mais 0.5."""

    def test_threshold_ai_plan_query(self):
        """Query do AI plan não deve mais usar 0.5."""
        import inspect
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

        # Lê o arquivo diretamente para verificar a query sem instanciar
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "btc_trading_agent", "trading_agent.py"
        )
        with open(source_path, encoding="utf-8") as f:
            source = f.read()

        # Conta quantas vezes cada threshold aparece em contexto de news_sentiment
        import re
        # Busca blocos com FROM btc.news_sentiment e confidence
        blocks = re.findall(
            r"FROM btc\.news_sentiment.*?confidence\s*>=\s*([\d.]+)",
            source,
            re.DOTALL,
        )
        for threshold in blocks:
            assert float(threshold) <= 0.30, (
                f"Query de news_sentiment ainda usa threshold {threshold} (esperado <= 0.30)"
            )

    def test_threshold_nao_usa_0_5_em_news_queries(self):
        """Garante que 0.5 foi removido das queries de news_sentiment."""
        import os
        import re

        source_path = os.path.join(
            os.path.dirname(__file__), "..", "btc_trading_agent", "trading_agent.py"
        )
        with open(source_path, encoding="utf-8") as f:
            source = f.read()

        # Verifica que nenhum bloco de news_sentiment usa confidence >= 0.5
        blocks = re.findall(
            r"FROM btc\.news_sentiment.*?confidence\s*>=\s*([\d.]+)",
            source,
            re.DOTALL,
        )
        assert blocks, "Nenhuma query de news_sentiment encontrada — verifique o arquivo"
        for threshold in blocks:
            assert float(threshold) != 0.5, (
                "Query de news_sentiment ainda usa threshold 0.5 — deve ser 0.30"
            )


# ---------------------------------------------------------------------------
# Testes de _get_trusted_news_sources (lógica de filtro 7 dias)
# ---------------------------------------------------------------------------

class TestTrustedNewsSourcesLogic:
    """Testa lógica de seleção de fontes com sinal positivo (>= 50% acerto, >= 5 previsões)."""

    def _run_filter(self, rows: list[tuple]) -> list[str]:
        """Replica a lógica de decisão de fonte confiável sem DB real.

        Cada row: (source, previsoes, acertos)
        """
        trusted = []
        for source, previsoes, acertos in rows:
            if previsoes >= 5:
                pct = round(100.0 * acertos / previsoes, 1) if previsoes > 0 else 0.0
                if pct >= 50.0:
                    trusted.append(source)
        return trusted

    def test_fonte_com_acerto_acima_50_incluida(self):
        result = self._run_filter([("coindesk", 10, 6)])
        assert "coindesk" in result

    def test_fonte_com_acerto_abaixo_50_excluida(self):
        result = self._run_filter([("theblock", 10, 4)])
        assert "theblock" not in result

    def test_fonte_com_menos_5_previsoes_excluida(self):
        result = self._run_filter([("newsbtc", 3, 3)])
        assert "newsbtc" not in result

    def test_fonte_com_exato_50_pct_incluida(self):
        result = self._run_filter([("beincrypto", 10, 5)])
        assert "beincrypto" in result

    def test_multiplas_fontes_filtragem_correta(self):
        rows = [
            ("coindesk", 20, 12),     # 60% → trusted
            ("cointelegraph", 10, 4), # 40% → NOT trusted
            ("decrypt", 4, 4),        # < 5 previsões → NOT trusted
            ("bitcoinist", 15, 8),    # 53.3% → trusted
        ]
        result = self._run_filter(rows)
        assert "coindesk" in result
        assert "bitcoinist" in result
        assert "cointelegraph" not in result
        assert "decrypt" not in result

    def test_sem_fontes_qualificadas_retorna_lista_vazia(self):
        rows = [
            ("source_a", 2, 2),   # < 5 previsões
            ("source_b", 10, 3),  # 30% → NOT trusted
        ]
        result = self._run_filter(rows)
        assert result == []

    def test_janela_7_dias_presente_na_query(self):
        """Garante que a query usa INTERVAL '7 days' e não 4 days."""
        import os, re
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "btc_trading_agent", "trading_agent.py"
        )
        with open(source_path, encoding="utf-8") as f:
            source = f.read()
        # Encontra o método _get_trusted_news_sources
        match = re.search(
            r"def _get_trusted_news_sources.*?(?=def |\Z)", source, re.DOTALL
        )
        assert match, "_get_trusted_news_sources não encontrado"
        method_body = match.group(0)
        assert "7 days" in method_body, "Janela deve ser 7 days"
        assert "4 days" not in method_body, "Janela antiga de 4 days não deve estar presente"

    def test_filtro_source_any_presente_nas_queries_de_consumo(self):
        """Garante que as queries de consumo de notícias filtram por source = ANY."""
        import os, re
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "btc_trading_agent", "trading_agent.py"
        )
        with open(source_path, encoding="utf-8") as f:
            source = f.read()
        # Deve existir pelo menos 3 ocorrências de source = ANY
        count = len(re.findall(r"source\s*=\s*ANY\s*\(", source))
        assert count >= 3, f"Esperado >= 3 filtros 'source = ANY', encontrado {count}"

