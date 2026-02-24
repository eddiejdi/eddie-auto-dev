#!/usr/bin/env bash
set -euo pipefail

# scripts/enable_esm_homelab.sh
# Uso:
#   export HOMELAB_HOST=192.168.15.2
#   export HOMELAB_USER=homelab         # opcional, padrão: homelab
#   export SUBSCRIPTION_TOKEN=XXXXX     # opcional (se necessário)
#   export SUBSCRIPTION_SECRET_NAME=eddie/ubuntu_pro  # opcional: nome do secret no Secrets Agent
#   ./scripts/enable_esm_homelab.sh
#
# Este script envia um pequeno script remoto via SSH para executar os
# passos de ativação do ESM. Se `SUBSCRIPTION_SECRET_NAME` estiver definido
# e o cliente `tools.secrets_agent_client` estiver disponível, o token
# será recuperado automaticamente do Secrets Agent local antes da execução.

HOST=${HOMELAB_HOST:-}
USER=${HOMELAB_USER:-homelab}
TOKEN=${SUBSCRIPTION_TOKEN:-}
SECRET_NAME=${SUBSCRIPTION_SECRET_NAME:-}

if [ -z "${HOST}" ]; then
  echo "ERRO: defina a variável HOMELAB_HOST (ex: export HOMELAB_HOST=192.168.15.2)"
  exit 1
fi

SSH_TARGET="${USER}@${HOST}"

echo "Preparando execução no ${SSH_TARGET}..."

# Se um nome de secret foi fornecido, tente usar o cliente Python local para buscar
if [ -n "${SECRET_NAME}" ] && [ -z "${TOKEN}" ]; then
  echo "Tentando recuperar token do Secrets Agent (secret: ${SECRET_NAME})..."
  if python3 - <<'PY'
import sys
try:
    from tools.secrets_agent_client import get_secrets_agent_client
    c = get_secrets_agent_client()
    s = c.get_secret('${SECRET_NAME}')
    if isinstance(s, dict):
        if 'SUBSCRIPTION_TOKEN' in s:
            print(s['SUBSCRIPTION_TOKEN'])
        elif 'token' in s:
            print(s['token'])
        elif 'value' in s:
            print(s['value'])
        else:
            print('')
    else:
        print(s)
except Exception:
    # falha silenciosa — retornará código 0 mas sem saída
    pass
PY
  then
    TOKEN=$(python3 - <<'PY'
import sys
try:
    from tools.secrets_agent_client import get_secrets_agent_client
    c = get_secrets_agent_client()
    s = c.get_secret('${SECRET_NAME}')
    if isinstance(s, dict):
        if 'SUBSCRIPTION_TOKEN' in s:
            print(s['SUBSCRIPTION_TOKEN'])
        elif 'token' in s:
            print(s['token'])
        elif 'value' in s:
            print(s['value'])
        else:
            print('')
    else:
        print(s)
except Exception:
    pass
PY
    if [ -n "${TOKEN}" ]; then
      echo "Token obtido do Secrets Agent."
    else
      echo "Não foi possível obter token do Secrets Agent (ou field não encontrado)."
    fi
  else
    echo "Cliente do Secrets Agent não disponível; pulando recuperação automática." 
  fi
fi

# Constrói o script que será executado remotamente. O token será inserido
# aqui localmente (se disponível) antes de enviar para o host remoto.
REMOTE_SCRIPT=$(cat <<'EOF'
set -euo pipefail
echo "Atualizando repositórios..."
sudo apt update -y

# instalar ua se necessário
if ! command -v ua >/dev/null 2>&1; then
  echo "Instalando ubuntu-advantage-tools..."
  sudo apt install -y ubuntu-advantage-tools
else
  echo "ubuntu-advantage-tools já instalado"
fi

# anexar token se estiver presente
TOKEN_PLACEHOLDER="__SUBSCRIPTION_TOKEN__"
if [ "${TOKEN_PLACEHOLDER}" != "" ] && [ "${TOKEN_PLACEHOLDER}" != "__SUBSCRIPTION_TOKEN__" ]; then
  echo "Anexando subscrição Canonical..."
  sudo ua attach "${TOKEN_PLACEHOLDER}" || echo "ua attach falhou (verifique o token)"
else
  echo "Nenhum token fornecido; pulando 'ua attach'"
fi

# habilitar ESM apps + infra (não falha se já habilitado)
echo "Habilitando esm-apps e esm-infra..."
sudo ua enable esm-apps || true
sudo ua enable esm-infra || true

echo "Verificando status do UA..."
sudo ua status
EOF
)

# Insere token no script remoto, se disponível
if [ -n "${TOKEN}" ]; then
  # escapa barras e cifrões para evitar problemas na substituição
  esc_token=$(printf '%s' "${TOKEN}" | sed -e 's/\/\\\//g' -e 's/\$/\\\$/g')
  REMOTE_SCRIPT_REPLACED=$(printf "%s" "${REMOTE_SCRIPT}" | sed "s#__SUBSCRIPTION_TOKEN__#${esc_token}#g")
else
  REMOTE_SCRIPT_REPLACED="${REMOTE_SCRIPT}"
fi

echo "Executando comandos remotos (via SSH)..."
printf '%s' "${REMOTE_SCRIPT_REPLACED}" | ssh -o BatchMode=yes "${SSH_TARGET}" "bash -s"

echo "Concluído. Se houve problemas de autenticação SSH, conecte-se manualmente e rode os comandos listados no README."

exit 0
