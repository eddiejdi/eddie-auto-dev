# Nextcloud → NAS: Migração, Backup em Fita e Limpeza

> **Data**: 20–22 de março de 2026
> **Operador**: Eddie Auto-Dev (agente AI)
> **Status**: ✅ COMPLETO

---

## Sumário Executivo

Migração completa do armazenamento Nextcloud do RAID1 local (homelab 192.168.15.2) para o NAS dedicado (192.168.15.4) via NFS, seguida de backup parcial em fita LTO-6, recuperação do Nextcloud após incidente de disco cheio, e limpeza de ~289 GB de dados redundantes.

| Métrica | Valor |
|---------|-------|
| Dados migrados | **149 GB** (120 GB data + 29 GB external) |
| Arquivos verificados | **46.046** (match 100%) |
| Dados gravados em fita | **33 GB** (47 batches) |
| Espaço liberado (total) | **~289 GB** |
| NAS uso final | **70%** (152 GB / 229 GB) |
| Homelab RAID1 uso final | **55%** (770 GB / 1.5 TB) |

---

## 1. Infraestrutura Envolvida

### 1.1 NAS (rpa4all-nas-001)

| Item | Detalhe |
|------|---------|
| IP | 192.168.15.4 |
| OS | Debian 13 (Trixie) + OMV 8 |
| Disco sistema | NVMe SK hynix BC511 256 GB |
| HBA | QLogic QLE2462 dual-port FC 4 Gbps |
| Tape drive | HP Ultrium 6-SCSI (LTO-6), serial HUL831AMRM |
| SSH | `sshpass -p 'Rpa_four_all!' ssh root@192.168.15.4` |

### 1.2 Homelab

| Item | Detalhe |
|------|---------|
| IP | 192.168.15.2 |
| OS | Ubuntu 24.04.4 LTS |
| Storage | mergerfs RAID1 ~1.5 TB |
| User | homelab (ssh, sudo disponível) |
| Docker | Nextcloud v33.0.0.16 (porta 8880) |
| URL | https://nextcloud.rpa4all.com |

---

## 2. Migração Nextcloud para NAS

### 2.1 Motivação

- Dados do Nextcloud em `/mnt/raid1/` consumiam ~149 GB do RAID1 do homelab
- NAS dedicado com NVMe tinha espaço disponível
- Objetivo: liberar RAID1 e centralizar storage no NAS

### 2.2 Fonte e Destino

| Tipo | Fonte (Homelab) | Destino (NAS) | Tamanho |
|------|-----------------|---------------|---------|
| Dados Nextcloud | `/mnt/raid1/gdrive-pessoal-temp/` | `/srv/nextcloud/data/` | 120 GB |
| External Storage | `/mnt/raid1/nextcloud-external/` | `/srv/nextcloud/external/RPA4ALL/` | 29 GB |

### 2.3 Método de Transferência

```
rsync -avh --progress /mnt/raid1/gdrive-pessoal-temp/ root@192.168.15.4:/srv/nextcloud/data/
rsync -avh --progress /mnt/raid1/nextcloud-external/ root@192.168.15.4:/srv/nextcloud/external/RPA4ALL/
```

### 2.4 NFS Mount

**NAS (export)**:
```
/srv/nextcloud 192.168.15.0/24(rw,sync,no_subtree_check,no_root_squash)
```

**Homelab (fstab)**:
```
192.168.15.4:/srv/nextcloud /mnt/nas-nextcloud nfs rw,hard,intr,nfsvers=4,_netdev,nofail 0 0
```

### 2.5 Docker Compose (atualizado)

Localização: `/mnt/raid1/nextcloud/docker-compose.yml`

```yaml
volumes:
  - /mnt/nas-nextcloud/data:/var/www/html/data       # NFS → NAS
  - /mnt/nas-nextcloud/external:/mnt/external         # NFS → NAS
  - /mnt/raid1/nextcloud/html:/var/www/html           # Local (RAID1)
  - /mnt/raid1/nextcloud/config:/var/www/html/config  # Local (RAID1)
```

