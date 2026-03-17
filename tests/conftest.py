"""
Fixtures compartilhadas para testes unitários e de integração.

Inclui fixtures para Selenium, Ollama (GPU0/GPU1) e verificação de GPU.
"""

import json
import os
from pathlib import Path

import pytest

try:
    import httpx
except ImportError:
    httpx = None

# ── Selenium ──

try:
    from selenium import webdriver
except ImportError:
    webdriver = None


@pytest.fixture
def driver():
    if webdriver is None:
        pytest.skip("selenium not installed")
    try:
        options = webdriver.ChromeOptions()
        headed = os.getenv("HEADLESS", "1").lower() in {"0", "false", "off", "no"}
        if not headed:
            options.add_argument("--headless=new")
        drv = webdriver.Chrome(options=options)
    except Exception as e:
        pytest.skip(f"Cannot start Chrome driver: {e}")
        return
    yield drv
    try:
        drv.quit()
    except Exception:
        pass


# ── Ollama GPU fixtures ──

OLLAMA_GPU0_URL = "http://192.168.15.2:11434"
OLLAMA_GPU1_URL = "http://192.168.15.2:11435"


def _ollama_reachable(url: str) -> bool:
    """Verifica se uma instância Ollama está acessível."""
    if httpx is None:
        return False
    try:
        resp = httpx.get(f"{url}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def ollama_gpu0_url() -> str:
    """URL da instância Ollama na GPU0 (RTX 2060)."""
    if not _ollama_reachable(OLLAMA_GPU0_URL):
        pytest.skip("Ollama GPU0 (:11434) não acessível")
    return OLLAMA_GPU0_URL


@pytest.fixture(scope="session")
def ollama_gpu1_url() -> str:
    """URL da instância Ollama na GPU1 (GTX 1050)."""
    if not _ollama_reachable(OLLAMA_GPU1_URL):
        pytest.skip("Ollama GPU1 (:11435) não acessível")
    return OLLAMA_GPU1_URL


@pytest.fixture(scope="session")
def gpu1_model_info(ollama_gpu1_url: str) -> dict:
    """Informações do modelo carregado na GPU1."""
    if httpx is None:
        pytest.skip("httpx not installed")
    resp = httpx.get(f"{ollama_gpu1_url}/api/ps", timeout=5)
    resp.raise_for_status()
    models = resp.json().get("models", [])
    if not models:
        pytest.skip("Nenhum modelo carregado na GPU1")
    return models[0]


@pytest.fixture(scope="session")
def selfheal_config() -> dict:
    """Configuração do trading self-heal."""
    config_path = Path(__file__).parent.parent / "btc_trading_agent" / "trading_selfheal_config.json"
    if not config_path.exists():
        pytest.skip(f"Config não encontrado: {config_path}")
    return json.loads(config_path.read_text())


@pytest.fixture(scope="session")
def grafana_selfheal_config() -> dict:
    """Configuração do exporter Grafana self-heal."""
    config_path = Path(__file__).parent.parent / "grafana" / "exporters" / "trading_selfheal_config.json"
    if not config_path.exists():
        pytest.skip(f"Config não encontrado: {config_path}")
    return json.loads(config_path.read_text())
