"""Configuração pytest para testes integrados."""

import pytest
import sys
import os
from pathlib import Path
import asyncio

# Adicionar root ao path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

# Timeout para testes de integração
DEFAULT_TIMEOUT = 30


@pytest.fixture
def postgres_url():
    """URL do PostgreSQL para testes."""
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5433/btc_test"
    )


@pytest.fixture
def ollama_gpu0():
    """URL do Ollama GPU0 (remoto)."""
    return "http://192.168.15.2:11434"


@pytest.fixture
def ollama_gpu1():
    """URL do Ollama GPU1 (remoto)."""
    return "http://192.168.15.2:11435"


@pytest.fixture
def event_loop():
    """Event loop para testes async."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_integration_tests():
    """Setup para testes de integração."""
    # Verificar conectividade essencial
    pass


# Marcadores para testes integrados
def pytest_configure(config):
    """Registrar marcadores."""
    config.addinivalue_line(
        "markers", "slow: testes integrados lentos"
    )
    config.addinivalue_line(
        "markers", "requires_postgres: requer PostgreSQL"
    )
    config.addinivalue_line(
        "markers", "requires_ollama: requer Ollama remoto"
    )
    config.addinivalue_line(
        "markers", "requires_network: requer conexão de rede"
    )
