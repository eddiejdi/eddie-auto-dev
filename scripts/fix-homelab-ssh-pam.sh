#!/usr/bin/env bash
# =============================================================================
# fix-homelab-ssh-pam.sh
# Corrige o PAM do sshd no homelab:
#   - Altera account requisite → account optional para o authentik-login-guard
#   - Adiciona edenilson/homelab ao ALLOW_LOCAL_USERS no env do guard
#   - Reinicia nada crítico (sshd recarrega com kill -HUP que é seguro)
# Executar como root/sudo no homelab (192.168.15.2)
# =============================================================================
set -euo pipefail

SSHD_PAM="/etc/pam.d/sshd"
ENV_FILE="/etc/authentik/login-guard.env"
BACKUP_PAM="${SSHD_PAM}.bak.$(date +%Y%m%d_%H%M%S)"

echo "=== Fix PAM sshd + authentik-login-guard ==="

# 1. Backup do PAM sshd
if [[ -f "$SSHD_PAM" ]]; then
    cp "$SSHD_PAM" "$BACKUP_PAM"
    echo "✓ Backup: $BACKUP_PAM"
fi

# 2. Alterar account requisite → account optional para o guard
if grep -q "authentik-login-guard.*--pam-stage account" "$SSHD_PAM" 2>/dev/null; then
    sed -i 's/^account\s\+requisite\s\+pam_exec\.so\s.*authentik-login-guard.*--pam-stage account.*/account  optional  pam_exec.so quiet \/usr\/local\/bin\/authentik-login-guard --pam-stage account/' "$SSHD_PAM"
    echo "✓ account requisite → optional no $SSHD_PAM"
else
    echo "  (guard não encontrado em $SSHD_PAM — nada alterado no PAM)"
fi

# 3. Garantir allow_local_users inclui root,homelab,edenilson
if [[ -f "$ENV_FILE" ]]; then
    if grep -q "AUTHENTIK_LOGIN_ALLOW_LOCAL" "$ENV_FILE"; then
        sed -i 's/^AUTHENTIK_LOGIN_ALLOW_LOCAL=.*/AUTHENTIK_LOGIN_ALLOW_LOCAL=root,homelab,edenilson/' "$ENV_FILE"
        echo "✓ ALLOW_LOCAL_USERS atualizado em $ENV_FILE"
    else
        echo "AUTHENTIK_LOGIN_ALLOW_LOCAL=root,homelab,edenilson" >> "$ENV_FILE"
        echo "✓ ALLOW_LOCAL_USERS adicionado em $ENV_FILE"
    fi
else
    mkdir -p "$(dirname "$ENV_FILE")"
    echo "AUTHENTIK_LOGIN_ALLOW_LOCAL=root,homelab,edenilson" > "$ENV_FILE"
    echo "✓ $ENV_FILE criado com ALLOW_LOCAL_USERS"
fi

# 4. Recarregar sshd de forma segura (sem reiniciar — preserva sessões)
echo "Recarregando sshd..."
kill -HUP "$(cat /run/sshd.pid 2>/dev/null || pgrep -ox sshd)" 2>/dev/null && echo "✓ sshd recarregado (HUP)" || true

# 5. Verificar resultado
echo ""
echo "=== Estado atual do PAM sshd (linhas relevantes) ==="
grep -E "authentik|pam_exec" "$SSHD_PAM" 2>/dev/null || echo "(sem linhas do guard)"
echo ""
echo "=== ALLOW_LOCAL_USERS ==="
grep "ALLOW_LOCAL_USERS" "$ENV_FILE" 2>/dev/null || echo "(não encontrado)"
echo ""
echo "✓ Concluído. Teste SSH a partir do cliente."
