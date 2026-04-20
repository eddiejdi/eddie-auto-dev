# Nextcloud + Authentik Integration Flow

## Resumo do fluxo atual

Este projeto integra o Nextcloud com o Authentik como provedor de identidade e também com o NAS LTFS para armazenamento externo.

### Componentes principais

- `forks/rpa4all-nextcloud-authentik/`
  - `docker-compose.yml`: stack Nextcloud + MariaDB + Redis.
  - `scripts/configure_authentik_nextcloud_oidc.py`: provisiona o provider OIDC do Nextcloud no Authentik.
  - `scripts/bootstrap_nextcloud_oidc.sh`: instala o app `oidc_login`, habilita `groupfolders` e aplica a configuração OIDC no Nextcloud.
  - `scripts/sync_authentik_hierarchy_groups.py`: exporta a hierarquia de grupos/usuários do Authentik.
  - `scripts/apply_nextcloud_team_folders.py`: cria grupos e Group Folders no Nextcloud com base na hierarquia do Authentik.

- `scripts/nas_ltfs_nextcloud_reactivate.sh`
  - Reativa LTFS no NAS e cria bind mount para `Nextcloud` em `/srv/nextcloud/external/LTO`.
  - Garante que o volume LTFS seja montado e que a pasta externa esteja disponível para o Nextcloud.

- `storage_portal_api.py`
  - Usa as variáveis `NEXTCLOUD_URL` e `NEXTCLOUD_BASE_PATH`.
  - Gera URLs de workspace em Nextcloud para contratos do portal de armazenamento.

## Fluxo lógico expandido

1. Autenticação
   - Authentik atua como IdP OIDC.
   - Nextcloud usa o app `oidc_login` para autenticar via Authentik.
   - O script `configure_authentik_nextcloud_oidc.py` registra o provider OIDC no Authentik com:
     - client_id `authentik-nextcloud`
     - client_secret `nextcloud-sso-secret-2026`
     - redirect URIs:
       - `https://nextcloud.rpa4all.com/apps/oidc_login/oidc`
       - `https://nextcloud.rpa4all.com/apps/user_oidc/code`
   - `bootstrap_nextcloud_oidc.sh` configura o Nextcloud para usar Authentik como provedor.

2. Provisionamento de usuários e grupos
   - Authentik sincroniza usuários e hierarquia de gestores/subordinados.
   - `sync_authentik_hierarchy_groups.py` exporta os dados de grupos e membros.
   - `apply_nextcloud_team_folders.py` converte esse mapeamento em:
     - grupos Nextcloud
     - Group Folders correspondentes
     - permissões do grupo sobre a pasta

3. Arquivos e armazenamento
   - O NAS monta a fita LTFS em `/mnt/tape/lto6`.
   - A reativação do LTFS monta bind em `/srv/nextcloud/external/LTO`.
   - Nextcloud passa a ver esse caminho como armazenamento externo.
   - O pipeline do portal de contratos cria links para `NEXTCLOUD_URL + NEXTCLOUD_BASE_PATH + /<contract>`.

4. Publicação e uso
   - Usuários autenticados via Authentik acessam Nextcloud.
   - Grupos de equipe recebem acesso automático a Group Folders.
   - A integração com LTFS fornece um caminho de armazenamento físico para arquivos grandes.

## Achados do site oficial do Nextcloud

A documentação oficial confirma:

- O app `user_oidc` permite ao Nextcloud autenticar usuários usando provedores OIDC externos.
- Se o Nextcloud deve ser identity provider, o app `oidc` é usado.
- Para validação de tokens bearer em APIs, o Nextcloud pode aceitar tokens OIDC e acess tokens.
- No modo IdP, o `user_oidc` precisa de `oidc_provider_bearer_validation=true` para validar tokens via o app `oidc`.

Isso valida a arquitetura do workspace:
- `oidc_login` no Nextcloud é a forma adequada para login via Authentik.
- Authentik é configurado como provider OIDC com as URLs de callback que o Nextcloud espera.

## Reativação completa do fluxo

Este repositório agora suporta a reativação completa do fluxo Nextcloud + Authentik + LTFS em dois passos:

1. Reativar a fita LTFS no NAS:
   - `scp scripts/nas_ltfs_nextcloud_reactivate.sh root@192.168.15.4:/tmp/`
   - `ssh root@192.168.15.4 bash /tmp/nas_ltfs_nextcloud_reactivate.sh`
   - Ou use `bash scripts/reactivate_nextcloud_lto_authentik.sh --nas-host 192.168.15.4` para orquestrar a reativação do NAS via SSH.
2. Reconfigurar o Nextcloud para Authentik:
   - `cd forks/rpa4all-nextcloud-authentik`
   - `set -a; source .env; set +a`
   - `python3 scripts/configure_authentik_nextcloud_oidc.py`
   - `bash scripts/bootstrap_nextcloud_oidc.sh`

### Ordem esperada

- Primeiro, restabeleça o LTFS e o bind mount em `/srv/nextcloud/external/LTO`.
- Depois, execute o bootstrap OIDC no Nextcloud para garantir que o provider Authentik esteja disponível e os apps necessários estejam habilitados.

## Pontos de expansão sugeridos

- Documentar claramente em `docs/ltfs-plan.md` ou `docs/nextcloud-authentik-flow.md` como o LTFS externo se conecta ao Nextcloud.
- Verificar se o script `nas_ltfs_nextcloud_reactivate.sh` está presente e ativado no NAS depois de cada reboot ou falha.
- Adicionar validação de `NEXTCLOUD_URL` e `NEXTCLOUD_BASE_PATH` no portal de contratos para garantir que os links de workspace sempre funcionem.
- Consolidar o fluxo de grupo do Authentik → Nextcloud Group Folders em um único script/documento de operação.
- Confirmar se o `oidc_login` app e o `groupfolders` app estão instalados automaticamente no bootstrap e se há rollback em caso de falha.

## Conclusão

O workspace já contém um fluxo Nextcloud robusto:
- autenticação via Authentik,
- provisioning de equipe e Group Folders,
- armazenamento externo via LTFS,
- portal de contratos ligado ao Nextcloud.

A pesquisa externa mostra o modelo oficial do Nextcloud OIDC ser compatível com esta implementação e reforça que o `oidc_login` plugin é o caminho certo para este caso.
