# Deploy via GitHub Actions to Homelab

O repositório inclui um workflow GitHub Actions (`.github/workflows/deploy-to-homelab.yml`) que executa deploy no host remoto (homelab) quando um Pull Request recebe a label `deploy` ou via manual `workflow_dispatch`.

Variáveis / Secrets necessários no repositório (Settings > Secrets):

- `HOMELAB_HOST` (ex: 192.168.15.2)
- `HOMELAB_USER` (ex: homelab)
- `HOMELAB_SSH_PRIVATE_KEY` (chave privada SSH do usuário)

O workflow faz um `ssh` para o host e executa `cd ~/eddie-auto-dev && git pull && ./deploy_prod.sh`.

Use com cuidado: assegure que o usuário remoto tem permissões para executar `docker` e que as chaves SSH são seguras.

## Self-hosted runner (recomendado para redes privadas)

GitHub-hosted runners não conseguem alcançar IPs privados (ex.: `192.168.*.*`). Se seu homelab está em uma rede privada, instale um **self-hosted runner** no homelab e use o workflow dedicado `Deploy to Homelab (Self-hosted)` (Actions → `Deploy to Homelab (Self-hosted)`) para executar deploys a partir da máquina homelab.

Passos rápidos:

1. No homelab, crie um token de registro do runner em GitHub (Repo → Settings → Actions → Runners → Add runner).
2. No homelab, rode `tools/deploy/setup_self_hosted_runner.sh` com `RUNNER_TOKEN` exportado (o script configura e registra o runner como serviço systemd).
3. No GitHub, abra Actions → `Deploy to Homelab (Self-hosted)` → `Run workflow` e forneça os inputs `host` e `user` (o job será executado no runner self-hosted e fará o deploy localmente).

Observação: o workflow principal `deploy-to-homelab.yml` agora **tenta executar primeiro** em um runner self-hosted (`deploy-selfhost`), com timeout curto. Se o self-hosted não estiver disponível ou falhar, o workflow automaticamente tentará o fallback em runners GitHub-hosted (`deploy`) — mas este último **não** alcançará IPs privados; prefira self-hosted para redes privadas.

Esse método evita problemas de NAT/firewall e é a forma mais confiável de automatizar deploys em hosts privados.

## Monitoramento automático (opcional)

Adicionei um workflow agendado (`.github/workflows/selfhost-monitor.yml`) que roda a cada hora e cria uma issue automática se nenhum runner self-hosted com label `self-hosted` ou `homelab` for encontrado. Ele usa `GITHUB_TOKEN` (já disponível para Actions) — você pode desabilitar o workflow se preferir não criar issues automaticamente.
