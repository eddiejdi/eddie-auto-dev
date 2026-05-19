"""Testes unitarios para tools/tape_component_quality_agent.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import tape_component_quality_agent as mod


@pytest.fixture()
def fake_fc_report() -> SimpleNamespace:
    """Retorna relatorio sintetico do fc_hba_tester para testes."""
    return SimpleNamespace(
        ports=[
            SimpleNamespace(
                host="host0",
                pci_slot="0000:01:00.0",
                score=15.0,
                grade="F",
                recommendation="Porta inutilizavel.",
                tests=[
                    SimpleNamespace(name="link_state", score=0.0, passed=False, message="Linkdown"),
                ],
            ),
            SimpleNamespace(
                host="host7",
                pci_slot="0000:01:00.1",
                score=97.0,
                grade="A",
                recommendation="Porta excelente.",
                tests=[
                    SimpleNamespace(name="link_state", score=100.0, passed=True, message="Online"),
                ],
            ),
        ]
    )


def test_check_device_nodes_all_present(tmp_path: Path) -> None:
    device = tmp_path / "sg1"
    st = tmp_path / "st1"
    nst = tmp_path / "nst1"
    device.touch()
    st.touch()
    nst.touch()

    result = mod._check_device_nodes(str(device), str(st), str(nst))

    assert result.status == "pass"
    assert result.score == 100.0
    assert result.details["missing"] == []


def test_check_drive_transport_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    device = tmp_path / "sg1"
    device.touch()
    monkeypatch.setattr(mod, "_run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="Vendor identification: HP", stderr=""))

    result = mod._check_drive_transport(str(device))

    assert result.status == "pass"
    assert result.score == 100.0
    assert "sucesso" in result.message.lower()


def test_check_drive_transport_busy_is_pass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Device ocupado pelo LTFS deve ser tratado como pass, não falha."""
    device = tmp_path / "sg1"
    device.touch()
    monkeypatch.setattr(mod, "_run", lambda *args, **kwargs: SimpleNamespace(
        returncode=1, stdout="", stderr="sg_inq: error opening file: /dev/sg0: Device or resource busy"
    ))

    result = mod._check_drive_transport(str(device))

    assert result.status == "pass"
    assert result.score == 90.0
    assert "em uso" in result.message.lower() or "ltfs" in result.message.lower()


def test_check_ltfs_stack_with_missing_binaries(monkeypatch: pytest.MonkeyPatch) -> None:
    available = {"ltfs": True, "mkltfs": True, "ltfsck": False, "sg_inq": True, "sg_turs": False}

    def fake_binary_available(binary: str) -> tuple[bool, str]:
        return available[binary], f"/usr/bin/{binary}" if available[binary] else ""

    monkeypatch.setattr(mod, "_binary_available", fake_binary_available)
    result = mod._check_ltfs_stack()

    assert result.status == "degraded"
    assert set(result.details["missing"]) == {"ltfsck", "sg_turs"}


