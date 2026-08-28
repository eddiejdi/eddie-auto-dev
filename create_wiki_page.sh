#!/bin/bash
# Publica/atualiza a página do LTFS Self-Heal no Wiki.js do homelab.
# Usa update se a página já existir, create se não existir.

set -euo pipefail

WIKI_URL="http://192.168.15.2:3009/graphql"
PAGE_PATH="operations/ltfs-selfheal-system"
PAGE_TITLE="LTFS Self-Heal System — Referência Operacional"
PAGE_LOCALE="pt"
PAGE_DESC="Referência operacional do sistema de self-heal LTFS: causa raiz, correção sync_type, alertas e cenários de recovery."
PAGE_TAGS='["ltfs","nas","monitoring","self-heal","infraestrutura"]'

# ── Conteúdo da página ────────────────────────────────────────────────────────
read -r -d '' WIKI_CONTENT << 'CONTENT_EOF' || true
# LTFS Self-Heal System — Referência Operacional

## Causa Raiz e Correção (2026-04-26)

```
Incidente: 13:55:44 → 13:56:52 (68 segundos)
  Causa:   -o sync_type=unmount acumulou tudo em RAM.
           No unmount, flush único e massivo → fuse hung → watchdog reboot.
  Fix:     -o sync_type=time -o sync_time=300
           Flush incremental a cada 5 min; unmount vira operação leve.
```

Arquivos corrigidos: `tmp/ltfs-fc-stable-start` e `tmp/ltfs-retry.sh`.

---

## Alertas Prometheus

**Arquivo:** `/etc/prometheus/rules/ltfs-selfheal-rules.yml`

| Alert | Severidade | Trigger | Nota |
|-------|-----------|---------|------|
| LTFSMountDown | CRITICAL | `nas_ltfs_mount_up == 0` por 2 min | |
| LTFSIOHung | CRITICAL | `nas_ltfs_io_hung == 1` imediato | Novo — hang mid-sync |
| LTFSSelfHealFailed | CRITICAL | `consecutive_failures >= 3` por 1 min | Escalar manual |
| LTFSDrainStall | WARNING | `rate(drain[10m]) == 0` por **10 min** | Era 3 min; ajustado para não alarmar durante flush periódico de 300s |
| NASRebootedRecently | WARNING | uptime < 5 min | Imediato |

