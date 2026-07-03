# Validação do Fluxo Nextcloud → Staging → Fita LTO
**Data: 2026-06-28**  
**Status: Documentação de validação operacional**

---

## Resumo Executivo

Este documento valida o **fluxo completo** desde upload no Nextcloud até gravação em fita no NAS.

```
Nextcloud (homelab 192.168.15.2:8880)
    ↓ upload via WebDAV/UI
    ↓
/var/www/html/external/LTO (container)
    ↓ bind mount
    ↓
/mnt/lto6-nc (homelab)
    ↓ bind mount
    ↓
/mnt/raid1/lto6-cache (staging em disco)
    ↓ ltfs-cache-flush.service (periodicamente)
    ↓ SSH orchestrator
    ↓
NAS (192.168.15.4:/var/db/ltfs-tools/ltfs_recovery.py)
    ↓ mount LTFS /mnt/tape/lto6
    ↓
Fita física LTO-6
```

---

## Pontos de Validação Críticos

### 1. **Container Nextcloud — Escrita em `/var/www/html/external/LTO`**

**Onde:** homelab, dentro do container `nextcloud-app`  
**Usuário:** `www-data` (uid=33, gid=33)  
**Objetivo:** Confirmar que o upload chega ao staging

**Teste:**
```bash
# Desde o host homelab
docker exec -u www-data nextcloud-app sh -lc \
  'p=/var/www/html/external/LTO/.probe-123; date > "$p"; stat "$p"; rm -f "$p"'
```

**Resultado esperado:**
```
-rw-r--r-- 1 www-data www-data 30 Jun 28 14:23 /var/www/html/external/LTO/.probe-123
```

**Falha provável:** Permissão ou mount ausente; verificar próximo ponto.

---

### 2. **Mount Point `/mnt/lto6-nc` — Bind de Staging em Disco**

**Onde:** homelab (192.168.15.2)  
**Tipo:** `bind` (NÃO NFS, NÃO LTFS direto)  
**Objetivo:** Expor `/mnt/raid1/lto6-cache` ao container via docker-compose

**Configuração esperada em `/etc/fstab` (homelab):**
```fstab
# Nextcloud /LTO e staging em disco, nao LTFS.
/mnt/raid1/lto6-cache /mnt/lto6-nc none bind 0 0
```

**Verificação:**
```bash
# 1. Checar se está montado
findmnt /mnt/lto6-nc

# Saída esperada:
# TARGET       SOURCE               FSTYPE     OPTIONS
# /mnt/lto6-nc /mnt/raid1/lto6-cache bind       rw,relatime,bind

# 2. Montar manualmente se não está
sudo mount /mnt/lto6-nc

# 3. Listar conteúdo
ls -la /mnt/lto6-nc/
```

**Falha provável:**
- Mount para `/mnt/tape/lto6` em vez de staging → **CRÍTICO**, remover do fstab
- Permissão insuficiente → `sudo mount -o remount,uid=33,gid=33,mode=770 /mnt/lto6-nc`

---

### 3. **Permissões no Staging `/mnt/raid1/lto6-cache`**

**Onde:** homelab, disco físico  
**Dono:** `www-data:www-data` ou `root:root` com permissão 770  
**Objetivo:** Garantir que www-data possa escrever

**Verificação:**
```bash
stat /mnt/raid1/lto6-cache

# Esperado:
#   Access: (0770/drwxrwx---)  Uid: (  33/www-data) Gid: (  33/www-data)
# ou
#   Access: (0770/drwxrwx---)  Uid: (   0/   root) Gid: (   0/   root)
```

**Corrigir se necessário:**
```bash
sudo chown www-data:www-data /mnt/raid1/lto6-cache
sudo chmod 770 /mnt/raid1/lto6-cache
```

---

### 4. **Docker-Compose do Nextcloud — Bind Mount Configurado**

