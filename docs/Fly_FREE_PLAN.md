**Fly.io — Free / Minimal Usage Guide (project adjustments)**

Resumo do levantamento (pesquisa oficial Fly.io):
- Máquinas nomeadas mínimas: `shared-cpu-1x` (smallest shared CPU preset; available memory variants from 256MB upward).
- Comandos `flyctl scale vm <size>` e `flyctl scale count <n>` permitem definir o tamanho e número de instâncias.
- Volumes e snapshots são cobrados; evitar volumes reduz custos (volumes: $0.15/GB/month). Volume snapshots incur additional charges (first 10GB free/month).
- Fly historically offered legacy free allowances (e.g. up to 3 shared-cpu-1x 256MB VMs for some legacy orgs) but new accounts follow pay-as-you-go pricing. Use smallest VM and scale to 1 to minimise cost.

Objetivo deste ajuste
- Garantir que o repositório tenha instruções e templates para implantar os serviços com a configuração mínima compatível com o cenário free/minimal do Fly.io.

Recomendações aplicadas ao projeto
- Sempre usar `shared-cpu-1x` como `vm` size e `scale count 1` para ambientes gratuitos/experimentais.
- Evitar volumes persistentes: use serviços externos gerenciados (Upstash/Redis, managed DBs) ou configure a app para operar sem estado.
- Minimizar tráfego de saída e usar uma única região próxima aos utilizadores para reduzir egress costs.
- Nunca habilitar múltiplas réplicas/auto-scale por padrão.

Flyctl quick commands (example)
```bash
# create or select app
flyctl apps create specialized-agents --org <ORG> --region ams

# deploy (build + deploy)
flyctl deploy --app specialized-agents

# set minimal vm size and single instance
flyctl scale vm shared-cpu-1x --app specialized-agents
flyctl scale count 1 --app specialized-agents

# ensure no volumes attached; if volumes exist, remove or detach
flyctl volumes list --app specialized-agents
```

Files added to this repo for free/minimal deployment
- `deploy/fly/specialized-agents.fly.toml` — template `fly.toml` with minimal service (http) and notes.
- `deploy/fly/deploy_minimal.sh` — helper script with the recommended `flyctl` commands (editable by user).
- `docs/Fly_FREE_PLAN.md` — este arquivo.

Observações finais
- As configurações no repositório são conservadoras: não faço mudanças automáticas nas rotinas de deploy existentes; em vez disso forneço templates e recomendações para usar o plano free/minimal.
- Precaução: reveja qualquer screenshot ou arquivo com dados sensíveis antes de commitar artefatos de UI.
