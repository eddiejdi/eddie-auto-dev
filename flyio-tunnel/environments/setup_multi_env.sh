#!/bin/bash
# =============================================================================
# Script para criar túneis Fly.io para HOM e CER
# Reutiliza a infraestrutura existente do PROD
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
HOMELAB_IP="192.168.15.2"

# Configuração dos ambientes
# PROD já existe: homelab-tunnel-sparkling-sun-3565 (portas 8081-8085)
# HOM usará portas 8091-8095
# CER usará portas 8101-8105

declare -A ENVS
ENVS[HOM]="8091"  # Base port para HOM
ENVS[CER]="8101"  # Base port para CER

# Mapeamento de serviços (offset da porta base)
# +0: Open WebUI (3000)
# +1: Ollama (11434)  
# +2: RAG API (8001)
# +3: RAG Dashboard (8501)
# +4: GitHub Agent (8502)

print_header() {
    echo -e "${BLUE}"
    echo "=============================================="
    echo "  🌐 Fly.io Multi-Environment Setup"
    echo "=============================================="
    echo -e "${NC}"
}

check_flyctl() {
    if ! command -v fly &> /dev/null; then
        echo -e "${RED}❌ flyctl não encontrado. Instale com:${NC}"
        echo "curl -L https://fly.io/install.sh | sh"
        exit 1
    fi
    
    if ! fly auth whoami &> /dev/null; then
        echo -e "${YELLOW}⚠️  Faça login no Fly.io:${NC}"
        fly auth login
    fi
    
    echo -e "${GREEN}✅ flyctl configurado${NC}"
}

create_app_config() {
    local ENV_NAME=$1
    local BASE_PORT=$2
    local APP_NAME="homelab-tunnel-${ENV_NAME,,}"  # lowercase
    
    local DIR="$SCRIPT_DIR/$ENV_NAME"
    mkdir -p "$DIR"
    
    echo -e "${YELLOW}📝 Criando configuração para $ENV_NAME...${NC}"
    
    # Criar fly.toml
    cat > "$DIR/fly.toml" << EOF
app = "$APP_NAME"
primary_region = "gru"

[build]
  dockerfile = "../Dockerfile"

[env]
  HOMELAB_HOST = "[fdaa:3b:60e0:a7b:8cfe:0:a:202]"
  WEBUI_PORT = "$((BASE_PORT + 0))"
  OLLAMA_PORT = "$((BASE_PORT + 1))"
  RAG_API_PORT = "$((BASE_PORT + 2))"
  RAG_DASHBOARD_PORT = "$((BASE_PORT + 3))"
  GITHUB_AGENT_PORT = "$((BASE_PORT + 4))"
  ENV_NAME = "$ENV_NAME"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1
  processes = ["app"]

  [http_service.concurrency]
    type = "requests"
    hard_limit = 250
    soft_limit = 200

[[vm]]
  memory = "256mb"
  cpu_kind = "shared"
  cpus = 1
EOF

    echo -e "${GREEN}✅ Configuração $ENV_NAME criada em $DIR/fly.toml${NC}"
}

