# CMDB Stack - NetBox + GLPI

Este diretorio aplica a `Fase 0.5` e a `Fase 1` do plano de CMDB:

- stack de containers para `NetBox + GLPI`
- proxy HTTP simples para separar os vhosts
- baseline generator para transformar o repositorio atual em artefatos iniciais do CMDB
- helper de deploy seguro para staging no homelab

## O que este stack faz

- `NetBox` como `source of truth` de infraestrutura
- `GLPI` como camada operacional de inventario e atendimento
- portas diretas em loopback para bootstrap local
- proxy HTTP em vhosts para preparar publicacao controlada

## Arquivos principais

- `docker-compose.yml`
- `.env.example`
- `nginx/templates/default.conf.template`
- `glpi/php/cmdb.ini`
- `bootstrap/generated/`

## Quick start local

1. Criar o arquivo de ambiente:

```bash
cd /workspace/eddie-auto-dev/deploy/cmdb
cp .env.example .env
```

2. Trocar todas as senhas e hostnames de `.env`.

3. Validar o compose:

```bash
docker compose --env-file .env -f docker-compose.yml config >/dev/null
```

4. Subir o stack:

```bash
docker compose --env-file .env -f docker-compose.yml up -d
```

5. Inicializar o schema do GLPI de forma confiavel:

```bash
/workspace/eddie-auto-dev/scripts/cmdb/install_glpi_schema.sh \
  --env-file /workspace/eddie-auto-dev/deploy/cmdb/.env \
  --container cmdb-glpi
```

## Endpoints de bootstrap

- NetBox direto: `http://127.0.0.1:18091`
- GLPI direto: `http://127.0.0.1:18092`
- Proxy HTTP: `http://127.0.0.1:18090`
- Portal Authentik: `https://auth.rpa4all.com/cmdb/`
- NetBox publicado: `https://auth.rpa4all.com/cmdb/netbox/`
- GLPI publicado: `https://auth.rpa4all.com/cmdb/glpi/index.php`

O proxy usa hostnames. Para testar sem DNS publico, adicione entradas locais ou use `curl --resolve`.

## Baseline do CMDB

Gerar os artefatos iniciais do MVP a partir do repositorio:

```bash
python3 /workspace/eddie-auto-dev/scripts/cmdb/generate_cmdb_baseline.py
```

Saidas:

- `deploy/cmdb/bootstrap/generated/cmdb-baseline.json`
- `deploy/cmdb/bootstrap/generated/cmdb-baseline.md`
- `deploy/cmdb/bootstrap/generated/netbox-devices.csv`
- `deploy/cmdb/bootstrap/generated/glpi-computers.csv`
- `deploy/cmdb/bootstrap/generated/applications-review.csv`

Opcionalmente, mantenha overrides versionados em:

- `deploy/cmdb/bootstrap/cmdb-agent-overrides.json`

Use esse arquivo para fixar:

- `primary_ip4` com CIDR real por host
- `target_device` padrao para os itens do NetBox
- `target_computer` padrao para os vinculos de software do GLPI

## Seed minimo do NetBox

Para criar o site, device, interface, prefixo e IP primario do homelab:

```bash
/workspace/eddie-auto-dev/scripts/cmdb/seed_netbox_minimal.sh \
  --container cmdb-netbox
```

## Deploy seguro para o homelab

O helper abaixo copia os arquivos para staging remoto por padrao e so aplica se `--apply` for informado:

```bash
scripts/deployment/deploy_cmdb_stack.sh --host 192.168.15.2 --user homelab
scripts/deployment/deploy_cmdb_stack.sh --host 192.168.15.2 --user homelab --apply
```

## Publicacao com Authentik

Para acoplar o CMDB ao `auth.rpa4all.com` com SSO por proxy:

```bash
scripts/deployment/deploy_cmdb_auth.sh
```

Esse fluxo:

- publica o portal em `auth.rpa4all.com/cmdb/`
- publica `NetBox` em `auth.rpa4all.com/cmdb/netbox/`
- publica `GLPI` em `auth.rpa4all.com/cmdb/glpi/index.php`
- garante o vhost publico `auth.rpa4all.com` em `80/443` apontando para o backend local `127.0.0.1:9001`
- ativa `REMOTE_AUTH` do NetBox usando os headers `X-authentik-*`
- ativa o SSO delegado do GLPI com `HTTP_X_AUTHENTIK_USERNAME`
- registra um atalho `CMDB Portal` na biblioteca do Authentik

Se precisar reaplicar apenas a configuracao do GLPI:

```bash
scripts/cmdb/configure_glpi_sso.sh --env-file /workspace/eddie-auto-dev/deploy/cmdb/.env
scripts/cmdb/ensure_glpi_admin_users.sh --env-file /workspace/eddie-auto-dev/deploy/cmdb/.env
```

## Observacoes importantes

- o stack nasce com o proxy em `127.0.0.1` para reduzir superficie por padrao
- o frontend HTTPS de `auth.rpa4all.com` deve existir e encaminhar para `127.0.0.1:9001`; o template versionado fica em `site/deploy/auth-public-server.nginx.conf`
- `NetBox` usa `BASE_PATH` definido em `deploy/cmdb/netbox/extra.py` para funcionar em `/cmdb/netbox/`
- `GLPI` recebe um `Alias /cmdb/glpi` no Apache interno para preservar o subpath sem reescrita fragil no gateway
- o gerador de baseline usa apenas artefatos locais do repositorio; ele nao substitui a reconciliacao com o ambiente vivo
- `GLPI_SKIP_AUTOINSTALL=true` e a instalacao via CLI foram mais confiaveis do que depender da auto-instalacao da imagem
