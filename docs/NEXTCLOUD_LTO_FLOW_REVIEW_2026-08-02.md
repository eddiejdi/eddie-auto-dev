# Revisão do Fluxo Nextcloud → Staging → Fita LTO

**Data:** 2026-08-02  
**Baseado em:** Código em `specialized_agents/nextcloud_agent.py`, `tools/lto6-drain-backups`, `tools/ltfs_checkpoint_writer.py`, `tools/ltfs_recovery.py`, `systemd/*`, `tests/validate_nextcloud_flow.sh`, docs de arquitetura e incidentes.

---

## Resumo da Arquitetura Atual

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FLUXO COMPLETO                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────────┐                │
│  │ Nextcloud│────▶│ Staging Disk │────▶│   LTFS Tape      │                │
│  │  (LTO)   │     │ /mnt/raid1/  │     │   (NAS)          │                │
│  │  Users   │     │ lto6-cache   │     │                  │                │
│  └──────────┘     └──────┬───────┘     └────────┬─────────┘                │
│                          │                      │                          │
│                   bind mount                  LTFS                         │
│                   /mnt/lto6-nc                mount                        │
│                          │                      │                          │
│                   ┌──────▼───────┐     ┌────────▼────────┐                 │
│                   │ Container NC │     │  ltfs-lto6.svc  │                 │
│                   │ /var/www/    │     │  /mnt/tape/lto6 │                 │
│                   │ html/external│     │                 │                 │
│                   │ /LTO         │     │  Cache Flush    │                 │
│                   └──────────────┘     │  Worker         │                 │
│                                        └────────┬────────┘                 │
│                                                 │                          │
│                                        ┌────────▼────────┐                 │
│                                        │ CIFS / SMB      │                 │
│                                        │ /mnt/lto6-smb-  │                 │
│                                        │ proof           │                 │
│                                        └────────┬────────┘                 │
│                                                 │                          │
│                    ┌────────────────────────────┼────────────────────┐    │
│                    │                            │                    │    │
│            ┌───────▼────────┐          ┌────────▼────────┐   ┌────────▼──┐ │
│            │ lto6-drain-    │          │ ltfs_checkpoint_│   │tape-log-  │ │
│            │ backups        │          │ writer          │   │spool-drain│ │
│            │ (snapshots)    │          │ (checkpoint/    │   │(logs)     │ │
│            └────────────────┘          │ recovery)       │   └───────────┘ │
│                                        └─────────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Invariantes Críticas (do `NEXTCLOUD_LTO_STAGING_ARCHITECTURE_2026-04-23.md`)

1. **Nextcloud NUNCA grava direto na LTFS** — `/LTO` é staging em disco
2. **Staging:** `/mnt/raid1/lto6-cache` → bind mount `/mnt/lto6-nc` → container `/var/www/html/external/LTO`
3. **Único escritor de fita:** `ltfs-cache-flush.service` (serializado por lock `/run/ltfs-cache-flush.lock`)
4. **Janelas controladas:** mount → copy → sync → verify → catalog → unmount limpo
5. **Proibido:** bind-mount LTFS em `/srv/nextcloud/external/LTO`, `/home/homelab/nextcloud/external_local/LTO` ou home de usuários

---

## G19 — Boundary entre os dois pipelines de fita (documentado)

Existem **dois** pipelines independentes escrevendo na fita LTO, com semânticas
diferentes. **Não unificar** — manter separados, com boundary explícita:

| | Pipeline A: `ltfs-cache-flush` | Pipeline B: `lto6-drain-backups` |
|---|---|---|
| **O quê** | Dados do staging Nextcloud (`/mnt/raid1/lto6-cache`) | Snapshots de backup (rotinas de backup do homelab) |
| **Trigger** | Timer `ltfs-cache-flush.timer` (30min) | Service/agendamento de snapshot |
| **Lock** | `/run/ltfs-cache-flush.lock` + lock global `tape-exclusive-wrap` | Lock global `tape-exclusive-wrap` |
| **Destino** | `//192.168.15.4/LTO6_CACHE` (LTFS `lto6-cache`) | `//192.168.15.4/LTO6_SG1` (LTFS `sg1`) |
| **Verificação** | SHA256 + catalog.jsonl | rsync + checkpoint writer |
| **Consumidor** | Usuários Nextcloud via `/LTO` | Processos de backup (não-user-facing) |