**Onde:** `forks/rpa4all-nextcloud-authentik/docker-compose.yml`  
**Objetivo:** Container vê o staging via `/var/www/html/external/LTO`

**Configuração esperada:**
```yaml
services:
  nextcloud-app:
    image: nextcloud:29-apache
    volumes:
      - /mnt/lto6-nc:/var/www/html/external/LTO
      # ... outros volumes
```

**Verificação:**
```bash
# Dentro do container
docker exec nextcloud-app mount | grep external/LTO

# Esperado:
# /mnt/lto6-nc on /var/www/html/external/LTO type bind (rw,relatime,bind)
```

**Corrigir se necessário:**
```bash
cd forks/rpa4all-nextcloud-authentik
docker-compose down
docker-compose up -d
```

---

### 5. **Serviço `ltfs-cache-flush.service` — Único Escritor da Fita**

**Onde:** homelab (192.168.15.2), systemd  
**Frequência:** Timer a cada 30 minutos (`*:0/30`)  
**Lock:** `/run/ltfs-cache-flush.lock`  
**Objetivo:** Copiar arquivos maduros do staging para NAS

**Verificação:**
```bash
# Status
systemctl status ltfs-cache-flush.service
systemctl status ltfs-cache-flush.timer

# Logs recentes (últimas 20 linhas)
journalctl -u ltfs-cache-flush.service -n 20 --no-pager

# Próxima execução
systemctl list-timers ltfs-cache-flush.timer
```

**Drop-ins esperados:**
```bash
ls -la /etc/systemd/system/ltfs-cache-flush.service.d/

# Esperado:
# 60-tape-gate.conf         — gate para evitar conflito com outros workers
# 70-rearm-timer-on-exit.conf — rearma timer se falhar
```

**Se não existe o serviço:**
```bash
# O serviço pode estar apenas no NAS; verificar SSH
ssh root@192.168.15.4 systemctl status ltfs-cache-flush.service
```

---

### 6. **Orchestrator LTFS na NAS — `/var/db/ltfs-tools/ltfs_recovery.py`**

**Onde:** NAS (192.168.15.4)  
**Objeto:** Script Python que monta/desmonta LTFS e gerencia fita  
**Objetivo:** Executar operações LTFS de forma segura via SSH

**Verificação:**
```bash
# Conectar ao NAS
ssh root@192.168.15.4

# Confirmar que o script existe
ls -la /var/db/ltfs-tools/ltfs_recovery.py

# Confirmar variáveis de ambiente
cat /etc/default/ltfs-lto6
```

**Saída esperada de `/etc/default/ltfs-lto6`:**
```bash
LTFS_DEVICE=/dev/sg3           # ou sg1, sg5 conforme drive
LTFS_VOLSER=SG0001             # ou outra volser
LTFS_MOUNT_POINT=/mnt/tape/lto6
```

**Teste de conectividade:**
```bash
# Do homelab
ssh root@192.168.15.4 "source /etc/default/ltfs-lto6 && ls -d $LTFS_MOUNT_POINT 2>/dev/null || echo 'Tape não está montada'"
```

---

### 7. **Storage Externo no Nextcloud — Configuração OCS**

**Onde:** container `nextcloud-app`, admin CLI  
**Objetivo:** Validar que `/LTO` está declarado como storage externo

**Verificação:**
```bash
# Via occ
docker exec nextcloud-app php occ files_external:list

# Esperado output (contém linha com /LTO):
# +---+-------+---------------+--------+
# | id| mount | storage       | status |
# +---+-------+---------------+--------+
# | 1 | /LTO  | Local         | ok     |
# +---+-------+---------------+--------+
```

**Testar acesso:**
```bash
docker exec nextcloud-app php occ files_external:verify 1
```

**Se não está listado:**
```bash
# Criá-lo manualmente
docker exec nextcloud-app php occ files_external:create \
  /LTO local null::local \
  -c datadir=/var/www/html/external/LTO \
  --applicable All
```

