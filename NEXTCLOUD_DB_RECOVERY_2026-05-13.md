# Nextcloud DB Recovery — 2026-05-13

## Contexto

Em 12/05/2026 às ~08:31, o processo de purge LTO (`homelab-purge-20260512_083120`) moveu
o diretório `nextcloud-db_local` para a fita LTO6. O diretório foi transferido **sem o
arquivo `ibdata1`** do MariaDB — apenas a estrutura vazia foi gravada na fita.

Resultado: o banco de dados do Nextcloud ficou com 0 tabelas, causando erro
`Table 'nextcloud.oc_appconfig' doesn't exist` em todas as requisições.

Adicionalmente, o container `nextcloud-app` estava configurado com bind local
(`/home/homelab/nextcloud/data_local`) em vez do volume NFS correto (`nc-nas-data`),
que aponta para `192.168.15.4:/srv/nextcloud/data`.

---

## Diagnóstico

| Sintoma | Causa |
|---------|-------|
| `Table 'nextcloud.oc_appconfig' doesn't exist` | ibdata1 movido para fita, DB vazio |
| `/var/www/html/data` com 5 pastas / 64 arquivos | Container montando `data_local` em vez do NFS |
| `Login failed: 'homelab-backup'` nos logs | Fresh install criou novo instanceid, hash da senha diferente |
| Botão "Login with Authentik" ausente | App `oidc_login` desabilitado após fresh install |

### Verificação da fita
```
/mnt/tape/lto6/homelab-purge-20260512_083120/nextcloud-db_local/
  mysql_upgrade_info   ← único arquivo presente (16 bytes)
  nextcloud/           ← diretório VAZIO
```
O `ibdata1` não foi gravado na fita — dados perdidos na origem, não recuperáveis da fita.

---

## Solução Executada

### 1. Recriar schema do banco

```bash
# Tornar config.php como não-instalado
sed -i "s/'installed' => true/'installed' => false/" /var/www/html/config/config.php
chown -R www-data:www-data /home/homelab/nextcloud/data_local/

# Instalar schema limpo
docker exec -u www-data nextcloud-app php /var/www/html/occ maintenance:install \
  --database mysql \
  --database-host nextcloud-db \
  --database-name nextcloud \
  --database-user nextcloud \
  --database-pass eddie_nextcloud_db_2026 \
  --admin-user eddie \
  --admin-pass eddie_nc_2026 \
  --data-dir /var/www/html/data
```

Resultado: 126 tabelas criadas.

### 2. Recriar container com volume NFS correto

O container estava com `/home/homelab/nextcloud/data_local` como data dir.
Recriado com o volume Docker NFS `nc-nas-data`:

```bash
docker rm -f nextcloud-app

docker run -d \
  --name nextcloud-app \
  --restart unless-stopped \
  --network nextcloud-net \
  -p 8880:80 \
  -v /home/homelab/nextcloud/html_local:/var/www/html \
  -v /mnt/raid1/nextcloud/config:/var/www/html/config \
  -v nc-nas-data:/var/www/html/data \
  -v nc-nas-external:/var/www/html/external \
  -v /mnt/lto6-nc:/var/www/html/external/LTO \
  -e MYSQL_HOST=nextcloud-db \
  -e MYSQL_DATABASE=nextcloud \
  -e MYSQL_USER=nextcloud \
  -e MYSQL_PASSWORD=eddie_nextcloud_db_2026 \
  -e REDIS_HOST=nextcloud-redis \
  -e REDIS_HOST_PASSWORD=eddie_redis_nc_2026 \
  -e NEXTCLOUD_TRUSTED_DOMAINS="192.168.15.2 homelab.local nextcloud.local nextcloud.rpa4all.com" \
  -e OVERWRITEPROTOCOL=https \
  -e OVERWRITEHOST=nextcloud.rpa4all.com \
  -e PHP_MEMORY_LIMIT=512M \
  -e PHP_UPLOAD_LIMIT=10G \
  nextcloud:latest
```

### 3. Restaurar config.php

O arquivo `/mnt/raid1/nextcloud/config/config.php` continha a configuração original
(instanceid, trusted_domains, OIDC, Redis). Foi restaurado via:

```bash
docker cp /tmp/nextcloud-config-recovered.php nextcloud-app:/var/www/html/config/config.php
docker exec nextcloud-app chown www-data:www-data /var/www/html/config/config.php
```

Configurações presentes no config.php restaurado:
```php
'instanceid' => 'oc304ec5e2b9',
'trusted_domains' => ['192.168.15.2', 'homelab.local', 'nextcloud.local', 'nextcloud.rpa4all.com'],
'oidc_login_provider_url' => 'https://auth.rpa4all.com/application/o/nextcloud/',
'oidc_login_client_id' => 'authentik-nextcloud',
'oidc_login_client_secret' => 'nextcloud-sso-secret-2026',
'oidc_login_scope' => 'openid profile email groups',
'oidc_login_password_authentication' => true,
'redis' => ['host' => 'nextcloud-redis', 'password' => 'eddie_redis_nc_2026'],
```

### 4. Recriar usuários