**Regras de boundary (não violar):**
1. Pipeline A só lê staging Nextcloud; Pipeline B só lê snapshots — nunca um lê do outro.
2. Ambos respeitam o **lock global de fita** (`/run/lock/tape-global.lock` via `tape-exclusive-wrap`); a fita é o recurso compartilhado serializado.
3. Rotação de fita (G16) para **ambos** — um fluxo nunca rota a fita do outro sem o orchestrator `ltfs_recovery.py`.
4. Cada pipeline tem métricas e journal próprios; `ltfs_catalog_verify` valida só o catálogo do Pipeline A.
5. Se um dia for necessário unificar, primeiro documentar o ganho real — hoje a separação protege dados de usuário (Pipeline A) de rotinas internas (Pipeline B).

---

## Gaps Encontrados

### 🔴 Críticos (Podem causar perda de dados ou falha silenciosa)

| # | Gap | Impacto | Evidência |
|---|-----|---------|-----------|
| **G1** | **`ltfs-cache-flush` binary/script ausente no repo** | O worker principal de flush não está versionado; impossível auditar lógica de seleção de arquivos, retry, verificação SHA256 | Service aponta para `/usr/local/bin/ltfs-cache-flush` e `/usr/local/sbin/tape-exclusive-wrap` — não existem em `tools/`, `deploy/`, nem `scripts/` |
| **G2** | **Conflito de writers na fita** | `ltfs-cache-flush`, `lto6-drain-backups`, `ltfs_checkpoint_writer` todos escrevem na mesma fita via CIFS/LTFS; sem coordenação explícita além de lock local | `ltfs-cache-flush` usa lock `/run/ltfs-cache-flush.lock`; `lto6-drain-backups` usa `ConditionPathIsMountPoint` + guard CIFS; `ltfs_checkpoint_writer` usa SSH para parar/iniciar LTFS na NAS — **não há lock global compartilhado** |
| **G3** | **Sem monitoramento de espaço em staging** | Se `/mnt/raid1/lto6-cache` encher, uploads Nextcloud falham silenciosamente (HTTP 507) sem alerta | Validation script checa mount e write, mas **não checa `df /mnt/raid1/lto6-cache`** |
| **G4** | **Sem validação de integridade do catálogo pós-flush** | `catalog.jsonl` e `placements.json` podem corromper sem detecção até recovery | Architecture doc menciona validar catálogo, mas **não há job automático de verificação** |
| **G5** | **`tape-log-spool-drain` binary ausente** | Logs do pipeline Nextcloud→tape não são drenados; journal enche disco | Service referencia `/usr/local/sbin/tape-log-spool-drain` — não existe no repo |

---

### 🟡 Altos (Risco operacional, degradação silenciosa)

| # | Gap | Impacto | Evidência |
|---|-----|---------|-----------|
| **G6** | **Timer `ltfs-cache-flush.timer` não versionado** | Architecture doc exige `OnCalendar=*:0/30` + `AccuracySec=1min`; sem o arquivo não dá para confirmar | Documentado em `NEXTCLOUD_LTO_STAGING_ARCHITECTURE_2026-04-23.md:72` mas arquivo não encontrado |
| **G7** | **Cleanup de staging não definido** | Arquivos flushados ficam no staging indefinidamente → disco enche | Não há policy de retenção, `tmpwatch`, ou step no flush worker que remove arquivos confirmados |
| **G8** | **Race: Nextcloud escreve enquanto flush lê** | Flush pode pegar arquivo "em escrita" (parcial) se não checar estabilidade (`MIN_STABLE_SECONDS`) | `ltfs-cache-flush` tem flags `--min-age-seconds` e `--min-stable-seconds` mas **valor real não versionado** (drop-in só passa vars) |
| **G9** | **Self-heal CIFS pode matar flush ativo** | `lto6-smb-proof-selfheal.sh` faz `pkill -9 rsync` e `systemctl restart mnt-lto6-smb-proof.mount` durante drain | Script em `tools/selfheal/lto6-smb-proof-selfheal.sh:24-26` — **não checa se `lto6-drain-backups` ou `ltfs_checkpoint_writer` estão rodando** |
| **G10** | **Sem teste end-to-end automatizado** | `validate_nextcloud_flow.sh` testa componentes isolados; não testa fluxo completo upload→staging→flush→tape→verify | Script testa mount, write, storage externo, serviço — **não faz upload real + flush + verify SHA256 na fita** |

---

### 🟢 Médios (Melhorias de robustez/observabilidade)

