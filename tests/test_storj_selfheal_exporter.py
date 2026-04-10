"""Testes unitarios para o Storj self-heal exporter."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest


EXPORTER_PATH = (
    Path(__file__).parent.parent
    / "grafana"
    / "exporters"
    / "storj_selfheal_exporter.py"
)
MODULE_NAME = "storj_selfheal_exporter"
SPEC = importlib.util.spec_from_file_location(MODULE_NAME, str(EXPORTER_PATH))
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules.setdefault("prometheus_client", MagicMock())
sys.modules[MODULE_NAME] = MODULE
SPEC.loader.exec_module(MODULE)

StorjHealthChecker = MODULE.StorjHealthChecker
StorjNodeDef = MODULE.StorjNodeDef
StorjNodeState = MODULE.StorjNodeState
load_node_config = MODULE.load_node_config
parse_timestamp = MODULE.parse_timestamp
parse_port = MODULE.parse_port
detect_public_ip = MODULE.detect_public_ip


@pytest.fixture
def default_node() -> StorjNodeDef:
    """Retorna uma definicao basica de no Storj para testes."""

    return StorjNodeDef(
        name="storagenode",
        api_url="http://127.0.0.1:14002/api/sno",
        container_name="storagenode",
        expected_external_address="191.202.237.52:28967",
        config_path="/tmp/config.yaml",
        probe_host="192.168.15.250",
        probe_port=28967,
        port_forward_command="bash /home/homelab/eddie-auto-dev/grafana/exporters/storj_sync_port_forward.sh",
        port_forward_service="storj-port-forward.service",
        dynamic_public_ip=True,
        sync_public_address_command=(
            "python3 /home/homelab/eddie-auto-dev/grafana/exporters/"
            "storj_sync_public_address.py --container storagenode "
            "--config /mnt/disk3/storj/data/config.yaml --port 28967"
        ),
    )


def test_load_node_config_uses_json_file(tmp_path: Path) -> None:
    """Carrega definicoes do arquivo JSON quando ele existe."""

    config_path = tmp_path / "storj_selfheal.json"
    config_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "name": "storagenode",
                        "api_url": "http://127.0.0.1:14002/api/sno",
                        "container_name": "storagenode",
                        "expected_external_address": "191.202.237.52:28967",
                        "config_path": "/tmp/config.yaml",
                        "probe_host": "192.168.15.250",
                        "probe_port": 28967,
                        "port_forward_command": "bash /home/homelab/eddie-auto-dev/grafana/exporters/storj_sync_port_forward.sh",
                        "port_forward_service": "storj-port-forward.service",
                        "host_shim_service": "storj-host-shim.service",
                        "api_external_address_required": True
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    nodes = load_node_config(str(config_path))

    assert len(nodes) == 1
    assert nodes[0].expected_external_address == "191.202.237.52:28967"
    assert nodes[0].host_shim_service == "storj-host-shim.service"


def test_parse_timestamp_accepts_storj_format() -> None:
    """Converte timestamps com nanossegundos e Z para datetime UTC."""

    parsed = parse_timestamp("2026-04-08T11:27:36.839226145Z")

    assert parsed is not None
    assert parsed.tzinfo is not None


def test_parse_port_accepts_numeric_string() -> None:
    """Normaliza portas numericas vindas como string pela API."""

    assert parse_port("28967") == 28967


def test_detect_public_ip_returns_first_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Usa o primeiro endpoint de IP publico que responder com valor valido."""

    class FakeResponse:
        """Resposta HTTP fake para testes."""

        def __init__(self, body: str) -> None:
            self.body = body

        def read(self) -> bytes:
            """Retorna o corpo bruto."""

            return self.body.encode("utf-8")

        def __enter__(self) -> "FakeResponse":
            """Context manager compat."""

            return self

        def __exit__(self, *_args: object) -> None:
            """Fecha o contexto fake."""

            return None

    calls: list[str] = []

    def fake_urlopen(request: object, timeout: int = 0) -> FakeResponse:
        """Falha no primeiro endpoint e responde no segundo."""

        url = request.full_url
        calls.append(url)
        if url.endswith("one"):
            raise MODULE.urllib.error.URLError("boom")
        return FakeResponse("94.140.11.114\n")

    monkeypatch.setattr(MODULE.urllib.request, "urlopen", fake_urlopen)

    value = detect_public_ip(["https://example.com/one", "https://example.com/two"])

    assert value == "94.140.11.114"
    assert calls == ["https://example.com/one", "https://example.com/two"]


