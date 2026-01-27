#!/usr/bin/env bash
set -euo pipefail

# deploy_via_ssh.sh
# Copia scripts para o host remoto, cria o arquivo de env e ativa a unidade systemd
# Uso:
# ./deploy_via_ssh.sh --host HOST --user USER --instance dev --port 3000 --subdomain mysub

REMOTE_HOST=""
REMOTE_USER=""
INSTANCE="dev"
PORT=3000
SUBDOMAIN=""

usage(){
  echo "Usage: $0 --host HOST --user USER --instance INSTANCE --port PORT [--subdomain SUB]" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) REMOTE_HOST="$2"; shift 2 ;;
    --user) REMOTE_USER="$2"; shift 2 ;;
    --instance) INSTANCE="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --subdomain) SUBDOMAIN="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1"; usage ;;
  esac
done

if [ -z "$REMOTE_HOST" ] || [ -z "$REMOTE_USER" ]; then
  usage
fi

SSH_TARGET="$REMOTE_USER@$REMOTE_HOST"

echo "Preparando deploy para $SSH_TARGET (instance=$INSTANCE)"

REMOTE_BIN_DIR=/usr/local/bin
REMOTE_ETC_DIR=/etc/eddie
REMOTE_SYSTEMD_DIR=/etc/systemd/system

echo "Criando diretórios remotos..."
ssh "$SSH_TARGET" "sudo mkdir -p $REMOTE_ETC_DIR /var/lib/eddie && sudo chown root:root $REMOTE_ETC_DIR /var/lib/eddie"

echo "Copiando scripts..."
scp tools/tunnels/start_remote_tunnel.sh "$SSH_TARGET":/tmp/start_remote_tunnel.sh
ssh "$SSH_TARGET" "sudo mv /tmp/start_remote_tunnel.sh $REMOTE_BIN_DIR/start_remote_tunnel.sh && sudo chmod +x $REMOTE_BIN_DIR/start_remote_tunnel.sh"

echo "Instalando unidade systemd..."
scp tools/tunnels/localtunnel@.service "$SSH_TARGET":/tmp/localtunnel@.service
ssh "$SSH_TARGET" "sudo mv /tmp/localtunnel@.service $REMOTE_SYSTEMD_DIR/localtunnel@.service"

echo "Criando arquivo de ambiente /etc/eddie/localtunnel-$INSTANCE.env"
ssh "$SSH_TARGET" "sudo tee $REMOTE_ETC_DIR/localtunnel-$INSTANCE.env > /dev/null <<EOF
PORT=$PORT
SUBDOMAIN=$SUBDOMAIN
EOF
" 

echo "Reload systemd, enable and start service for instance $INSTANCE"
ssh "$SSH_TARGET" "sudo systemctl daemon-reload && sudo systemctl enable --now localtunnel@$INSTANCE.service"

echo "Deploy concluído. Verifique status remoto:" 
echo "ssh $SSH_TARGET 'sudo systemctl status localtunnel@$INSTANCE'"
