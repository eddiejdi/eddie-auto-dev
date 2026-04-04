#!/usr/bin/env bash
# =============================================================================
# fix-authentik-vscode-keyring.sh
# Corrige o prompt de senha do VSCode após login via Authentik.
#
# Problema: pam_gnome_keyring.so está posicionado APÓS o módulo "sufficient"
#   do authentik-login-guard. Quando o Authentik autentica com sucesso,
#   o PAM pula todos os módulos auth seguintes → keyring não é desbloqueado
#   → VSCode pede senha e só aceita a senha local antiga.
#
# Solução: mover pam_gnome_keyring.so para ANTES do módulo sufficient.
# =============================================================================
set -euo pipefail

PAM_FILE="/etc/pam.d/lightdm"
BACKUP="${PAM_FILE}.bak.$(date +%Y%m%d_%H%M%S)"

echo "=== Fix Authentik + VSCode Keyring ==="
echo "Arquivo: $PAM_FILE"

# 1. Verificar que o arquivo existe e tem o marcador do guard
if ! grep -q "authentik-login-guard" "$PAM_FILE"; then
    echo "ERRO: $PAM_FILE não contém 'authentik-login-guard'. Abortando."
    exit 1
fi

# 2. Verificar se pam_gnome_keyring.so já está antes do sufficient (fix já aplicado)
KEYRING_LINE=$(grep -n "pam_gnome_keyring.so" "$PAM_FILE" | grep -v "session\|auto_start" | head -1 | cut -d: -f1)
SUFFICIENT_LINE=$(grep -n "sufficient.*authentik-login-guard" "$PAM_FILE" | head -1 | cut -d: -f1)

if [[ -n "$KEYRING_LINE" && -n "$SUFFICIENT_LINE" && "$KEYRING_LINE" -lt "$SUFFICIENT_LINE" ]]; then
    echo "✓ Fix já aplicado (keyring na linha $KEYRING_LINE, sufficient na linha $SUFFICIENT_LINE)."
    echo "  Nenhuma alteração necessária."
else
    # 3. Backup
    cp "$PAM_FILE" "$BACKUP"
    echo "✓ Backup salvo em: $BACKUP"

    # 4. Aplicar correção:
    #    - remover a linha -auth optional pam_gnome_keyring.so (após @include common-auth)
    #    - inserir antes da linha do sufficient
    python3 - <<'PYEOF'
import re
with open("/etc/pam.d/lightdm", "r") as f:
    content = f.read()

# Remover linha existente do keyring na posição errada (auth, não session)
content_fixed = re.sub(
    r'\n-auth\s+optional\s+pam_gnome_keyring\.so\s*\n',
    '\n',
    content
)

# Inserir ANTES da linha sufficient do authentik-login-guard
content_fixed = re.sub(
    r'(# Managed by Shared Auto-Dev: Authentik login guard\n)(auth\s+sufficient)',
    r'\1-auth  optional        pam_gnome_keyring.so\n\2',
    content_fixed
)

with open("/etc/pam.d/lightdm", "w") as f:
    f.write(content_fixed)

print("✓ PAM file atualizado.")
PYEOF
fi

echo ""
echo "=== Resultado atual ==="
grep -n "pam_gnome_keyring\|sufficient.*authentik\|@include common-auth" "$PAM_FILE"

echo ""
echo "=== PASSO 2: Trocar senha do GNOME Keyring ==="
echo "O keyring 'Login' ainda usa a senha LOCAL antiga."
echo "Para que o VSCode pare de pedir senha após login Authentik, execute:"
echo ""
echo "  seahorse"
echo ""
echo "  Depois: clique no cadeado 'Login' → clique com botão direito"
echo "  → 'Mudar Senha' → informe a senha LOCAL atual e defina a nova"
echo "    senha igual à sua senha do Authentik."
echo ""
echo "  OU (alternativa sem interface gráfica): deixe a senha vazia:"
echo "  python3 -c \""
echo "  import secretstorage, keyring as k"
echo "  # use seahorse para trocar para a senha do Authentik"
echo "  \""
echo ""
echo "IMPORTANTE: após trocar a senha do keyring, o próximo login via Authentik"
echo "  desbloqueará o keyring automaticamente e o VSCode não pedirá mais senha."
echo ""
echo "=== CONCLUÍDO ==="
