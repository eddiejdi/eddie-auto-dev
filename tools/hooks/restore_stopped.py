#!/usr/bin/env python3
"""Stop hook: restaura serviços parados durante a sessão."""
import sys, json, os, subprocess

data = json.load(sys.stdin)
session = data.get("session_id", "default")
stopfile = f"/tmp/claude-stopped-{session}.jsonl"

if not os.path.exists(stopfile):
    sys.exit(0)

with open(stopfile) as f:
    lines = [l.strip() for l in f if l.strip()]
os.remove(stopfile)

if not lines:
    sys.exit(0)

# Deduplica
seen, entries = set(), []
for l in lines:
    try:
        e = json.loads(l)
        key = f"{e['type']}:{e.get('name') or e.get('dir')}:{e.get('host','')}"
        if key not in seen:
            seen.add(key)
            entries.append(e)
    except Exception:
        pass

if not entries:
    sys.exit(0)

restored, failed = [], []

def run(host, cmd):
    full = ["ssh", host, cmd] if host else ["bash", "-c", cmd]
    try:
        r = subprocess.run(full, capture_output=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False

for e in entries:
    t, host = e.get("type"), e.get("host", "")
    label = e.get("name") or e.get("dir") or "?"
    try:
        if t == "docker":
            ok = run(host, f"docker start {e['name']}")
        elif t == "docker-compose":
            d = e.get("dir", "")
            ok = run(host, f"cd {d} && docker compose start" if d else "docker compose start")
        elif t == "systemctl":
            ok = run(host, f"systemctl start {e['name']}")
        else:
            continue
        (restored if ok else failed).append(f"{t}:{label}")
    except Exception as ex:
        failed.append(f"{t}:{label}(erro:{ex})")

if not restored and not failed:
    sys.exit(0)

parts = []
if restored:
    parts.append("Restaurados: " + ", ".join(restored))
if failed:
    parts.append("Falha: " + ", ".join(failed))

msg = "⚙️ Serviços restaurados ao encerrar sessão — " + " | ".join(parts)
print(json.dumps({"systemMessage": msg}))
