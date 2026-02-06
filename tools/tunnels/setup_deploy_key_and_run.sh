#!/usr/bin/env bash
set -euo pipefail

# setup_deploy_key_and_run.sh
# Gera um par de chaves SSH (se não existir), pede para você instalar a chave pública
# no(s) host(s) remoto(s), envia a chave privada para o Secrets do repositório via `gh` e
# dispara o workflow `deploy_localtunnel.yml` com os inputs fornecidos.

REPO="eddiejdi/eddie-auto-dev"
KEY_PATH="$HOME/.ssh/eddie_deploy_rsa"
SECRET_NAME="SSH_PRIVATE_KEY"

usage(){
  cat <<EOF
Usage: $0 --host HOST --user USER --instance INSTANCE [--port PORT] [--subdomain SUBDOMAIN] [--ref REF]

Example:
  $0 --host ${HOMELAB_HOST} --user homelab --instance dev --port 3000 --subdomain '' --ref chore/vault-secrets

This will:
 - generate key pair at $KEY_PATH (if não existir)
 - print the public key for you to install on the remote host(s)
 - upload the private key to GitHub Actions Secrets as $SECRET_NAME for repo $REPO
 - trigger the workflow `deploy_localtunnel.yml` on the given ref with the provided inputs
EOF
  exit 2
}

HOST=""
USER="homelab"
INSTANCE="dev"
PORT="3000"
SUBDOMAIN=""
REF="chore/vault-secrets"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2;;
    --user) USER="$2"; shift 2;;
    --instance) INSTANCE="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --subdomain) SUBDOMAIN="$2"; shift 2;;
    --ref) REF="$2"; shift 2;;
    -h|--help) usage;;
    *) echo "Unknown arg: $1"; usage;;
  esac
done

if [ -z "$HOST" ]; then
  echo "--host is required" >&2; usage
fi

command -v gh >/dev/null 2>&1 || { echo "gh CLI not found. Install and authenticate (gh auth login)." >&2; exit 1; }

# Generate key if missing
if [ ! -f "$KEY_PATH" ]; then
  echo "Gerando par de chaves em $KEY_PATH..."
  mkdir -p "$(dirname "$KEY_PATH")"
  ssh-keygen -t rsa -b 4096 -N "" -C "deploy@${REPO}" -f "$KEY_PATH"
else
  echo "Usando chave existente: $KEY_PATH"
fi

echo "--- Public key (install this on $USER@$HOST in ~/.ssh/authorized_keys) ---"
cat "$KEY_PATH.pub"
echo "--- End public key ---"

read -p "Press ENTER after you've installed the public key on the remote host(s)." _

echo "Uploading private key to GitHub Actions Secrets as $SECRET_NAME for repo $REPO..."
PRIVATE_CONTENT=$(cat "$KEY_PATH")

gh secret set "$SECRET_NAME" --body "$PRIVATE_CONTENT" -R "$REPO"

echo "Secret uploaded. Now dispatching workflow deploy_localtunnel.yml (ref=$REF)"

if [ -n "$SUBDOMAIN" ]; then
  gh workflow run deploy_localtunnel.yml -R "$REPO" --ref "$REF" --field instance="$INSTANCE" --field host="$HOST" --field user="$USER" --field port="$PORT" --field subdomain="$SUBDOMAIN"
else
  gh workflow run deploy_localtunnel.yml -R "$REPO" --ref "$REF" --field instance="$INSTANCE" --field host="$HOST" --field user="$USER" --field port="$PORT"
fi

echo "Workflow dispatched. Check Actions in GitHub or run: gh run list -R $REPO"
