"""Testes unitários para kucoin_postgres_sync — foco na reconciliação de orphans."""
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Stub modules importados pelo script antes de importar o módulo real
sys.modules.setdefault("kucoin_api", MagicMock())
sys.modules.setdefault("secrets_helper", MagicMock())

# Garantir que o diretório de scripts esteja no path
SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import kucoin_postgres_sync as sync  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_fills():
    """Fills simulados da KuCoin (2 orders, 3 fills)."""
    ts = int(time.time() * 1000)
    return [
        {
            "orderId": "order-AAA",
            "tradeId": "trade-1",
            "symbol": "BTC-USDT",
            "side": "buy",
            "price": "72000.0",
            "size": "0.0001",
            "funds": "7.2",
            "createdAt": ts,
        },
        {
            "orderId": "order-AAA",
            "tradeId": "trade-2",
            "symbol": "BTC-USDT",
            "side": "buy",
            "price": "72100.0",
            "size": "0.00005",
            "funds": "3.605",
            "createdAt": ts + 100,
        },
        {
            "orderId": "order-BBB",
            "tradeId": "trade-3",
            "symbol": "BTC-USDT",
            "side": "sell",
            "price": "73000.0",
            "size": "0.00015",
            "funds": "10.95",
            "createdAt": ts + 5000,
        },
    ]


@pytest.fixture()
def mock_cursor():
    """Cursor mock com tracking de queries executadas."""
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


# ---------------------------------------------------------------------------
# Tests: _aggregate_fills
# ---------------------------------------------------------------------------

class TestAggregateFills:
    """Testes para agregação de fills por order_id."""

    def test_aggregates_by_order_id(self, sample_fills):
        """Fills com mesmo orderId devem ser agrupados."""
        grouped = sync._aggregate_fills(sample_fills)
        assert len(grouped) == 2
        assert "order-AAA" in grouped
        assert "order-BBB" in grouped

    def test_aggregated_size_is_sum(self, sample_fills):
        """Size do grupo deve ser soma dos fills individuais."""
        grouped = sync._aggregate_fills(sample_fills)
        aaa = grouped["order-AAA"]
        assert abs(aaa["size"] - 0.00015) < 1e-10

    def test_aggregated_price_is_weighted_avg(self, sample_fills):
        """Preço do grupo deve ser média ponderada por size."""
        grouped = sync._aggregate_fills(sample_fills)
        aaa = grouped["order-AAA"]
        expected_price = (72000.0 * 0.0001 + 72100.0 * 0.00005) / 0.00015
        assert abs(aaa["price"] - expected_price) < 0.01

    def test_skips_fills_without_order_id(self):
        """Fills sem orderId devem ser ignorados."""
        fills = [
            {"orderId": "", "tradeId": "t1", "price": "70000", "size": "0.001", "funds": "70"},
            {"tradeId": "t2", "price": "70000", "size": "0.001", "funds": "70"},
        ]
        grouped = sync._aggregate_fills(fills)
        assert len(grouped) == 0

    def test_trade_ids_are_deduplicated(self):
        """Trade IDs duplicados devem ser removidos."""
        fills = [
            {"orderId": "X", "tradeId": "t1", "symbol": "BTC-USDT", "side": "buy",
             "price": "1", "size": "1", "funds": "1", "createdAt": 1000},
            {"orderId": "X", "tradeId": "t1", "symbol": "BTC-USDT", "side": "buy",
             "price": "1", "size": "1", "funds": "1", "createdAt": 1000},
        ]
        grouped = sync._aggregate_fills(fills)
        assert grouped["X"]["trade_ids"] == ["t1"]

    def test_side_is_lowered(self, sample_fills):
        """Campo side deve ser normalizado para minúsculas."""
        fills = [
            {"orderId": "Z", "tradeId": "t1", "symbol": "BTC-USDT", "side": "BUY",
             "price": "100", "size": "1", "funds": "100", "createdAt": 1000},
        ]
        grouped = sync._aggregate_fills(fills)
        assert grouped["Z"]["side"] == "buy"


