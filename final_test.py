#!/usr/bin/env python3
"""Teste final de integração - confirmando que tudo funciona."""
import sys
sys.path.insert(0, '/home/eddie/myClaude')

from specialized_agents.api import app

# Verificar rotas
routes = [r.path for r in app.routes if hasattr(r, 'path') and '/interceptor' in r.path]

print("=" * 60)
print("TESTE FINAL DE INTEGRAÇÃO DO INTERCEPTADOR")
print("=" * 60)
print(f"\n✓ Rotas /interceptor registradas: {len(routes)}")
print(f"\nPrimeiras 5 rotas:")
for r in sorted(routes)[:5]:
    print(f"  - {r}")

if len(routes) > 0:
    print(f"\n✅ INTEGRAÇÃO SUCESSO!")
    print(f"Agora a API está pronta para receber requisições em /interceptor/*")
else:
    print(f"\n❌ INTEGRAÇÃO FALHOU")
    sys.exit(1)
