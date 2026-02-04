#!/bin/bash
# Script para corrigir autenticação SSH no homelab
# Execute após preencher a senha: bash fix_ssh_key.sh

set -e

echo "==================================================================="
echo "CORREÇÃO DE CHAVE SSH - HOMELAB"
echo "==================================================================="

SSH_USER="homelab"
SSH_HOST="192.168.15.2"
LOCAL_PUB_KEY="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDLiaUi9+EzKJjktGJZRh3zPItW6dKbV7gnQsHmhECuBANQUJXSiKqVZLGkMZ32rMNkE4DsjrQns8QkIfLu8VmeJV6g43r5rJOrtjIPDm1fZiWpTMdbcjIZINQy+dmPJJ1mEgh0sRejERuQ5LyVfiWTQ3j6+YomJPK5zhvp5jhQ2iGr1dLAoRZEk7aYwVR8Ka+kFjTs+u9+3uieGmw6IMpC20rFYrcS8iOU/qBDg/yzyIOtMuMw7yJG2921LjOAX2hEvrZ28gC5rspzNSvI4Us2ySEbAOXnz/0q37xybOKQUSeF6SxQIsTrfgSTiEYbf52sjM7ivaKMEzCohxSkTTM9lsvc8uLLqe+9xVrjExdsXFPIfqP3tHoT0YImvOcAQSnC+P/JX0pjqa7tr0hHxGrfY4a9bd0qyKH3Sm9xU5ymq3Fj9fTWqb0MAgadw6EN7fXqy1GUrRTGMJed0Vwj8h+40of/7EYj3x7W6+LSVf3zqPRqus4RgG2rSQVO0LlOjzJtnlM1nDmCzPJpatoIrBCBFlysis4CX/3m7eEEBovS8Jkh7IAJveriW2UCdSgMIEcJCwnMNLcRXPp/meED9y7mwQhHOwACn0jz1+JGst0FJyWttRPGP7/SSj8tNXJueQ11u0O9PvEzxjQRg1nt9jC9Nw7fALSHKvCheU3X44bMww== homelab@192.168.15.1"

echo ""
echo "📋 Passo 1: Fazendo backup do authorized_keys atual..."
ssh ${SSH_USER}@${SSH_HOST} "mkdir -p ~/.ssh && cp ~/.ssh/authorized_keys ~/.ssh/authorized_keys.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true"

echo ""
echo "🔑 Passo 2: Adicionando nova chave RSA..."
ssh ${SSH_USER}@${SSH_HOST} "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '${LOCAL_PUB_KEY}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

echo ""
echo "🧹 Passo 3: Removendo chaves duplicadas..."
ssh ${SSH_USER}@${SSH_HOST} "sort -u ~/.ssh/authorized_keys > ~/.ssh/authorized_keys.tmp && mv ~/.ssh/authorized_keys.tmp ~/.ssh/authorized_keys"

echo ""
echo "✅ Passo 4: Testando conexão SSH sem senha..."
if ssh -o BatchMode=yes -o ConnectTimeout=5 ${SSH_USER}@${SSH_HOST} "echo 'Conexão SSH funcionando!'" 2>/dev/null; then
    echo "✅ SUCESSO: Conexão SSH funcionando sem senha!"
    echo ""
    echo "🔐 Chave RSA configurada corretamente!"
else
    echo "⚠️  ATENÇÃO: Ainda requer senha. Verifique as permissões no servidor."
    echo ""
    echo "Execute no servidor:"
    echo "  chmod 700 ~/.ssh"
    echo "  chmod 600 ~/.ssh/authorized_keys"
    echo "  restorecon -R ~/.ssh 2>/dev/null || true"
fi

echo ""
echo "==================================================================="
echo "FINALIZADO"
echo "==================================================================="
