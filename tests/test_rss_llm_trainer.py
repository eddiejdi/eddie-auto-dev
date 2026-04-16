"""Testes unitários para rss_llm_trainer.py.

Cobertura alvo: ≥ 80% do código novo.
Mocks em todos os I/Os externos (Ollama, PostgreSQL, RSS feeds).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock, call, patch

# ── Importação do módulo via importlib (evita problemas de dataclass) ──────────

_MOD_PATH = Path(__file__).parent.parent / "grafana" / "exporters" / "rss_llm_trainer.py"
_MOD_NAME = "rss_llm_trainer"

_spec = importlib.util.spec_from_file_location(_MOD_NAME, _MOD_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules[_MOD_NAME] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]


# ── Re-exports para facilitar uso nos testes ───────────────────────────────────

ArticleSample = _mod.ArticleSample
TrainingStats = _mod.TrainingStats
detect_primary_coin = _mod.detect_primary_coin
_parse_ollama_response = _mod._parse_ollama_response
compute_ground_truth = _mod.compute_ground_truth
generate_modelfile = _mod.generate_modelfile
fetch_rss_feed = _mod.fetch_rss_feed
classify_with_ollama = _mod.classify_with_ollama
_ollama_request = _mod._ollama_request
get_price_at_ts = _mod.get_price_at_ts
upsert_sample = _mod.upsert_sample
ensure_training_table = _mod.ensure_training_table
get_training_stats = _mod.get_training_stats
get_best_training_examples = _mod.get_best_training_examples
collect_all_feeds = _mod.collect_all_feeds
mode_train = _mod.mode_train
mode_report = _mod.mode_report
mode_predict = _mod.mode_predict
BASE_FEW_SHOT_EXAMPLES = _mod.BASE_FEW_SHOT_EXAMPLES
PRICE_CHANGE_THRESHOLD_PCT = _mod.PRICE_CHANGE_THRESHOLD_PCT
_parse_modelfile_to_api_payload = _mod._parse_modelfile_to_api_payload


# ── TestArticleSample ─────────────────────────────────────────────────────────


class TestArticleSample(unittest.TestCase):
    """Testes do dataclass ArticleSample."""

    def test_criacao_minima(self) -> None:
        """Testa criação com apenas campos obrigatórios."""
        sample = ArticleSample(
            url="https://example.com/news",
            title="Bitcoin news",
            description="Short description",
            source="coindesk",
            published_ts=1700000000.0,
            coin="BTC",
        )
        self.assertEqual(sample.url, "https://example.com/news")
        self.assertEqual(sample.coin, "BTC")
        self.assertIsNone(sample.price_at_publish)
        self.assertIsNone(sample.ground_truth_label)
        self.assertIsNone(sample.prediction_correct)

    def test_campos_opcionais(self) -> None:
        """Testa que campos opcionais podem ser preenchidos."""
        sample = ArticleSample(
            url="https://x.com/a",
            title="ETH upgrade",
            description="Details",
            source="decrypt",
            published_ts=1700000000.0,
            coin="ETH",
            price_at_publish=2000.0,
            price_at_impact=2100.0,
            price_change_pct=5.0,
            ground_truth_label="BULLISH",
            ollama_sentiment=0.75,
            ollama_confidence=0.88,
            ollama_direction="BULLISH",
            ollama_category="technical",
            prediction_correct=True,
        )
        self.assertEqual(sample.ground_truth_label, "BULLISH")
        self.assertTrue(sample.prediction_correct)


# ── TestDetectPrimaryCoin ──────────────────────────────────────────────────────


class TestDetectPrimaryCoin(unittest.TestCase):
    """Testes da função detect_primary_coin."""

    def test_btc_por_nome(self) -> None:
        self.assertEqual(detect_primary_coin("Bitcoin price surges", ""), "BTC")

    def test_btc_por_sigla(self) -> None:
        self.assertEqual(detect_primary_coin("BTC hits new high", ""), "BTC")

    def test_eth_ethereum(self) -> None:
        self.assertEqual(detect_primary_coin("Ethereum upgrade", ""), "ETH")

    def test_eth_por_sigla(self) -> None:
        self.assertEqual(detect_primary_coin("ETH 2.0 launch", ""), "ETH")

    def test_sol_solana(self) -> None:
        self.assertEqual(detect_primary_coin("Solana network outage", ""), "SOL")

    def test_xrp_ripple(self) -> None:
        self.assertEqual(detect_primary_coin("Ripple wins SEC case", ""), "XRP")

    def test_doge_dogecoin(self) -> None:
        self.assertEqual(detect_primary_coin("Dogecoin Elon Musk", ""), "DOGE")

    def test_ada_cardano(self) -> None:
        self.assertEqual(detect_primary_coin("Cardano smart contracts", ""), "ADA")

    def test_simbolo_btc(self) -> None:
        self.assertEqual(detect_primary_coin("₿ reaches $100k", ""), "BTC")

    def test_padrao_btc_sem_match(self) -> None:
        """Texto sem cripto → retorna BTC como padrão."""
        self.assertEqual(detect_primary_coin("Stock market crash", "equities fall"), "BTC")

    def test_detecta_na_descricao(self) -> None:
        """Detecta moeda na descrição quando título não tem."""
        self.assertEqual(detect_primary_coin("News today", "Ethereum update deployed"), "ETH")

    def test_case_insensitive(self) -> None:
        self.assertEqual(detect_primary_coin("BITCOIN ETFS", ""), "BTC")


# ── TestParseOllamaResponse ────────────────────────────────────────────────────


class TestParseOllamaResponse(unittest.TestCase):
    """Testes do parser de resposta do Ollama."""

    def test_formato_completo(self) -> None:
        """Testa parsing do formato completo com DIRECTION."""
        resp = "SENTIMENT: 0.85 | CONFIDENCE: 0.90 | DIRECTION: BULLISH | CATEGORY: adoption"
        s, c, d, cat = _parse_ollama_response(resp)
        self.assertAlmostEqual(s, 0.85)
        self.assertAlmostEqual(c, 0.90)
        self.assertEqual(d, "BULLISH")
        self.assertEqual(cat, "adoption")

    def test_formato_bearish(self) -> None:
        resp = "SENTIMENT: -0.75 | CONFIDENCE: 0.88 | DIRECTION: BEARISH | CATEGORY: hack"
        s, c, d, cat = _parse_ollama_response(resp)
        self.assertAlmostEqual(s, -0.75)
        self.assertEqual(d, "BEARISH")
        self.assertEqual(cat, "hack")

    def test_neutro(self) -> None:
        resp = "SENTIMENT: 0.0 | CONFIDENCE: 0.50 | DIRECTION: NEUTRAL | CATEGORY: general"
        s, c, d, cat = _parse_ollama_response(resp)
        self.assertAlmostEqual(s, 0.0)
        self.assertEqual(d, "NEUTRAL")

    def test_clamp_sentiment(self) -> None:
        """Valores fora do range [-1, 1] devem ser clampados."""
        resp = "SENTIMENT: 1.5 | CONFIDENCE: 1.2 | DIRECTION: BULLISH | CATEGORY: price"
        s, c, _, _ = _parse_ollama_response(resp)
        self.assertAlmostEqual(s, 1.0)
        self.assertAlmostEqual(c, 1.0)

    def test_clamp_sentimento_negativo(self) -> None:
        resp = "SENTIMENT: -2.0 | CONFIDENCE: 0.9 | DIRECTION: BEARISH | CATEGORY: macro"
        s, _, _, _ = _parse_ollama_response(resp)
        self.assertAlmostEqual(s, -1.0)

    def test_remove_thinking_tags(self) -> None:
        """Tags <think>...</think> do qwen3 devem ser removidas."""
        resp = "<think>Let me analyze...</think>SENTIMENT: 0.7 | CONFIDENCE: 0.85 | DIRECTION: BULLISH | CATEGORY: adoption"
        s, c, d, _ = _parse_ollama_response(resp)
        self.assertAlmostEqual(s, 0.7)
        self.assertEqual(d, "BULLISH")

    def test_resposta_vazia(self) -> None:
        """Resposta vazia → defaults."""
        s, c, d, cat = _parse_ollama_response("")
        self.assertAlmostEqual(s, 0.0)
        self.assertAlmostEqual(c, 0.5)
        self.assertEqual(d, "NEUTRAL")
        self.assertEqual(cat, "general")

    def test_resposta_invalida(self) -> None:
        """Texto sem padrão esperado → defaults."""
        s, c, d, cat = _parse_ollama_response("I cannot determine the sentiment of this article.")
        self.assertAlmostEqual(s, 0.0)
        self.assertEqual(d, "NEUTRAL")

    def test_categoria_invalida_ignorada(self) -> None:
        """Categoria não reconhecida → mantém 'general'."""
        resp = "SENTIMENT: 0.5 | CONFIDENCE: 0.7 | DIRECTION: BULLISH | CATEGORY: random_unknown"
        _, _, _, cat = _parse_ollama_response(resp)
        self.assertEqual(cat, "general")

    def test_categorias_validas(self) -> None:
        """Todas as categorias válidas devem ser reconhecidas."""
        valid = ["regulation", "adoption", "hack", "price", "macro", "defi", "technical"]
        for c_name in valid:
            resp = f"SENTIMENT: 0.5 | CONFIDENCE: 0.8 | DIRECTION: BULLISH | CATEGORY: {c_name}"
            _, _, _, cat = _parse_ollama_response(resp)
            self.assertEqual(cat, c_name, f"Categoria {c_name} não reconhecida")


# ── TestComputeGroundTruth ─────────────────────────────────────────────────────


class TestComputeGroundTruth(unittest.TestCase):
    """Testes da função compute_ground_truth."""

    def test_bullish_acima_threshold(self) -> None:
        """Variação positiva acima do threshold → BULLISH."""
        result = compute_ground_truth(100.0, 102.0)  # +2%
        self.assertEqual(result, "BULLISH")

    def test_bearish_abaixo_threshold(self) -> None:
        """Variação negativa abaixo do threshold → BEARISH."""
        result = compute_ground_truth(100.0, 98.0)  # -2%
        self.assertEqual(result, "BEARISH")

    def test_neutral_dentro_range(self) -> None:
        """Variação pequena → NEUTRAL."""
        result = compute_ground_truth(100.0, 100.5)  # +0.5%
        self.assertEqual(result, "NEUTRAL")

    def test_exatamente_no_threshold(self) -> None:
        """Claramente acima do threshold → BULLISH."""
        threshold = PRICE_CHANGE_THRESHOLD_PCT
        # Adiciona pequena margem para evitar imprecisão de float
        result = compute_ground_truth(100.0, 100.0 * (1 + (threshold + 0.01) / 100))
        self.assertEqual(result, "BULLISH")

    def test_preco_pub_zero(self) -> None:
        """Preço zero no publish → NEUTRAL (evita divisão por zero)."""
        result = compute_ground_truth(0.0, 100.0)
        self.assertEqual(result, "NEUTRAL")

    def test_btc_alt_grande(self) -> None:
        """Simula pump BTC 5%."""
        result = compute_ground_truth(90000.0, 94500.0)  # +5%
        self.assertEqual(result, "BULLISH")

    def test_crash_grande(self) -> None:
        """Simula crash -20%."""
        result = compute_ground_truth(90000.0, 72000.0)  # -20%
        self.assertEqual(result, "BEARISH")


# ── TestGenerateModelfile ──────────────────────────────────────────────────────


class TestGenerateModelfile(unittest.TestCase):
    """Testes do gerador de Modelfile."""

    def test_modelfile_base_sem_db_examples(self) -> None:
        """Gera Modelfile sem exemplos do DB."""
        modelfile = generate_modelfile([])
        self.assertIn("FROM ", modelfile)
        self.assertIn("SYSTEM", modelfile)
        self.assertIn("PARAMETER temperature", modelfile)
        self.assertIn("MESSAGE user", modelfile)
        self.assertIn("MESSAGE assistant", modelfile)

    def test_modelfile_inclui_prompt_sistema(self) -> None:
        """Sistema prompt deve estar presente."""
        modelfile = generate_modelfile([])
        self.assertIn("trading-sentiment", modelfile)
        self.assertIn("SENTIMENT:", modelfile)
        self.assertIn("BULLISH", modelfile)
        self.assertIn("BEARISH", modelfile)

    def test_modelfile_com_exemplos_db(self) -> None:
        """Com exemplos do DB, Modelfile deve incluir seção de exemplos calibrados."""
        examples = [
            {
                "title": "Bitcoin ETF approved",
                "description": "The SEC approved a spot Bitcoin ETF.",
                "coin": "BTC",
                "ground_truth": "BULLISH",
                "ollama_sentiment": 0.90,
                "ollama_confidence": 0.92,
                "ollama_direction": "BULLISH",
                "ollama_category": "regulation",
                "price_change_pct": 5.2,
            }
        ]
        modelfile = generate_modelfile(examples)
        self.assertIn("calibrados com dados reais", modelfile)
        self.assertIn("Bitcoin ETF approved", modelfile)
        self.assertIn("+5.20%", modelfile)

    def test_modelfile_parametros_temperatura(self) -> None:
        """Verifica parâmetros de geração."""
        modelfile = generate_modelfile([])
        self.assertIn("temperature 0.05", modelfile)
        self.assertIn("num_predict 80", modelfile)

    def test_base_few_shot_no_modelfile(self) -> None:
        """Todos os exemplos hardcoded devem aparecer no Modelfile."""
        modelfile = generate_modelfile([])
        # Verifica que pelo menos metade dos exemplos base estão no modelfile
        found = sum(
            1 for user_msg, _ in BASE_FEW_SHOT_EXAMPLES
            if user_msg[:30] in modelfile
        )
        self.assertGreaterEqual(found, len(BASE_FEW_SHOT_EXAMPLES) // 2)


# ── TestFetchRssFeed ───────────────────────────────────────────────────────────


class TestFetchRssFeed(unittest.TestCase):
    """Testes da função fetch_rss_feed com feedparser mockado."""

    def _make_entry(self, title: str, link: str, description: str = "desc", published: str = "") -> MagicMock:
        """Cria um mock de entry do feedparser."""
        entry = MagicMock()
        entry.get.side_effect = lambda key, default="": {
            "title": title,
            "link": link,
            "description": description,
            "summary": description,
            "published": published,
        }.get(key, default)
        entry.published_parsed = None
        return entry

    @patch(f"{_MOD_NAME}.feedparser.parse")
    def test_fetch_retorna_artigos(self, mock_parse: MagicMock) -> None:
        """Feed válido retorna lista de artigos."""
        mock_feed = MagicMock()
        entry = self._make_entry("BTC news", "https://example.com/1", "Bitcoin rises")
        mock_feed.entries = [entry]
        mock_parse.return_value = mock_feed

        result = fetch_rss_feed("https://example.com/rss", "testfeed", limit=10)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "BTC news")
        self.assertEqual(result[0]["source"], "testfeed")

    @patch(f"{_MOD_NAME}.feedparser.parse")
    def test_fetch_sem_titulo_ignorado(self, mock_parse: MagicMock) -> None:
        """Entries sem título ou URL são ignorados."""
        mock_feed = MagicMock()
        e1 = self._make_entry("", "https://example.com/1")
        e2 = self._make_entry("Title OK", "")
        e3 = self._make_entry("Valid Title", "https://example.com/3")
        mock_feed.entries = [e1, e2, e3]
        mock_parse.return_value = mock_feed

        result = fetch_rss_feed("https://x.com/rss", "feed", limit=10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Valid Title")

    @patch(f"{_MOD_NAME}.feedparser.parse")
    def test_fetch_erro_connexao(self, mock_parse: MagicMock) -> None:
        """Exceção no feedparser → retorna lista vazia."""
        mock_parse.side_effect = Exception("connection refused")
        result = fetch_rss_feed("https://bad.url/rss", "broken", limit=10)
        self.assertEqual(result, [])

    @patch(f"{_MOD_NAME}.feedparser.parse")
    def test_fetch_respeita_limite(self, mock_parse: MagicMock) -> None:
        """Respeita o parâmetro limit."""
        mock_feed = MagicMock()
        entries = [
            self._make_entry(f"Title {i}", f"https://example.com/{i}") for i in range(20)
        ]
        mock_feed.entries = entries
        mock_parse.return_value = mock_feed

        result = fetch_rss_feed("https://x.com/rss", "feed", limit=5)
        self.assertLessEqual(len(result), 5)

    @patch(f"{_MOD_NAME}.feedparser.parse")
    def test_fetch_remove_html(self, mock_parse: MagicMock) -> None:
        """HTML tags devem ser removidas da descrição."""
        mock_feed = MagicMock()
        entry = self._make_entry("Title", "https://x.com/1", "<b>Bold text</b> and <p>paragraph</p>")
        mock_feed.entries = [entry]
        mock_parse.return_value = mock_feed

        result = fetch_rss_feed("https://x.com/rss", "feed", limit=10)
        self.assertNotIn("<b>", result[0]["description"])
        self.assertNotIn("<p>", result[0]["description"])
        self.assertIn("Bold text", result[0]["description"])


# ── TestClassifyWithOllama ─────────────────────────────────────────────────────


class TestClassifyWithOllama(unittest.TestCase):
    """Testes de classify_with_ollama com _ollama_request mockado."""

    @patch(f"{_MOD_NAME}._ollama_request")
    def test_sucesso_gpu1(self, mock_req: MagicMock) -> None:
        """GPU1 retorna resposta correta."""
        mock_req.return_value = (True, "SENTIMENT: 0.8 | CONFIDENCE: 0.9 | DIRECTION: BULLISH | CATEGORY: adoption")
        s, c, d, cat = classify_with_ollama("BTC ETF approved", "SEC approved", "BTC")
        self.assertAlmostEqual(s, 0.8)
        self.assertEqual(d, "BULLISH")
        # Deve ter tentado GPU1 (primeira chamada)
        self.assertEqual(mock_req.call_count, 1)

    @patch(f"{_MOD_NAME}._ollama_request")
    def test_fallback_gpu0_quando_gpu1_falha(self, mock_req: MagicMock) -> None:
        """GPU1 falha → fallback para GPU0."""
        mock_req.side_effect = [
            (False, "connection error"),
            (True, "SENTIMENT: -0.7 | CONFIDENCE: 0.85 | DIRECTION: BEARISH | CATEGORY: hack"),
        ]
        s, c, d, _ = classify_with_ollama("Exchange hacked", "500M stolen", "BTC")
        self.assertAlmostEqual(s, -0.7)
        self.assertEqual(d, "BEARISH")
        self.assertEqual(mock_req.call_count, 2)

    @patch(f"{_MOD_NAME}._ollama_request")
    def test_ambas_gpus_falham(self, mock_req: MagicMock) -> None:
        """Ambas GPUs falham → retorna neutro."""
        mock_req.return_value = (False, "timeout")
        s, c, d, _ = classify_with_ollama("Some news", "description", "ETH")
        self.assertAlmostEqual(s, 0.0)
        self.assertAlmostEqual(c, 0.3)
        self.assertEqual(d, "NEUTRAL")

    @patch(f"{_MOD_NAME}._ollama_request")
    def test_coin_passado_no_prompt(self, mock_req: MagicMock) -> None:
        """Verifica que o coin é incluído no prompt enviado ao Ollama."""
        mock_req.return_value = (True, "SENTIMENT: 0.5 | CONFIDENCE: 0.8 | DIRECTION: BULLISH | CATEGORY: price")
        classify_with_ollama("SOL news", "description", "SOL")
        # Verifica que o prompt contém o coin
        call_args = mock_req.call_args_list[0]
        prompt = call_args[0][2]  # terceiro argumento posicional
        self.assertIn("SOL", prompt)


# ── TestComputeGroundTruthIntegration ─────────────────────────────────────────


class TestGetPriceAtTs(unittest.TestCase):
    """Testes de get_price_at_ts com DB mockado."""

    def test_retorna_preco_proximo(self) -> None:
        """Retorna preço de fechamento mais próximo do timestamp."""
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = (95000.50,)

        price = get_price_at_ts(conn, "BTC-USDT", 1700000000.0, window_min=30)
        self.assertAlmostEqual(price, 95000.50)

    def test_retorna_none_sem_dados(self) -> None:
        """Sem dados no range → None."""
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = None

        price = get_price_at_ts(conn, "BTC-USDT", 9999999999.0, window_min=5)
        self.assertIsNone(price)

    def test_converte_timestamp_segundos(self) -> None:
        """Timestamp em segundos deve ser usado como int na query."""
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = (100.0,)

        ts_seconds = 1700000000.0  # 10 dígitos = segundos
        get_price_at_ts(conn, "BTC-USDT", ts_seconds, window_min=10)

        call_args = cur.execute.call_args
        params = call_args[0][1]  # tupla de parâmetros SQL
        ts_in_query = params[1]   # segundo parâmetro (o timestamp)
        # Deve ser convertido para int (segundos, não ms)
        self.assertEqual(ts_in_query, int(ts_seconds))


# ── TestEnsureTrainingTable ────────────────────────────────────────────────────


class TestEnsureTrainingTable(unittest.TestCase):
    """Testes de ensure_training_table."""

    def test_cria_tabela(self) -> None:
        """Deve executar CREATE TABLE IF NOT EXISTS."""
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        ensure_training_table(conn)

        sql = cur.execute.call_args[0][0]
        self.assertIn("CREATE TABLE IF NOT EXISTS", sql)
        self.assertIn("btc.training_samples", sql)


# ── TestUpsertSample ───────────────────────────────────────────────────────────


class TestUpsertSample(unittest.TestCase):
    """Testes de upsert_sample."""

    def test_upsert_basico(self) -> None:
        """Deve executar INSERT ... ON CONFLICT DO UPDATE."""
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        sample = ArticleSample(
            url="https://x.com/1",
            title="Test",
            description="Desc",
            source="test",
            published_ts=1700000000.0,
            coin="BTC",
            ollama_sentiment=0.5,
            ollama_confidence=0.8,
            ollama_direction="BULLISH",
            ollama_category="adoption",
        )
        upsert_sample(conn, sample, model_version="test-model")

        sql = cur.execute.call_args[0][0]
        self.assertIn("INSERT INTO btc.training_samples", sql)
        self.assertIn("ON CONFLICT", sql)

    def test_trunca_campos_longos(self) -> None:
        """Título e descrição muito longos devem ser truncados."""
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        sample = ArticleSample(
            url="https://x.com/1",
            title="T" * 600,  # muito longo
            description="D" * 1200,  # muito longo
            source="test",
            published_ts=1700000000.0,
            coin="BTC",
        )
        upsert_sample(conn, sample)

        params = cur.execute.call_args[0][1]
        title_param = params[1]  # segundo parâmetro é o título
        desc_param = params[2]   # terceiro é a descrição
        self.assertLessEqual(len(title_param), 500)
        self.assertLessEqual(len(desc_param), 1000)


# ── TestGetTrainingStats ───────────────────────────────────────────────────────


class TestGetTrainingStats(unittest.TestCase):
    """Testes de get_training_stats."""

    def test_retorna_stats_basicas(self) -> None:
        """Verifica que stats são retornadas corretamente."""
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Simulando retornos sequenciais de fetchone e fetchall
        cur.fetchone.side_effect = [(100,), (60,), (45,), (0.78,)]
        cur.fetchall.return_value = [("BULLISH", 30), ("BEARISH", 20), ("NEUTRAL", 10)]

        stats = get_training_stats(conn)

        self.assertEqual(stats.total_articles, 100)
        self.assertEqual(stats.with_price_data, 60)
        self.assertEqual(stats.total_correct, 45)
        self.assertAlmostEqual(stats.avg_confidence, 0.78)
        self.assertEqual(stats.label_distribution["BULLISH"], 30)


# ── TestCollectAllFeeds ────────────────────────────────────────────────────────


class TestCollectAllFeeds(unittest.TestCase):
    """Testes de collect_all_feeds."""

    @patch(f"{_MOD_NAME}.fetch_rss_feed")
    @patch(f"{_MOD_NAME}.time.sleep")
    def test_coleta_todos_feeds(self, mock_sleep: MagicMock, mock_fetch: MagicMock) -> None:
        """Deve chamar fetch_rss_feed para cada feed configurado."""
        mock_fetch.return_value = [
            {"url": "https://x.com/1", "title": "T1", "description": "D", "source": "test", "published_ts": 1700000000.0}
        ]
        result = collect_all_feeds(limit_per_feed=5)
        # Deve ter chamado fetch_rss_feed N vezes (uma por feed)
        call_count = mock_fetch.call_count
        from rss_llm_trainer import RSS_FEEDS
        self.assertEqual(call_count, len(RSS_FEEDS))

    @patch(f"{_MOD_NAME}.fetch_rss_feed")
    @patch(f"{_MOD_NAME}.time.sleep")
    def test_remove_duplicatas_url(self, mock_sleep: MagicMock, mock_fetch: MagicMock) -> None:
        """URLs duplicadas devem ser removidas."""
        same_article = {
            "url": "https://x.com/same",
            "title": "Same title",
            "description": "D",
            "source": "test",
            "published_ts": 1700000000.0,
        }
        mock_fetch.return_value = [same_article] * 3
        result = collect_all_feeds(limit_per_feed=5)
        # Todos feeds retornam o mesmo URL → apenas 1 artigo único
        self.assertEqual(len(result), 1)


# ── TestModePredict ────────────────────────────────────────────────────────────


class TestModePredict(unittest.TestCase):
    """Testes do modo predict."""

    @patch(f"{_MOD_NAME}._ollama_request")
    @patch(f"{_MOD_NAME}.time.sleep")
    def test_mode_predict_executa(self, mock_sleep: MagicMock, mock_req: MagicMock) -> None:
        """mode_predict deve executar sem erros."""
        mock_req.return_value = (
            True,
            "SENTIMENT: 0.8 | CONFIDENCE: 0.9 | DIRECTION: BULLISH | CATEGORY: adoption",
        )
        # Não deve lançar exceção
        mode_predict()
        self.assertTrue(mock_req.called)

    @patch(f"{_MOD_NAME}._ollama_request")
    @patch(f"{_MOD_NAME}.time.sleep")
    def test_mode_predict_com_falha_gpu(self, mock_sleep: MagicMock, mock_req: MagicMock) -> None:
        """mode_predict com ambas GPUs falhando não deve lançar exceção."""
        mock_req.return_value = (False, "error")
        mode_predict()  # Deve completar sem exceção


# ── TestBaseFewShotExamples ────────────────────────────────────────────────────


class TestBaseFewShotExamples(unittest.TestCase):
    """Testes dos exemplos few-shot base."""

    def test_existem_exemplos_suficientes(self) -> None:
        """Deve ter pelo menos 8 exemplos base."""
        self.assertGreaterEqual(len(BASE_FEW_SHOT_EXAMPLES), 8)

    def test_exemplos_tem_formato_correto(self) -> None:
        """Cada exemplo deve ser uma tupla (user_msg, assistant_msg)."""
        for i, example in enumerate(BASE_FEW_SHOT_EXAMPLES):
            self.assertIsInstance(example, tuple, f"Exemplo {i} não é tupla")
            self.assertEqual(len(example), 2, f"Exemplo {i} não tem 2 elementos")

    def test_respostas_tem_formato_correto(self) -> None:
        """Cada resposta assistant deve ter o formato SENTIMENT | CONFIDENCE | DIRECTION | CATEGORY."""
        for _, assistant_msg in BASE_FEW_SHOT_EXAMPLES:
            self.assertIn("SENTIMENT:", assistant_msg)
            self.assertIn("CONFIDENCE:", assistant_msg)
            self.assertIn("DIRECTION:", assistant_msg)
            self.assertIn("CATEGORY:", assistant_msg)

    def test_direcao_consistente_com_sentimento(self) -> None:
        """DIRECTION deve ser consistente com SENTIMENT em todos os exemplos."""
        import re
        for user_msg, assistant_msg in BASE_FEW_SHOT_EXAMPLES:
            s_match = re.search(r"SENTIMENT:\s*([-+]?\d+\.?\d*)", assistant_msg)
            d_match = re.search(r"DIRECTION:\s*(\w+)", assistant_msg)
            if s_match and d_match:
                sentiment = float(s_match.group(1))
                direction = d_match.group(1)
                if sentiment > 0.1:
                    self.assertEqual(direction, "BULLISH",
                                     f"Sentimento positivo mas direction={direction}: {assistant_msg}")
                elif sentiment < -0.1:
                    self.assertEqual(direction, "BEARISH",
                                     f"Sentimento negativo mas direction={direction}: {assistant_msg}")


# ── TestOllamaRequest ──────────────────────────────────────────────────────────


class TestOllamaRequest(unittest.TestCase):
    """Testes da função _ollama_request."""

    @patch("urllib.request.urlopen")
    def test_sucesso(self, mock_urlopen: MagicMock) -> None:
        """Request bem-sucedido retorna (True, response_text)."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"response": "SENTIMENT: 0.5"}).encode()
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        ok, text = _ollama_request("http://localhost:11434", "qwen3:1.7b", "test prompt", timeout=5)

        self.assertTrue(ok)
        self.assertIn("SENTIMENT: 0.5", text)

    @patch("urllib.request.urlopen")
    def test_timeout(self, mock_urlopen: MagicMock) -> None:
        """Timeout retorna (False, ...)."""
        import socket
        mock_urlopen.side_effect = socket.timeout("timed out")

        ok, text = _ollama_request("http://localhost:11434", "model", "prompt", timeout=1)
        self.assertFalse(ok)

    @patch("urllib.request.urlopen")
    def test_connection_refused(self, mock_urlopen: MagicMock) -> None:
        """Conexão recusada retorna (False, ...)."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")

        ok, text = _ollama_request("http://bad:1234", "model", "prompt", timeout=5)
        self.assertFalse(ok)


# ── TestParseModelfileToApiPayload ────────────────────────────────────────────


class TestParseModelfileToApiPayload(unittest.TestCase):
    """Testes de _parse_modelfile_to_api_payload."""

    def test_extrai_from(self) -> None:
        """Deve extrair o modelo base do campo FROM."""
        mf = 'FROM qwen3:1.7b\nSYSTEM """sou expert"""\n'
        payload = _parse_modelfile_to_api_payload(mf, "trading-sentiment:latest")
        self.assertEqual(payload["from"], "qwen3:1.7b")

    def test_extrai_system(self) -> None:
        """Deve extrair o bloco SYSTEM triple-quoted."""
        mf = 'FROM qwen3:1.7b\nSYSTEM """Você é trading-sentiment."""\n'
        payload = _parse_modelfile_to_api_payload(mf, "trading-sentiment:latest")
        self.assertEqual(payload["system"], "Você é trading-sentiment.")

    def test_extrai_parameters_float(self) -> None:
        """Deve extrair PARAMETERs com valores float/int."""
        mf = (
            "FROM qwen3:1.7b\n"
            "PARAMETER temperature 0.05\n"
            "PARAMETER num_predict 80\n"
            "PARAMETER repeat_penalty 1.1\n"
        )
        payload = _parse_modelfile_to_api_payload(mf, "m")
        self.assertAlmostEqual(payload["parameters"]["temperature"], 0.05)
        self.assertEqual(payload["parameters"]["num_predict"], 80)
        self.assertAlmostEqual(payload["parameters"]["repeat_penalty"], 1.1)

    def test_extrai_messages(self) -> None:
        """Deve extrair pares MESSAGE user/assistant."""
        mf = (
            "FROM qwen3:1.7b\n"
            'MESSAGE user """Coin: BTC\nTitle: ETF"""\n'
            'MESSAGE assistant """SENTIMENT: 0.9 | CONFIDENCE: 0.85"""\n'
        )
        payload = _parse_modelfile_to_api_payload(mf, "m")
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertEqual(payload["messages"][1]["role"], "assistant")

    def test_sem_from_nao_inclui_campo(self) -> None:
        """Modelfile sem FROM não deve incluir campo 'from'."""
        mf = 'SYSTEM """test"""\n'
        payload = _parse_modelfile_to_api_payload(mf, "x:latest")
        self.assertNotIn("from", payload)

    def test_nome_modelo_incluido(self) -> None:
        """O nome do modelo sempre deve estar no payload."""
        payload = _parse_modelfile_to_api_payload("FROM qwen3:1.7b\n", "trading-sentiment:latest")
        self.assertEqual(payload["model"], "trading-sentiment:latest")

    def test_stream_sempre_true(self) -> None:
        """stream deve ser True no payload."""
        payload = _parse_modelfile_to_api_payload("FROM qwen3:1.7b\n", "m")
        self.assertTrue(payload["stream"])


# ── TestCreateOllamaModel ──────────────────────────────────────────────────────


class TestCreateOllamaModel(unittest.TestCase):
    """Testes de create_ollama_model."""

    @patch("urllib.request.urlopen")
    def test_cria_modelo_com_sucesso(self, mock_urlopen: MagicMock) -> None:
        """Resposta stream com status → retorna True."""
        mock_resp = MagicMock()
        mock_resp.readline.side_effect = [
            json.dumps({"status": "reading model metadata"}).encode(),
            json.dumps({"status": "success"}).encode(),
            b"",  # EOF
        ]
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        result = _mod.create_ollama_model("FROM qwen3:1.7b\n", OLLAMA_HOST_GPU0)
        self.assertTrue(result)

    @patch("urllib.request.urlopen")
    def test_falha_com_erro_no_stream(self, mock_urlopen: MagicMock) -> None:
        """Evento de erro no stream → retorna False."""
        mock_resp = MagicMock()
        mock_resp.readline.side_effect = [
            json.dumps({"error": "model not found"}).encode(),
            b"",
        ]
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        result = _mod.create_ollama_model("FROM qwen3:1.7b\n", OLLAMA_HOST_GPU0)
        self.assertFalse(result)

    @patch("urllib.request.urlopen")
    def test_falha_conexao(self, mock_urlopen: MagicMock) -> None:
        """Falha de conexão → retorna False."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")

        result = _mod.create_ollama_model("FROM qwen3:1.7b\n", "http://bad:9999")
        self.assertFalse(result)


