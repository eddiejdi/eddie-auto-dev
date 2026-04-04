Centralização de perfis de usuário
=================================

Objetivo
--------
Armazenar os perfis de aplicações (home/config) dos usuários num servidor central
e montá-los automaticamente no login, independente do sistema operativo cliente.

Arquitetura recomendada
-----------------------
- Linux: NFSv4 + autofs + SSSD + `pam_mkhomedir` (montagem por demanda)
- Windows: Samba (SMB) com `homes` / Folder Redirection ou Nextcloud sync
- macOS: SMB mount ou Nextcloud sync

Pré-requisitos
--------------
- Authentik com LDAP Outpost configurado e acessível (ex: ldap://192.168.15.2)
- Servidor de ficheiros (homelab) com espaço em /srv/home ou similar
- DNS ou /etc/hosts para resolução entre clientes e servidor
- Backups e políticas de segurança definidas

Fluxo de alto nível
-------------------
1. Server: exportar /srv/home via NFS (ou Samba) e garantir permissões.
2. Authentik: expor contas via LDAP (Outpost) para que SSSD possa consultar.
3. Client (Linux): configurar SSSD para identidade/auth, configurar autofs
   para montar /home/<user> automaticamente e habilitar `pam_mkhomedir`.
4. Windows/macOS: mapear para SMB ou usar cliente Nextcloud para perfis de
   aplicações que suportam sincronização.

Segurança e recomendações
-------------------------
- Use TLS para LDAP quando possível (LDAPS/StartTLS) ou restrinja rede.
- Prefira `root_squash` no NFS para reduzir riscos, ajuste conforme necessário.
- Monitore logs (`/var/log/auth.log`, `journalctl -u sssd`) e espaço em disco.
- Teste em um cliente antes de rollout global.

Conteúdo deste diretório
------------------------
- `server-setup-nfs.sh` : script template para configurar NFS no servidor
- `client-setup.sh`     : script template para configurar cliente Linux
- `sssd.conf.template`  : template de `sssd.conf` para uso com Authentik LDAP
- `authentik-ldap.md`   : instruções rápidas para configurar LDAP Outpost
- `check-client.sh`     : checagens rápidas pós-configuração

Próximos passos
---------------
1. Revisar templates e ajustar variáveis (LDAP bind DN, base DN, IPs).
2. Executar `server-setup-nfs.sh` no homelab (com sudo), validar `showmount -e`.
3. Executar `client-setup.sh` em um cliente teste, validar login e montagem.

Se desejar, aplico as mudanças ao servidor homelab (192.168.15.2) com seus
credenciais, ou forneço os comandos para que execute manualmente.
