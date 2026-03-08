"""Testes unitários para o exportador de métricas Storj."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from tools.storj_exporter import StorjMetrics


@pytest.fixture
def mock_sno_response() -> dict:
    """Retorna resposta mock da API SNO do Storj."""
    return {
        "nodeID": "12hFihxX45hZGVyrGgpjNKwmSYGsMCuRF2GnbjJ76Kuw7i8YoYK",
        "version": "1.142.7",
        "upToDate": True,
        "quicStatus": "OK",
        "diskSpace": {
            "used": 1073741824,
            "available": 268435456000,
            "trash": 52428800,
            "overused": 0,
        },
        "bandwidth": {"used": 536870912},
        "satellites": [
            {
                "id": "12EayRS2V1kEsWESU9QMRseFhdxYxKicsiFmxrsLZHeLUtdps3S",
                "url": "us1.storj.io:7777",
                "auditScore": 1.0,
                "suspensionScore": 1.0,
                "onlineScore": 0.998,
                "disqualified": None,
                "suspended": None,
            }
        ],
    }


@pytest.fixture
def mock_payout_response() -> dict:
    """Retorna resposta mock da API de pagamento estimado."""
    return {
        "currentMonth": {
            "egressBandwidthPayout": 15,
            "diskSpacePayout": 42,
            "held": 10,
        },
        "previousMonth": {
            "egressBandwidthPayout": 10,
            "diskSpacePayout": 30,
        },
    }


class TestStorjMetrics:
    """Testes para a classe StorjMetrics."""

    def test_collect_success(
        self, mock_sno_response: dict, mock_payout_response: dict
    ) -> None:
        """Verifica coleta de métricas com resposta válida."""
        collector = StorjMetrics(base_url="http://fake:14002/api")

        with patch.object(collector, "_get") as mock_get:
            mock_get.side_effect = lambda ep: {
                "sno/": mock_sno_response,
                "sno/estimated-payout": mock_payout_response,
            }.get(ep)

            metrics = collector.collect()

        assert "storj_node_online 1" in metrics
        assert "storj_disk_used_bytes 1073741824" in metrics
        assert "storj_disk_available_bytes 268435456000" in metrics
        assert "storj_disk_trash_bytes 52428800" in metrics
        assert "storj_bandwidth_used_bytes 536870912" in metrics
        assert "storj_satellites_count 1" in metrics
        assert "storj_quic_ok 1" in metrics
        assert "storj_version_up_to_date 1" in metrics
        assert "storj_audit_score" in metrics
        assert "storj_online_score" in metrics
        assert "storj_payout_current_month_cents 57" in metrics
        assert "storj_payout_current_egress_cents 15" in metrics
        assert "storj_payout_current_storage_cents 42" in metrics
        assert "storj_payout_current_held_cents 10" in metrics
        assert "storj_payout_previous_month_cents 40" in metrics
        assert "storj_exporter_up 1" in metrics

    def test_collect_api_down(self) -> None:
        """Verifica que exporter não quebra se API do Storj estiver offline."""
        collector = StorjMetrics(base_url="http://fake:14002/api")

        with patch.object(collector, "_get", return_value=None):
            metrics = collector.collect()

        assert "storj_exporter_up 1" in metrics
        assert "storj_node_online" not in metrics

    def test_collect_partial_response(self, mock_sno_response: dict) -> None:
        """Verifica coleta quando apenas SNO responde (sem payout)."""
        collector = StorjMetrics(base_url="http://fake:14002/api")

        with patch.object(collector, "_get") as mock_get:
            mock_get.side_effect = lambda ep: {
                "sno/": mock_sno_response,
                "sno/estimated-payout": None,
            }.get(ep)

            metrics = collector.collect()

        assert "storj_node_online 1" in metrics
        assert "storj_payout_current_month_cents" not in metrics

    def test_get_request_error(self) -> None:
        """Verifica tratamento de erro de conexão."""
        from urllib.error import URLError

        collector = StorjMetrics(base_url="http://fake:14002/api")

        with patch("tools.storj_exporter.urlopen", side_effect=URLError("refused")):
            result = collector._get("sno/")

        assert result is None

    def test_node_offline_indicator(self) -> None:
        """Verifica indicador online=0 quando nodeID ausente."""
        collector = StorjMetrics(base_url="http://fake:14002/api")

        with patch.object(collector, "_get") as mock_get:
            mock_get.side_effect = lambda ep: {
                "sno/": {"diskSpace": {}, "bandwidth": {}, "satellites": []},
                "sno/estimated-payout": None,
            }.get(ep)

            metrics = collector.collect()

        assert "storj_node_online 0" in metrics
        assert "storj_satellites_count 0" in metrics

    def test_disk_usage_percent(self, mock_sno_response: dict) -> None:
        """Verifica cálculo de percentual de uso."""
        collector = StorjMetrics(base_url="http://fake:14002/api")

        with patch.object(collector, "_get") as mock_get:
            mock_get.side_effect = lambda ep: {
                "sno/": mock_sno_response,
                "sno/estimated-payout": None,
            }.get(ep)

            metrics = collector.collect()

        # 1073741824 / 268435456000 * 100 = 0.4
        assert "storj_disk_usage_percent 0.4" in metrics

    def test_satellite_disqualified_flag(self) -> None:
        """Verifica flag de desqualificação de satélite."""
        collector = StorjMetrics(base_url="http://fake:14002/api")

        sno = {
            "nodeID": "test",
            "diskSpace": {},
            "bandwidth": {},
            "satellites": [
                {
                    "id": "12EayRS2V1kEsW",
                    "url": "us1.storj.io:7777",
                    "auditScore": 0.5,
                    "suspensionScore": 0.0,
                    "onlineScore": 0.3,
                    "disqualified": "2026-01-01T00:00:00Z",
                    "suspended": None,
                }
            ],
        }

        with patch.object(collector, "_get") as mock_get:
            mock_get.side_effect = lambda ep: {
                "sno/": sno,
                "sno/estimated-payout": None,
            }.get(ep)

            metrics = collector.collect()

        assert "storj_satellite_disqualified" in metrics
        assert 'storj_satellite_disqualified{satellite_id="12EayRS2V1kEsW",url="us1.storj.io"} 1' in metrics