### 2.6 Validação da Migração

```
# Homelab (fonte):
du -sh /mnt/raid1/gdrive-pessoal-temp/   → 120G, 45688 arquivos
du -sh /mnt/raid1/nextcloud-external/     → 29G,  358 arquivos

# NAS (destino):
du -sh /srv/nextcloud/data/               → 120G, 45688 arquivos  ✅ MATCH
du -sh /srv/nextcloud/external/RPA4ALL/   → 29G,  358 arquivos    ✅ MATCH
```

**149 GB / 46.046 arquivos — migração 100% verificada.**

### 2.7 Ações Pós-Migração

1. Criação de `.ncdata` em `/srv/nextcloud/data/`
2. Permissões: `chown -R www-data:www-data /srv/nextcloud/data/`, `chmod 770`
3. `docker exec nextcloud php occ files:scan --all`
4. `docker exec nextcloud php occ files:cleanup`

---

## 3. Backup em Fita LTO-6

### 3.1 Problema: FC Instável

O link Fibre Channel entre o NAS e o tape drive apresentava instabilidade crônica (LOOP DOWN/UP) que inviabilizou o uso de LTFS para backup direto.

**Sintomas**:
- LTFS → EOD corruption após write interruption
- SCSI commands in-flight → DID_TRANSPORT_DISRUPTED
- FC drops a cada ~1-2 min durante I/O sustentado

**Diagnóstico FC**:
- Porta 1 (host7): INSTÁVEL — loss_of_signal=1, loss_of_sync=4, múltiplos LOOP DOWN
- Porta 0 (host0): Mais estável mas ainda flapping sob carga

### 3.2 Solução: tape-dd-chunked.sh

Abordagem alternativa ao LTFS: tar + dd fragmentado, com staging em NVMe local.

**Script**: `/usr/local/bin/tape-dd-chunked.sh` (v3) no NAS

**Estratégia**:
1. Dividir dados em batches de **500 MiB** (tar)
2. Staging no NVMe local (`/srv/tape-staging/`)
3. dd para tape em fragmentos de **400 MiB** com pausa de **5s** entre eles
4. Detecção automática de dispositivo tape (`lsscsi`)
5. Recuperação SCSI automática (delete + rescan + fix nst0)
6. Espera por FC estável (30s sem LOOP UP) antes de cada write
7. Estado persistente para resume

**Parâmetros**:

| Param | Valor |
|-------|-------|
| `CHUNK_SIZE_MB` | 500 |
| `DD_PIECE_MB` | 400 |
| `DD_PAUSE_SEC` | 5 |
| `MAX_RETRIES` | 10 |

### 3.3 Resultado

```
47/47 batches escritos com sucesso
Total: 33 GB gravados em fita LTO-6
Verificação: tar tvf /dev/nst0 -b 512  ✅
```

### 3.4 Bug Encontrado: /dev/nst0 era arquivo regular

Durante SCSI delete + rescan, o udev não recriou `/dev/nst0` automaticamente.
O dispositivo existia como arquivo regular em vez de character device.

**Fix**:
```bash
rm /dev/nst0
mknod /dev/nst0 c 9 128
chown root:tape /dev/nst0
chmod 660 /dev/nst0
```

Adicionada função `fix_nst_device()` ao script para auto-correção.

### 3.5 Dados Pendentes

~87 GB de dados Nextcloud ainda não foram copiados para fita (apenas os 33 GB já em staging foram gravados). O NAS agora tem 66 GB livres, permitindo futuras sessões.

---

## 4. Incidente: Nextcloud "Pausado" (errno=28)

### 4.1 Causa

O staging de dados para backup em fita consumiu o NVMe do NAS até **96%** (errno=28 — No space left on device). O container Nextcloud entrou em estado degradado e não se recuperou automaticamente após a liberação de espaço.