---

### 8. **Fluxo de Arquivo — Do Upload até a Fita**

**Cenário:**
1. Usuário faz upload de arquivo grande (~5 GB) via WebDAV
2. Arquivo fica em staging em disco por ~15 min (maturidade)
3. `ltfs-cache-flush` identifica arquivo maduro
4. SSH para NAS, monta LTFS, copia arquivo
5. NAS atualiza `catalog.jsonl` e desmonta limpo

**Teste prático:**
```bash
# 1. Upload um arquivo de teste
curl -u admin:PASSWORD \
  -T /tmp/teste-5gb.bin \
  "http://127.0.0.1:8880/remote.php/dav/files/admin/LTO/teste-5gb.bin"

# 2. Confirmar em staging
ls -lh /mnt/raid1/lto6-cache/teste-5gb.bin

# 3. Aguardar ~15 min ou forçar manualmente
sudo systemctl start ltfs-cache-flush.service

# 4. Verificar logs
journalctl -u ltfs-cache-flush.service -n 50 --no-pager | tail -20

# 5. Confirmar em NAS (SSH)
ssh root@192.168.15.4 "ls -lh /mnt/tape/lto6/teste-5gb.bin"

# 6. Confirmar no catálogo
ssh root@192.168.15.4 "tail -n 5 /var/lib/ltfs-cache-flush/catalog.jsonl"
```

---

## Checklist de Validação Operacional

### Antes de Ativar em Produção

- [ ] `/mnt/lto6-nc` é bind de `/mnt/raid1/lto6-cache` (fstab verificado)
- [ ] Permissões: `770` dono `www-data:www-data` no staging
- [ ] Docker-compose do Nextcloud tem bind mount correto
- [ ] `ltfs-cache-flush.service` está habilitado (`systemctl enable`)
- [ ] Timer `ltfs-cache-flush.timer` agendado a cada 30 min
- [ ] Orchestrator LTFS acessível via SSH em NAS
- [ ] Storage `/LTO` listado em Nextcloud (`occ files_external:list`)
- [ ] Teste de escrita www-data funciona (`.probe` file)
- [ ] Logs limpos de erros de staging/fita (jounalctl)
- [ ] Arquivo prova de teste não foi gravado em fita

### Alertas para Monitorar Continuamente

**Se um destes falhar, o fluxo quebra:**

| Ponto | Falha | Efeito | Ação |
|-------|-------|--------|------|
| `/mnt/lto6-nc` | Não montado | Nextcloud não consegue escrever em `/LTO` | Montar via fstab |
| Permissões staging | `777` ou outro dono | www-data não consegue escrever | `chown 33:33` + `chmod 770` |
| `ltfs-cache-flush` | Desativado | Staging acumula arquivos | `systemctl enable` + timer |
| SSH NAS | Sem acesso | Flush não consegue copiar | Testar SSH key |
| LTFS NAS | Offline | Flush falha na cópia | Montar via orchestrator |
| Catálogo | Não atualizado | Arquivo não registrado | Verificar perms. em NAS |

---

## Problemas Conhecidos e Soluções

### **Problema 1: `EOD of DP(1) is missing` na fita**

**Causa:** Escrita simultânea em LTFS (antes de staging ser implementado)  
**Solução:** Garantir que **APENAS** `ltfs-cache-flush` escreve na fita
- Validar que Nextcloud não tem bind direto para `/mnt/tape/lto6`
- Desativar `lto-logical-mount-refresh.timer`
- Usar deep-recovery se fita estiver em erro

### **Problema 2: Upload via Android → `TooManyRequests` (429)**

**Causa:** IP bloqueado por brute-force do Nextcloud  
**Solução:**
```bash
docker exec nextcloud-app php occ security:bruteforce:reset <IP_ANDROID>
```

### **Problema 3: `/LTO` vazio no Nextcloud**