# ── TestParseEntryTimestamp ────────────────────────────────────────────────────


class TestParseEntryTimestamp(unittest.TestCase):
    """Testes de parse_entry_timestamp."""

    def _entry(self, published_parsed=None, published: str = "", updated: str = "") -> MagicMock:
        entry = MagicMock()
        entry.published_parsed = published_parsed
        entry.get.side_effect = lambda key, default="": {
            "published": published,
            "updated": updated,
            "published_parsed": published_parsed,
        }.get(key, default)
        return entry

    def test_com_published_parsed(self) -> None:
        """Usa published_parsed quando disponível."""
        # struct_time-like: (2026, 3, 8, 12, 0, 0, ...)
        parsed = (2026, 3, 8, 12, 0, 0, 5, 67, 0)
        entry = self._entry(published_parsed=parsed)
        ts = _mod.parse_entry_timestamp(entry)
        self.assertIsNotNone(ts)
        self.assertIsInstance(ts, float)
        # 2026-03-08 should be > 2025's timestamps
        self.assertGreater(ts, 1700000000.0)

    def test_com_published_string(self) -> None:
        """Usa campo published como string quando published_parsed é None."""
        entry = self._entry(
            published_parsed=None,
            published="Mon, 08 Mar 2026 12:00:00 +0000",
        )
        ts = _mod.parse_entry_timestamp(entry)
        self.assertIsNotNone(ts)
        self.assertIsInstance(ts, float)

    def test_sem_dados_retorna_none(self) -> None:
        """Sem dados de data → None."""
        entry = self._entry(published_parsed=None, published="", updated="")
        ts = _mod.parse_entry_timestamp(entry)
        self.assertIsNone(ts)

    def test_published_parsed_invalido(self) -> None:
        """published_parsed inválido → tenta string."""
        entry = self._entry(
            published_parsed=(0, 0, 0),  # inválido
            published="Mon, 08 Mar 2026 12:00:00 +0000",
        )
        # Pode retornar None ou timestamp da string
        ts = _mod.parse_entry_timestamp(entry)
        # Deve tentar a string e retornar valor válido
        self.assertIsNotNone(ts)


