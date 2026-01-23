#!/bin/bash
# Script de Setup do Interceptador de Conversas
# Instala e configura o sistema completo

set -e

echo "🔍 Configurando Agent Conversation Interceptor..."

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Verificar dependências Python
echo -e "${BLUE}📦 Verificando dependências...${NC}"

REQUIRED_PACKAGES="fastapi uvicorn websockets streamlit pandas plotly click tabulate requests"

for package in $REQUIRED_PACKAGES; do
    if ! python3 -c "import ${package%%[ =]*}" 2>/dev/null; then
        echo "  ⚠️  Instalando $package..."
        pip install "$package" --quiet
    else
        echo "  ✅ $package instalado"
    fi
done

# 2. Criar diretório de dados
echo -e "${BLUE}📁 Criando estrutura de diretórios...${NC}"

DATA_DIR="specialized_agents/interceptor_data"
mkdir -p "$DATA_DIR"
echo "  ✅ Diretório criado: $DATA_DIR"

# 3. Inicializar banco de dados
echo -e "${BLUE}💾 Inicializando banco de dados...${NC}"

python3 << 'EOF'
from specialized_agents.agent_interceptor import get_agent_interceptor
interceptor = get_agent_interceptor()
print("  ✅ Banco de dados SQLite inicializado")
EOF

# 4. Criar arquivos de configuração
echo -e "${BLUE}⚙️  Criando arquivos de configuração...${NC}"

# Arquivo de configuração do interceptador
cat > specialized_agents/.interceptor_config << 'EOF'
# Configuração do Interceptador de Conversas
# Criado automaticamente - editável

# Buffer de mensagens (máximo)
MESSAGE_BUFFER_SIZE=1000

# Retenção de dados em dias
DATA_RETENTION_DAYS=30

# Tamanho máximo de conversa antes de arquivar
MAX_CONVERSATION_MESSAGES=10000

# Intervalo de limpeza (horas)
CLEANUP_INTERVAL=24

# Ativar logging verbose
VERBOSE=false

# Caminho do banco de dados
DB_PATH=interceptor_data/conversations.db
EOF

echo "  ✅ Arquivo de configuração criado"

# 5. Criar scripts auxiliares
echo -e "${BLUE}🔧 Criando scripts auxiliares...${NC}"

# Script para iniciar o dashboard
cat > start_interceptor_dashboard.sh << 'EOF'
#!/bin/bash
echo "🔍 Iniciando Dashboard do Interceptador..."
streamlit run specialized_agents/conversation_monitor.py
EOF

chmod +x start_interceptor_dashboard.sh
echo "  ✅ Script: start_interceptor_dashboard.sh"

# Script para iniciar o CLI
cat > interceptor << 'EOF'
#!/bin/bash
python3 specialized_agents/interceptor_cli.py "$@"
EOF

chmod +x interceptor
echo "  ✅ Script: interceptor"

# 6. Criar serviço systemd (opcional)
echo -e "${BLUE}🚀 Criando serviço systemd...${NC}"

cat > specialized_agents/eddie-interceptor.service << 'EOF'
[Unit]
Description=Eddie Agent Conversation Interceptor
After=network.target

[Service]
Type=simple
User=eddie
WorkingDirectory=/home/eddie/myClaude
ExecStart=/usr/bin/python3 specialized_agents/conversation_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "  ✅ Serviço criado: eddie-interceptor.service"
echo "  💡 Para instalar: sudo cp specialized_agents/eddie-interceptor.service /etc/systemd/system/"
echo "  💡 Para ativar:   sudo systemctl enable eddie-interceptor.service"

# 7. Teste rápido
echo -e "${BLUE}🧪 Executando teste rápido...${NC}"

python3 << 'EOF'
from specialized_agents.agent_interceptor import get_agent_interceptor
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType

# Obter instâncias
interceptor = get_agent_interceptor()
bus = get_communication_bus()

# Teste: publicar mensagem
bus.publish(
    message_type=MessageType.REQUEST,
    source="SetupTest",
    target="System",
    content="Teste de inicialização",
    metadata={"test": True}
)

# Verificar
stats = interceptor.get_stats()
print(f"  ✅ Teste bem-sucedido!")
print(f"  📊 Total de mensagens: {stats['total_messages_intercepted']}")
print(f"  🔴 Conversas ativas: {stats['active_conversations']}")
EOF

# 8. Resumo final
echo ""
echo -e "${GREEN}✅ Setup concluído com sucesso!${NC}"
echo ""
echo "📚 Próximos passos:"
echo ""
echo "1️⃣  Dashboard Streamlit:"
echo "   ./start_interceptor_dashboard.sh"
echo "   Ou: streamlit run specialized_agents/conversation_monitor.py"
echo ""
echo "2️⃣  Interface CLI:"
echo "   ./interceptor conversations active"
echo "   ./interceptor stats overview"
echo "   ./interceptor monitor"
echo ""
echo "3️⃣  API REST (já integrada):"
echo "   GET http://localhost:8503/interceptor/conversations/active"
echo "   GET http://localhost:8503/interceptor/stats"
echo ""
echo "4️⃣  Documentação:"
echo "   cat INTERCEPTOR_README.md"
echo ""
echo "🔗 Links úteis:"
echo "   • Dashboard: https://heights-treasure-auto-phones.trycloudflare.com"
echo "   • API: http://localhost:8503"
echo "   • Docs: INTERCEPTOR_README.md"
echo ""