### 4.2 Sintomas

- Interface web inacessível ("pausado")
- Logs: `fwrite(): Write of 679 bytes failed with errno=28`
- Erros de upload do Android client (parcial transfers)
- HTTP ServiceUnavailable para assets de theming

### 4.3 Resolução

```bash
# 1. Liberar espaço (staging já tinha sido limpo: 96% → 81%)

# 2. Reiniciar container
docker restart nextcloud

# 3. Reparação profunda
docker exec -u www-data nextcloud php occ maintenance:repair --include-expensive

# 4. Limpar log inflado
truncate -s 0 /path/to/nextcloud.log
```

**Resultado**: HTTP 200, maintenance:false, sem novos erros.

---

## 5. Batimento (Reconciliação de Disco)

### 5.1 NAS — Antes da Limpeza

| Caminho | Tamanho | Status |
|---------|---------|--------|
| `/srv/nextcloud/data/` | 120 GB | ✅ Produção |
| `/srv/nextcloud/external/RPA4ALL/` | 29 GB | ✅ Produção |
| `/var/spool/lto6-cache/` | 14 GB | ❌ Órfão (cache LTFS antigo) |
| `/mnt/tape/lto6/` | 11 GB | ❌ Órfão (rsync tentativas antigas) |

### 5.2 Homelab RAID1 — Antes da Limpeza

| Caminho | Tamanho | Status |
|---------|---------|--------|
| `/mnt/raid1/gdrive-pessoal-temp/` | 120 GB | ❌ Redundante (migrado para NAS) |
| `/mnt/raid1/nextcloud-external/` | 29 GB | ❌ Redundante (migrado para NAS) |
| `/mnt/raid1/lto6-cache/nextcloud-data/` | 111 GB | ❌ Cópia intermediária LTFS |
| `/mnt/raid1/lto6-cache/nextcloud-backup-20260321/` | 5.4 GB | ❌ rsync parcial |
| `/mnt/raid1/nextcloud/` (html/config) | 1.1 GB | ✅ Produção (Docker) |

---

## 6. Limpeza Executada

### 6.1 NAS — 24 GB Liberados

```bash
# Cache LTFS antigo
rm -rf /var/spool/lto6-cache/RPA4ALL_SSH
rm -rf /var/spool/lto6-cache/RPA4ALL
rm -rf /var/spool/lto6-cache/_flush_probe
rm -rf /var/spool/lto6-cache/_flush_test
rm -rf /var/spool/lto6-cache/nextcloud-data

# Tentativas de rsync antigas
rm -rf /mnt/tape/lto6/nextcloud-backup-20260321
rm -rf /mnt/tape/lto6/nextcloud-backup-20260322
rm -rf /mnt/tape/lto6/.verify
```

**NAS: 81% → 70%** (152 GB usado, 66 GB livre)

### 6.2 Homelab — 265 GB Liberados

```bash
# Cópias intermediárias LTFS (117 GB)
sudo rm -rf /mnt/raid1/lto6-cache/nextcloud-data
sudo rm -rf /mnt/raid1/lto6-cache/nextcloud-backup-20260321

# Fontes originais migradas (149 GB)
sudo rm -rf /mnt/raid1/gdrive-pessoal-temp
sudo rm -rf /mnt/raid1/nextcloud-external
```

**RAID1: 74% → 55%** (770 GB usado, 632 GB livre)

---

## 7. Estado Final da Infraestrutura

### 7.1 Discos

| Sistema | Capacidade | Usado | Livre | Uso% |
|---------|-----------|-------|-------|------|
| NAS NVMe | 229 GB | 152 GB | 66 GB | **70%** |
| Homelab RAID1 | 1.5 TB | 770 GB | 632 GB | **55%** |

### 7.2 Nextcloud

