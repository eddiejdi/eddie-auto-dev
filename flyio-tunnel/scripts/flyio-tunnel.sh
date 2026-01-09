#!/bin/bash
# flyio-tunnel.sh - Gerenciamento do túnel Fly.io
# Caminho oficial para acesso externo ao homelab

FLY_BIN="/home/homelab/.fly/bin/fly"
APP_NAME="homelab-tunnel-sparkling-sun-3565"
APP_URL="https://homelab-tunnel-sparkling-sun-3565.fly.dev"

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

case "$1" in
    status)
        echo -e "${BLUE}=== Status do Túnel Fly.io ===${NC}"
        $FLY_BIN status -a $APP_NAME
        echo ""
        echo -e "${BLUE}=== Teste de Conectividade ===${NC}"
        if curl -s -o /dev/null -w "%{http_code}" "$APP_URL/health" | grep -q "200"; then
            echo -e "${GREEN}✓ Túnel está online${NC}"
            echo -e "  URL: $APP_URL"
        else
            echo -e "${RED}✗ Túnel não está respondendo${NC}"
        fi
        ;;

    start)
        echo -e "${BLUE}Iniciando máquina do Fly.io...${NC}"
        MACHINE_ID=$($FLY_BIN status -a $APP_NAME 2>/dev/null | grep "^app" | awk '{print $2}')
        if [ -n "$MACHINE_ID" ]; then
            $FLY_BIN machine start $MACHINE_ID -a $APP_NAME
            echo -e "${GREEN}✓ Máquina iniciada${NC}"
        else
            echo -e "${RED}✗ Não foi possível encontrar a máquina${NC}"
        fi
        ;;

    stop)
        echo -e "${YELLOW}Parando máquina do Fly.io...${NC}"
        MACHINE_ID=$($FLY_BIN status -a $APP_NAME 2>/dev/null | grep "^app" | awk '{print $2}')
        if [ -n "$MACHINE_ID" ]; then
            $FLY_BIN machine stop $MACHINE_ID -a $APP_NAME
            echo -e "${GREEN}✓ Máquina parada${NC}"
        else
            echo -e "${RED}✗ Não foi possível encontrar a máquina${NC}"
        fi
        ;;

    restart)
        echo -e "${BLUE}Reiniciando app Fly.io...${NC}"
        $FLY_BIN apps restart $APP_NAME
        echo -e "${GREEN}✓ App reiniciado${NC}"
        ;;

    logs)
        echo -e "${BLUE}=== Logs do Fly.io ===${NC}"
        $FLY_BIN logs -a $APP_NAME
        ;;

    deploy)
        echo -e "${BLUE}Fazendo deploy...${NC}"
        cd ~/projects/flyio-tunnel
        $FLY_BIN deploy -a $APP_NAME
        ;;

    test)
        echo -e "${BLUE}=== Testando Endpoints ===${NC}"
        echo ""
        echo -n "Health: "
        curl -s "$APP_URL/health" && echo ""
        echo ""
        echo -n "Ollama Models: "
        curl -s "$APP_URL/v1/models" | head -c 100
        echo "..."
        ;;

    url)
        echo "$APP_URL"
        ;;

    *)
        echo "Uso: $0 {status|start|stop|restart|logs|deploy|test|url}"
        echo ""
        echo "Comandos:"
        echo "  status   - Mostra status do túnel"
        echo "  start    - Inicia a máquina"
        echo "  stop     - Para a máquina"
        echo "  restart  - Reinicia o app"
        echo "  logs     - Mostra logs"
        echo "  deploy   - Faz deploy de alterações"
        echo "  test     - Testa endpoints"
        echo "  url      - Mostra URL do túnel"
        echo ""
        echo "URL: $APP_URL"
        exit 1
        ;;
esac