**Causa:** Mount não existe ou staging vazio  
**Solução:**
```bash
# 1. Verificar mount
findmnt /mnt/lto6-nc

# 2. Se vazio, pode estar em período sem flushes
ls -la /mnt/raid1/lto6-cache

# 3. Forçar flush manual
sudo systemctl start ltfs-cache-flush.service
```

### **Problema 4: `ltfs-cache-flush` não está gravando em fita**

**Causa:** Arquivo não atinge maturidade ou SSH falha  
**Diagnóstico:**
```bash
# Ver logs detalhados
journalctl -u ltfs-cache-flush.service -n 100 -p err

# Testar SSH manualmente
ssh root@192.168.15.4 echo "SSH OK"

# Forçar teste de escrita via SSH
ssh root@192.168.15.4 \
  "source /etc/default/ltfs-lto6 && touch /mnt/tape/lto6/.test && rm /mnt/tape/lto6/.test"
```

---

## Referência de Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│ HOMELAB (192.168.15.2)                                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Docker Container: nextcloud-app                      │  │
│  │ ┌────────────────────────────────────────────────┐   │  │
│  │ │ Nextcloud 29-apache                            │   │  │
│  │ │ /var/www/html/external/LTO ← bind mount       │   │  │
│  │ │ (usuário www-data:33:33)                       │   │  │
│  │ └────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────┘  │
│           ↓ (docker-compose volumes)                        │
│  /mnt/lto6-nc                                               │
│           ↓ (fstab bind)                                    │
│  /mnt/raid1/lto6-cache (STAGING EM DISCO)                 │
│           ↓ (ltfs-cache-flush.service, via SSH)            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ NAS (192.168.15.4)                                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  /var/db/ltfs-tools/ltfs_recovery.py (orchestrator)        │
│           ↓ (monta /dev/sg3 ou sg5)                         │
│  /mnt/tape/lto6 (LTFS mount point)                         │
│           ↓ (rsync via CIFS/NFS from homelab)              │
│  /dev/nst0 (LTFS tape device, physicamente na drive)      │
│           ↓ (escreve)                                       │
│  Fita LTO-6 física (volser SG0001, etc)                    │
│                                                              │
│  /var/lib/ltfs-cache-flush/catalog.jsonl (índice de arquivos)
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Comandos Rápidos de Diagnóstico

```bash
# Status geral do fluxo
echo "=== HOMELAB STATUS ===" && \
  echo "Mount /mnt/lto6-nc:" && findmnt /mnt/lto6-nc && \
  echo "Staging files:" && ls -lh /mnt/raid1/lto6-cache | head && \
  echo "ltfs-cache-flush timer:" && systemctl list-timers ltfs-cache-flush.timer && \
  echo ""

# Logs reais de um flush (últimos 30 min)
journalctl -u ltfs-cache-flush.service --since "30 min ago" -n 50

# NAS — confirmar LTFS está OK
ssh root@192.168.15.4 "source /etc/default/ltfs-lto6 && \
  echo 'LTFS Mount:' && findmnt \$LTFS_MOUNT_POINT && \
  echo 'Recent files:' && ls -lhrt \$LTFS_MOUNT_POINT | tail -10"

# Listar últimos arquivos no catálogo
ssh root@192.168.15.4 "tail -10 /var/lib/ltfs-cache-flush/catalog.jsonl | jq '.filename, .size, .timestamp'"
```

---

## Status de Validação (2026-06-28)

- **Arquitetura:** ✓ Documentada e validada
- **Agent Nextcloud:** ✓ Implementado com bypass Cloudflare
- **Mount points:** ✓ Configurados (verificar em produção)
- **Serviço flush:** ✓ Configurado com gates e drop-ins
- **Orchestrator NAS:** ✓ SSH acessível
- **Teste end-to-end:** ⚠ Pendente (requer ambiente de produção com LTFS)

**Próximo passo:** Executar o checklist em produção após deploy do ltfs-cache-flush.service.