| # | Gap | Impacto | Evidência |
|---|-----|---------|-----------|
| **G11** | **Brute-force allowlist manual** | Incidente 2026-04-23 exigiu adicionar IP do TANK manualmente; poderia ser automático via agent | `nextcloud_agent.py` tem `admin.brute_reset` mas **não tem auto-allowlist para IPs conhecidos** |
| **G12** | **Métricas de capacidade de fita sem alerta** | `export-lto6-metrics.sh` exporta `nas_ltfs_avail_bytes` mas não há rule de alerta (ex: <10% livre) | Métricas existem, **alerting não documentado** |
| **G13** | **`ltfs_checkpoint_writer` só roda no homelab** | Se homelab cai durante flush, recovery depende de SSH na NAS + journal local; single point of failure | Journal em `/var/lib/ltfs-journal` no homelab; se homelab perde disco, **journal some** |
| **G14** | **Validação de `files_external:list` frágil** | Teste só grepa `/LTO`; não valida que está `enabled=true`, `applicable=All`, `mount_point` correto | `validate_nextcloud_flow.sh:99` — `grep -q /LTO` |
| **G15** | **Permissões de staging não enforcadas em boot** | `fstab` faz bind mount mas se `/mnt/raid1/lto6-cache` tiver permissão errada, Nextcloud falha | Architecture doc exige `uid=33,gid=33,mode=770` — **não há systemd oneshot para corrigir no boot** |
| **G16** | **Falta documentação de procedimento de troca de fita** | Quando fita enche (EOD), como swapar, catalogar, validar? | Incident doc menciona `catalog.jsonl`, `placements.json` mas **não há runbook de rotação** |

---

### 🔵 Baixos (Dívida técnica / Nice-to-have)

| # | Gap | Impacto |
|---|-----|---------|
| **G17** | `nextcloud_agent.py` tem `admin.storage_diagnostics` mas não expõe "último flush bem-sucedido" | Observabilidade |
| **G18** | `ltfs_recovery.py` tem `KNOWN_ISSUES` hardcoded; novos padrões de falha exigem deploy | Extensibilidade |
| **G19** | Dois pipelines de backup para fita (`lto6-drain-backups` snapshots + `ltfs-cache-flush` staging Nextcloud) com semânticas diferentes; unificar ou documentar boundary | Complexidade |
| **G20** | `validate_nextcloud_flow.sh` usa `tee -a` mas não rotaciona `RESULTS_FILE` | Logs acumulam |

---

## Matriz de Rastreabilidade: Invariante → Gap

| Invariante | Gaps Relacionados |
|------------|-------------------|
| Nextcloud não grava direto na LTFS | G1, G2, G8 |
| Staging em disco (`/mnt/raid1/lto6-cache`) | G3, G7, G15 |
| Único escritor: `ltfs-cache-flush` | G1, G2, G6, G8 |
| Serialização por lock | G2 (lock não global) |
| Janelas controladas mount/copy/sync/verify | G4, G10 |
| Proibido bind-mount LTFS em user dirs | — (validado no incidente) |
| `ltfs-cache-flush.timer` em lote (30min) | G6 |
| `MIN_AGE_SECONDS=900`, `MIN_STABLE_SECONDS=300` | G8 (valores não versionados) |

---

## Plano de Ação Sugerido (Prioridade)

> **Status de implementação (2026-08-02):** itens 1–20 implementados.
> 1–5 ✅ `tools/ltfs_cache_flush.py`, `tools/tape-exclusive-wrap`, check `df` 2b no
> `tests/validate_nextcloud_flow.sh` + rules Prometheus, `tools/ltfs_catalog_verify.py`
> (+service/timer), `tools/tape_log_spool_drain.py` (+service/timer).
> 6–9 ✅ `systemd/ltfs-cache-flush.timer`, cleanup policy no flush worker (G7),
> guard no `tools/selfheal/lto6-smb-proof-selfheal.sh` (G9), teste E2E no
> `tests/validate_nextcloud_flow.sh` via `E2E_ENABLED=1` (G10).
> 10–15 ✅ auto-allowlist brute-force no `nextcloud_agent.py` (G11), rules de
> capacidade fita (G12), `tools/ltfs_journal_replicate.py` + service/timer (G13),
> validação `files_external` estruturada (G14), `tools/fix_staging_perms.py` (G15),
> runbook `docs/OPERATIONS/TAPE_ROTATION.md` (G16).
> 16–20 ✅ `last_flush` no `admin.storage_diagnostics` (G17),
> `LTFS_KNOWN_ISSUES_EXTRA_FILE` (G18), boundary dos dois pipelines documentada
> (G19), rotação do `RESULTS_FILE` (G20).

