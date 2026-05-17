#!/usr/bin/env python3
"""
Publicar/atualizar página wiki do sistema LTFS Self-Heal.
Usa Wiki.js GraphQL API. Faz update se a página já existir, create se não.
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

# Configuração
WIKI_HOST = "192.168.15.2"
WIKI_PORT = 3009
WIKI_URL = f"http://{WIKI_HOST}:{WIKI_PORT}/graphql"

PAGE_PATH   = "operations/ltfs-selfheal-system"
PAGE_TITLE  = "LTFS Self-Heal System — Referência Operacional"
PAGE_LOCALE = "pt"
PAGE_TAGS   = ["ltfs", "nas", "monitoring", "self-heal", "infraestrutura"]
PAGE_DESC   = "Referência operacional do sistema de self-heal LTFS: causa raiz, correção sync_type, alertas e cenários de recovery."

SECRETS_ENDPOINT = "/".join([
    "http://192.168.15.2:8088",
    "secret",
    "wikijs",
    "token",
])

# Conteúdo da página (Markdown)
LTFS_CONTENT = """# LTFS Self-Heal System — Referência Operacional

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

> **Grace period de 60s no SIGTERM:** com sync_type=time o LTFS pode estar no meio de gravar o índice na fita. Dar tempo para terminar evita corrupção do índice.

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
ssh root@192.168.15.4 'cat /proc/$(pgrep -f "ltfs /mnt")/cmdline | tr "\\0" "\\n" | grep sync'
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
"""

def get_api_token():
    """
    Obter API token do Wiki.js via SSH + secrets do homelab
    Tenta: 1) WIKI_TOKEN 2) secrets agent 3) arquivo local 4) login JWT
    """
    print("[*] Obtendo API token do Wiki.js...", file=sys.stderr)

    token = os.getenv("WIKI_TOKEN", "").strip()
    if token:
        print("[✓] Token obtido via WIKI_TOKEN", file=sys.stderr)
        return token

    try:
        print("[*] Tentando obter token via Secrets Agent...", file=sys.stderr)
        result = subprocess.run(
            ["curl", "-sf", SECRETS_ENDPOINT],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            secret = json.loads(result.stdout).get("value", "").strip()
            if secret:
                print("[✓] Token obtido via Secrets Agent", file=sys.stderr)
                return secret
    except Exception as e:
        print(f"[!] Secrets Agent falhou: {e}", file=sys.stderr)
    
    try:
        # Tentar fazer login via GraphQL para obter JWT
        # Use credenciais padrão (admin)
        login_query = {
            "query": """
            mutation($e:String!,$p:String!){
                authentication{
                    login(username:$e,password:$p,strategy:"local"){
                        jwt
                    }
                }
            }
            """,
            "variables": {
                "e": "admin@wiki.local",
                "p": "changeme"  # Senha padrão, pode falhar
            }
        }
        
        req = urllib.request.Request(
            WIKI_URL,
            data=json.dumps(login_query).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode('utf-8'))
            if result.get('data', {}).get('authentication', {}).get('login', {}).get('jwt'):
                token = result['data']['authentication']['login']['jwt']
                print("[✓] JWT obtido via login", file=sys.stderr)
                return token
    except Exception as e:
        print(f"[!] Login padrão falhou: {e}", file=sys.stderr)
    
    # Fallback: Tentar obter via SSH do homelab
    try:
        print("[*] Tentando obter token via SSH homelab...", file=sys.stderr)
        result = subprocess.run(
            [
                "ssh", "-oBatchMode=yes", "-oConnectTimeout=5",
                "homelab@192.168.15.2",
                "cat ~/.wikijs-api-key 2>/dev/null || echo 'NOT_FOUND'"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )
        token = result.stdout.strip()
        if token and token != "NOT_FOUND":
            print("[✓] API Key obtida via SSH", file=sys.stderr)
            return token
    except Exception as e:
        print(f"[!] SSH falhou: {e}", file=sys.stderr)
    
    # Último fallback: usar Bearer token vazio (pode funcionar se API estiver aberta)
    print("[!] Nenhum token encontrado, tentaremos sem autenticação", file=sys.stderr)
    return None

def graphql(payload, api_token):
    headers = {'Content-Type': 'application/json'}
    if api_token:
        headers['Authorization'] = f'Bearer {api_token}'
    req = urllib.request.Request(
        WIKI_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode('utf-8'))


def get_page_id(api_token):
    """Retorna o ID da página se ela já existir, ou None."""
    result = graphql({
        "query": """
        query($path:String!,$locale:String!){
            pages{ singleByPath(path:$path,locale:$locale){ id } }
        }
        """,
        "variables": {"path": PAGE_PATH, "locale": PAGE_LOCALE},
    }, api_token)
    single = (result.get('data') or {}).get('pages', {}).get('singleByPath')
    if not isinstance(single, dict):
        return None
    return single.get('id')


def build_wiki_url(page_path):
    """Monta a URL pública final da página considerando o locale."""
    locale_prefix = f"/{PAGE_LOCALE}" if PAGE_LOCALE != "en" else ""
    return f"https://wiki.rpa4all.com{locale_prefix}/{page_path}"


def create_or_update_page(api_token):
    """Faz update se a página já existe, create se não existe."""
    existing_id = get_page_id(api_token)

    if existing_id:
        print(f"[*] Página existente id={existing_id} — fazendo update...", file=sys.stderr)
        result = graphql({
            "query": """
            mutation($id:Int!,$content:String!,$description:String!,$editor:String!,
                     $isPublished:Boolean!,$isPrivate:Boolean!,$locale:String!,
                     $path:String!,$tags:[String]!,$title:String!){
                pages{
                    update(id:$id,content:$content,description:$description,editor:$editor,
                           isPublished:$isPublished,isPrivate:$isPrivate,locale:$locale,
                           path:$path,tags:$tags,title:$title){
                        responseResult{succeeded message}
                        page{id title path}
                    }
                }
            }
            """,
            "variables": {
                "id": existing_id,
                "content": LTFS_CONTENT,
                "description": PAGE_DESC,
                "editor": "markdown",
                "isPublished": True,
                "isPrivate": False,
                "locale": PAGE_LOCALE,
                "path": PAGE_PATH,
                "tags": PAGE_TAGS,
                "title": PAGE_TITLE,
            },
        }, api_token)
        op = (result.get('data') or {}).get('pages', {}).get('update', {})
    else:
        print("[*] Página não existe — criando...", file=sys.stderr)
        result = graphql({
            "query": """
            mutation($content:String!,$description:String!,$editor:String!,
                     $isPublished:Boolean!,$isPrivate:Boolean!,$locale:String!,
                     $path:String!,$tags:[String]!,$title:String!){
                pages{
                    create(content:$content,description:$description,editor:$editor,
                           isPublished:$isPublished,isPrivate:$isPrivate,locale:$locale,
                           path:$path,tags:$tags,title:$title){
                        responseResult{succeeded message}
                        page{id title path}
                    }
                }
            }
            """,
            "variables": {
                "content": LTFS_CONTENT,
                "description": PAGE_DESC,
                "editor": "markdown",
                "isPublished": True,
                "isPrivate": False,
                "locale": PAGE_LOCALE,
                "path": PAGE_PATH,
                "tags": PAGE_TAGS,
                "title": PAGE_TITLE,
            },
        }, api_token)
        op = (result.get('data') or {}).get('pages', {}).get('create', {})

    if result.get('errors'):
        print(f"[✗] GraphQL Error: {result['errors']}", file=sys.stderr)
        return None

    rr = op.get('responseResult', {})
    if rr.get('succeeded'):
        page = op.get('page', {})
        print(f"[✓] OK — id={page.get('id')} path={page.get('path')}", file=sys.stderr)
        return page.get('path')
    else:
        print(f"[✗] {rr.get('message')}", file=sys.stderr)
        return None


def main():
    print("╔════════════════════════════════════════════════════════════╗", file=sys.stderr)
    print("║  Wiki: LTFS Self-Heal System — update-or-create           ║", file=sys.stderr)
    print("╚════════════════════════════════════════════════════════════╝", file=sys.stderr)

    api_token = get_api_token()
    page_path = create_or_update_page(api_token)

    if page_path:
        wiki_url = build_wiki_url(page_path)
        print(f"\n✅ {wiki_url}\n", file=sys.stderr)
        print(wiki_url)
        sys.exit(0)
    else:
        print("\n[✗] Falha ao publicar página", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
