# Incidente — Pipeline LTO Flush + Badge "Crítico" Falso — 2026-05-14

> Diagnóstico do pipeline Nextcloud → cache → fita; selfheal do mount point de prova; e correção do badge "Crítico" falso no painel AI Assessment do Grafana.

---

## Resumo Executivo

Em 2026-05-14, três problemas foram identificados e corrigidos no pipeline de arquivamento LTO:

1. **`lto6-drain-backups.service` pulando diariamente** — mount point `/mnt/lto6-smb-proof` nunca tinha sido criado como unit systemd; a `ConditionPathIsMountPoint=` jamais era satisfeita.

2. **Badge "Crítico" falso no painel AI Assessment (Grafana panel-31)** — três causas em cadeia: métrica `nas_ltfs_mount_up` estagnada em 0, arquivo `ltfs_selfheal.prom` com entrada duplicada e stale, e lógica do assessor sem fallback.

3. **Pipeline de flush ocioso (esperado)** — o `ltfs-cache-flush` estava saudável; a ausência de candidatos era correta pois nenhum arquivo novo foi enviado ao storage LTO do Nextcloud desde 2026-05-10.

---

## Topologia do Pipeline

```
Nextcloud (container nextcloud-app)
  └─ external/LTO → /mnt/lto6-nc (mergerfs → /mnt/raid1/lto6-cache)
                                         │
                              ltfs-cache-flush (a cada 5min)
                                         │
                              /mnt/lto6-cache-nas  ← CIFS → NAS 192.168.15.4
                              (LTO6_CACHE share)
                                         │
                              ltfs:/dev/sg0 → /mnt/tape/lto6 (LTFS na fita física)
```

```
lto6-drain-backups.timer (diário 04:00)
  └─ ConditionPathIsMountPoint=/mnt/lto6-smb-proof   ← gate de saúde da NAS
       └─ mnt-lto6\x2dsmb\x2dproof.mount             ← unit que faltava
```

---

## Incidente 1 — `lto6-drain-backups` pulando por falta da unit `.mount`

### Sintoma

```
mai 13 04:00:00 homelab systemd[1]: lto6-drain-backups.service was skipped
because of an unmet condition check (ConditionPathIsMountPoint=/mnt/lto6-smb-proof).
```

O timer rodava diariamente às 04:00 mas o serviço era sempre pulado.

### Causa Raiz

O `lto6-drain-backups.service` referenciava:
- `Wants=mnt-lto6\x2dsmb\x2dproof.mount`
- `After=mnt-lto6\x2dsmb\x2dproof.mount`
- `ConditionPathIsMountPoint=/mnt/lto6-smb-proof`

A unit `mnt-lto6\x2dsmb\x2dproof.mount` **nunca havia sido criada**. O diretório `/mnt/lto6-smb-proof` existia, mas nunca era montado — systemd não tentava montar porque não havia unit.

O share CIFS alvo (`//192.168.15.4/LTO6_CACHE`) estava funcional e montado em `/mnt/lto6-cache-nas`, mas o mount point de prova era independente.

### Correção

Criados quatro arquivos:

**`/etc/systemd/system/mnt-lto6\x2dsmb\x2dproof.mount`**
```ini
[Unit]
Description=CIFS proof mount — LTO6 NAS reachability gate
After=network-online.target
Wants=network-online.target

[Mount]
What=//192.168.15.4/LTO6_CACHE
Where=/mnt/lto6-smb-proof
Type=cifs
Options=credentials=/root/.smb-lto6-cache-credentials,vers=3.0,iocharset=utf8,uid=1000,gid=1000,file_mode=0664,dir_mode=0775,soft,nounix,_netdev
TimeoutSec=30

[Install]
WantedBy=multi-user.target
```

**`/usr/local/sbin/lto6-smb-proof-selfheal`** — detecta stale mount, força `umount -f -l` e reinicia a unit.

**`/etc/systemd/system/lto6-smb-proof-selfheal.service`** — oneshot que executa o script.

**`/etc/systemd/system/lto6-smb-proof-selfheal.timer`** — dispara a cada 2 minutos (`OnBootSec=60`, `OnUnitActiveSec=2min`).

```bash
systemctl enable --now 'mnt-lto6\x2dsmb\x2dproof.mount'
systemctl enable --now lto6-smb-proof-selfheal.timer
```

### Verificação

