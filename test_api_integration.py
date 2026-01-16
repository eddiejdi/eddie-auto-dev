#!/usr/bin/env python3
"""Teste rápido da integração do interceptador na API."""
import sys
sys.path.insert(0, '.')

try:
    from specialized_agents.api import app
    
    # Listar rotas
    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    interceptor_routes = [r for r in routes if '/interceptor' in r]
    
    print(f'✓ API importada com sucesso')
    print(f'Total de rotas: {len(routes)}')
    print(f'Rotas /interceptor: {len(interceptor_routes)}')
    
    if interceptor_routes:
        print(f'\n✓ INTEGRAÇÃO SUCESSO - Interceptador registrado na API')
        print(f'\nRotas do interceptador (primeiras 10):')
        for r in sorted(interceptor_routes)[:10]:
            print(f'  - {r}')
    else:
        print(f'\n✗ INTEGRAÇÃO FALHOU - Nenhuma rota /interceptor encontrada')
        sys.exit(1)
        
except Exception as e:
    print(f'✗ ERRO: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
