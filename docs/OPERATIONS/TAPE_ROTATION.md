# Runbook — Rotação de Fita LTO (G16)

Gap G16 do review `docs/NEXTCLOUD_LTO_FLOW_REVIEW_2026-08-02.md`: faltava
procedimento operacional documentado para trocar a fita LTFS quando está cheia
ou degradada. Este runbook cobre a rotação completa: parada controlada,
ejeção, inserção de fita nova e revalidação.

## Terminologia (não confundir — lição L8 do 2026-05-19)

| Nível | Exemplo |
|---|---|
| Nome lógico do fluxo | `lto6-sg1` / `lto6-cache` |
| Export CIFS consumida pelo homelab | `//192.168.15.4/LTO6_SG1`, `//192.168.15.4/LTO6_CACHE` |
| Device LTFS real na NAS | `/dev/sg2`, `/dev/nst2`, mount `/mnt/tape/lto6-sg1` |

Sempre confirmar com `mt-st`/`ltfs` na NAS qual device físico corresponde à
fita lógica antes de qualquer ação.

## Pré-condições

- Fita com menos de 80% de capacidade (alerta `LTFSCapacityHigh`) **ou** EOD
  próximo do fim físico.
- Nenhum incidente em andamento no fluxo de backup Nextcloud → fita
  (sem `ltfs-cache-flush.service` em `activating/failed`).

## Procedimento

### 1. Parar escritores de fita (ordem)

```bash
# No homelab (192.168.15.2):
sudo systemctl stop ltfs-cache-flush.service ltfs-cache-flush.timer
sudo systemctl stop ltfs-journal-replicate.timer
sudo systemctl stop lto6-drain-backups.service
sudo systemctl stop ltfs-checkpoint-drain.service 2>/dev/null || true
sudo systemctl stop tape-log-spool-drain-nextcloud.timer
```

Verificar que não há processos escrevendo na fita:

```bash
pgrep -af "rsync.*lto6-smb-proof|ltfs-cache-flush|ltfs_checkpoint_writer"
# Saída esperada: vazia
```

### 2. Forçar flush pendente (opcional, recomendado)

```bash
ltfs-cache-flush --buffer-root /mnt/raid1/lto6-cache \
  --primary-buffer-root /mnt/raid1/lto6-cache \
  --target-root /mnt/lto6-smb-proof \
  --state-file /var/lib/ltfs-cache-flush/state.json \
  --placement-file /var/lib/ltfs-cache-flush/placements.json \
  --catalog-file /var/lib/ltfs-cache-flush/catalog.jsonl \
  --metrics-file /var/lib/ltfs-cache-flush/metrics.json \
  --metrics-state-file /var/lib/ltfs-cache-flush/metrics_state.json \
  --lock-file /run/ltfs-cache-flush.lock \
  --min-age-seconds 0 --min-stable-seconds 0 \
  --min-target-total-bytes 0 --min-target-free-bytes 0
```

Confirmar que `status: success` e que o catalog.jsonl foi atualizado.

### 3. Replicar journal e estado para a NAS

```bash
sudo systemctl start ltfs-journal-replicate.service
journalctl -u ltfs-journal-replicate.service -n 5 --no-pager
```

### 4. Desmontar o export CIFS (homelab)

```bash
sudo systemctl stop mnt-lto6\\x2dsmb\\x2dproof.mount
sudo mountpoint -q /mnt/lto6-smb-proof && echo "AINDA MONTADO" || echo "desmontado"
```

> Se ainda montado, não forçar `umount -l` antes de confirmar que a NAS
> liberou a sessão (ver passo 5). Mount "stale" derruba o self-heal.

### 5. Ejetar fita na NAS (via SSH)

```bash
ssh root@192.168.15.4 'ltfs -o eject /mnt/tape/lto6-cache'
```

> NUNCA usar `sg_raw`/`mt-st eject` direto sem o orchestrator
> (`ltfs_recovery.py`) — política 3 do AGENTS.md. A ejeção de rotina acima é
> feita pelo `ltfs` da NAS, que é o caminho suportado pelo orchestrator.

Se o eject falhar por fita cheia (requer força), usar o orchestrator:

```bash
ssh root@192.168.15.4 '/var/db/ltfs-tools/ltfs_recovery.py --mode eject --force'
```

### 6. Trocar fita fisicamente

- Retirar a fita ejetada; registrar no inventário (número de série, data, uso).
- Inserir a fita nova/reciclada (ver política de retenção no Anexo A).
- Confirmar que o drive travou a fita (sem erro no painel do drive/NAS).

### 7. Montar e validar a fita nova

```bash
# Homelab:
sudo systemctl start mnt-lto6\\x2dsmb\\x2dproof.mount
sleep 5
mountpoint -q /mnt/lto6-smb-proof && echo "OK" || echo "FALHOU"
```

```bash
# NAS: verificar que a LTFS montou RW e gravável
ssh root@192.168.15.4 'df -h /mnt/tape/lto6-cache; ls /mnt/tape/lto6-cache | head'
```

### 8. Reiniciar o pipeline

```bash
sudo systemctl start ltfs-cache-flush.timer
sudo systemctl start lto6-drain-backups.service
sudo systemctl start ltfs-journal-replicate.timer
sudo systemctl start tape-log-spool-drain-nextcloud.timer
sudo systemctl start fix-staging-perms.service
```

### 9. Revalidar fluxo completo

```bash
tests/validate_nextcloud_flow.sh | tee /tmp/validation_$(date +%F).log
```

- Confirmar `Fluxo Nextcloud → Staging → Fita pronto para produção`.
- Opcionalmente rodar E2E: `E2E_ENABLED=1 tests/validate_nextcloud_flow.sh`
  (faz upload → flush → verificação SHA256 na fita).

### 10. Registrar rotação

- Data, fita anterior → nova, espaço liberado.
- Atualizar inventário de fitas (Anexo A) e o painel
  `http://192.168.15.2:8093/`.
- Se houve falha no meio do caminho: seguir `docs/ltfs-emergency-runbook.md`.

## Anexo A — Política de retenção sugerida

| Fita | Uso | Rotação |
|---|---|---|
| `LTO6-CACHE` | Staging Nextcloud → LTO | Quando ≥80% (alert) / EOD próximo |
| `LTO6-SG1` | Logs / snapshots | Conforme size; guarda de mount via automount (lição L3) |

## Anexo B — Sinais de que a fita precisa de rotação

- Prometheus `lto_tape_capacity_percent >= 80` (warn) / `>= 90` (critical)
- `ltfs-cache-flush` falhando com `No space left` ou EOD em `check_target_capacity`
- `ltfs_catalog_verify` reportando falhas de verificação persistentes
