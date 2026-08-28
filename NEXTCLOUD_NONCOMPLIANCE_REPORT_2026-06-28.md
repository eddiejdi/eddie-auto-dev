# ⚠️ RELATÓRIO DE NÃO-CONFORMIDADE CRÍTICA
## Fluxo Nextcloud → Staging → Fita LTO

**Data:** 2026-06-28 23:37 UTC-3  
**Status:** 🔴 **BLOQUEANTE — Não conforme com arquitetura**  
**Severidade:** CRÍTICA

---

## 1. PROBLEMA IDENTIFICADO

### Mount Point Incorreto em Produção

**Estado Atual (❌ NÃO CONFORME):**
```
SOURCE:  192.168.15.4:/mnt/tank/pretape/lto6-cache  (NFS do NAS)
TARGET:  /mnt/lto6-nc
FSTYPE:  nfs
```

**Estado Esperado (✓ CONFORME):**
```
SOURCE:  /mnt/raid1/lto6-cache  (disco local do homelab)
TARGET:  /mnt/lto6-nc
FSTYPE:  bind
```

### Violação de Arquitetura

| Requisito | Especificado em | Estado Atual | Conformidade |
|-----------|-----------------|-------------|---|
| Staging em disco LOCAL | NEXTCLOUD_LTO_STAGING_ARCHITECTURE_2026-04-23 | NFS (remoto) | ❌ |
| Sem latência de rede | Contrato 2026-04-23 | ~1-5ms NFS | ❌ |
| Sem bloqueio por NAS | Contrato 2026-04-23 | Bloqueado se NAS cai | ❌ |

---

## 2. RAIZ-CAUSA

### fstab Histórico (Múltiplas Tentativas)

```bash
# /etc/fstab atual no homelab:

# [ltfs-fix-2026-04-22] (DESCONTINUADO)
//192.168.15.4/LTO6 /mnt/lto6-nc cifs ...

# [ltfs-fix-2026-04-22] (DESCONTINUADO)
/mnt/nextcloud-nas/external/LTO /mnt/lto6-nc none bind ...

# disabled by codex-lto-staging-2026-04-23 (DESATIVADO MAS NÃO REMOVIDO)
192.168.15.4:/mnt/tape/lto6 /mnt/lto6-nc nfs4 ... (comentado)

# ✓ ATIVO ATUALMENTE:
/mnt/pretape/lto6-cache /mnt/lto6-nc none bind 0 0
```

### Por Que Está Errado

O fstab diz bind de `/mnt/pretape/lto6-cache`, mas:

```bash
# /mnt/pretape é mount NFS:
/mnt/pretape  →  192.168.15.4:/mnt/tank/pretape/lto6-cache (nfs)

# Logo:
/mnt/pretape/lto6-cache/  →  NFS remoto
/mnt/lto6-nc              →  bind de NFS remoto
```

**Conclusão:** O "disco local" é na verdade um bind de NFS.

---

## 3. IMPACTO OPERACIONAL

### Risco Imediato

| Cenário | Impacto | Severidade |
|---------|---------|-----------|
| **NAS offline** | Nextcloud não consegue escrever em `/LTO` | 🔴 CRÍTICO |
| **Latência NFS** | Uploads lentos, timeouts Docker | 🔴 CRÍTICO |
| **Flush concorrente com backup** | Conflito de I/O, corrupted files | 🟠 ALTO |
| **NAS perda de poder** | Fita em estado incompleto | 🔴 CRÍTICO |

### Incidentes Conhecidos (2026-04-23)

Este foi exatamente o padrão que causou:
- ❌ `EOD of DP(1) is missing`
- ❌ `Medium revalidation failed`

---

## 4. AÇÃO IMEDIATA NECESSÁRIA

### Passo 1: Verificar Disco Local

```bash
# SSH homelab
ssh homelab@192.168.15.2

# Listar discos locais
lsblk | grep -E "raid|sda|sdb|nvme"

# Confirmar /mnt/raid1 existe
df -h /mnt/raid1

# Status do RAID
cat /proc/mdstat
```

**Resultado esperado:**
```
/dev/md0 ou /dev/md1 montado em /mnt/raid1
Espaço disponível: >= 100 GB
```

### Passo 2: Preparar Staging Local

```bash
# 1. Criar diretório se não existir
sudo mkdir -p /mnt/raid1/lto6-cache

# 2. Definir permissões
sudo chown 33:33 /mnt/raid1/lto6-cache
sudo chmod 770 /mnt/raid1/lto6-cache

# 3. Validar
stat /mnt/raid1/lto6-cache
# Esperado: Uid: (  33/www-data) Gid: (  33/www-data)  Access: (0770/drwxrwx---)
```

### Passo 3: Atualizar fstab

```bash
# BACKUP do fstab antigo
sudo cp /etc/fstab /etc/fstab.bak.2026-06-28

# Editar fstab e encontrar/remover linhas incorretas:
sudo nano /etc/fstab

# REMOVER COMPLETAMENTE:
# ❌ //192.168.15.4/LTO6 /mnt/lto6-nc cifs ...
# ❌ /mnt/nextcloud-nas/external/LTO /mnt/lto6-nc none bind ...
# ❌ 192.168.15.4:/mnt/tape/lto6 /mnt/lto6-nc nfs4 ...
# ❌ /mnt/pretape/lto6-cache /mnt/lto6-nc none bind 0 0

# ADICIONAR:
# ✓ Nextcloud /LTO é staging em disco, não LTFS.
/mnt/raid1/lto6-cache /mnt/lto6-nc none bind 0 0
```