def test_check_node_healthy(monkeypatch: pytest.MonkeyPatch, default_node: StorjNodeDef) -> None:
    """Marca o no como saudavel quando API, porta e enderecos estao consistentes."""

    checker = StorjHealthChecker([default_node], dry_run=True)
    recent_ping = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    monkeypatch.setattr(
        checker,
        "resolve_expected_external_address",
        lambda _node: "191.202.237.52:28967",
    )
    monkeypatch.setattr(
        checker,
        "fetch_api_payload",
        lambda _url: {
            "quicStatus": "OK",
            "configuredPort": "28967",
            "lastPinged": recent_ping,
            "contact": {"externalAddress": "191.202.237.52:28967"},
        },
    )
    monkeypatch.setattr(checker, "read_container_address", lambda _name: "191.202.237.52:28967")
    monkeypatch.setattr(checker, "read_config_external_address", lambda _path: "191.202.237.52:28967")
    monkeypatch.setattr(checker, "probe_tcp_port", lambda _host, _port: True)

    healthy = checker.check_node("storagenode")
    state = checker.states["storagenode"]

    assert healthy is True
    assert state.up is True
    assert state.consecutive_failures == 0
    assert state.last_issues == []


def test_check_node_detects_address_drift(monkeypatch: pytest.MonkeyPatch, default_node: StorjNodeDef) -> None:
    """Detecta drift quando o ADDRESS efetivo diverge do endereco esperado."""

    checker = StorjHealthChecker([default_node], dry_run=True)
    monkeypatch.setattr(checker, "resolve_expected_external_address", lambda _node: "94.140.11.114:28967")
    monkeypatch.setattr(
        checker,
        "fetch_api_payload",
        lambda _url: {
            "quicStatus": "OK",
            "configuredPort": 28967,
            "lastPinged": datetime.now(timezone.utc).isoformat(),
            "contact": {"externalAddress": "191.202.237.52:28967"},
        },
    )
    monkeypatch.setattr(checker, "read_container_address", lambda _name: "185.255.129.19:28967")
    monkeypatch.setattr(checker, "read_config_external_address", lambda _path: "191.202.237.52:28967")
    monkeypatch.setattr(checker, "probe_tcp_port", lambda _host, _port: True)

    healthy = checker.check_node("storagenode")
    state = checker.states["storagenode"]

    assert healthy is False
    assert state.address_drift is True
    assert "address_drift" in state.last_issues


def test_check_node_detects_api_external_address_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    default_node: StorjNodeDef,
) -> None:
    """Detecta quando a API nao anuncia o endereco externo esperado."""

    checker = StorjHealthChecker([default_node], dry_run=True)
    monkeypatch.setattr(
        checker,
        "fetch_api_payload",
        lambda _url: {
            "quicStatus": "Misconfigured",
            "configuredPort": 28967,
            "lastPinged": datetime.now(timezone.utc).isoformat(),
            "contact": {"externalAddress": "185.255.129.19:28967"},
        },
    )
    monkeypatch.setattr(checker, "read_container_address", lambda _name: "191.202.237.52:28967")
    monkeypatch.setattr(checker, "read_config_external_address", lambda _path: "191.202.237.52:28967")
    monkeypatch.setattr(checker, "probe_tcp_port", lambda _host, _port: True)

    healthy = checker.check_node("storagenode")
    state = checker.states["storagenode"]

    assert healthy is False
    assert state.api_external_address_ok is False
    assert "api_external_address_mismatch" in state.last_issues