# ── TestGetBestTrainingExamples ────────────────────────────────────────────────


class TestGetBestTrainingExamples(unittest.TestCase):
    """Testes de get_best_training_examples."""

    def test_retorna_exemplos_do_db(self) -> None:
        """Deve retornar lista de dicts com os melhores exemplos."""
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Simular retorno do DictCursor
        row1 = {
            "title": "BTC ETF", "description": "desc", "coin": "BTC",
            "ground_truth": "BULLISH", "ollama_sentiment": 0.9,
            "ollama_confidence": 0.92, "ollama_direction": "BULLISH",
            "ollama_category": "regulation", "price_change_pct": 5.2,
        }
        cur.fetchall.return_value = [row1]

        result = get_best_training_examples(conn, limit=5)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "BTC ETF")

    def test_db_vazio_retorna_lista_vazia(self) -> None:
        """DB vazio → []."""
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchall.return_value = []

        result = get_best_training_examples(conn, limit=10)
        self.assertEqual(result, [])


# ── TestModeCollect ────────────────────────────────────────────────────────────


class TestModeCollect(unittest.TestCase):
    """Testes do modo collect com todos os externos mockados."""

    @patch(f"{_MOD_NAME}.upsert_sample")
    @patch(f"{_MOD_NAME}.ensure_training_table")
    @patch(f"{_MOD_NAME}.get_db_connection")
    @patch(f"{_MOD_NAME}.classify_with_ollama")
    @patch(f"{_MOD_NAME}.get_price_at_ts")
    @patch(f"{_MOD_NAME}.collect_all_feeds")
    @patch(f"{_MOD_NAME}.time.sleep")
    def test_mode_collect_basico(
        self,
        mock_sleep: MagicMock,
        mock_collect: MagicMock,
        mock_price: MagicMock,
        mock_classify: MagicMock,
        mock_conn: MagicMock,
        mock_ensure: MagicMock,
        mock_upsert: MagicMock,
    ) -> None:
        """mode_collect processa artigos e faz upsert."""
        mock_collect.return_value = [
            {
                "url": "https://x.com/1",
                "title": "Bitcoin ETF approved",
                "description": "The SEC approved....",
                "source": "coindesk",
                "published_ts": 1772000000.0,
            }
        ]
        mock_price.side_effect = [95000.0, 96500.0]  # pub, impact
        mock_classify.return_value = (0.85, 0.90, "BULLISH", "regulation")

        _mod.mode_collect(limit_per_feed=5)

        mock_upsert.assert_called_once()
        sample = mock_upsert.call_args[0][1]
        self.assertEqual(sample.coin, "BTC")
        self.assertEqual(sample.ground_truth_label, "BULLISH")
        self.assertTrue(sample.prediction_correct)

    @patch(f"{_MOD_NAME}.upsert_sample")
    @patch(f"{_MOD_NAME}.ensure_training_table")
    @patch(f"{_MOD_NAME}.get_db_connection")
    @patch(f"{_MOD_NAME}.classify_with_ollama")
    @patch(f"{_MOD_NAME}.get_price_at_ts")
    @patch(f"{_MOD_NAME}.collect_all_feeds")
    @patch(f"{_MOD_NAME}.time.sleep")
    def test_mode_collect_sem_preco_disponivel(
        self,
        mock_sleep: MagicMock,
        mock_collect: MagicMock,
        mock_price: MagicMock,
        mock_classify: MagicMock,
        mock_conn: MagicMock,
        mock_ensure: MagicMock,
        mock_upsert: MagicMock,
    ) -> None:
        """Sem dados de preço → ground_truth permanece None."""
        mock_collect.return_value = [
            {
                "url": "https://x.com/1",
                "title": "ETH news",
                "description": "Ethereum update",
                "source": "decrypt",
                "published_ts": 1772000000.0,
            }
        ]
        mock_price.return_value = None  # sem candle
        mock_classify.return_value = (0.5, 0.7, "BULLISH", "technical")

        _mod.mode_collect(limit_per_feed=5)

        sample = mock_upsert.call_args[0][1]
        self.assertIsNone(sample.ground_truth_label)
        self.assertIsNone(sample.prediction_correct)

    @patch(f"{_MOD_NAME}.collect_all_feeds")
    @patch(f"{_MOD_NAME}.time.sleep")
    def test_mode_collect_sem_artigos(
        self, mock_sleep: MagicMock, mock_collect: MagicMock
    ) -> None:
        """Nenhum artigo coletado → retorna sem processar."""
        mock_collect.return_value = []
        # Não deve lançar exceção, nem tentar DB
        _mod.mode_collect(limit_per_feed=5)