### Passo 4: Remontar

```bash
# 1. Desmontar atual
sudo umount /mnt/lto6-nc

# 2. Remontar novo
sudo mount /mnt/lto6-nc

# 3. Validar
findmnt /mnt/lto6-nc
# Esperado:
# TARGET       SOURCE               FSTYPE OPTIONS
# /mnt/lto6-nc /mnt/raid1/lto6-cache bind   rw,relatime,bind
```

### Passo 5: Validar em Container

```bash
# SSH homelab
ssh homelab@192.168.15.2

# Reiniciar container (para remontar bind)
docker-compose -f /home/homelab/forks/rpa4all-nextcloud-authentik/docker-compose.yml restart nextcloud-app

# Testar escrita
docker exec -u www-data nextcloud-app sh -c 'p=/var/www/html/external/LTO/.probe; date > "$p" && stat "$p" && rm "$p"'
# Esperado: sucesso sem erro
```

### Passo 6: Confirmar Conforme

```bash
# Rodar validação
/workspace/eddie-auto-dev/tests/validate_nextcloud_flow.sh

# Esperado: exit 0 (sucesso)
```

---

## 5. CHECKLIST DE CORREÇÃO

- [ ] Backup fstab realizado: `/etc/fstab.bak.2026-06-28`
- [ ] Disco local `/mnt/raid1` confirmado (>= 100 GB)
- [ ] Staging `/mnt/raid1/lto6-cache` criado com perms 770
- [ ] fstab atualizado com bind correto
- [ ] `/mnt/lto6-nc` desmontado e remontado
- [ ] Docker-compose nextcloud-app reiniciado
- [ ] Teste de escrita www-data passou
- [ ] Validação automática passou (exit 0)
- [ ] SSH NAS ainda acessível
- [ ] ltfs-cache-flush.service não está afetado

---

## 6. DOCUMENTAÇÃO CORRIGIDA

Após correção, os seguintes documentos permanecerão válidos:

| Documento | Ação | Status |
|-----------|------|--------|
| `docs/NEXTCLOUD_FLOW_VALIDATION_2026-06-28.md` | Nenhuma (correto) | ✓ |
| `tests/validate_nextcloud_flow.sh` | Nenhuma (correto) | ✓ |
| `.github/agents/nextcloud.agent.md` | ✓ Já corrigido | ✓ |
| `NEXTCLOUD_LTO_PRODUCTION_VALIDATION_REPORT.md` | ⚠ Desatualizar com findings | Pendente |

---

## 7. CRONOGRAMA DE CORREÇÃO

| Etapa | Tempo | Risco |
|-------|-------|-------|
| Backup fstab | < 1 min | Baixo |
| Desmontar NFS | < 1 min | **Médio** (Nextcloud pausará) |
| Remontar bind disco | < 1 min | Baixo |
| Reiniciar container | 30-60 s | Médio (downtime) |
| Validação | < 2 min | Baixo |
| **Total** | **~5 min** | **Aceitável em off-peak** |

**Recomendação:** Executar fora de horário de uso (noite/madrugada).

---

## 8. EVIDÊNCIA COLETADA

### Mount Point Atual (Não Conforme)

```bash
SOURCE:                                    TARGET       FSTYPE OPTIONS
192.168.15.4:/mnt/tank/pretape/lto6-cache /mnt/lto6-nc nfs    rw,relatime,vers=3,rsize=1048576,wsize=1048576,namlen=255,hard,proto=tcp,timeo=600,retrans=2,sec=sys,mountaddr=192.168.15.4,mountvers=3,mountport=58851,mountproto=tcp,local_lock=none,addr=192.168.15.4
```

### fstab Atual (Histórico de Erros)

```bash
# [ltfs-fix-2026-04-22] //192.168.15.4/LTO6 /mnt/lto6-nc cifs ...
# [ltfs-fix-2026-04-22] /mnt/nextcloud-nas/external/LTO /mnt/lto6-nc none bind 0 0
# disabled by codex-lto-staging-2026-04-23: 192.168.15.4:/mnt/tape/lto6 /mnt/lto6-nc nfs4 ...
/mnt/pretape/lto6-cache /mnt/lto6-nc none bind 0 0
```

### Disco Local Confirmado

```bash
✓ /mnt/raid1 existe
✓ /mnt/raid1/lto6-cache/backups/ existe (com conteúdo)
✓ Permissões precisam ser corrigidas
```

---

## 9. STATUS PÓS-CORREÇÃO

Após aplicar as ações acima:

- ✓ Mount `/mnt/lto6-nc` apontará para disco LOCAL
- ✓ Zero latência de rede
- ✓ Upload Nextcloud em µs, não ms
- ✓ Staging protegido de falha NAS
- ✓ ltfs-cache-flush.service não afetado (usa SSH)
- ✓ Conformidade total com arquitetura 2026-04-23

---

## 10. ASSINATURA

**Validação realizada:** 2026-06-28 23:37 UTC-3  
**Encontrado por:** Claude Code / Produção Validation  
**Severidade:** CRÍTICA  
**Status:** ⚠️ **Pendente execução de correção**

---

## Próximos Passos

1. **Imediato:** Confirmar disponibilidade de janela de manutenção
2. **Antes:** Comunicar downtime de 5 min do Nextcloud
3. **Executar:** Passos 1-6 em sequência
4. **Pós:** Rerun de `validate_nextcloud_flow.sh` com exit 0

**Pronto para executar correção?**

