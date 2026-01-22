#!/bin/bash
# Gerenciamento do túnel Fly.io
# Prefer an explicit FLY_BIN env var (set e.g. in /etc/autonomous_remediator.env)
FLY=${FLY_BIN:-~/.fly/bin/fly}
APP=homelab-tunnel-sparkling-sun-3565
URL=https://homelab-tunnel-sparkling-sun-3565.fly.dev

case "$1" in
    status)
        echo "=== Status do Túnel ==="
        $FLY status -a $APP
        ;;
    start)
        echo "Iniciando máquina..."
        MACHINE=$($FLY status -a $APP 2>/dev/null | grep app | awk '{print $2}')
        $FLY machine start $MACHINE -a $APP
        ;;
    stop)
        echo "Parando máquina..."
        MACHINE=$($FLY status -a $APP 2>/dev/null | grep app | awk '{print $2}')
        $FLY machine stop $MACHINE -a $APP
        ;;
    restart)
        echo "Reiniciando app..."
        $FLY apps restart $APP
        ;;
    logs)
        $FLY logs -a $APP
        ;;
    test)
        echo "=== Testando Endpoints ==="
        echo -n "Raiz: "; curl -s -o /dev/null -w '%{http_code}' $URL/; echo ""
        echo -n "Ollama: "; curl -s -o /dev/null -w '%{http_code}' $URL/api/ollama; echo ""
        echo -n "WebUI: "; curl -s -o /dev/null -w '%{http_code}' $URL/webui/; echo ""
        echo -n "OpenAI: "; curl -s -o /dev/null -w '%{http_code}' $URL/v1/models; echo ""
        ;;
    url)
        echo $URL
        ;;
    deploy)
        echo "Fazendo deploy..."
        cd ~/projects/flyio-tunnel && $FLY deploy
        ;;
    *)
        echo "Uso: fly-tunnel {status|start|stop|restart|logs|test|url|deploy}"
        echo ""
        echo "Comandos:"
        echo "  status  - Mostra status da máquina"
        echo "  start   - Inicia a máquina"
        echo "  stop    - Para a máquina"
        echo "  restart - Reinicia o app"
        echo "  logs    - Mostra logs"
        echo "  test    - Testa endpoints"
        echo "  url     - Mostra URL do túnel"
        echo "  deploy  - Faz deploy das alterações"
        echo ""
        echo "URL: $URL"
        ;;
esac