def test_check_runtime_paths_handles_bad_address(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mount_path = tmp_path / "ltfs"
    work_path = tmp_path / "work"
    work_path.mkdir()

    original_exists = Path.exists

    def fake_exists(path: Path) -> bool:
        if path == mount_path:
            raise OSError(14, "Bad address")
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", fake_exists)

    result = mod._check_runtime_paths(str(mount_path), str(work_path))

    assert result.status == "fail"
    assert result.score == pytest.approx(33.3, rel=1e-3)
    assert result.details["mount_point_exists"] is False
    assert "Bad address" in str(result.details["mount_point_error"])
    assert result.details["mount_point_is_mount"] is False
    assert result.details["work_dir_exists"] is True


def test_check_runtime_paths_requires_active_mount(tmp_path: Path) -> None:
    mount_path = tmp_path / "ltfs"
    work_path = tmp_path / "work"
    mount_path.mkdir()
    work_path.mkdir()

    result = mod._check_runtime_paths(str(mount_path), str(work_path))

    assert result.status == "degraded"
    assert result.score == pytest.approx(66.7, rel=1e-3)
    assert result.details["mount_point_exists"] is True
    assert result.details["mount_point_is_mount"] is False
    assert result.details["work_dir_exists"] is True


def test_collect_component_quality_aggregates_components(
    monkeypatch: pytest.MonkeyPatch,
    fake_fc_report: SimpleNamespace,
) -> None:
    monkeypatch.setattr(mod, "_check_hba_quality", lambda hosts, device: [
        mod.ComponentQualityResult("fc_host0", "hba", "host0", 15.0, "fail", "bad"),
        mod.ComponentQualityResult("fc_host7", "hba", "host7", 97.0, "pass", "good"),
    ])
    monkeypatch.setattr(mod, "_check_device_nodes", lambda *args, **kwargs: mod.ComponentQualityResult("device_nodes", "device", "/dev/sg0", 100.0, "pass", "ok"))
    monkeypatch.setattr(mod, "_check_drive_transport", lambda *args, **kwargs: mod.ComponentQualityResult("drive_transport", "device", "/dev/sg0", 100.0, "pass", "ok"))
    monkeypatch.setattr(mod, "_check_ltfs_stack", lambda: mod.ComponentQualityResult("ltfs_stack", "software", "ltfs", 80.0, "degraded", "partial"))
    monkeypatch.setattr(mod, "_check_tape_access_script", lambda: mod.ComponentQualityResult("tape_access", "orchestration", "script", 100.0, "pass", "ok"))
    monkeypatch.setattr(mod, "_check_service_unit", lambda service: mod.ComponentQualityResult("ltfs_service_unit", "service", service, 80.0, "degraded", "inactive"))
    monkeypatch.setattr(mod, "_check_runtime_paths", lambda mount_point, work_dir: mod.ComponentQualityResult("runtime_paths", "filesystem", mount_point, 100.0, "pass", "ok"))

    report = mod.collect_component_quality()

    assert len(report.components) == 8
    assert report.summary == {"pass": 5, "degraded": 2, "fail": 1}
    assert report.overall_score == pytest.approx(84.0, rel=1e-3)


def test_check_service_unit_treats_activating_as_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mod,
        "_run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="loaded\nactivating\nstart\nstart-post\n",
            stderr="",
        ),
    )

    result = mod._check_service_unit("ltfs-lto6.service")

    assert result.status == "degraded"
    assert result.score == 80.0
    assert "inicializacao" in result.message


def test_derive_fc_subcomponent_scores_maps_expected_tests() -> None:
    report = SimpleNamespace(
        ports=[
            SimpleNamespace(
                tests=[
                    SimpleNamespace(name="error_counters", score=90.0),
                    SimpleNamespace(name="lip_stability", score=80.0),
                    SimpleNamespace(name="transfer_latency", score=70.0),
                    SimpleNamespace(name="link_state", score=100.0),
                    SimpleNamespace(name="port_speed", score=95.0),
                    SimpleNamespace(name="reconnect_time", score=85.0),
                    SimpleNamespace(name="tgt_reachability", score=75.0),
                ]
            )
        ]
    )

    scores = mod._derive_fc_subcomponent_scores(report)

    assert scores["fc_cable_lc_lc"] == pytest.approx(80.0, rel=1e-3)
    assert scores["fc_sfp_transceiver"] == pytest.approx(90.0, rel=1e-3)
    assert scores["fc_hba_pcie"] == pytest.approx(93.3, rel=1e-3)
    assert scores["fc_switch_path"] == pytest.approx(86.7, rel=1e-3)


def test_derive_fc_test_scores_maps_expected_tests() -> None:
    report = SimpleNamespace(
        ports=[
            SimpleNamespace(
                tests=[
                    SimpleNamespace(name="link_state", score=100.0),
                    SimpleNamespace(name="port_speed", score=95.0),
                    SimpleNamespace(name="error_counters", score=90.0),
                    SimpleNamespace(name="lip_stability", score=80.0),
                    SimpleNamespace(name="tgt_reachability", score=75.0),
                    SimpleNamespace(name="transfer_latency", score=70.0),
                    SimpleNamespace(name="reconnect_time", score=85.0),
                ]
            )
        ]
    )

    scores = mod._derive_fc_test_scores(report)

    assert scores["fc_link_state"] == pytest.approx(100.0, rel=1e-3)
    assert scores["fc_port_speed"] == pytest.approx(95.0, rel=1e-3)
    assert scores["fc_error_counters"] == pytest.approx(90.0, rel=1e-3)
    assert scores["fc_lip_stability"] == pytest.approx(80.0, rel=1e-3)
    assert scores["fc_tgt_reachability"] == pytest.approx(75.0, rel=1e-3)
    assert scores["fc_transfer_latency"] == pytest.approx(70.0, rel=1e-3)
    assert scores["fc_reconnect_time"] == pytest.approx(85.0, rel=1e-3)