```bash
# eddie (admin — já criado pelo install)
docker exec -e OC_PASS="eddie_nc_2026" -u www-data nextcloud-app \
  php occ user:resetpassword --password-from-env eddie

# edenilson.paschoa@rpa4all.com
docker exec -e OC_PASS="eddie_nc_2026" -u www-data nextcloud-app \
  php occ user:add --password-from-env --display-name="Edenilson Paschoa" \
  --group="admin" "edenilson.paschoa@rpa4all.com"

# antonio.carneiro@rpa4all.com
docker exec -e OC_PASS="eddie_nc_2026" -u www-data nextcloud-app \
  php occ user:add --password-from-env --display-name="Antonio Carneiro" \
  "antonio.carneiro@rpa4all.com"

# homelab-backup (usado pelo rclone)
docker exec -e OC_PASS="eddie_nc_2026" -u www-data nextcloud-app \
  php occ user:add --password-from-env --display-name="Homelab Backup" \
  "homelab-backup"
```

### 5. Indexar arquivos (files:scan)

```bash
# Flush Redis para limpar locks stale
docker exec nextcloud-redis redis-cli -a eddie_redis_nc_2026 --no-auth-warning FLUSHALL

# Scan completo
docker exec -u www-data nextcloud-app php occ files:scan --all
```

Resultado: **18.430 pastas / 73.688 arquivos / 0 erros / 25min 39s**

### 6. Restaurar acesso rclone (homelab-backup)

O rclone em `/etc/rclone/nextcloud-backup.conf` usava senha obfuscada.
Revelada e sincronizada com o novo usuário:

```bash
RCLONE_PASS=$(rclone reveal "Up0H39lBC7ltbBIVyanrVb-lL4HNnbojSWtphrNExaeivKC4VLCbX-LuIzJPQuQ")
# Resultado: jFHOnCay7o7BIt5CTBlSJbGHYRTtd78

docker exec -e OC_PASS="$RCLONE_PASS" -u www-data nextcloud-app \
  php occ user:resetpassword --password-from-env homelab-backup

# Limpar bruteforce ban (172.21.0.1 estava banado por logins falhos)
docker exec -u www-data nextcloud-app php occ security:bruteforce:reset 172.21.0.1

# Teste: HTTP 200
curl -s -o /dev/null -w "%{http_code}" \
  -u "homelab-backup:$RCLONE_PASS" \
  http://localhost:8880/remote.php/dav/files/homelab-backup/
# → 200
```

### 7. Restaurar login Authentik (OIDC)

O app `oidc_login` foi desabilitado automaticamente durante o fresh install.

```bash
docker exec -u www-data nextcloud-app php occ app:enable oidc_login

# Adicionar configurações do botão
docker exec -u www-data nextcloud-app php occ config:system:set \
  oidc_login_button_text --value="Login with Authentik"
docker exec -u www-data nextcloud-app php occ config:system:set \
  oidc_login_hide_password_form --value=false --type=boolean
docker exec -u www-data nextcloud-app php occ config:system:set \
  oidc_login_auto_redirect --value=false --type=boolean
docker exec -u www-data nextcloud-app php occ config:system:set \
  oidc_login_redir_fallback --value=true --type=boolean
```

Confirmado no HTML da página de login:
```json
[{"name":"Login with Authentik","href":"/apps/oidc_login/oidc","class":"oidc-button"}]
```

---

## Estado Final

| Item | Valor |
|------|-------|
| HTTP status | 200 OK |
| installed | true |
| version | 33.0.0 |
| maintenance | false |
| Tabelas no banco | 126 |
| Pastas indexadas | 18.430 |
| Arquivos indexados | 73.688 |
| rclone WebDAV | HTTP 200 ✓ |
| Login Authentik | Botão presente ✓ |

### Containers UP

| Container | Status |
|-----------|--------|
| nextcloud-app | Up (nc-nas-data NFS) |
| nextcloud-db | Up |
| nextcloud-redis | Up |

### Mounts do container

| Tipo | Origem | Destino |
|------|--------|---------|
| bind | `/home/homelab/nextcloud/html_local` | `/var/www/html` |
| bind | `/mnt/raid1/nextcloud/config` | `/var/www/html/config` |
| volume NFS | `nc-nas-data` → `192.168.15.4:/srv/nextcloud/data` | `/var/www/html/data` |
| volume NFS | `nc-nas-external` | `/var/www/html/external` |
| bind | `/mnt/lto6-nc` | `/var/www/html/external/LTO` |

---

## Prevenção

### Problema raiz no processo de purge

O script de purge LTO move `nextcloud-db_local` para a fita sem fazer dump SQL primeiro.
O MariaDB usa `ibdata1` como tablespace compartilhado — mover apenas os arquivos `.frm`/`.ibd`
sem o `ibdata1` resulta em banco inacessível.

### Recomendações

1. **Antes de qualquer purge**, criar dump SQL:
   ```bash
   docker exec nextcloud-db mysqldump -u root -p<PASS> --all-databases \
     > /mnt/raid1/nextcloud-db-backup/nextcloud-$(date +%Y%m%d).sql
   ```

2. **O selfheal** (`nextcloud_selfheal_exporter.py`) já usa `nc-nas-data` corretamente
   na função `recreate_app()` — o container não deve mais ser recriado com bind local.

3. **O host mount** `/mnt/nas-nextcloud/data` não está montado, mas o volume Docker
   `nc-nas-data` funciona diretamente via NFS — isso é o comportamento esperado.