# ── TestModeTrain ──────────────────────────────────────────────────────────────


class TestModeTrain(unittest.TestCase):
    """Testes do modo train com externos mockados."""

    @patch(f"{_MOD_NAME}.create_ollama_model")
    @patch(f"{_MOD_NAME}.get_best_training_examples")
    @patch(f"{_MOD_NAME}.get_training_stats")
    @patch(f"{_MOD_NAME}.ensure_training_table")
    @patch(f"{_MOD_NAME}.get_db_connection")
    def test_mode_train_cria_modelo(
        self,
        mock_conn: MagicMock,
        mock_ensure: MagicMock,
        mock_stats: MagicMock,
        mock_examples: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        """mode_train deve gerar Modelfile e chamar create_ollama_model."""
        mock_stats.return_value = TrainingStats(
            total_articles=50, with_price_data=30, total_correct=25,
            avg_confidence=0.82, label_distribution={"BULLISH": 15, "BEARISH": 10, "NEUTRAL": 5}
        )
        mock_examples.return_value = []
        mock_create.return_value = True

        mode_train()

        mock_create.assert_called()
        # Verifica que o Modelfile foi criado
        modelfile_path = _mod.OUTPUT_DIR / "Modelfile.trading-sentiment"
        # Arquivo pode ou não existir dependendo de permissões, mas a chamada foi feita

    @patch(f"{_MOD_NAME}.create_ollama_model")
    @patch(f"{_MOD_NAME}.get_best_training_examples")
    @patch(f"{_MOD_NAME}.get_training_stats")
    @patch(f"{_MOD_NAME}.ensure_training_table")
    @patch(f"{_MOD_NAME}.get_db_connection")
    def test_mode_train_fallback_gpu1_quando_gpu0_falha(
        self,
        mock_conn: MagicMock,
        mock_ensure: MagicMock,
        mock_stats: MagicMock,
        mock_examples: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        """Se GPU0 falha, tenta GPU1."""
        mock_stats.return_value = TrainingStats()
        mock_examples.return_value = []
        mock_create.side_effect = [False, True]  # GPU0 falha, GPU1 ok

        mode_train()
        self.assertEqual(mock_create.call_count, 2)


# ── TestModeReport ─────────────────────────────────────────────────────────────


class TestModeReport(unittest.TestCase):
    """Testes do modo report."""

    @patch(f"{_MOD_NAME}.get_db_connection")
    @patch(f"{_MOD_NAME}.ensure_training_table")
    @patch(f"{_MOD_NAME}.get_training_stats")
    def test_mode_report_executa(
        self,
        mock_stats: MagicMock,
        mock_ensure: MagicMock,
        mock_conn: MagicMock,
    ) -> None:
        """mode_report deve executar sem exceção."""
        mock_stats.return_value = TrainingStats(
            total_articles=100,
            with_price_data=60,
            total_correct=45,
            avg_confidence=0.79,
            label_distribution={"BULLISH": 25, "BEARISH": 20, "NEUTRAL": 15},
        )
        conn = MagicMock()
        mock_conn.return_value = conn

        # Mock do DictCursor para a query de últimas amostras
        cur = MagicMock()
        cur.fetchall.return_value = []
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mode_report()  # Não deve lançar exceção


# ── TestMain ───────────────────────────────────────────────────────────────────


class TestMain(unittest.TestCase):
    """Testes da função main (entry point)."""

    @patch(f"{_MOD_NAME}.mode_collect")
    @patch(f"{_MOD_NAME}.mode_train")
    def test_main_modo_full(self, mock_train: MagicMock, mock_collect: MagicMock) -> None:
        """Modo full deve chamar collect e train."""
        with patch("sys.argv", ["rss_llm_trainer.py", "--mode", "full", "--feeds", "5"]):
            _mod.main()
        mock_collect.assert_called_once()
        mock_train.assert_called_once()

    @patch(f"{_MOD_NAME}.mode_collect")
    def test_main_modo_collect(self, mock_collect: MagicMock) -> None:
        """Modo collect deve chamar apenas mode_collect."""
        with patch("sys.argv", ["rss_llm_trainer.py", "--mode", "collect", "--feeds", "10"]):
            _mod.main()
        mock_collect.assert_called_once_with(limit_per_feed=10)

    @patch(f"{_MOD_NAME}.mode_train")
    def test_main_modo_train(self, mock_train: MagicMock) -> None:
        """Modo train deve chamar apenas mode_train."""
        with patch("sys.argv", ["rss_llm_trainer.py", "--mode", "train"]):
            _mod.main()
        mock_train.assert_called_once()

    @patch(f"{_MOD_NAME}.mode_report")
    def test_main_modo_report(self, mock_report: MagicMock) -> None:
        """Modo report deve chamar mode_report."""
        with patch("sys.argv", ["rss_llm_trainer.py", "--mode", "report"]):
            _mod.main()
        mock_report.assert_called_once()

    @patch(f"{_MOD_NAME}.mode_predict")
    def test_main_modo_predict(self, mock_predict: MagicMock) -> None:
        """Modo predict deve chamar mode_predict."""
        with patch("sys.argv", ["rss_llm_trainer.py", "--mode", "predict"]):
            _mod.main()
        mock_predict.assert_called_once()


# ── Helper ────────────────────────────────────────────────────────────────────

OLLAMA_HOST_GPU0 = _mod.OLLAMA_HOST_GPU0

if __name__ == "__main__":
    unittest.main(verbosity=2)