def test_check_node_allows_missing_api_external_address_when_quic_ok(
    monkeypatch: pytest.MonkeyPatch,
    default_node: StorjNodeDef,
) -> None:
    """Nao trata `externalAddress` nulo como falha quando o no ja esta funcional."""

    checker = StorjHealthChecker([default_node], dry_run=True)
    monkeypatch.setattr(
        checker,
        "resolve_expected_external_address",
        lambda _node: "179.93.21.39:28967",
    )
    monkeypatch.setattr(
        checker,
        "fetch_api_payload",
        lambda _url: {
            "quicStatus": "OK",
            "configuredPort": "28967",
            "lastPinged": datetime.now(timezone.utc).isoformat(),
            "contact": {"externalAddress": None},
        },
    )
    monkeypatch.setattr(checker, "read_container_address", lambda _name: "179.93.21.39:28967")
    monkeypatch.setattr(checker, "read_config_external_address", lambda _path: "179.93.21.39:28967")
    monkeypatch.setattr(checker, "probe_tcp_port", lambda _host, _port: True)

    healthy = checker.check_node("storagenode")
    state = checker.states["storagenode"]

    assert healthy is True
    assert state.api_external_address_ok is True
    assert state.last_issues == []


def test_check_node_allows_missing_quic_status_when_other_checks_are_healthy(
    monkeypatch: pytest.MonkeyPatch,
    default_node: StorjNodeDef,
) -> None:
    """Nao trata falta de quicStatus como falha se o node esta funcional."""

    checker = StorjHealthChecker([default_node], dry_run=True)
    monkeypatch.setattr(checker, "resolve_expected_external_address", lambda _node: "179.93.21.39:28967")
    monkeypatch.setattr(
        checker,
        "fetch_api_payload",
        lambda _url: {
            "configuredPort": "28967",
            "lastPinged": datetime.now(timezone.utc).isoformat(),
            "contact": {"externalAddress": "179.93.21.39:28967"},
        },
    )
    monkeypatch.setattr(checker, "read_container_address", lambda _name: "179.93.21.39:28967")
    monkeypatch.setattr(checker, "read_config_external_address", lambda _path: "179.93.21.39:28967")
    monkeypatch.setattr(checker, "probe_tcp_port", lambda _host, _port: True)

    healthy = checker.check_node("storagenode")
    state = checker.states["storagenode"]

    assert healthy is True
    assert state.quic_ok is False
    assert state.last_quic_status == "unknown"
    assert state.last_issues == []


def test_decide_action_prefers_port_forward_first(default_node: StorjNodeDef) -> None:
    """Prioriza sincronizar port-forward antes de reiniciar o container."""

    checker = StorjHealthChecker([default_node], dry_run=True)
    state = StorjNodeState(consecutive_failures=2, last_issues=["port_closed", "quic_misconfigured"])

    action = checker.decide_action(default_node, state)
    assert action == "sync_port_forward"

    state.last_action = "sync_port_forward"
    state.consecutive_failures = 4
    action = checker.decide_action(default_node, state)
    assert action == "restart_port_forward_service"

    state.last_action = "restart_port_forward_service"
    state.consecutive_failures = 5
    action = checker.decide_action(default_node, state)
    assert action == "restart_host_shim_service"

    state.last_action = "restart_host_shim_service"
    state.consecutive_failures = 6
    action = checker.decide_action(default_node, state)
    assert action == "restart_container"


def test_decide_action_restarts_container_on_api_announcement_mismatch(default_node: StorjNodeDef) -> None:
    """Reinicia o container quando a API continua anunciando endereco errado."""

    checker = StorjHealthChecker([default_node], dry_run=True)
    state = StorjNodeState(
        consecutive_failures=2,
        last_issues=["api_external_address_mismatch"],
    )

    action = checker.decide_action(default_node, state)

    assert action == "restart_container"