```
/mnt/lto6-smb-proof is a mountpoint
lto6-smb-proof-selfheal: mount healthy, nothing to do
```

### Arquivos no Repositório

```
tools/selfheal/mnt-lto6-smb-proof.mount
tools/selfheal/lto6-smb-proof-selfheal.sh
tools/selfheal/lto6-smb-proof-selfheal.service
tools/selfheal/lto6-smb-proof-selfheal.timer
```

---

## Incidente 2 — Badge "Crítico" Falso no Painel AI Assessment

### Sintoma

Grafana `nas-rpa4all-omv` → panel-31 "AI Assessment" exibindo badge vermelho **Crítico** com:
- Drive: Pronto
- Mídia: Carregada
- Compressão: **Desativada** (mas fita funcionando normalmente)
- Escrita: 0.0 B/s
- Flush: 0.0 B/s

### Causa Raiz (três camadas)

#### Camada 1 — `ltfs_selfheal.prom` com entrada duplicada e stale

O arquivo `/var/lib/prometheus/node-exporter/ltfs_selfheal.prom` (modificado em 2026-05-03, há 11 dias) continha apenas:

```
nas_ltfs_mount_up{mountpoint="/mnt/tape/lto6"} 0
```

O node-exporter lê **todos** os arquivos `.prom` do textfile collector directory. Com dois arquivos definindo a mesma série (`lto6.prom` e `ltfs_selfheal.prom`), o node-exporter servia 0 — ignorando o valor correto em `lto6.prom`.

**Fix:** `ltfs_selfheal.prom` zerado (a métrica é responsabilidade exclusiva de `lto6.prom`).

#### Camada 2 — `export-lto6-metrics.sh` bloqueado por `tape-access tryrun`

O script do exporter começa com:
```bash
if [[ -z "${TAPE_ACCESS_ACTIVE:-}" ]]; then
    export TAPE_ACCESS_ACTIVE=1
    exec /usr/local/sbin/tape-access tryrun --name "export-lto6-metrics" -- "$0" "$@"
fi
```

Quando LTFS está servindo arquivos (tape ocupado), `tape-access tryrun` encerra o processo sem executar o resto do script. O arquivo `lto6.prom` fica com o último valor escrito — que era `mount_up=0` de uma execução anterior quando o mount estava caindo.

**Fix:** Adicionado `_quick_mount_update()` que roda **antes** do gate `tape-access`, atualizando apenas as linhas `nas_ltfs_service_up` e `nas_ltfs_mount_up` no arquivo existente via `sed` + `findmnt`:

```bash
_quick_mount_update() {
  # Atualiza mount_up/service_up sem precisar de acesso exclusivo à fita
  findmnt "$mp" >/dev/null 2>&1 && mnt_val=1
  sed -e "s|^\(nas_ltfs_mount_up[^}]*}\) [0-9]*$|\1 ${mnt_val}|" \
      "$out_file" > "$tmp" && mv "$tmp" "$out_file"
}
_quick_mount_update   # roda sempre, antes do tape-access gate
```

Backup criado em `/usr/local/sbin/export-lto6-metrics.sh.bak_20260514`.

#### Camada 3 — `nas_ai_assessor.py` sem fallback e comp `-1` errado

O assessor usava exclusivamente `nas_ltfs_mount_up` para determinar saúde do LTFS:
```python
if ltfs_up and mount_up:      # mount_up=0 → issue "LTFS indisponível"
    positives.append(...)
else:
    issues.append("LTFS indisponível ou não montado")  # → badge Crítico
```

E exibia `compression_enabled = -1` (valor indeterminado — sg0 ocupado) como "Desativada":
```python
comp_label = "Ativa" if ... else ("Desativada" if comp_val is not None else "N/A")
# -1 não é None → "Desativada" (errado)
```

**Fix em `tools/homelab/nas_ai_assessor.py`:**

1. Adicionadas queries para `nas_tape_volume_mounted` e `nas_tape_volume_ready` (atualizadas pelo discoverer, path independente do tape-access gate).

2. `build_summary` usa `volume_mounted` como fallback:
```python
ltfs_accessible = ltfs_up and (mount_up or volume_mounted)
```

3. Drive/media usam `volume_ready` como fallback para `drive_ready=-1`:
```python
drive_ok = (drive_ready >= 1) or (volume_ready >= 1)
```

4. Compressão indeterminada exibe "N/A":
```python
if comp_val is None or comp_val < 0:
    comp_label = "N/A"   # -1 = sg0 ocupado, não significa desativada
```

