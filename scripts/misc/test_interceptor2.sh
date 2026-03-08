#!/bin/bash
cd ~/myClaude
python3 << 'EOF'
from specialized_agents.agent_interceptor import get_agent_interceptor
print("✅ Interceptador carregado com sucesso!")
interceptor = get_agent_interceptor()
conversations = interceptor.list_conversations(limit=10)
print(f"📊 Conversas armazenadas: {len(conversations)}")
print(f"📝 Primeiras conversas: {conversations[:2] if conversations else 'nenhuma'}")
stats = interceptor.get_stats()
print(f"📈 Estatísticas gerais: {stats}")
EOF
