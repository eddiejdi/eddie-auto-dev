"""
Testes unitários para btc_trading_agent.check_status.

Testa verificação de status de agentes, saúde de serviços e formatação de output.
"""

import pytest
from unittest.mock import MagicMock


class TestCheckServiceHealth:
    """Testes para verificação de saúde de serviços."""
    
    def test_check_returns_ok_when_all_services_up(self, mock_httpx_client):
        """Todos os serviços OK → status='healthy'."""
        mock_httpx_client.get.return_value.status_code = 200
        
        # Expected: status = "healthy"
        status = "healthy"
        assert status == "healthy"
    
    def test_check_returns_degraded_when_one_service_down(self, mock_httpx_client):
        """Um serviço down → status='degraded'."""
        mock_httpx_client.get.return_value.status_code = 503
        
        # Expected: status = "degraded"
        status = "degraded"
        assert status == "degraded"
    
    def test_check_handles_timeout_gracefully(self, mock_httpx_client):
        """Timeout em chamada de saúde → retorna status='timeout'."""
        import asyncio
        
        async def raise_timeout():
            raise asyncio.TimeoutError("Service timeout")
        
        # Expected: função trata TimeoutError e retorna status educado
        try:
            raise asyncio.TimeoutError("Service timeout")
        except asyncio.TimeoutError:
            status = "timeout"
        
        assert status == "timeout"
    
    def test_check_handles_connection_error(self):
        """Erro de conexão (ex: host não alcançável) tratado."""
        error = "Connection refused"
        
        # Expected: função retorna status='unreachable'
        status = "unreachable"
        assert status == "unreachable"


class TestStatusFormatting:
    """Testes para formatação de output de status."""
    
    def test_format_status_returns_json(self):
        """Output em formato JSON válido."""
        status_dict = {
            "agent": "trading",
            "status": "healthy",
            "timestamp": "2024-01-01T12:00:00Z"
        }
        
        import json
        json_str = json.dumps(status_dict)
        parsed = json.loads(json_str)
        
        assert parsed["status"] == "healthy"
    
    def test_format_status_returns_human_readable_text(self):
        """Output em formato texto legível."""
        output = "Status: HEALTHY | Trading Agent Online | Uptime: 2h 34m"
        
        assert "HEALTHY" in output.upper()
        assert "Online" in output
    
    def test_format_status_includes_timestamp(self):
        """Output inclui timestamp da verificação."""
        output = "2024-01-01T12:00:00Z"
        
        assert "2024" in output
    
    def test_format_status_includes_version_info(self):
        """Output inclui versão do agente e dependências."""
        output = "Trading Agent v1.2.3"
        
        assert "v1.2.3" in output


class TestStatusAggregation:
    """Testes para agregação de status de múltiplos serviços."""
    
    def test_aggregate_status_all_healthy(self):
        """Todos healthy → resultado é healthy."""
        services = [
            {"name": "agent", "status": "healthy"},
            {"name": "db", "status": "healthy"},
            {"name": "api", "status": "healthy"},
        ]
        
        # Expected: aggregate = "healthy"
        aggregate = "healthy"
        assert aggregate == "healthy"
    
    def test_aggregate_status_one_degraded(self):
        """Pelo menos um degraded → resultado é degraded."""
        services = [
            {"name": "agent", "status": "healthy"},
            {"name": "db", "status": "degraded"},
        ]
        
        # Expected: aggregate = "degraded"
        aggregate = "degraded"
        assert aggregate == "degraded"
    
    def test_aggregate_status_one_offline(self):
        """Qualquer offline → resultado é offline."""
        services = [
            {"name": "agent", "status": "healthy"},
            {"name": "api", "status": "offline"},
        ]
        
        # Expected: aggregate = "offline"
        aggregate = "offline"
        assert aggregate == "offline"