# ---------------------------------------------------------------------------
# Tests: _match_orphan_to_fill
# ---------------------------------------------------------------------------

class TestMatchOrphanToFill:
    """Testes para vinculação de fills KuCoin a trades órfãos do agent."""

    def test_matches_orphan_by_timestamp_side_size(self, mock_cursor):
        """Deve encontrar orphan trade com timestamp e size próximos."""
        ts = time.time()
        orphan_row = {
            "id": 42,
            "size": 0.000135,
            "timestamp": ts - 5,
            "metadata": json.dumps({"source": "external_deposit"}),
        }
        mock_cursor.fetchone = MagicMock(return_value=orphan_row)

        fill_row = {
            "symbol": "BTC-USDT",
            "side": "buy",
            "size": 0.000137,
            "price": 72000.0,
            "funds": 9.864,
            "trade_ids": ["t1"],
            "raw_fills": [{"tradeId": "t1"}],
        }
        result = sync._match_orphan_to_fill(mock_cursor, "order-123", fill_row, ts)
        assert result == 42

        # Verificar que UPDATE foi chamado com order_id correto
        update_call = mock_cursor.execute.call_args_list[-1]
        update_sql = update_call[0][0]
        update_params = update_call[0][1]
        assert "UPDATE" in update_sql
        assert update_params[0] == "order-123"  # order_id

    def test_no_match_when_no_orphan_found(self, mock_cursor):
        """Retorna None se nenhum orphan encontrado."""
        mock_cursor.fetchone = MagicMock(return_value=None)

        fill_row = {
            "symbol": "BTC-USDT",
            "side": "buy",
            "size": 0.001,
            "price": 72000.0,
            "funds": 72.0,
            "trade_ids": [],
            "raw_fills": [],
        }
        result = sync._match_orphan_to_fill(mock_cursor, "order-X", fill_row, time.time())
        assert result is None

    def test_no_match_when_size_is_zero(self, mock_cursor):
        """Retorna None se fill tem size=0."""
        fill_row = {
            "symbol": "BTC-USDT",
            "side": "buy",
            "size": 0.0,
            "price": 72000.0,
            "funds": 0.0,
            "trade_ids": [],
            "raw_fills": [],
        }
        result = sync._match_orphan_to_fill(mock_cursor, "order-X", fill_row, time.time())
        assert result is None
        mock_cursor.execute.assert_not_called()

    def test_preserves_original_source_in_metadata(self, mock_cursor):
        """Metadata deve manter original_source para rastreabilidade."""
        ts = time.time()
        orphan_row = {
            "id": 99,
            "size": 0.001,
            "timestamp": ts,
            "metadata": {"source": "external_deposit", "auto_detected": True},
        }
        mock_cursor.fetchone = MagicMock(return_value=orphan_row)

        fill_row = {
            "symbol": "BTC-USDT",
            "side": "buy",
            "size": 0.001,
            "price": 70000.0,
            "funds": 70.0,
            "trade_ids": ["t5"],
            "raw_fills": [],
        }
        sync._match_orphan_to_fill(mock_cursor, "order-Y", fill_row, ts)

        update_call = mock_cursor.execute.call_args_list[-1]
        metadata_json = update_call[0][1][5]  # 6th param (metadata)
        metadata = json.loads(metadata_json)
        assert metadata["original_source"] == "external_deposit"
        assert metadata["matched_by"] == "orphan_fill_reconciliation"
        assert metadata["source"] == "kucoin_sync"


# ---------------------------------------------------------------------------
# Tests: _row_event_timestamp
# ---------------------------------------------------------------------------

class TestRowEventTimestamp:
    """Testes para conversão de timestamp de fill."""

    def test_converts_ms_to_seconds(self):
        row = {"created_at": 1775600000000}
        result = sync._row_event_timestamp(row)
        assert abs(result - 1775600000.0) < 0.001

    def test_returns_current_time_when_none(self):
        row = {"created_at": None}
        before = time.time()
        result = sync._row_event_timestamp(row)
        after = time.time()
        assert before <= result <= after

    def test_handles_invalid_value(self):
        row = {"created_at": "invalid"}
        before = time.time()
        result = sync._row_event_timestamp(row)
        after = time.time()
        assert before <= result <= after


