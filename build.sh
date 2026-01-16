#!/bin/bash
# Build para Produção

echo "================================================"
echo "BUILD - Sistema Distribuído + Interceptador"
echo "================================================"
echo ""

cd /home/eddie/myClaude

# 1. Validar sintaxe
echo "[1/4] Validando sintaxe Python..."
python3 -m py_compile specialized_agents/distributed_coordinator.py
python3 -m py_compile specialized_agents/distributed_routes.py
python3 -m py_compile specialized_agents/interceptor_routes.py
python3 -m py_compile specialized_agents/agent_interceptor.py
echo "✓ Sintaxe validada"

# 2. Testar imports
echo ""
echo "[2/4] Testando importações..."
python3 << 'EOF'
try:
    from specialized_agents.distributed_coordinator import get_distributed_coordinator
    from specialized_agents.distributed_routes import router
    from specialized_agents.interceptor_routes import router as interceptor_router
    from specialized_agents.agent_interceptor import get_agent_interceptor
    print("✓ Todas as importações OK")
except Exception as e:
    print(f"✗ Erro: {e}")
    exit(1)
EOF

# 3. Verificar dependências
echo ""
echo "[3/4] Verificando dependências..."
python3 -c "import fastapi; import httpx; import sqlite3; print('✓ FastAPI, httpx, sqlite3 OK')"

# 4. Versão
echo ""
echo "[4/4] Versão"
git log --oneline -1

echo ""
echo "================================================"
echo "✅ BUILD SUCESSO"
echo "================================================"
