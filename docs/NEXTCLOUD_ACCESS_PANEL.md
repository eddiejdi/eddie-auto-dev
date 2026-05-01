# Painel de Acesso ao Nextcloud

## Objetivo

Fornecer um painel administrativo para criar usuários no Authentik já prontos para utilizar o Nextcloud via OIDC, sem precisar criar conta diretamente no Nextcloud.

## Como funciona

1. O painel envia os dados para `POST /nextcloud-access/users`.
2. O backend cria o usuário no Authentik.
3. Os grupos necessários para o fluxo do Nextcloud são aplicados.
4. O Nextcloud faz o auto-provisionamento no primeiro login do usuário em `https://nextcloud.rpa4all.com`.

## Endpoints

- Painel HTML: `GET /nextcloud-access/panel`
- Criação de usuário: `POST /nextcloud-access/users`
- Healthcheck: `GET /nextcloud-access/health`

## Perfil criado

O perfil de acesso Nextcloud usa o backend de `specialized_agents.user_management`, mas com diferenças importantes:

- não cria conta local do sistema operacional;
- não provisiona caixa de email por padrão;
- aplica grupos base do Nextcloud via Authentik;
- pode anexar grupo de equipe no padrão `NC_TEAM_<gestor>`.

## Registro no Authentik

Para tornar o painel visível dentro do portal do Authentik:

```bash
python3 tools/authentik_management/register_nextcloud_access_panel.py
```

Variáveis úteis:

- `AUTHENTIK_URL`
- `AUTHENTIK_TOKEN`
- `NEXTCLOUD_ACCESS_PANEL_URL`
- `NEXTCLOUD_ACCESS_PANEL_NAME`
- `NEXTCLOUD_ACCESS_PANEL_SLUG`

Valor padrão de publicação:

```text
https://auth.rpa4all.com/nextcloud-access/
```

## Observação operacional

O fluxo esperado é publicar o painel dentro do vhost do Authentik, em `auth.rpa4all.com`, usando o template versionado:

```text
site/deploy/auth-nextcloud-access-location.nginx.conf
```

O Authentik continua como portal de entrada, enquanto o backend do painel segue servido pelo FastAPI do projeto em `/nextcloud-access/`.
