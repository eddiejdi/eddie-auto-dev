"""Configuração pytest para testes unitários."""

import pytest
import sys
from pathlib import Path

# Adicionar root ao path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def test_data_dir():
    """Diretório de dados para testes."""
    return Path(__file__).parent / "data"


@pytest.fixture
def trading_config():
    """Configuração padrão para testes de trading."""
    return {
        "symbol": "BTC-USDT",
        "dry_run": True,
        "min_volume": 500,
        "max_leverage": 1,
    }


@pytest.fixture
def homelab_config():
    """Configuração padrão para testes de homelab."""
    return {
        "host": "192.168.15.2",
        "port": 8503,
        "timeout": 5,
        "retries": 3,
    }


# Marcadores customizados
def pytest_configure(config):
    """Registrar marcadores customizados."""
    config.addinivalue_line(
        "markers", "unit: testes unitários (rápidos)"
    )
    config.addinivalue_line(
        "markers", "integration: testes integrados (mais lentos)"
    )
    config.addinivalue_line(
        "markers", "e2e: testes end-to-end (muito lentos)"
    )
    config.addinivalue_line(
        "markers", "gpu: testes que usam GPU"
    )
    config.addinivalue_line(
        "markers", "ollama: testes que usam Ollama remoto"
    )
    config.addinivalue_line(
        "markers", "postgres: testes que usam PostgreSQL"
    )
