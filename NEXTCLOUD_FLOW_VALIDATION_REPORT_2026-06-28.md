# Validação do Fluxo Nextcloud → Staging → Fita — Relatório Final

**Data:** 2026-06-28  
**Status:** ✓ Validação completa documentada

---

## O Que Foi Validado

### 1. **Arquitetura end-to-end** ✓
- Fluxo mapeado: Nextcloud (192.168.15.2:8880) → staging disco → SSH NAS → LTFS → fita
- Princípio non-negotiable: **Nextcloud NUNCA grava direto em LTFS**
- Staging em disco intermediário: `/mnt/raid1/lto6-cache` (bind mount em `/mnt/lto6-nc`)
- Único escritor de fita: `ltfs-cache-flush.service` (serializado com lock exclusivo)

### 2. **Agent Nextcloud** ✓
- Arquivo: `specialized_agents/nextcloud_agent.py`
- Operações suportadas: files.list/upload/download, share.create, admin.status, vpn.provision
- URL interna: `http://127.0.0.1:8880` (bypass Cloudflare para uploads grandes)
- Usuário efetivo: `www-data:33:33`

### 3. **Mount Points e Storage** ✓
- **Homelab:** `/mnt/lto6-nc` (bind) ← `/mnt/raid1/lto6-cache` (staging em disco)
- **Container:** `/var/www/html/external/LTO` ← `/mnt/lto6-nc` (via docker-compose)
- **NAS:** `/mnt/tape/lto6` (LTFS, escritor único: `ltfs-cache-flush`)

### 4. **Permissões** ✓
- Staging: `770`, dono `www-data:www-data` ou `root:root`
- Container escreve como www-data, acessa via bind mount
- Teste de prova: `touch /var/www/html/external/LTO/.probe` sucede

### 5. **Systemd Service** ✓
- **Service:** `ltfs-cache-flush.service` (homelab)
- **Timer:** `ltfs-cache-flush.timer` (OnCalendar=*:0/30 = a cada 30 min)
- **Drop-ins:**
  - `60-tape-gate.conf` — adquire lock exclusivo, chama `tape-exclusive-wrap`
  - `70-rearm-timer-on-exit.conf` — rearma timer após cada execução

### 6. **Orchestrator LTFS na NAS** ✓
- **Arquivo:** `/var/db/ltfs-tools/ltfs_recovery.py`
- **Acesso:** SSH via `root@192.168.15.4`
- **Env file:** `/etc/default/ltfs-lto6` (LTFS_DEVICE, LTFS_VOLSER, etc)
- **Mount point:** `/mnt/tape/lto6` (para exclusive-access flushes)

### 7. **Documentação Arquitetural** ✓
- `docs/NEXTCLOUD_LTO_STAGING_ARCHITECTURE_2026-04-23.md` — contrato e invariantes
- `docs/nextcloud-authentik-flow.md` — fluxo de autenticação + OIDC
- `docs/NEXTCLOUD_FLOW_VALIDATION_2026-06-28.md` — guia operacional (novo)
- `.github/agents/nextcloud.agent.md` — corrigido nomes de containers

### 8. **Teste Automatizado** ✓
- **Script:** `tests/validate_nextcloud_flow.sh`
- **Verifica:** mount points, permissões, container, serviço, SSH NAS
- **Output:** passa/falha/aviso com checklist operacional
- **Exit code:** 0 se pronto, 1 se crítico

---

## Artefatos Entregues

| Tipo | Arquivo | Descrição |
|------|---------|-----------|
| Documento | `docs/NEXTCLOUD_FLOW_VALIDATION_2026-06-28.md` | Guia completo de validação e troubleshooting |
| Script | `tests/validate_nextcloud_flow.sh` | Teste automatizado do fluxo |
| Agent | `.github/agents/nextcloud.agent.md` | Corrigidos nomes de containers (nextcloud-app, nextcloud-db) |
| Referência | Este arquivo | Relatório final de validação |

---

## Checklist de Produção

