"""Testes unitários para o Trading Bot."""

import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class TestTradingBotBasics:
    """Testes básicos do trading bot."""
    
    @pytest.mark.unit
    def test_config_loading(self, trading_config):
        """Teste: carregar configuração padrão."""
        assert trading_config["symbol"] == "BTC-USDT"
        assert trading_config["dry_run"] is True
        assert trading_config["min_volume"] >= 0
    
    @pytest.mark.unit
    def test_dry_run_mode(self, trading_config):
        """Teste: modo dry-run está habilitado."""
        assert trading_config["dry_run"] is True
    
    @pytest.mark.unit
    def test_leverage_safety(self, trading_config):
        """Teste: alavancagem limitada para testes."""
        assert trading_config["max_leverage"] < 2


class TestTradingBotEddieMigration:
    """Testes para verificar migração de "SHARED" para "CRYPTO"."""
    
    @pytest.mark.unit
    def test_no_shared_references(self):
        """Teste: não há referências SHARED no código refatorado."""
        # Este teste será preenchido após refatoração
        pass
    
    @pytest.mark.unit
    def test_new_crypto_naming(self):
        """Teste: novo padrão de nomes CRYPTO está em uso."""
        # Este teste será preenchido após refatoração
        pass


class TestTradingBotIntegration:
    """Testes de integração do trading bot."""
    
    @pytest.mark.integration
    @pytest.mark.requires_postgres
    def test_database_connection(self, postgres_url):
        """Teste: conexão com PostgreSQL funciona."""
        # TODO: implementar teste de conexão
        assert postgres_url is not None
    
    @pytest.mark.integration
    @pytest.mark.requires_ollama
    async def test_ollama_availability(self, ollama_gpu0, ollama_gpu1):
        """Teste: Ollama remoto está acessível."""
        # TODO: implementar teste de conectividade
        assert ollama_gpu0.startswith("http://")
        assert ollama_gpu1.startswith("http://")