### Resultado Final

```
overall: saudavel
issues: []
positives: ['LTFS ativo e montado', 'LTFS em leitura e escrita', 'Drive pronto com mídia carregada']
mount_up: 1.0  |  volume_mounted: 1.0  |  volume_ready: 1.0
```

### Arquivos Modificados

| Arquivo | Tipo | Mudança |
|---|---|---|
| `tools/homelab/nas_ai_assessor.py` | Python | fallback volume_mounted, fix comp=-1, fix drive/media |
| `/usr/local/sbin/export-lto6-metrics.sh` (NAS) | Bash | `_quick_mount_update()` antes do tape-access gate |
| `/var/lib/prometheus/node-exporter/ltfs_selfheal.prom` (NAS) | .prom | zerado (entrada duplicada stale) |

---

## Incidente 3 — Pipeline de Flush Ocioso (não-incidente)

### Observação

O `ltfs-cache-flush` reportava `no completed files eligible for flush` em todas as execuções. O cache local (`/mnt/raid1/lto6-cache`) tinha 0 arquivos.

### Diagnóstico

O pipeline estava **correto e saudável**. O último arquivo arquivado foi em **2026-05-10T02:47:19Z** — todos os arquivos enviados ao storage LTO externo do Nextcloud já haviam sido movidos para o NAS.

O cache fica vazio após o flush bem-sucedido. A ausência de candidatos indica que nenhum usuário enviou novos arquivos para a pasta LTO do Nextcloud desde 2026-05-10.

### Estado do Pipeline

| Componente | Status |
|---|---|
| `ltfs-cache-flush.timer` | ativo, rodando a cada 5min |
| `/mnt/lto6-cache-nas` (CIFS → NAS) | montado, 91G usados / 2.3T |
| `ltfs:/dev/sg0` na NAS | montado em `/mnt/tape/lto6`, 4% cheio |
| Nextcloud LTO external storage | montado (`/var/www/html/external/LTO`) |
| Fluxo de novos arquivos | nenhum desde 2026-05-10 |

### Ação

Nenhuma — pipeline aguardando novos uploads. Se houver expectativa de fluxo contínuo, verificar se algum processo de sincronização automática para a pasta LTO do Nextcloud está configurado e ativo.

---

## Estado dos Serviços Relevantes (pós-correção)

| Serviço | Status |
|---|---|
| `mnt-lto6\x2dsmb\x2dproof.mount` | active (mounted) |
| `lto6-smb-proof-selfheal.timer` | active (waiting), próximo disparo em 2min |
| `lto6-drain-backups.timer` | active (waiting), roda às 04:00 |
| `ltfs-cache-flush.timer` | active (waiting), a cada 5min |
| `nas_ltfs_mount_up` (Prometheus) | 1 |
| AI Assessment badge | Saudável |
| `hdd-backup-spindown` | failed (pré-existente, sem logs recentes) |
| `tape-quality-ollama-narrator` | failed (Ollama 404 às 06:01 — GPU sem modelo carregado nesse horário) |

---

## Commits Relacionados

```
add8f520  feat(tape): selfheal para /mnt/lto6-smb-proof CIFS — drain desbloqueado
5b1ce00b  fix(nas-assessor): corrigir falso 'Crítico' por mount_up estagnado e comp -1
```

---

## Lições Aprendidas

1. **Mount points de prova precisam de units systemd explícitas** — um diretório existente não é suficiente para `ConditionPathIsMountPoint=` ser satisfeita pelo systemd.

2. **Múltiplos arquivos `.prom` com a mesma série causam conflito silencioso** no textfile collector do node-exporter. Cada métrica deve ter exatamente um arquivo responsável.

3. **Scripts de exporter gateados por `tape-access tryrun` devem separar checks de mount** (sem necessidade de I/O na fita) dos checks SCSI (que precisam de acesso exclusivo). Checks de disponibilidade de mount devem sempre rodar.

4. **`-1` em métricas de hardware significa indeterminado, não "desativado"** — quando `/dev/sg0` está ocupado com LTFS, `tapeinfo` retorna erro; o valor `-1` não deve ser exibido como estado negativo.

5. **`nas_tape_volume_*` é mais confiável que `nas_ltfs_*` para indicar saúde do tape** — é atualizado pelo discoverer via `findmnt` + `mt status`, não pelo path gateado por tape-access.