Ver: [Prometheus Alerts](http://127.0.0.1:9090/alerts) · [Rules](http://127.0.0.1:9090/rules)

---

## Self-Heal — Cenários Cobertos

**Script:** `/home/homelab/bin/ltfs-selfheal-remount.sh`
**Schedule:** 30s após boot, a cada 5 min

| Caso | Detecção | Ação |
|------|---------|------|
| Mount down | findmnt falha | restart ltfs-lto6 (3 tentativas) |
| Stale fuse mount | findmnt ok + processo morto | fusermount -u -z → restart |
| Hang mid-sync | findmnt ok + processo vivo + `timeout 15 ls` trava | SIGTERM → 60s grace → SIGKILL → fusermount -u -z → restart |
| Saudável | findmnt ok + I/O < 15s | Sem ação |

> **Grace period de 60s no SIGTERM:** com sync_type=time o LTFS pode estar gravando o índice na fita. Dar tempo para terminar evita corrupção de índice.

---

## Métricas (textfile exporter na NAS)

```
nas_ltfs_mount_up{mountpoint="/mnt/tape/lto6"}            1 ou 0
nas_ltfs_io_hung{mountpoint="/mnt/tape/lto6"}             1 quando I/O não responde em 15s
nas_ltfs_selfheal_consecutive_failures{...}               0-N
nas_ltfs_selfheal_last_result_code{...}
  # 0=ok  1=recovered  2=failed  5=stale_mount  6=hung_sync
```

---

## Dashboards Grafana

- [NAS Monitoring](http://127.0.0.1:3002/d/nas-monitoring-stable) — CPU, RAM, Disco, I/O, Rede
- [LTFS Crash Detection](http://127.0.0.1:3002/d/nas-ltfs-crash-detection) — Mount status, I/O hung, drain, self-heal

---

## Comandos Úteis

```bash
# Logs self-heal em tempo real
ssh homelab@192.168.15.2 'tail -f /var/log/ltfs-selfheal.log'

# Status do timer
ssh homelab@192.168.15.2 'sudo systemctl status ltfs-selfheal.timer'

# Forçar self-heal agora
ssh homelab@192.168.15.2 'sudo systemctl start ltfs-selfheal.service'

# Confirmar sync_type ativo na NAS
ssh root@192.168.15.4 'cat /proc/$(pgrep -f "ltfs /mnt")/cmdline | tr "\0" "\n" | grep sync'
# Esperado: sync_type=time e sync_time=300

# Alerts LTFS ativos
curl -sS http://127.0.0.1:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.category=="ltfs")'
```

---

## Deploy / Atualização

```bash
scp tools/ltfs-selfheal-remount.sh homelab@192.168.15.2:/home/homelab/bin/ltfs-selfheal-remount.sh
ssh homelab@192.168.15.2 'chmod +x /home/homelab/bin/ltfs-selfheal-remount.sh'

scp monitoring/prometheus/ltfs-selfheal-rules.yml homelab@192.168.15.2:/etc/prometheus/rules/ltfs-selfheal-rules.yml
ssh homelab@192.168.15.2 'curl -sX POST http://localhost:9090/-/reload'

scp tmp/ltfs-fc-stable-start root@192.168.15.4:/usr/local/sbin/ltfs-fc-stable-start
ssh root@192.168.15.4 'chmod +x /usr/local/sbin/ltfs-fc-stable-start && systemctl restart ltfs-lto6'
```

---

**Última atualização:** 2026-04-26
**Status:** ✅ ACTIVE — sync_type=time operacional
CONTENT_EOF

# ── Helpers ──────────────────────────────────────────────────────────────────

gql() {
    local payload=$1
    ssh -oBatchMode=yes homelab@192.168.15.2 \
        "curl -sf -X POST '${WIKI_URL}' \
             -H 'Content-Type: application/json' \
             ${JWT:+-H 'Authorization: Bearer ${JWT}'} \
             --data-binary @-" <<< "$payload"
}

get_jwt() {
    local resp
    resp=$(ssh -oBatchMode=yes homelab@192.168.15.2 \
        "curl -sf -X POST '${WIKI_URL}' \
             -H 'Content-Type: application/json' \
             -d '{\"query\":\"mutation(\$e:String!,\$p:String!){authentication{login(username:\$e,password:\$p,strategy:\\\"local\\\"){jwt}}}\",\"variables\":{\"e\":\"admin@wiki.local\",\"p\":\"changeme\"}}'" 2>/dev/null || true)
    echo "$resp" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('authentication',{}).get('login',{}).get('jwt',''))" 2>/dev/null || true
}

get_page_id() {
    local resp
    resp=$(gql "$(python3 -c "
import json
print(json.dumps({'query':'''query(\$path:String!,\$locale:String!){pages{singleByPath(path:\$path,locale:\$locale){id}}}''','variables':{'path':'${PAGE_PATH}','locale':'${PAGE_LOCALE}'}}))
")")
    echo "$resp" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('pages',{}).get('singleByPath') and d['data']['pages']['singleByPath'].get('id') or '')" 2>/dev/null || true
}

# ── Main ─────────────────────────────────────────────────────────────────────

echo "[*] Obtendo JWT do Wiki.js..."
JWT=$(get_jwt)
[[ -n "$JWT" ]] && echo "[✓] JWT obtido" || echo "[!] Sem JWT — tentando sem autenticação"

echo "[*] Verificando se página já existe em ${PAGE_PATH}..."
PAGE_ID=$(get_page_id)

PAYLOAD=$(python3 - <<PYEOF
import json

content = open('/dev/stdin').read() if False else """${WIKI_CONTENT}"""
page_id = "${PAGE_ID}"

if page_id:
    q = """mutation(\$id:Int!,\$content:String!,\$description:String!,\$editor:String!,\$isPublished:Boolean!,\$isPrivate:Boolean!,\$locale:String!,\$path:String!,\$tags:[String]!,\$title:String!){pages{update(id:\$id,content:\$content,description:\$description,editor:\$editor,isPublished:\$isPublished,isPrivate:\$isPrivate,locale:\$locale,path:\$path,tags:\$tags,title:\$title){responseResult{succeeded message}page{id title path}}}}"""
    variables = {"id": int(page_id), "content": content, "description": "${PAGE_DESC}", "editor": "markdown", "isPublished": True, "isPrivate": False, "locale": "${PAGE_LOCALE}", "path": "${PAGE_PATH}", "tags": ${PAGE_TAGS}, "title": "${PAGE_TITLE}"}
else:
    q = """mutation(\$content:String!,\$description:String!,\$editor:String!,\$isPublished:Boolean!,\$isPrivate:Boolean!,\$locale:String!,\$path:String!,\$tags:[String]!,\$title:String!){pages{create(content:\$content,description:\$description,editor:\$editor,isPublished:\$isPublished,isPrivate:\$isPrivate,locale:\$locale,path:\$path,tags:\$tags,title:\$title){responseResult{succeeded message}page{id title path}}}}"""
    variables = {"content": content, "description": "${PAGE_DESC}", "editor": "markdown", "isPublished": True, "isPrivate": False, "locale": "${PAGE_LOCALE}", "path": "${PAGE_PATH}", "tags": ${PAGE_TAGS}, "title": "${PAGE_TITLE}"}

print(json.dumps({"query": q, "variables": variables}))
PYEOF
)

OP=$([[ -n "$PAGE_ID" ]] && echo "update" || echo "create")
echo "[*] Operação: ${OP} (page_id=${PAGE_ID:-novo})"

RESPONSE=$(gql "$PAYLOAD")

echo "$RESPONSE" | python3 -c "
import json, sys
d = json.load(sys.stdin)
if d.get('errors'):
    print('[✗] GraphQL Error:', d['errors'])
    sys.exit(1)
pages = d.get('data', {}).get('pages', {})
op = pages.get('update') or pages.get('create') or {}
rr = op.get('responseResult', {})
if rr.get('succeeded'):
    p = op.get('page', {})
    print(f'[✓] OK — id={p.get(\"id\")} path={p.get(\"path\")}')
    print(f'    https://wiki.rpa4all.com/{p.get(\"path\")}')
else:
    print(f'[✗] {rr.get(\"message\")}')
    sys.exit(1)
"
