# CMDB Agent

Agente para preparar a carga do CMDB em `NetBox` e `GLPI` a partir dos artefatos
já versionados no repositório.

## O que ele faz

- reaproveita `scripts/cmdb/generate_cmdb_baseline.py`
- levanta hosts e serviços do repositório
- revisa lacunas que ainda exigem confirmação humana
- gera pacotes de carga orientados a `NetBox` e `GLPI`
- gera plano de aplicação para `NetBox`
- gera plano operacional de import para `GLPI`
- materializa relatórios e CSVs de apoio para a importação

## Overrides versionados

O agente aceita um arquivo opcional em:

- `deploy/cmdb/bootstrap/cmdb-agent-overrides.json`

Esse contrato serve para tirar ambiguidade do baseline, por exemplo:

- corrigir `primary_ip4` com CIDR real quando o inventário só tiver IP sem máscara
- fixar `target_device` padrão para os itens do NetBox
- fixar `target_computer` padrão para os vínculos de software do GLPI

## Artefatos gerados

- `cmdb-baseline.json`
- `cmdb-baseline.md`
- `netbox-load-package.json`
- `netbox-apply-plan.json`
- `glpi-load-package.json`
- `glpi-apply-plan.json`
- `glpi-apply.sql`
- `review-queue.json`
- `cmdb-agent-report.json`
- `cmdb-agent-report.md`
- `netbox-device-import.csv`
- `glpi-computer-import.csv`

## Uso CLI

```bash
python3 -m specialized_agents.cmdb_agent \
  --repo-root /workspace/eddie-auto-dev \
  --inventory-file /workspace/eddie-auto-dev/config/inventory_homelab.yml \
  --output-dir /workspace/eddie-auto-dev/deploy/cmdb/bootstrap/generated \
  --overrides-file /workspace/eddie-auto-dev/deploy/cmdb/bootstrap/cmdb-agent-overrides.json \
  --site-name homelab-main
```

Dry-run do aplicador NetBox:

```bash
python3 -m specialized_agents.cmdb_agent \
  --apply-netbox-package /workspace/eddie-auto-dev/deploy/cmdb/bootstrap/generated/netbox-load-package.json \
  --netbox-container cmdb-netbox
```

Execução real no host que possui o container:

```bash
python3 -m specialized_agents.cmdb_agent \
  --apply-netbox-package /workspace/eddie-auto-dev/deploy/cmdb/bootstrap/generated/netbox-load-package.json \
  --netbox-container cmdb-netbox \
  --execute
```

Preview operacional do GLPI:

```bash
python3 -m specialized_agents.cmdb_agent \
  --plan-glpi-package /workspace/eddie-auto-dev/deploy/cmdb/bootstrap/generated/glpi-load-package.json
```

Execução real no host do stack GLPI:

```bash
python3 -m specialized_agents.cmdb_agent \
  --plan-glpi-package /workspace/eddie-auto-dev/deploy/cmdb/bootstrap/generated/glpi-load-package.json \
  --glpi-env-file /workspace/eddie-auto-dev/deploy/cmdb/.env \
  --execute
```

## Uso HTTP

- `GET /cmdb/agent/health`
- `POST /cmdb/agent/run`
- `POST /cmdb/agent/apply/netbox`
- `POST /cmdb/agent/apply/glpi`

Exemplo:

```json
{
  "repo_root": "/workspace/eddie-auto-dev",
  "inventory_file": "/workspace/eddie-auto-dev/config/inventory_homelab.yml",
  "output_dir": "/workspace/eddie-auto-dev/deploy/cmdb/bootstrap/generated",
  "overrides_file": "/workspace/eddie-auto-dev/deploy/cmdb/bootstrap/cmdb-agent-overrides.json",
  "site_name": "homelab-main",
  "write_outputs": true
}
```

## Aplicação

### NetBox

- suportado de forma idempotente
- estratégia atual: `docker exec ... manage.py shell` no container `cmdb-netbox`
- cria/atualiza site, manufacturer, role, platform, device type, device, interface, prefix e IP
- materializa `service_candidates` como `InventoryItem` e `InventoryItemRole` no device alvo inferido
- quando o baseline não traz mapeamento explícito de host, usa o host principal inferido e marca a associação como revisão posterior
- quando existir `cmdb-agent-overrides.json`, o target padrão pode ser explicitado ali e deixa de entrar como pendência

### GLPI

- suportado por SQL idempotente para `computers`, `softwares`, `softwareversions` e `items_softwareversions`
- estratégia atual: `docker exec ... mariadb` no container `glpi-db`
- faz `upsert` por `name` em `entity 0`
- preserva o owner em `contact` e tenta mapear `users_id`/`users_id_tech` quando existir usuário GLPI com o mesmo `name`
- cria e mantém `softwarecategories` por domínio sob a raiz `CMDB Imported`
- materializa `applications_review` como catálogo de software e vincula ao computador alvo inferido
- quando o baseline não traz vínculo explícito com o ativo, o link gerado deve ser reconciliado após a primeira onda de import
- quando existir `cmdb-agent-overrides.json`, o target padrão pode ser explicitado ali e deixa de entrar como pendência
