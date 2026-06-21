import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "grafana"
    / "exporters"
    / "tunnel_healthcheck_exporter.py"
)
SPEC = importlib.util.spec_from_file_location("tunnel_healthcheck_exporter", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

TunnelDef = MODULE.TunnelDef
TunnelHealthChecker = MODULE.TunnelHealthChecker


def test_docker_tunnel_checks_container_not_legacy_process():
    tunnel = TunnelDef(
        name="grafana",
        tunnel_type="docker",
        systemd_unit="docker.service",
        docker_container="grafana",
        health_url="http://127.0.0.1:3002/api/health",
        expected_process="docker-proxy.*3002",
    )
    checker = TunnelHealthChecker([tunnel])

    calls = {"container": 0, "process": 0}

    checker.check_systemd_active = lambda unit: True
    checker.check_http = lambda url, timeout=5: (True, 0.01)

    def fake_container(container_name: str) -> bool:
        calls["container"] += 1
        return True

    def fake_process(pattern: str) -> bool:
        calls["process"] += 1
        return False

    checker.check_docker_container_running = fake_container
    checker.check_process = fake_process

    assert checker.check_tunnel("grafana") is True
    assert calls == {"container": 1, "process": 0}


def test_non_docker_tunnel_still_uses_process_check():
    tunnel = TunnelDef(
        name="nginx-proxy",
        tunnel_type="nginx",
        systemd_unit="nginx.service",
        health_url="http://127.0.0.1:8090/",
        expected_process="nginx: master",
    )
    checker = TunnelHealthChecker([tunnel])

    calls = {"process": 0}

    checker.check_systemd_active = lambda unit: True
    checker.check_http = lambda url, timeout=5: (True, 0.01)

    def fake_process(pattern: str) -> bool:
        calls["process"] += 1
        return True

    checker.check_process = fake_process

    assert checker.check_tunnel("nginx-proxy") is True
    assert calls == {"process": 1}
