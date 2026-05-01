import json
import os
import requests
import pytest
import docker


def _read_opencode_password():
    env_path = "/opt/opencode/.env"
    if not os.path.exists(env_path):
        pytest.skip("OPENCODE env file not present on host")
    with open(env_path, "r") as f:
        for line in f:
            if line.startswith("OPENCODE_SERVER_PASSWORD="):
                return line.strip().split("=", 1)[1]
    pytest.skip("OPENCODE_SERVER_PASSWORD not set in env file")


def test_caddy_proxy_health():
    """Verify Caddy proxies to OpenCode and /global/health returns 200."""
    password = _read_opencode_password()
    resp = requests.get("http://127.0.0.1:18080/global/health", auth=("opencode", password), timeout=5)
    assert resp.status_code == 200


def test_ollama_models_endpoint():
    """Check Ollama /v1/models responds with JSON list."""
    resp = requests.get("http://127.0.0.1:11434/v1/models", timeout=5)
    assert resp.status_code == 200
    j = resp.json()
    assert isinstance(j, dict)
    assert "data" in j and isinstance(j["data"], list)


def test_containers_running():
    """Ensure opencode and caddy-opencode containers are running (via Docker SDK)."""
    client = docker.from_env()
    names = [c.name for c in client.containers.list()]
    assert "opencode" in names, "opencode container not running"
    assert "caddy-opencode" in names, "caddy-opencode container not running"