create_caddyfile() {
    local ENV_NAME=$1
    local BASE_PORT=$2
    local DIR="$SCRIPT_DIR/$ENV_NAME"
    
    cat > "$DIR/Caddyfile" << EOF
# Caddyfile para ambiente $ENV_NAME
{
    auto_https off
}

:8080 {
    # Open WebUI - Principal
    reverse_proxy {env.HOMELAB_HOST}:$((BASE_PORT + 0)) {
        header_up Host {upstream_hostport}
        header_up X-Forwarded-Proto https
    }
    
    # Rotas específicas
    handle_path /api/ollama/* {
        reverse_proxy {env.HOMELAB_HOST}:$((BASE_PORT + 1))
    }
    
    handle_path /api/rag/* {
        reverse_proxy {env.HOMELAB_HOST}:$((BASE_PORT + 2))
    }
    
    handle_path /dashboard/* {
        reverse_proxy {env.HOMELAB_HOST}:$((BASE_PORT + 3))
    }
    
    handle_path /github-agent/* {
        reverse_proxy {env.HOMELAB_HOST}:$((BASE_PORT + 4))
    }
}
EOF

    echo -e "${GREEN}✅ Caddyfile $ENV_NAME criado${NC}"
}

update_ipv6_proxy() {
    echo -e "${YELLOW}📝 Atualizando ipv6-proxy.py com novas portas...${NC}"
    
    local PROXY_FILE="/home/homelab/ipv6-proxy.py"
    
    # Backup
    ssh homelab@$HOMELAB_IP "cp $PROXY_FILE ${PROXY_FILE}.bak"
    
    # Criar novo arquivo com todas as portas
    cat > /tmp/ipv6-proxy-multi.py << 'EOF'
#!/usr/bin/env python3
"""
IPv6-to-IPv4 TCP Proxy for Fly.io Private Network
Bridges Fly6PN IPv6 connections to local IPv4 services

Ambientes:
- PROD: portas 8081-8085
- HOM:  portas 8091-8095
- CER:  portas 8101-8105
"""
import asyncio
import socket

# Mapeamento de portas para serviços locais
SERVICES = {
    # ============ PROD (existente) ============
    8081: ("127.0.0.1", 3000),   # Open WebUI
    8082: ("127.0.0.1", 11434),  # Ollama
    8083: ("127.0.0.1", 8001),   # RAG API
    8084: ("127.0.0.1", 8501),   # RAG Dashboard
    8085: ("127.0.0.1", 8502),   # GitHub Agent
    
    # ============ HOM ============
    8091: ("127.0.0.1", 3000),   # Open WebUI (mesmo serviço)
    8092: ("127.0.0.1", 11434),  # Ollama
    8093: ("127.0.0.1", 8001),   # RAG API
    8094: ("127.0.0.1", 8501),   # RAG Dashboard
    8095: ("127.0.0.1", 8502),   # GitHub Agent
    
    # ============ CER ============
    8101: ("127.0.0.1", 3000),   # Open WebUI (mesmo serviço)
    8102: ("127.0.0.1", 11434),  # Ollama
    8103: ("127.0.0.1", 8001),   # RAG API
    8104: ("127.0.0.1", 8501),   # RAG Dashboard
    8105: ("127.0.0.1", 8502),   # GitHub Agent
}

async def forward_data(reader, writer):
    try:
        while True:
            data = await reader.read(8192)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except:
            pass

async def handle_connection(local_reader, local_writer, target_host, target_port):
    try:
        remote_reader, remote_writer = await asyncio.open_connection(target_host, target_port)
        await asyncio.gather(
            forward_data(local_reader, remote_writer),
            forward_data(remote_reader, local_writer)
        )
    except Exception as e:
        print(f"Connection error to {target_host}:{target_port}: {e}")
    finally:
        try:
            local_writer.close()
            await local_writer.wait_closed()
        except:
            pass

async def start_proxy(listen_port, target_host, target_port):
    def client_connected(reader, writer):
        asyncio.create_task(handle_connection(reader, writer, target_host, target_port))
    
    servers = []
    
    # IPv6 para Fly6PN
    try:
        server = await asyncio.start_server(
            client_connected,
            host="fdaa:3b:60e0:a7b:8cfe:0:a:202",
            port=listen_port,
        )
        servers.append(server)
        print(f"✅ Proxy fly0[{listen_port}] -> {target_host}:{target_port}")
    except Exception as e:
        print(f"⚠️  Failed fly0 binding on {listen_port}: {e}")
    
    # IPv4 para acesso local
    try:
        server = await asyncio.start_server(
            client_connected,
            host="0.0.0.0",
            port=listen_port,
        )
        servers.append(server)
        print(f"✅ Proxy 0.0.0.0:{listen_port} -> {target_host}:{target_port}")
    except Exception as e:
        print(f"⚠️  Failed IPv4 binding on {listen_port}: {e}")
    
    return servers

async def main():
    print("=" * 60)
    print("🌐 IPv6-to-IPv4 Proxy for Fly.io Private Network")
    print("=" * 60)
    print()
    print("📋 Ambientes configurados:")
    print("   PROD: portas 8081-8085")
    print("   HOM:  portas 8091-8095")
    print("   CER:  portas 8101-8105")
    print()
    
    all_servers = []
    for listen_port, (target_host, target_port) in SERVICES.items():
        try:
            servers = await start_proxy(listen_port, target_host, target_port)
            all_servers.extend(servers)
        except Exception as e:
            print(f"❌ Failed to start proxy on {listen_port}: {e}")
    
    print()
    print(f"🚀 Started {len(all_servers)} proxy servers")
    
    if all_servers:
        await asyncio.gather(*[s.serve_forever() for s in all_servers])
    else:
        print("❌ No servers started!")

if __name__ == "__main__":
    asyncio.run(main())
EOF

    # Copiar para servidor
    scp /tmp/ipv6-proxy-multi.py homelab@$HOMELAB_IP:$PROXY_FILE
    
    # Reiniciar serviço
    ssh homelab@$HOMELAB_IP "sudo systemctl restart ipv6-proxy"
    
    echo -e "${GREEN}✅ ipv6-proxy atualizado e reiniciado${NC}"
}

deploy_app() {
    local ENV_NAME=$1
    local DIR="$SCRIPT_DIR/$ENV_NAME"
    
    echo -e "${YELLOW}🚀 Deploying $ENV_NAME...${NC}"
    
    cd "$DIR"
    
    # Criar app se não existe
    local APP_NAME="homelab-tunnel-${ENV_NAME,,}"
    if ! fly apps list | grep -q "$APP_NAME"; then
        echo -e "${BLUE}📦 Criando novo app: $APP_NAME${NC}"
        fly apps create "$APP_NAME" --org personal
    fi
    
    # Deploy
    fly deploy --app "$APP_NAME"
    
    # Mostrar URL
    local URL=$(fly info --app "$APP_NAME" -j | jq -r '.Hostname')
    echo -e "${GREEN}✅ $ENV_NAME deployado: https://$URL${NC}"
}

print_summary() {
    echo -e "${GREEN}"
    echo "=============================================="
    echo "  ✅ Configuração Completa!"
    echo "=============================================="
    echo -e "${NC}"
    echo ""
    echo "📋 URLs dos Ambientes:"
    echo ""
    echo "   PROD: https://homelab-tunnel-sparkling-sun-3565.fly.dev"
    echo "   HOM:  https://homelab-tunnel-hom.fly.dev"
    echo "   CER:  https://homelab-tunnel-cer.fly.dev"
    echo ""
    echo "⚠️  IMPORTANTE:"
    echo "   - Todos apontam para o MESMO servidor (192.168.15.2)"
    echo "   - Separação de código é feita por GIT BRANCHES"
    echo "   - Para OAuth funcionar em HOM/CER, configure:"
    echo "     1. Google Cloud Console -> Redirect URIs"
    echo "     2. Containers Open WebUI separados (opcional)"
    echo ""
}

# Main
print_header
check_flyctl

echo -e "${YELLOW}📝 Criando configurações para cada ambiente...${NC}"
for ENV in "${!ENVS[@]}"; do
    create_app_config "$ENV" "${ENVS[$ENV]}"
    create_caddyfile "$ENV" "${ENVS[$ENV]}"
done

echo ""
read -p "Deseja atualizar o ipv6-proxy.py no servidor? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    update_ipv6_proxy
fi

echo ""
read -p "Deseja fazer deploy dos apps no Fly.io? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    for ENV in "${!ENVS[@]}"; do
        deploy_app "$ENV"
    done
fi

print_summary