# ---------------------------------------------------------------------------
# Tests: _safe_float
# ---------------------------------------------------------------------------

class TestSafeFloat:
    """Testes para conversão segura de float."""

    def test_converts_string(self):
        assert sync._safe_float("72000.5") == 72000.5

    def test_converts_int(self):
        assert sync._safe_float(42) == 42.0

    def test_returns_zero_for_none(self):
        assert sync._safe_float(None) == 0.0

    def test_returns_zero_for_invalid(self):
        assert sync._safe_float("abc") == 0.0


# ---------------------------------------------------------------------------
# Tests: _sync_fills (integration-style com mocks)
# ---------------------------------------------------------------------------

class TestSyncFills:
    """Testes de integração para _sync_fills com DB mockado."""

    @patch.object(sync, "get_fills")
    @patch.object(sync, "_trades_has_profile", return_value=True)
    def test_inserts_new_fill(self, mock_hp, mock_gf):
        """Fill novo (order_id não existe no BD) deve ser inserido."""
        ts = int(time.time() * 1000)
        mock_gf.return_value = [{
            "orderId": "new-order",
            "tradeId": "t1",
            "symbol": "BTC-USDT",
            "side": "buy",
            "price": "72000",
            "size": "0.001",
            "funds": "72",
            "createdAt": ts,
        }]

        mock_conn = MagicMock()
        mock_cur = MagicMock(spec=["execute", "fetchone", "__enter__", "__exit__"])
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        # fetchone: 1st call=no existing, 2nd call=no orphan, 3rd call=inserted id
        mock_cur.fetchone = MagicMock(side_effect=[None, None, {"id": 999}])
        mock_conn.cursor.return_value = mock_cur

        result = sync._sync_fills(mock_conn)
        assert result == 1

    @patch.object(sync, "get_fills")
    @patch.object(sync, "_trades_has_profile", return_value=True)
    def test_updates_existing_fill(self, mock_hp, mock_gf):
        """Fill com order_id existente deve atualizar, não inserir."""
        ts = int(time.time() * 1000)
        mock_gf.return_value = [{
            "orderId": "existing-order",
            "tradeId": "t1",
            "symbol": "BTC-USDT",
            "side": "buy",
            "price": "72000",
            "size": "0.001",
            "funds": "72",
            "createdAt": ts,
        }]

        mock_conn = MagicMock()
        mock_cur = MagicMock(spec=["execute", "fetchone", "__enter__", "__exit__"])
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        # fetchone: existing row found
        mock_cur.fetchone = MagicMock(return_value={"id": 100, "metadata": {}})
        mock_conn.cursor.return_value = mock_cur

        result = sync._sync_fills(mock_conn)
        assert result == 0  # no inserts, only updates

    @patch.object(sync, "get_fills")
    @patch.object(sync, "_trades_has_profile", return_value=True)
    @patch.object(sync, "_match_orphan_to_fill", return_value=42)
    def test_matches_orphan_instead_of_inserting(self, mock_match, mock_hp, mock_gf):
        """Fill sem order_id no BD deve tentar match com orphan antes de inserir."""
        ts = int(time.time() * 1000)
        mock_gf.return_value = [{
            "orderId": "orphan-match-order",
            "tradeId": "t1",
            "symbol": "BTC-USDT",
            "side": "buy",
            "price": "72000",
            "size": "0.001",
            "funds": "72",
            "createdAt": ts,
        }]

        mock_conn = MagicMock()
        mock_cur = MagicMock(spec=["execute", "fetchone", "__enter__", "__exit__"])
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone = MagicMock(return_value=None)  # no existing by order_id
        mock_conn.cursor.return_value = mock_cur

        result = sync._sync_fills(mock_conn)
        assert result == 0  # no inserts — orphan was matched
        mock_match.assert_called_once()