def test_check_hba_quality_import_error_exposes_fc_subcomponents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = __import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "tools.fc_hba_tester":
            raise ImportError("boom")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    results = mod._check_hba_quality(["host0", "host7"], "/dev/sg0")
    components = {item.component for item in results}

    assert "fc_diagnostic_core" in components
    assert "fc_cable_lc_lc" in components
    assert "fc_sfp_transceiver" in components
    assert "fc_hba_pcie" in components
    assert "fc_switch_path" in components
    assert "fc_link_state" in components
    assert "fc_port_speed" in components
    assert "fc_error_counters" in components
    assert "fc_lip_stability" in components
    assert "fc_tgt_reachability" in components
    assert "fc_transfer_latency" in components
    assert "fc_reconnect_time" in components


def test_check_hba_quality_supports_standalone_fc_hba_tester_module(
    monkeypatch: pytest.MonkeyPatch,
    fake_fc_report: SimpleNamespace,
) -> None:
    """Quando instalado fora do repo, o agente deve importar fc_hba_tester local."""
    import builtins

    original_import = builtins.__import__

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level=0):
        if name == "tools.fc_hba_tester":
            raise ImportError("repo package unavailable")
        if name == "fc_hba_tester":
            return SimpleNamespace(run_dual_hba_test=lambda **kwargs: fake_fc_report)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    results = mod._check_hba_quality(["host0", "host7"], "/dev/sg0")
    components = {item.component for item in results}

    assert "fc_cable_lc_lc" in components
    assert "fc_diagnostic_core" not in components


def test_report_to_dict_is_json_serializable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "_check_hba_quality", lambda hosts, device: [])
    monkeypatch.setattr(mod, "_check_device_nodes", lambda *args, **kwargs: mod.ComponentQualityResult("device_nodes", "device", "/dev/sg0", 100.0, "pass", "ok"))
    monkeypatch.setattr(mod, "_check_drive_transport", lambda *args, **kwargs: mod.ComponentQualityResult("drive_transport", "device", "/dev/sg0", 100.0, "pass", "ok"))
    monkeypatch.setattr(mod, "_check_ltfs_stack", lambda: mod.ComponentQualityResult("ltfs_stack", "software", "ltfs", 100.0, "pass", "ok"))
    monkeypatch.setattr(mod, "_check_tape_access_script", lambda: mod.ComponentQualityResult("tape_access", "orchestration", "script", 100.0, "pass", "ok"))
    monkeypatch.setattr(mod, "_check_service_unit", lambda service: mod.ComponentQualityResult("ltfs_service_unit", "service", service, 100.0, "pass", "ok"))
    monkeypatch.setattr(mod, "_check_runtime_paths", lambda mount_point, work_dir: mod.ComponentQualityResult("runtime_paths", "filesystem", mount_point, 100.0, "pass", "ok"))

    report = mod.collect_component_quality()
    payload = mod.report_to_dict(report)

    encoded = json.dumps(payload)
    assert "overall_score" in encoded


class DummyGauge:
    """Gauge minimo para testar o exporter sem prometheus_client real."""

    def __init__(self, *_args, **_kwargs) -> None:
        self.values: dict[tuple[str, ...], float] = {}
        self.direct_value: float | None = None

    def labels(self, *labels: str) -> "DummyGauge":
        self._current_labels = labels
        return self

    def set(self, value: float) -> None:
        labels = getattr(self, "_current_labels", None)
        if labels is None:
            self.direct_value = value
        else:
            self.values[labels] = value

    def remove(self, *labels: str) -> None:
        self.values.pop(labels, None)


def test_exporter_updates_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "Gauge", DummyGauge)
    monkeypatch.setattr(mod, "CollectorRegistry", MagicMock)
    monkeypatch.setattr(mod, "HAS_PROMETHEUS", True)

    exporter = mod.TapeComponentQualityExporter(registry=MagicMock())
    report = mod.TapeComponentQualityReport(
        hostname="host",
        generated_at="2026-05-08T10:00:00",
        overall_score=88.5,
        summary={"pass": 1, "degraded": 1, "fail": 0},
        components=[
            mod.ComponentQualityResult("fc_host7", "hba", "host7", 97.0, "pass", "ok"),
            mod.ComponentQualityResult("ltfs_stack", "software", "ltfs", 80.0, "degraded", "partial"),
        ],
    )

    exporter.update(report)

    assert exporter.overall_score.direct_value == 88.5
    assert exporter.component_score.values[("fc_host7", "hba", "host7")] == 97.0
    assert exporter.component_status.values[("ltfs_stack", "software", "ltfs")] == 1
