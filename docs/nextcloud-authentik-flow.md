# Nextcloud + Authentik Integration Flow

## Resumo do fluxo atual

Este projeto integra o Nextcloud com o Authentik como provedor de identidade.
O storage `/LTO` do Nextcloud nao deve apontar direto para LTFS: desde o incidente
de 2026-04-23 ele deve usar staging em disco, com flush controlado para a fita.

### Componentes principais

- `tools/authentik_management/configure_authentik_nextcloud_oidc.py`
  - Provisiona ou atualiza o provider OAuth2/OIDC `authentik-nextcloud` no Authentik.
  - Mantém duas redirect URIs: `oidc_login` como fluxo principal e `user_oidc` apenas para compatibilidade de migração.

- `tools/authentik_management/bootstrap_nextcloud_oidc.sh`
  - Habilita `oidc_login` e `groupfolders` no Nextcloud.
  - Aplica a configuração OIDC via `occ` no container `nextcloud-app`.

- `specialized_agents/api.py` e `specialized_agents/user_management.py`
  - Publicam o painel `/nextcloud-access/` em `auth.rpa4all.com`.
  - Criam usuários no Authentik e dependem do auto-provisionamento OIDC do Nextcloud no primeiro login.

- `docs/NEXTCLOUD_LTO_STAGING_ARCHITECTURE_2026-04-23.md`
  - Define o contrato correto: `/LTO` no Nextcloud aponta para staging em disco.
  - O worker `ltfs-cache-flush` e o unico caminho suportado para gravacao em fita.

- `storage_portal_api.py`
  - Usa as variáveis `NEXTCLOUD_URL` e `NEXTCLOUD_BASE_PATH`.
  - Gera URLs de workspace em Nextcloud para contratos do portal de armazenamento.

## Fluxo lógico expandido

1. Autenticação
   - Authentik atua como IdP OIDC.
   - Nextcloud usa o app `oidc_login` para autenticar via Authentik.
   - O script `tools/authentik_management/configure_authentik_nextcloud_oidc.py` registra o provider OIDC no Authentik com:
     - client_id `authentik-nextcloud`
     - client_secret `nextcloud-sso-secret-2026`
     - redirect URIs:
       - `https://nextcloud.rpa4all.com/apps/oidc_login/oidc`
       - `https://nextcloud.rpa4all.com/apps/user_oidc/code` apenas para compatibilidade durante migração
   - `tools/authentik_management/bootstrap_nextcloud_oidc.sh` configura o Nextcloud para usar Authentik como provedor.

2. Provisionamento de usuários e grupos
   - Authentik sincroniza usuários e hierarquia de gestores/subordinados.
   - O painel `/nextcloud-access/users` cria o usuário no Authentik com os grupos padrão para Nextcloud.
   - O grupo padrão do fluxo é `users`, alinhado com `specialized_agents/user_management.py`.
   - Grupos extras e grupos de equipe `NC_TEAM_*` podem ser adicionados no provisionamento.

3. Arquivos e armazenamento
   - O Nextcloud enxerga `/LTO` via bind de staging em disco (`/mnt/lto6-nc -> /var/www/html/external/LTO`).
   - O staging real deve apontar para disco local (`/mnt/raid1/lto6-cache`), nao para `/mnt/tape/lto6`.
   - A fita LTFS permanece fora do caminho online do Nextcloud.
   - O pipeline do portal de contratos cria links para `NEXTCLOUD_URL + NEXTCLOUD_BASE_PATH + /<contract>`.

4. Publicação e uso
   - Usuários autenticados via Authentik acessam Nextcloud.
   - Grupos de equipe recebem acesso automático a Group Folders.
   - A integração com LTFS fornece um caminho de armazenamento físico para arquivos grandes.

## Distinção importante de fluxos

Existem dois fluxos diferentes e eles não devem ser confundidos:

- Login do usuário final no Nextcloud:
  - URL: `https://nextcloud.rpa4all.com`
  - Plugin principal: `oidc_login`
  - Callback principal: `/apps/oidc_login/oidc`

- Painel administrativo protegido por Authentik:
  - URL: `https://auth.rpa4all.com/nextcloud-access/`
  - Proxy: `site/deploy/auth-nextcloud-access-location.nginx.conf`
  - Backend: FastAPI do projeto

## Reativação completa do fluxo

Este repositório suporta o bootstrap do fluxo Nextcloud + Authentik.
O fluxo antigo de "reativar LTFS no NAS e bindar direto no Nextcloud" foi aposentado.

1. Validar a arquitetura de staging:
   - Leia `docs/NEXTCLOUD_LTO_STAGING_ARCHITECTURE_2026-04-23.md`
   - Confirme que `/mnt/lto6-nc` aponta para staging em disco, nao para LTFS
   - Confirme que apenas `ltfs-cache-flush` escreve na fita
2. Reconfigurar o Nextcloud para Authentik:
   - `set -a; source .env; set +a`
   - `python3 tools/authentik_management/configure_authentik_nextcloud_oidc.py`
   - `bash tools/authentik_management/bootstrap_nextcloud_oidc.sh`

### Ordem esperada

- Primeiro, valide que `/LTO` usa staging em disco e que LTFS nao esta no caminho online do Nextcloud.
- Depois, execute o bootstrap OIDC no Nextcloud para garantir que o provider Authentik esteja disponível e os apps `oidc_login` e `groupfolders` estejam habilitados.

## Pontos de expansão sugeridos

- Documentar claramente em `docs/ltfs-plan.md` ou `docs/nextcloud-authentik-flow.md` como o LTFS externo se conecta ao Nextcloud.
- Remover ou aposentar automações que bindem LTFS diretamente em `/srv/nextcloud/external/LTO`.
- Adicionar validação de `NEXTCLOUD_URL` e `NEXTCLOUD_BASE_PATH` no portal de contratos para garantir que os links de workspace sempre funcionem.
- Consolidar o fluxo de grupo do Authentik → Nextcloud Group Folders em um único script/documento de operação.
- Adicionar um teste do bootstrap `occ` se o fluxo passar a ser exercitado em CI com container do Nextcloud.

## Conclusão

O workspace agora tem um fluxo menos ambíguo:
- autenticação principal via `oidc_login`,
- callback legacy `user_oidc` apenas para compatibilidade,
- bootstrap versionado em `tools/authentik_management/`,
- painel administrativo separado do login do usuário final.
