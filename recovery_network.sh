#!/bin/bash
# Recovery script - Restaurar servidor após quebra de rede
# Use assim que o homelab 192.168.15.2 voltar online

set -e

SSH_USER="homelab"
SSH_HOST="192.168.15.2"

echo "=================================================================="
echo "RECUPERAÇÃO DO SERVIDOR - PARAR SERVIÇO PROBLEMÁTICO"
echo "=================================================================="

# Tenta várias vezes com timeout crescente
for attempt in 1 2 3; do
    timeout_val=$((5 * attempt))
    echo ""
    echo "Tentativa $attempt (timeout: ${timeout_val}s)..."
    
    if timeout $timeout_val ssh -i ~/.ssh/id_rsa_eddie \
        -o IdentitiesOnly=yes \
        -o IdentityAgent=none \
        -o StrictHostKeyChecking=no \
        -o ConnectTimeout=3 \
        ${SSH_USER}@${SSH_HOST} \
        "sudo systemctl stop agent-network-exporter 2>/dev/null && echo '✅ Serviço parado'" 2>&1; then
        echo "✅ Conexão bem-sucedida!"
        break
    else
        if [ $attempt -eq 3 ]; then
            echo "❌ Servidor ainda inacessível após 3 tentativas"
            echo ""
            echo "Próximos passos:"
            echo "1. Acesse o servidor fisicamente ou via Proxmox/VirtualBox"
            echo "2. Execute: sudo systemctl stop agent-network-exporter"
            echo "3. Execute: sudo systemctl disable agent-network-exporter"
            echo "4. Execute: sudo systemctl restart ssh"
            exit 1
        fi
        sleep 2
    fi
done

echo ""
echo "Desabilitando serviço permanentemente..."
ssh -i ~/.ssh/id_rsa_eddie \
    -o IdentitiesOnly=yes \
    -o IdentityAgent=none \
    ${SSH_USER}@${SSH_HOST} \
    "sudo systemctl disable agent-network-exporter && \
     echo '✅ Serviço desabilitado permanentemente'"

echo ""
echo "Removendo arquivo de serviço..."
ssh -i ~/.ssh/id_rsa_eddie \
    -o IdentitiesOnly=yes \
    -o IdentityAgent=none \
    ${SSH_USER}@${SSH_HOST} \
    "sudo rm -f /etc/systemd/system/agent-network-exporter.service && \
     sudo systemctl daemon-reload && \
     echo '✅ Arquivo de serviço removido'"

echo ""
echo "Verificando status de SSH..."
ssh -i ~/.ssh/id_rsa_eddie \
    -o IdentitiesOnly=yes \
    -o IdentityAgent=none \
    ${SSH_USER}@${SSH_HOST} \
    "sudo systemctl restart ssh && \
     sleep 2 && \
     sudo systemctl status ssh --no-pager | head -10"

echo ""
echo "Testando clone do código atualizado..."
ssh -i ~/.ssh/id_rsa_eddie \
    -o IdentitiesOnly=yes \
    -o IdentityAgent=none \
    ${SSH_USER}@${SSH_HOST} \
    "cd eddie-auto-dev && git pull origin main && \
     echo '✅ Código atualizado'"

echo ""
echo "=================================================================="
echo "✅ SERVIDOR RECUPERADO!"
echo "=================================================================="
echo ""
echo "Próximos passos:"
echo "1. Validate que os serviços essenciais estão rodando:"
echo "   ssh homelab@192.168.15.2 'sudo systemctl status specialized-agents-api eddie-coordinator'"
echo ""
echo "2. O Agent Network Exporter pode ser re-habilitado DEPOIS com:"
echo "   - Ajustes de memória/performance no código"
echo "   - Configuração adequada no systemd (MemoryLimit)"
echo ""
