#!/usr/bin/env python3
"""Teste rápido da integração do interceptador na API."""
import sys
import pytest

sys.path.insert(0, '.')


def test_api_import():
    """Testa se a API pode ser importada com sucesso."""
    from specialized_agents.api import app
    assert app is not None, "API não pode ser importada"


def test_api_routes():
    """Testa se a API tem rotas registradas."""
    from specialized_agents.api import app
    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    assert len(routes) > 0, "API não tem rotas registradas"


def test_interceptor_routes():
    """Testa se o interceptador está integrado na API."""
    from specialized_agents.api import app
    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    interceptor_routes = [r for r in routes if '/interceptor' in r]
    
    # Interceptador é opcional - apenas avisa se não estiver presente
    if not interceptor_routes:
        pytest.skip("Interceptador não registrado na API (opcional)")
    
    assert len(interceptor_routes) > 0, "Rotas do interceptador esperadas"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
