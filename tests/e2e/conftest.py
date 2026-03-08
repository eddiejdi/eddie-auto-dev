"""Configuração pytest para testes end-to-end."""

import pytest
import sys
from pathlib import Path
import time


ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def api_base_url():
    """URL base da API principal."""
    return "http://localhost:8503"


@pytest.fixture
def telegram_bot_token():
    """Token do bot Telegram para testes."""
    import os
    return os.getenv("TEST_TELEGRAM_TOKEN", "")


@pytest.fixture
def trading_live_config():
    """Configuração para testes E2E de trading."""
    return {
        "symbol": "BTC-USDT",
        "dry_run": True,  # Sempre dry-run em testes
        "test_exchange": "kucoin",
        "timeout": 60,
    }


@pytest.fixture(scope="session", autouse=True)
def wait_for_services():
    """Aguardar serviços estarem prontos."""
    import subprocess
    
    # Aguardar API
    for i in range(30):
        try:
            result = subprocess.run(
                ["curl", "-s", "-m", "2", "http://localhost:8503/health"],
                capture_output=True
            )
            if result.returncode == 0:
                print("✓ API pronta")
                break
        except:
            pass
        
        if i < 29:
            time.sleep(1)
    
    yield


def pytest_configure(config):
    """Registrar marcadores E2E."""
    config.addinivalue_line(
        "markers", "e2e_slow: testes E2E muito lentos"
    )
    config.addinivalue_line(
        "markers", "e2e_critical: testes E2E críticos"
    )
    config.addinivalue_line(
        "markers", "sandbox: usar sandbox/testnet"
    )
