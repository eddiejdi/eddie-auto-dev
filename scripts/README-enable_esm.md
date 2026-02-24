Enable ESM on homelab
=====================

Resumo
-----
Pequeno guia sobre `scripts/enable_esm_homelab.sh` que ativa o Extended Security Maintenance (ESM) no homelab via SSH.

Uso rápido
----------
1. Torne o script executável e defina variáveis de ambiente:

```bash
chmod +x scripts/enable_esm_homelab.sh
export HOMELAB_HOST=192.168.15.2
export HOMELAB_USER=homelab
# opcional: token direto
# export SUBSCRIPTION_TOKEN=SEU_TOKEN
# opcional: buscar token do Secrets Agent local
# export SUBSCRIPTION_SECRET_NAME=eddie/ubuntu_pro
./scripts/enable_esm_homelab.sh
```

Notas de segurança
------------------
- Preferível recuperar o token do `Secrets Agent` usando `SUBSCRIPTION_SECRET_NAME`.
- O script tenta usar o cliente Python `tools.secrets_agent_client` se presente no repositório.
- Evite passar tokens em linha de comando em ambientes públicos.

SSH
---
- O script usa `ssh -o BatchMode=yes` e presume autenticação por chave. Se usar senha, abra uma sessão `ssh homelab@HOST` e execute manualmente os comandos listados abaixo.

Comandos remotos executados (para referência)
--------------------------------------------
- `sudo apt update -y`
- `sudo apt install -y ubuntu-advantage-tools` (se não existir)
- `sudo ua attach <TOKEN>` (se token fornecido)
- `sudo ua enable esm-apps`
- `sudo ua enable esm-infra`
- `sudo ua status`

Ansible (opcional)
-------------------
Se quiser, posso gerar um playbook Ansible idempotente para aplicar isso a múltiplos hosts.

Ajuda
-----
Se preferir que eu gere o playbook Ansible ou um wrapper interativo, diga "gerar Ansible" ou "wrapper interativo".
