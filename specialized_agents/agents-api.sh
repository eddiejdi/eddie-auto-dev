#!/bin/bash
# Controle da API de Agentes Especializados (On-Demand)
# Uso: ./agents-api.sh [start|stop|status|restart|logs|components]

API_URL="http://localhost:8503"
SERVICE_NAME="specialized-agents-api"
TMUX_SESSION="agents"

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

case "$1" in
    start)
        echo -e "${BLUE}Iniciando API On-Demand...${NC}"
        
        # Verificar se já está rodando
        if tmux has-session -t $TMUX_SESSION 2>/dev/null; then
            echo -e "${YELLOW}API já está rodando na sessão tmux '$TMUX_SESSION'${NC}"
            $0 status
            exit 0
        fi
        
        # Iniciar em sessão tmux
        cd ~/myClaude/specialized_agents
        tmux new-session -d -s $TMUX_SESSION "~/.local/bin/uvicorn api_ondemand:app --host 0.0.0.0 --port 8503"
        
        sleep 3
        if curl -s "$API_URL/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ API iniciada com sucesso!${NC}"
            echo -e "  URL: $API_URL"
            echo -e "  Docs: $API_URL/docs"
            echo -e "  Sessão tmux: $TMUX_SESSION"
        else
            echo -e "${RED}✗ Falha ao iniciar API${NC}"
            tmux capture-pane -t $TMUX_SESSION -p | tail -20
            exit 1
        fi
        ;;

    stop)
        echo -e "${YELLOW}Parando API...${NC}"
        # Parar componentes on-demand primeiro
        curl -s -X POST "$API_URL/ondemand/stop-all" > /dev/null 2>&1
        sleep 1
        # Matar sessão tmux
        tmux kill-session -t $TMUX_SESSION 2>/dev/null
        echo -e "${GREEN}✓ API parada${NC}"
        ;;

    restart)
        $0 stop
        sleep 2
        $0 start
        ;;

    status)
        echo -e "${BLUE}=== Status da API ===${NC}"
        
        # Verificar sessão tmux
        if tmux has-session -t $TMUX_SESSION 2>/dev/null; then
            echo -e "${GREEN}✓ Sessão tmux '$TMUX_SESSION' ativa${NC}"
        else
            echo -e "${RED}✗ Sessão tmux não encontrada${NC}"
        fi
        
        # Verificar se API está rodando
        if curl -s "$API_URL/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ API está respondendo${NC}"
            
            # Obter status on-demand
            echo -e "\n${BLUE}=== Componentes On-Demand ===${NC}"
            status=$(curl -s "$API_URL/ondemand/status" 2>/dev/null)
            
            if [ -n "$status" ]; then
                total=$(echo "$status" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total_components', 0))" 2>/dev/null || echo "?")
                running=$(echo "$status" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('running_components', 0))" 2>/dev/null || echo "?")
                
                echo -e "Total: $total | Rodando: ${GREEN}$running${NC}"
                echo ""
                
                # Listar componentes
                curl -s "$API_URL/ondemand/status" 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)
for name, comp in d.get('components', {}).items():
    status = comp.get('status', 'unknown')
    idle = comp.get('idle_seconds', 0)
    timeout = comp.get('idle_timeout', 0)
    if status == 'running':
        print(f'  ● {name}: running (idle: {idle}s / timeout: {timeout}s)')
    else:
        print(f'  ○ {name}: {status}')
" 2>/dev/null
            fi
        else
            echo -e "${RED}✗ API não está respondendo${NC}"
            exit 1
        fi
        ;;

    logs)
        echo -e "${BLUE}=== Logs da API ===${NC}"
        if tmux has-session -t $TMUX_SESSION 2>/dev/null; then
            tmux attach-session -t $TMUX_SESSION
        else
            echo "Sessão tmux não encontrada"
        fi
        ;;
    
    view-logs)
        echo -e "${BLUE}=== Últimas linhas do log ===${NC}"
        if tmux has-session -t $TMUX_SESSION 2>/dev/null; then
            tmux capture-pane -t $TMUX_SESSION -p | tail -30
        else
            echo "Sessão tmux não encontrada"
        fi
        ;;

    components)
        echo -e "${BLUE}=== Controle de Componentes ===${NC}"
        case "$2" in
            start)
                if [ -z "$3" ]; then
                    echo "Uso: $0 components start <nome>"
                    exit 1
                fi
                echo "Iniciando $3..."
                curl -s -X POST "$API_URL/ondemand/start/$3"
                echo ""
                ;;
            stop)
                if [ -z "$3" ]; then
                    echo "Uso: $0 components stop <nome>"
                    exit 1
                fi
                echo "Parando $3..."
                curl -s -X POST "$API_URL/ondemand/stop/$3"
                echo ""
                ;;
            stop-all)
                echo "Parando todos os componentes..."
                curl -s -X POST "$API_URL/ondemand/stop-all"
                echo ""
                ;;
            *)
                echo "Comandos disponíveis:"
                echo "  $0 components start <nome>  - Inicia componente"
                echo "  $0 components stop <nome>   - Para componente"
                echo "  $0 components stop-all      - Para todos"
                echo ""
                echo "Componentes: agent_manager, docker, github"
                ;;
        esac
        ;;

    install)
        echo -e "${BLUE}Instalando serviço systemd...${NC}"
        sudo cp ~/myClaude/specialized_agents/specialized-agents-api.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable specialized-agents-api
        echo -e "${GREEN}✓ Serviço instalado${NC}"
        echo "Use: sudo systemctl start specialized-agents-api"
        ;;

    *)
        echo "Uso: $0 {start|stop|status|restart|logs|view-logs|components|install}"
        echo ""
        echo "Comandos:"
        echo "  start      - Inicia a API on-demand (em tmux)"
        echo "  stop       - Para a API e componentes"
        echo "  status     - Mostra status da API e componentes"
        echo "  restart    - Reinicia a API"
        echo "  logs       - Anexa à sessão tmux (Ctrl+B D para sair)"
        echo "  view-logs  - Mostra últimas linhas do log"
        echo "  components - Controla componentes individuais"
        echo "  install    - Instala serviço systemd"
        exit 1
        ;;
esac
