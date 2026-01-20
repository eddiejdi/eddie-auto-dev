sleep 3
echo ""
echo ""
#!/bin/bash
# Install and deploy Fly.io tunnel for exposing LLMs / homelab services
# This replaces the previous Cloudflare-based installer to use the project's Fly.io tunnel

set -euo pipefail

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     EXPOSIÇÃO DE LLMs PELA INTERNET - FLY.IO TUNNEL        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Ensure flyctl is installed
if command -v ~/.fly/bin/flyctl &> /dev/null || command -v flyctl &> /dev/null; then
    echo "✅ flyctl já instalado: $(~/.fly/bin/flyctl version 2>/dev/null || flyctl version 2>/dev/null)"
else
    echo "📦 Instalando flyctl..."
    curl -L https://fly.io/install.sh | sh
    export PATH="$HOME/.fly/bin:$PATH"
    echo "✅ flyctl instalado em ~/.fly/bin/flyctl"
fi

echo ""
echo "Serviços locais que normalmente são expostos via túnel:"
echo " - Ollama API  : http://localhost:11434"
echo " - RAG API     : http://localhost:8001"
echo " - GitHub Agent: http://localhost:8502"
echo ""

echo "Próximo passo: deploy do app de túnel usando o diretório 'flyio-tunnel/'."
echo "Antes de prosseguir, certifique-se de ter autenticado o flyctl (token ou login interativo)."
read -p "Deseja continuar e executar 'fly deploy' agora? [y/N] " -r
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    echo "Autenticando (se necessário)..."
    if ! ~/.fly/bin/flyctl auth whoami >/dev/null 2>&1; then
        echo "Abra o browser para autenticar (fluxo interativo)." 
        ~/.fly/bin/flyctl auth login || true
    else
        echo "Autenticado: $(~/.fly/bin/flyctl auth whoami)"
    fi

    echo "Fazendo deploy do túnel (pasta flyio-tunnel)..."
    cd flyio-tunnel || { echo "Pasta flyio-tunnel não encontrada"; exit 1; }
    ~/.fly/bin/flyctl deploy || { echo "Deploy falhou"; exit 1; }

    echo "✅ Deploy concluído. Use flyio-tunnel/fly-tunnel.sh para gerenciar o túnel."
    echo "Exemplos:"
    echo "  ./flyio-tunnel/fly-tunnel.sh status"
    echo "  ./flyio-tunnel/fly-tunnel.sh start"
    echo "  ./flyio-tunnel/fly-tunnel.sh test"
else
    echo "Aborting: não foi feita alteração. Revise 'flyio-tunnel/' e rode este script novamente quando pronto."
fi

echo ""
echo "Guia rápido pós-deploy:" 
echo " - Ver logs: ~/.fly/bin/flyctl logs -a <APP_NAME>" 
echo " - Testar endpoints: ~/.fly/bin/flyctl proxy or use fly-tunnel.sh test" 
echo "" 
echo "Nota: Este instalador usa Fly.io conforme documentação do projeto. Não altera configurações locais de WireGuard nesta máquina; o app Fly criará a conectividade necessária remotamente via plataforma Fly." 