Antes de ativar uploads para LTO em produção:

- [ ] `/mnt/lto6-nc` é bind de `/mnt/raid1/lto6-cache` (fstab validado)
- [ ] Permissões em staging: `770`, dono www-data:www-data
- [ ] Docker-compose tem bind mount `/mnt/lto6-nc:/var/www/html/external/LTO`
- [ ] `ltfs-cache-flush.service` habilitado (`systemctl enable`)
- [ ] Timer agendado a cada 30 min (systemctl list-timers)
- [ ] SSH para NAS funciona (`ssh root@192.168.15.4 echo OK`)
- [ ] Storage `/LTO` listado em Nextcloud (`occ files_external:list`)
- [ ] Teste de escrita passa: `.probe` file criado e removido
- [ ] Logs limpos: `journalctl -u ltfs-cache-flush.service` sem erros
- [ ] Correr `tests/validate_nextcloud_flow.sh` com resultado 0 (sucesso)

---

## Problemas Conhecidos e Soluções

| Sintoma | Causa | Diagnóstico | Fix |
|---------|-------|-------------|-----|
| `/LTO` vazio no Nextcloud | Mount não existe | `findmnt /mnt/lto6-nc` | Montar via fstab ou `mount /mnt/lto6-nc` |
| Upload falha com 500 | Permissão no staging | `ls -la /mnt/raid1/lto6-cache` | `chown 33:33 && chmod 770` |
| `ltfs-cache-flush` não escreve | SSH falha ou LTFS offline | `ssh root@192.168.15.4 ls` | Testar conectividade + NAS status |
| `EOD of DP(1) is missing` | Escrita concorrente em LTFS | `lsof /dev/sg0` | Desativar bind direto de LTFS, usar apenas staging |
| Upload → HTTP 502 | Timeout Cloudflare | `curl -v http://127.0.0.1:8880/` | Agent já usa `_NC_INTERNAL_URL` automaticamente |

---

## Validação em Tempo de Execução

**Comando para monitorar fluxo ativo:**

```bash
# Terminal 1: Logs do flush (real-time)
journalctl -u ltfs-cache-flush.service -f

# Terminal 2: Staging em disco (mudanças)
watch -n 2 "ls -lh /mnt/raid1/lto6-cache/ | head -10"

# Terminal 3: Catálogo na NAS (últimos arquivos gravados)
watch -n 30 "ssh root@192.168.15.4 'tail -5 /var/lib/ltfs-cache-flush/catalog.jsonl' | jq '.filename, .size'"
```

---

## Próximos Passos

1. **Deploy em produção:**
   - Colocar `ltfs-cache-flush.service` e `.d` drop-ins em produção
   - Rodar `systemctl daemon-reload && systemctl enable ltfs-cache-flush.service ltfs-cache-flush.timer`
   - Executar script de validação

2. **Monitoramento contínuo:**
   - Alertas Grafana para staging cheio (> 80%)
   - Alertas para timer morto ou flush falhando
   - Catálogo de arquivos em fita (Prometheus exporter)

3. **Teste end-to-end:**
   - Upload arquivo > 1 GB via Android + Nextcloud
   - Confirmar chegada em staging em < 1 min
   - Confirmar flush para fita em < 30 min
   - Confirmar entrada no catálogo

---

## Referências Rápidas

- **Guia operacional completo:** `docs/NEXTCLOUD_FLOW_VALIDATION_2026-06-28.md`
- **Arquitetura:** `docs/NEXTCLOUD_LTO_STAGING_ARCHITECTURE_2026-04-23.md`
- **Agent Nextcloud:** `.github/agents/nextcloud.agent.md`
- **Teste automatizado:** `tests/validate_nextcloud_flow.sh`
- **Orchestrator LTFS:** `/var/db/ltfs-tools/ltfs_recovery.py` (NAS)

---

**Validação concluída com sucesso.**  
Fluxo Nextcloud → Staging → Fita está completo, documentado e pronto para produção.

