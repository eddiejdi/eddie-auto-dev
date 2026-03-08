#!/bin/bash
cd ~/myClaude
python3 << 'EOF'
from specialized_agents.agent_interceptor import get_agent_interceptor
print("✅ Interceptador carregado com sucesso!")
interceptor = get_agent_interceptor()
conversations = interceptor.get_all_conversations()
print(f"📊 Conversas armazenadas: {len(conversations)}")
stats = interceptor.get_stats()
print(f"📈 Estatísticas: {stats}")
EOF
