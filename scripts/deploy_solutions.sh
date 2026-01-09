#!/bin/bash
# Script de deploy para soluções auto-desenvolvidas
# Executado pelo CI/CD do GitHub ou manualmente

set -e

DEPLOY_PATH="/home/homelab/deployed_solutions"
SOLUTIONS_PATH="${1:-$DEPLOY_PATH}"
LOG_FILE="/var/log/autodev-deploy.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Iniciando Deploy de Soluções ==="

# Criar diretório se não existir
mkdir -p "$DEPLOY_PATH"
mkdir -p "$(dirname $LOG_FILE)"

# Navegar para diretório de soluções
cd "$SOLUTIONS_PATH"

log "Diretório: $SOLUTIONS_PATH"
log "Conteúdo:"
ls -la

# Processar cada solução
for solution_dir in */; do
    if [ -d "$solution_dir" ]; then
        solution_name="${solution_dir%/}"
        log "Processando solução: $solution_name"
        
        cd "$solution_dir"
        
        # Instalar dependências Python
        if [ -f "requirements.txt" ]; then
            log "  Instalando dependências Python..."
            pip3 install --user -r requirements.txt 2>&1 | tee -a "$LOG_FILE" || true
        fi
        
        # Instalar dependências Node.js
        if [ -f "package.json" ]; then
            log "  Instalando dependências Node.js..."
            npm install 2>&1 | tee -a "$LOG_FILE" || true
        fi
        
        # Instalar dependências Go
        if [ -f "go.mod" ]; then
            log "  Instalando dependências Go..."
            go mod download 2>&1 | tee -a "$LOG_FILE" || true
        fi
        
        # Executar script de deploy específico
        if [ -f "deploy.sh" ]; then
            log "  Executando deploy.sh..."
            chmod +x deploy.sh
            ./deploy.sh 2>&1 | tee -a "$LOG_FILE" || true
        fi
        
        # Tornar arquivos executáveis
        chmod +x *.py *.sh 2>/dev/null || true
        
        # Criar serviço systemd se houver arquivo .service
        for svc in *.service; do
            if [ -f "$svc" ]; then
                log "  Configurando serviço: $svc"
                sudo cp "$svc" /etc/systemd/system/
                sudo systemctl daemon-reload
                sudo systemctl enable "$(basename $svc .service)" || true
                sudo systemctl restart "$(basename $svc .service)" || true
            fi
        done
        
        cd ..
        log "  Solução $solution_name deployada!"
    fi
done

log "=== Deploy Concluído ==="

# Listar soluções deployadas
echo ""
echo "Soluções deployadas em $DEPLOY_PATH:"
ls -la "$DEPLOY_PATH"

# Verificar serviços ativos
echo ""
echo "Serviços autodev ativos:"
systemctl list-units --type=service --state=running | grep -E "autodev|solution" || echo "Nenhum serviço autodev rodando"
