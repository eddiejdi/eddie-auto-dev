# Deploy via GitHub Actions to Homelab

O repositório inclui um workflow GitHub Actions (`.github/workflows/deploy-to-homelab.yml`) que executa deploy no host remoto (homelab) quando um Pull Request recebe a label `deploy` ou via manual `workflow_dispatch`.

Variáveis / Secrets necessários no repositório (Settings > Secrets):

- `HOMELAB_HOST` (ex: 192.168.15.2)
- `HOMELAB_USER` (ex: homelab)
- `HOMELAB_SSH_PRIVATE_KEY` (chave privada SSH do usuário)

O workflow faz um `ssh` para o host e executa `cd ~/eddie-auto-dev && git pull && ./deploy_prod.sh`.

Use com cuidado: assegure que o usuário remoto tem permissões para executar `docker` e que as chaves SSH são seguras.
