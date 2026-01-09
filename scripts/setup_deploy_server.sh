#!/bin/bash
# Configuração inicial do servidor para receber deploys
# Executar uma vez no servidor (192.168.15.2)

set -e

echo "=== Configurando Servidor para Deploy ==="

# Criar diretório de deploy
DEPLOY_PATH="/home/homelab/deployed_solutions"
mkdir -p "$DEPLOY_PATH"

# Criar diretório de logs
sudo mkdir -p /var/log
sudo touch /var/log/autodev-deploy.log
sudo chown homelab:homelab /var/log/autodev-deploy.log

# Instalar dependências básicas
echo "Instalando dependências..."
sudo apt-get update
sudo apt-get install -y python3-pip nodejs npm git rsync

# Configurar SSH para GitHub Actions
echo "Configurando SSH..."
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Criar chave SSH se não existir
if [ ! -f ~/.ssh/id_ed25519 ]; then
    ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -C "deploy@homelab"
    echo ""
    echo "=== CHAVE PÚBLICA (adicionar como Deploy Key no GitHub) ==="
    cat ~/.ssh/id_ed25519.pub
    echo ""
    echo "=== CHAVE PRIVADA (adicionar como secret DEPLOY_SSH_KEY no GitHub) ==="
    cat ~/.ssh/id_ed25519
    echo ""
fi

# Adicionar GitHub aos hosts conhecidos
ssh-keyscan -H github.com >> ~/.ssh/known_hosts 2>/dev/null

# Criar script de verificação de deploy
cat > ~/check_deploy.sh << 'EOF'
#!/bin/bash
echo "=== Status das Soluções Deployadas ==="
echo ""
echo "Diretório de deploy:"
ls -la /home/homelab/deployed_solutions/
echo ""
echo "Últimas entradas no log:"
tail -20 /var/log/autodev-deploy.log 2>/dev/null || echo "Sem logs ainda"
echo ""
echo "Serviços ativos:"
systemctl list-units --type=service --state=running | grep -E "autodev|solution" || echo "Nenhum serviço autodev"
EOF
chmod +x ~/check_deploy.sh

echo ""
echo "=== Configuração Concluída ==="
echo ""
echo "Próximos passos:"
echo "1. Adicione a chave pública como Deploy Key no repositório GitHub"
echo "2. Adicione a chave privada como secret DEPLOY_SSH_KEY no GitHub"
echo "3. Adicione TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID nos secrets"
echo ""
echo "Para verificar deploys, execute: ~/check_deploy.sh"
