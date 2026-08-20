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


def test_http_treats_redirect_as_up(monkeypatch):
    class _Resp:
        status = 302

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class _Opener:
        def open(self, _req, timeout=5):
            return _Resp()

    monkeypatch.setattr(
        MODULE.urllib.request, "build_opener", lambda *_a, **_k: _Opener()
    )
    checker = TunnelHealthChecker([])
    ok, _elapsed = checker.check_http("http://127.0.0.1:8053/admin/")
    assert ok is True


def test_pihole_dns_up_does_not_restart_when_admin_http_fails():
    tunnel = TunnelDef(
        name="pihole",
        tunnel_type="docker",
        systemd_unit="pihole.service",
        docker_container="pihole",
        health_url="http://127.0.0.1:8053/admin/",
        health_dns="127.0.0.1",
        heal_checks=["dns"],
    )
    checker = TunnelHealthChecker([tunnel])
    restarts = {"n": 0}
    checker.check_docker_container_running = lambda _name: True
    checker.check_systemd_active = lambda _unit: True
    checker.check_http = lambda _url, timeout=5: (False, 0.01)
    checker.check_dns = lambda _server, name="example.com": True

    def _restart(_tunnel, _state):
        restarts["n"] += 1
        return False

    checker.restart_service = _restart
    assert checker.check_tunnel("pihole") is True
    assert checker.check_tunnel("pihole") is True
    assert restarts["n"] == 0
    assert checker.states["pihole"].up is True


def test_pihole_dns_down_triggers_restart_after_two_failures():
    tunnel = TunnelDef(
        name="pihole",
        tunnel_type="docker",
        systemd_unit="pihole.service",
        docker_container="pihole",
        health_dns="127.0.0.1",
        heal_checks=["dns"],
    )
    checker = TunnelHealthChecker([tunnel])
    restarts = {"n": 0}
    checker.check_docker_container_running = lambda _name: True
    checker.check_systemd_active = lambda _unit: True
    checker.check_dns = lambda _server, name="example.com": False

    def _restart(_tunnel, _state):
        restarts["n"] += 1
        return True

    checker.restart_service = _restart
    assert checker.check_tunnel("pihole") is False
    assert restarts["n"] == 0
    assert checker.check_tunnel("pihole") is False
    assert restarts["n"] == 1