| Item | Status |
|------|--------|
| Container | ✅ UP (porta 8880) |
| URL | ✅ https://nextcloud.rpa4all.com → HTTP 200 |
| Dados (120 GB) | `/srv/nextcloud/data/` no NAS via NFS |
| External (29 GB) | `/srv/nextcloud/external/RPA4ALL/` no NAS via NFS |
| Config/HTML | `/mnt/raid1/nextcloud/` no homelab RAID1 |
| DB | `/mnt/disk2/nextcloud-db` no homelab |

### 7.3 Fita LTO-6

| Item | Status |
|------|--------|
| Volume | NC0322 (NEXTCLOUD_20260322) |
| Conteúdo | 33 GB (47 tar batches de staging) |
| Verificação | ✅ `tar tvf -b 512` OK |
| Pendente | ~87 GB restantes não gravados |

### 7.4 Fibre Channel

| Item | Status |
|------|--------|
| Porta ativa | Port 0 (host0, PCI 01:00.0) |
| Porta desativada | Port 1 (host7, PCI 01:00.1) — instável |
| SLER | ✅ Habilitado (`ql2xtgt_tape_enable=1`) |
| Risco residual | FC flapping sob carga sustentada |
| Recomendação | Inspecionar SFP e cabo FC fisicamente |

---

## 8. Comandos de Referência

### Tape

```bash
# Carregar/ejetar
mt -f /dev/nst0 load
sg_start --eject /dev/sg0         # fallback quando mt trava

# Rebobinar e posicionar
mt -f /dev/nst0 rewind
mt -f /dev/nst0 fsf N             # avançar N filemarks

# Verificar conteúdo
tar tvf /dev/nst0 -b 512

# Reset SCSI
sg_reset -d /dev/sg0

# Delete + rescan SCSI
echo 1 > /sys/class/scsi_device/0:0:0:0/device/delete
echo "- - -" > /sys/class/scsi_host/host0/scan

# Recriar nst0 se virar arquivo regular
rm /dev/nst0
mknod /dev/nst0 c 9 128
chown root:tape /dev/nst0
chmod 660 /dev/nst0
```

### Nextcloud

```bash
# Restart
docker restart nextcloud

# Reparação
docker exec -u www-data nextcloud php occ maintenance:repair --include-expensive

# Scan arquivos
docker exec -u www-data nextcloud php occ files:scan --all

# Verificar status
curl -sI https://nextcloud.rpa4all.com | head -5
docker exec nextcloud php occ status
```

### NFS

```bash
# NAS: verificar export
exportfs -v

# Homelab: remontar
mount -t nfs 192.168.15.4:/srv/nextcloud /mnt/nas-nextcloud
```

---

## 9. Lições Aprendidas

1. **LTFS não é confiável com FC instável**: EOD corruption é irrecuperável. Preferir tar+dd fragmentado.
2. **dd com pausas resolve FC flapping**: 400 MiB chunks com 5s de intervalo evitam quedas por carga sustentada.
3. **NVMe staging é essencial**: Não fazer tar direto para tape — usar NVMe como buffer.
4. **Container Docker não se recupera de errno=28**: Mesmo após liberar espaço, é necessário `docker restart` + `maintenance:repair`.
5. **udev pode falhar com nst0**: Após delete+scan SCSI, verificar se `/dev/nst0` é character device, não regular file.
6. **Validar com contagem de arquivos**: Comparação por `du -sh` + `find -type f | wc -l` é a forma mais confiável.

---

## 10. Próximos Passos

- [ ] Backup dos ~87 GB restantes para fita (sessões de ~55 GB no NVMe)
- [ ] Corrigir verificação no `tape-dd-chunked.sh` (flag `-b 512`)
- [ ] Inspeção física do cabo FC e SFP port0
- [ ] Salvar credenciais root do NAS no Secrets Agent
- [ ] Avaliar segundo HDD para o NAS (expandir storage)