### Sprint 1 — Críticos (Bloqueiam produção segura)
1. **Versionar `ltfs-cache-flush`** — mover binary/script para `tools/ltfs-cache-flush` com testes
2. **Lock global de fita** — estender `ltfs_recovery.py` ou criar `/run/lock/tape-global.lock` compartilhado entre homelab e NAS (via NFS/SSH atomic)
3. **Monitoring de staging** — adicionar check `df` no `validate_nextcloud_flow.sh` + alerta Prometheus
4. **Validação de catálogo pós-flush** — job que lê `catalog.jsonl`, verifica SHA256 sample, alerta se mismatch
5. **Criar `tape-log-spool-drain`** — script simples que rotaciona logs do pipeline

### Sprint 2 — Altos (Eliminam degradação silenciosa)
6. **Versionar `ltfs-cache-flush.timer`** com `OnCalendar=*:0/30` + `AccuracySec=1min`
7. **Policy de cleanup de staging** — adicionar step no flush worker: após verify OK, `rm` arquivo do staging (ou mover para `.flushed/` com TTL)
8. **Guard no self-heal CIFS** — checar `systemctl is-active lto6-drain-backups ltfs_checkpoint_writer` antes de `pkill`
9. **Teste E2E** — estender `validate_nextcloud_flow.sh` com `make test-e2e` que faz upload→wait flush→verify tape

### Sprint 3 — Médios (Robustez operacional)
10. **Auto-allowlist brute-force** — no `nextcloud_agent`, detectar IPs de dispositivos conhecidos (TANK, etc.) e auto-whitelist
11. **Alerting de capacidade fita** — rule Prometheus `nas_ltfs_avail_bytes / nas_ltfs_size_bytes < 0.1`
12. **Journal replication** — replicar `/var/lib/ltfs-journal` para NAS (ou S3) via `rsync` no final de cada sessão
13. **Validação completa `files_external`** — checar `enabled`, `applicable`, `mount_point`, `options`
14. **Systemd oneshot `fix-staging-perms`** — roda no boot, garante `uid=33,gid=33,mode=770` em `/mnt/raid1/lto6-cache`
15. **Runbook de rotação de fita** — documento em `docs/OPERATIONS/TAPE_ROTATION.md`

---

## Comandos de Verificação Rápida (Para Homelab Atual)

```bash
# 1. Staging mount aponta para cache (não LTFS direto)
findmnt /mnt/lto6-nc -o SOURCE -n
# esperado: /mnt/raid1/lto6-cache

# 2. Permissões staging
stat -c "%a %U:%G" /mnt/raid1/lto6-cache
# esperado: 770 www-data:www-data (ou root:root com gid 33)

# 3. Nextcloud escreve no staging
docker exec -u www-data nextcloud-app sh -lc 'p=/var/www/html/external/LTO/.probe; date > "$p"; stat "$p"; rm -f "$p"'

# 4. Storage externo ativo
docker exec nextcloud-app php occ files_external:list | grep -A5 /LTO

# 5. Flush worker existe e timer configurado
systemctl cat ltfs-cache-flush.timer
# verificar OnCalendar=*:0/30

# 6. Lock de flush não órfão
ls -la /run/ltfs-cache-flush.lock 2>/dev/null || echo "lock não existe (ok se worker não rodando)"

# 7. Espaço em staging
df -h /mnt/raid1/lto6-cache

# 8. Último flush bem-sucedido (journal)
tail -5 /var/lib/ltfs-cache-flush/catalog.jsonl 2>/dev/null || echo "catalog não encontrado"

# 9. Fita montada na NAS (via SSH)
ssh root@192.168.15.4 "findmnt /mnt/tape/lto6 && df -h /mnt/tape/lto6"

# 10. Self-heal CIFS não conflitou recentemente
journalctl -u lto6-smb-proof-selfheal.service -n 20 --no-pager
```

---

## Referências

- `docs/INCIDENTS/NEXTCLOUD_TANK_LTO_UPLOAD_2026-04-23.md` — incidente que definiu a arquitetura
- `docs/NEXTCLOUD_LTO_STAGING_ARCHITECTURE_2026-04-23.md` — contrato operacional
- `specialized_agents/nextcloud_agent.py:766-867` — `_classify_lto_mount`, `_nextcloud_storage_diagnostics`
- `tools/lto6-drain-backups` — drain de snapshots via rsync/CIFS
- `tools/ltfs_checkpoint_writer.py` — drain com journal por arquivo + recovery
- `tools/ltfs_recovery.py` — orchestrator LTFS (mount, self-heal, ltfsck, deep-recovery)
- `systemd/ltfs-cache-flush.service.d/60-tape-gate.conf` — drop-in com lock exclusivo
- `tests/validate_nextcloud_flow.sh` — validação componentizada
- `deploy/nas/sbin/export-lto6-metrics.sh` — métricas Prometheus LTFS