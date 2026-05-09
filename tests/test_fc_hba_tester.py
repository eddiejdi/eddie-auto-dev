"""Testes unitários para tools/fc_hba_tester.py — agente testador dual HBA FC.

Estratégia:
- Todas as leituras de sysfs e chamadas SCSI são mockadas.
- Nenhum hardware real é necessário.
- Cobertura de todos os 7 sub-testes + orquestrador + renderização + serialização.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Adiciona tools/ ao path para import direto
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.fc_hba_tester import (
    check_error_counters,
    check_link_state,
    check_lip_stability,
    check_port_speed,
    check_reconnect_time,
    check_tgt_reachability,
    check_transfer_latency,
    MAX_ERROR_THRESHOLD,
    MAX_LATENCY_MS,
    MAX_LIP_PER_MINUTE,
    MAX_RECONNECT_MS,
    HBATestReport,
    PortReport,
    FCTestResult,
    render_text_report,
    report_to_dict,
    run_dual_hba_test,
    run_port_test,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────

ONLINE_STATE = "Online"
OFFLINE_STATE = "Linkdown"

GOOD_COUNTERS: dict[str, int] = {
    "invalid_crc_count": 0,
    "loss_of_signal_count": 0,
    "loss_of_sync_count": 0,
    "link_failure_count": 0,
    "tx_frames": 1000,
    "rx_frames": 1000,
}

BAD_COUNTERS: dict[str, int] = {
    "invalid_crc_count": 15,
    "loss_of_signal_count": 8,
    "loss_of_sync_count": 3,
    "link_failure_count": 5,
    "tx_frames": 1000,
    "rx_frames": 980,
}


@pytest.fixture()
def host() -> str:
    return "host0"


# ─── T1: link_state ──────────────────────────────────────────────────────────

class TestLinkState:
    def test_online_passes_with_full_score(self, host: str) -> None:
        with patch("tools.fc_hba_tester._read_port_state", return_value=ONLINE_STATE):
            r = check_link_state(host)
        assert r.passed is True
        assert r.score == 100.0
        assert r.name == "link_state"

    def test_offline_fails_with_zero_score(self, host: str) -> None:
        with patch("tools.fc_hba_tester._read_port_state", return_value=OFFLINE_STATE):
            r = check_link_state(host)
        assert r.passed is False
        assert r.score == 0.0
        assert OFFLINE_STATE in r.message

    def test_unreadable_sysfs_fails(self, host: str) -> None:
        with patch("tools.fc_hba_tester._read_port_state", return_value=""):
            r = check_link_state(host)
        assert r.passed is False


# ─── T2: port_speed ──────────────────────────────────────────────────────────

class TestPortSpeed:
    def _mock_speed(self, negotiated: str, supported: str) -> tuple[str, str]:
        return negotiated, supported

    def test_max_speed_full_score(self, host: str) -> None:
        with patch("tools.fc_hba_tester._read_port_speed", return_value="8 Gbit"), \
             patch("tools.fc_hba_tester._read_supported_speeds", return_value="8 Gbit"):
            r = check_port_speed(host)
        assert r.passed is True
        assert r.score == 100.0

    def test_half_speed_reduced_score(self, host: str) -> None:
        with patch("tools.fc_hba_tester._read_port_speed", return_value="4 Gbit"), \
             patch("tools.fc_hba_tester._read_supported_speeds", return_value="8 Gbit"):
            r = check_port_speed(host)
        assert r.passed is True
        assert r.score == 50.0

    def test_unreadable_speed_partial_score(self, host: str) -> None:
        with patch("tools.fc_hba_tester._read_port_speed", return_value="unknown"), \
             patch("tools.fc_hba_tester._read_supported_speeds", return_value=""):
            r = check_port_speed(host)
        assert r.passed is False
        assert 0.0 <= r.score <= 50.0


# ─── T3: error_counters ──────────────────────────────────────────────────────

class TestErrorCounters:
    def test_zero_errors_full_score(self, host: str) -> None:
        with patch("tools.fc_hba_tester._reset_error_counters"), \
             patch("tools.fc_hba_tester._read_error_counters", return_value=GOOD_COUNTERS):
            r = check_error_counters(host, window_s=0)
        assert r.passed is True
        assert r.score == 100.0

    def test_many_errors_low_score(self, host: str) -> None:
        with patch("tools.fc_hba_tester._reset_error_counters"), \
             patch("tools.fc_hba_tester._read_error_counters", return_value=BAD_COUNTERS):
            r = check_error_counters(host, window_s=0)
        assert r.passed is False
        assert r.score < 50.0

    def test_borderline_threshold_passes(self, host: str) -> None:
        borderline = {**GOOD_COUNTERS, "link_failure_count": MAX_ERROR_THRESHOLD}
        with patch("tools.fc_hba_tester._reset_error_counters"), \
             patch("tools.fc_hba_tester._read_error_counters", return_value=borderline):
            r = check_error_counters(host, window_s=0)
        assert r.passed is True

    def test_over_threshold_fails(self, host: str) -> None:
        over = {**GOOD_COUNTERS, "link_failure_count": MAX_ERROR_THRESHOLD + 1}
        with patch("tools.fc_hba_tester._reset_error_counters"), \
             patch("tools.fc_hba_tester._read_error_counters", return_value=over):
            r = check_error_counters(host, window_s=0)
        assert r.passed is False


# ─── T4: lip_stability ───────────────────────────────────────────────────────

class TestLipStability:
    def test_stable_link_full_score(self, host: str) -> None:
        with patch("tools.fc_hba_tester._reset_error_counters"), \
             patch("tools.fc_hba_tester._issue_lip", return_value=True), \
             patch("tools.fc_hba_tester._read_error_counters", return_value=GOOD_COUNTERS), \
             patch("tools.fc_hba_tester.time") as mock_time:
            mock_time.sleep = MagicMock()
            r = check_lip_stability(host, window_s=0)
        assert r.passed is True
        assert r.score == 100.0

    def test_high_failure_rate_fails(self, host: str) -> None:
        bad = {**GOOD_COUNTERS, "link_failure_count": 20, "loss_of_sync_count": 10}
        with patch("tools.fc_hba_tester._reset_error_counters"), \
             patch("tools.fc_hba_tester._issue_lip", return_value=True), \
             patch("tools.fc_hba_tester._read_error_counters", return_value=bad), \
             patch("tools.fc_hba_tester.time") as mock_time:
            mock_time.sleep = MagicMock()
            r = check_lip_stability(host, window_s=1)
        assert r.passed is False
        assert r.score < 50.0


# ─── T5: tgt_reachability ────────────────────────────────────────────────────

class TestTgtReachability:
    def test_one_target_passes(self, host: str) -> None:
        with patch("tools.fc_hba_tester._count_remote_targets", return_value=1):
            r = check_tgt_reachability(host)
        assert r.passed is True
        assert r.score == 100.0

    def test_no_targets_fails(self, host: str) -> None:
        with patch("tools.fc_hba_tester._count_remote_targets", return_value=0):
            r = check_tgt_reachability(host)
        assert r.passed is False
        assert r.score == 0.0


# ─── T6: transfer_latency ────────────────────────────────────────────────────

class TestTransferLatency:
    def test_fast_response_full_score(self, host: str) -> None:
        with patch("tools.fc_hba_tester._read_port_state", return_value=ONLINE_STATE), \
             patch("tools.fc_hba_tester._sg_inquiry_latency_ms", return_value=50.0):
            r = check_transfer_latency(host, "/dev/sg1")
        assert r.passed is True
        assert r.score == 100.0

    def test_slow_response_degraded_score(self, host: str) -> None:
        with patch("tools.fc_hba_tester._read_port_state", return_value=ONLINE_STATE), \
             patch("tools.fc_hba_tester._sg_inquiry_latency_ms", return_value=float(MAX_LATENCY_MS * 2)):
            r = check_transfer_latency(host, "/dev/sg1")
        assert r.passed is False
        assert r.score < 100.0

    def test_offline_port_not_measured(self, host: str) -> None:
        with patch("tools.fc_hba_tester._read_port_state", return_value=OFFLINE_STATE):
            r = check_transfer_latency(host, "/dev/sg1")
        assert r.passed is False
        assert r.score == 0.0
        assert r.value is None

    def test_device_inaccessible_partial_score(self, host: str) -> None:
        with patch("tools.fc_hba_tester._read_port_state", return_value=ONLINE_STATE), \
             patch("tools.fc_hba_tester._sg_inquiry_latency_ms", return_value=None):
            r = check_transfer_latency(host, "/dev/sg1")
        assert r.passed is False
        assert r.score == 30.0

    def test_device_busy_fc_path_active(self, host: str, tmp_path: Path) -> None:
        """Device ocupado pelo LTFS = caminho FC operacional, não é falha."""
        from types import SimpleNamespace
        device = str(tmp_path / "sg1")
        Path(device).touch()
        busy = SimpleNamespace(returncode=1, stdout="", stderr="Device or resource busy")
        with patch("tools.fc_hba_tester._read_port_state", return_value=ONLINE_STATE), \
             patch("tools.fc_hba_tester._run", return_value=busy):
            r = check_transfer_latency(host, device)
        assert r.passed is True
        assert r.score == 90.0
        assert r.value is None


# ─── T7: reconnect_time ──────────────────────────────────────────────────────

class TestReconnectTime:
    def test_fast_reconnect_full_score(self, host: str) -> None:
        states = iter(["Online", "Online"])
        with patch("tools.fc_hba_tester._read_port_state", side_effect=lambda h: next(states, "Online")), \
             patch("tools.fc_hba_tester._issue_lip", return_value=True), \
             patch("tools.fc_hba_tester.time") as mock_time:
            mock_time.perf_counter = MagicMock(side_effect=[0.0, 0.1, 5.0])
            mock_time.sleep = MagicMock()
            r = check_reconnect_time(host)
        assert r.passed is True

    def test_offline_port_skipped(self, host: str) -> None:
        with patch("tools.fc_hba_tester._read_port_state", return_value=OFFLINE_STATE):
            r = check_reconnect_time(host)
        assert r.passed is False
        assert r.score == 0.0


# ─── PortReport.compute_score ─────────────────────────────────────────────────

class TestPortReportScore:
    def _make_port_with_score(self, score: float) -> PortReport:
        p = PortReport(host="host0", pci_slot="0000:01:00.0")
        p.tests.append(FCTestResult(
            name="mock", passed=score >= 55, score=score,
            value=None, expected=None, message="", weight=1.0,
        ))
        p.compute_score()
        return p

    def test_grade_A_above_90(self) -> None:
        assert self._make_port_with_score(95.0).grade == "A"

    def test_grade_B_above_75(self) -> None:
        assert self._make_port_with_score(80.0).grade == "B"

    def test_grade_C_above_55(self) -> None:
        assert self._make_port_with_score(60.0).grade == "C"

    def test_grade_D_above_30(self) -> None:
        assert self._make_port_with_score(40.0).grade == "D"

    def test_grade_F_below_30(self) -> None:
        assert self._make_port_with_score(20.0).grade == "F"


# ─── run_dual_hba_test ────────────────────────────────────────────────────────

class TestRunDualHBA:
    def _mock_sysfs_exists(self, host: str) -> bool:
        return True

    def test_dual_port_returns_two_port_reports(self) -> None:
        with patch("tools.fc_hba_tester._read_port_state", return_value=ONLINE_STATE), \
             patch("tools.fc_hba_tester._read_port_speed", return_value="8 Gbit"), \
             patch("tools.fc_hba_tester._read_supported_speeds", return_value="8 Gbit"), \
             patch("tools.fc_hba_tester._count_remote_targets", return_value=1), \
             patch("tools.fc_hba_tester._sg_inquiry_latency_ms", return_value=50.0), \
             patch("tools.fc_hba_tester._read_port_name", return_value="0x50014380"), \
             patch("tools.fc_hba_tester._reset_error_counters"), \
             patch("tools.fc_hba_tester._issue_lip", return_value=True), \
             patch("tools.fc_hba_tester._read_error_counters", return_value=GOOD_COUNTERS), \
             patch("tools.fc_hba_tester.time") as mock_time, \
             patch.object(Path, "exists", return_value=True):
            mock_time.sleep = MagicMock()
            mock_time.perf_counter = MagicMock(side_effect=[0.0, 0.5, 10.0, 0.0, 0.5, 10.0])
            report = run_dual_hba_test(
                hosts=["host0", "host7"],
                device="/dev/sg1",
                skip_slow=True,
            )

        assert len(report.ports) == 2
        assert report.best_port != ""
        assert report.worst_port != ""
        assert report.overall_score > 0

    def test_missing_host_returns_zero_score(self) -> None:
        with patch.object(Path, "exists", return_value=False):
            report = run_dual_hba_test(
                hosts=["host99"],
                device="/dev/sg1",
                skip_slow=True,
            )
        assert len(report.ports) == 1
        assert report.ports[0].score == 0.0


# ─── Renderização e serialização ──────────────────────────────────────────────

class TestRendering:
    def _make_full_report(self) -> HBATestReport:
        r = HBATestReport(hostname="nas-test", device="/dev/sg1")
        for host in ["host0", "host7"]:
            p = PortReport(host=host, pci_slot="0000:01:00.0")
            p.tests.append(FCTestResult(
                name="link_state", passed=True, score=100.0,
                value="Online", expected="Online", message="OK.", weight=3.0,
            ))
            p.tests.append(FCTestResult(
                name="error_counters", passed=True, score=100.0,
                value=GOOD_COUNTERS, expected=f"≤ {MAX_ERROR_THRESHOLD}",
                message="Sem erros.", weight=3.0,
            ))
            p.compute_score()
            r.ports.append(p)
        r.finalize()
        return r

    def test_text_report_contains_host_names(self) -> None:
        report = self._make_full_report()
        text = render_text_report(report)
        assert "host0" in text
        assert "host7" in text

    def test_text_report_contains_grade(self) -> None:
        report = self._make_full_report()
        text = render_text_report(report)
        assert "Grade:" in text

    def test_json_serialization_roundtrip(self) -> None:
        report = self._make_full_report()
        d = report_to_dict(report)
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["hostname"] == "nas-test"
        assert len(parsed["ports"]) == 2
        assert "overall_score" in parsed

    def test_best_port_elected_correctly(self) -> None:
        report = HBATestReport(hostname="nas-test", device="/dev/sg1")
        p0 = PortReport(host="host0", pci_slot="0000:01:00.0")
        p0.tests.append(FCTestResult(
            name="t", passed=True, score=90.0,
            value=None, expected=None, message="", weight=1.0,
        ))
        p0.compute_score()
        p7 = PortReport(host="host7", pci_slot="0000:01:00.1")
        p7.tests.append(FCTestResult(
            name="t", passed=False, score=30.0,
            value=None, expected=None, message="", weight=1.0,
        ))
        p7.compute_score()
        report.ports = [p0, p7]
        report.finalize()
        assert report.best_port == "host0"
        assert report.worst_port == "host7"
