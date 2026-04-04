Authentik - configuração rápida do LDAP Outpost
===============================================

Resumo
------
O Authentik pode expor contas via um LDAP Outpost (LDAP/LDAPS) que permite
que SSSD/clients procurem identidades e façam autenticação via LDAP.

Passos (resumo)
----------------
1. No Authentik Admin → Outposts → Add Outpost → escolha LDAP Outpost.
2. Configure `Base DN` (ex: `dc=rpa4all,dc=com`) e as `Bind Credentials` se
   necessário (usuário de bind com permissão de leitura).
3. Ajuste o `Host` para o IP/hostname do container/host (ex: 192.168.15.2).
4. Habilite TLS/LDAPS se tiver certificado válido (recomendado).
5. Anote `ldap URI` e `base DN` para usar nos templates `sssd.conf`.

Exemplo minimal
---------------
- ldap URI: ldap://192.168.15.2:389
- base DN: dc=rpa4all,dc=com
- bind DN: cn=binduser,dc=rpa4all,dc=com

Notas
-----
- Teste com `ldapsearch -x -H ldap://192.168.15.2 -b "dc=rpa4all,dc=com"`.
- Se usar LDAPS (636), certifique-se de configurar `ldap_tls_reqcert` no SSSD.
