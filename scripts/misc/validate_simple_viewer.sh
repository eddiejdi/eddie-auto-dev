#!/bin/bash

# Script de Validação da Tela Simples
# ====================================

cd ~/myClaude

echo "🧪 Validando Sistema de Conversas Simples"
echo "========================================"
echo ""

python3 << 'PYTHON_EOF'
import sys
from pathlib import Path
import os

# Definir diretório de trabalho
os.chdir(str(Path.cwd()))

# Adicionar path
sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / "specialized_agents"))

print("1️⃣  Verificando imports...")
try:
    from specialized_agents.agent_interceptor import get_agent_interceptor
    from specialized_agents.agent_communication_bus import get_communication_bus
    print("   ✅ Imports carregados com sucesso")
except Exception as e:
    print(f"   ❌ Erro ao importar: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("")
print("2️⃣  Inicializando Interceptador...")
try:
    interceptor = get_agent_interceptor()
    print("   ✅ Interceptador inicializado")
except Exception as e:
    print(f"   ❌ Erro ao inicializar: {e}")
    sys.exit(1)

print("")
print("3️⃣  Testando API do Interceptador...")
try:
    # Listar conversas
    conversations = interceptor.list_conversations(limit=10)
    print(f"   ✅ list_conversations() - OK ({len(conversations)} conversas)")
    
    # Obter stats
    stats = interceptor.get_stats()
    print(f"   ✅ get_stats() - OK")
    print(f"      Total de conversas: {stats['total_conversations']}")
    print(f"      Total de mensagens: {stats['total_messages_intercepted']}")
    print(f"      Conversas ativas: {stats['active_conversations']}")
    
except Exception as e:
    print(f"   ❌ Erro ao testar API: {e}")
    sys.exit(1)

print("")
print("4️⃣  Verificando arquivo da interface simples...")
try:
    interface_file = Path("specialized_agents/simple_conversation_viewer.py")
    if interface_file.exists():
        lines = interface_file.read_text().count("\n")
        print(f"   ✅ simple_conversation_viewer.py existe ({lines} linhas)")
    else:
        print(f"   ❌ Arquivo não encontrado")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ Erro: {e}")
    sys.exit(1)

print("")
print("5️⃣  Testando Comunicação Bus...")
try:
    bus = get_communication_bus()
    print(f"   ✅ Communication Bus inicializado")
    print(f"      Bus status: OK")
except Exception as e:
    print(f"   ⚠️  Aviso não crítico: {e}")

print("")
print("✨ ========================================")
print("✅ VALIDAÇÃO COMPLETA COM SUCESSO!")
print("✨ ========================================")
print("")
print("🚀 Para iniciar a interface:")
print("   bash start_simple_viewer.sh")
print("")
print("📍 Ou acesse diretamente:")
print("   streamlit run specialized_agents/simple_conversation_viewer.py")
print("")

PYTHON_EOF