def test_decide_action_prefers_public_address_sync_on_drift(default_node: StorjNodeDef) -> None:
    """Em drift de endereco, sincroniza IP publico antes de reiniciar o container."""

    checker = StorjHealthChecker([default_node], dry_run=True)
    state = StorjNodeState(consecutive_failures=2, last_issues=["address_drift"])

    action = checker.decide_action(default_node, state)

    assert action == "sync_public_address"


def test_perform_action_respects_rate_limit(default_node: StorjNodeDef) -> None:
    """Bloqueia novas acoes quando o limite horario foi excedido."""

    checker = StorjHealthChecker([default_node], dry_run=True)
    state = StorjNodeState(actions_this_hour=MODULE.MAX_ACTIONS_PER_HOUR, hour_window_start=MODULE.time.time())

    success = checker.perform_action(default_node, state, "restart_container")

    assert success is False
    assert state.actions_total == {}


def test_perform_action_supports_host_shim_restart(default_node: StorjNodeDef) -> None:
    """Expande o mapa de acoes para reiniciar o host shim do macvlan."""

    checker = StorjHealthChecker([default_node], dry_run=True)
    state = StorjNodeState(hour_window_start=MODULE.time.time() - 5)

    success = checker.perform_action(default_node, state, "restart_host_shim_service")

    assert success is True
    assert state.actions_total == {"restart_host_shim_service": 1}


def test_check_node_triggers_action_after_threshold(
    monkeypatch: pytest.MonkeyPatch,
    default_node: StorjNodeDef,
) -> None:
    """Dispara uma acao corretiva ao atingir o limiar de falhas."""

    checker = StorjHealthChecker([default_node], dry_run=True)
    actions: list[str] = []
    monkeypatch.setattr(
        checker,
        "resolve_expected_external_address",
        lambda _node: "191.202.237.52:28967",
    )
    monkeypatch.setattr(
        checker,
        "fetch_api_payload",
        lambda _url: {
            "quicStatus": "Misconfigured",
            "contact": {"externalAddress": "191.202.237.52:28967"},
        },
    )
    monkeypatch.setattr(checker, "read_container_address", lambda _name: "191.202.237.52:28967")
    monkeypatch.setattr(checker, "read_config_external_address", lambda _path: "191.202.237.52:28967")
    monkeypatch.setattr(checker, "probe_tcp_port", lambda _host, _port: False)
    monkeypatch.setattr(
        checker,
        "perform_action",
        lambda _node, _state, action: actions.append(action) or True,
    )

    checker.check_node("storagenode")
    checker.check_node("storagenode")

    assert actions == ["sync_port_forward"]


def test_get_summary_contains_runtime_fields(default_node: StorjNodeDef) -> None:
    """Resumo exposto precisa incluir os campos principais de diagnostico."""

    checker = StorjHealthChecker([default_node], dry_run=True)
    state = checker.states["storagenode"]
    state.up = False
    state.api_up = True
    state.quic_ok = False
    state.port_open = False
    state.last_issues = ["quic_misconfigured", "port_closed"]
    state.actions_total = {"sync_port_forward": 1}
    state.last_check = datetime.now(timezone.utc).timestamp()

    summary = checker.get_summary()

    assert summary["storagenode"]["api_up"] is True
    assert summary["storagenode"]["issues"] == ["quic_misconfigured", "port_closed"]
    assert summary["storagenode"]["actions_total"] == {"sync_port_forward": 1}


def test_summary_exposes_api_external_address_ok(default_node: StorjNodeDef) -> None:
    """Resumo precisa expor se a API anuncia o endereco esperado."""

    checker = StorjHealthChecker([default_node], dry_run=True)
    state = checker.states["storagenode"]
    state.api_external_address_ok = False

    summary = checker.get_summary()

    assert summary["storagenode"]["api_external_address_ok"] is False