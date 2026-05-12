#!/usr/bin/env python3
"""PreToolUse hook: registra docker/systemctl stop para restauração ao fim da sessão."""
import sys, json, re, os

data = json.load(sys.stdin)
cmd = data.get("tool_input", {}).get("command", "") or ""
session = data.get("session_id", "default")
stopfile = f"/tmp/claude-stopped-{session}.jsonl"

if not cmd:
    sys.exit(0)

entries = []

# Extrai host SSH e conteúdo interno do comando
ssh_host = ""
ssh_match = re.search(r'\bssh\b[^"\']*(192\.168\.\d+\.\d+|homelab)\b', cmd)
if ssh_match:
    ssh_host = ssh_match.group(1)
    # Conteúdo entre aspas duplas ou simples após ssh host
    inner = re.search(r'(?:192\.168\.\d+\.\d+|homelab)[^"\']* ["\'](.+?)["\']', cmd, re.DOTALL)
    if inner:
        cmd = inner.group(1)

# docker stop <containers>
for m in re.finditer(r'\bdocker\s+stop\s+([^|&;<>\n]+)', cmd):
    for c in m.group(1).split():
        if c and not c.startswith('-'):
            entries.append({"type": "docker", "name": c, "host": ssh_host})

# docker compose stop / docker-compose stop
if re.search(r'\bdocker(?:\s+-compose|\s+compose)\s+stop\b', cmd):
    dir_match = re.search(r'\bcd\s+([^&|;<>\n]+)', cmd)
    d = dir_match.group(1).strip() if dir_match else ""
    entries.append({"type": "docker-compose", "dir": d, "host": ssh_host})

# systemctl stop <services>
for m in re.finditer(r'\bsystemctl\s+stop\s+([^|&;<>\n]+)', cmd):
    for s in m.group(1).split():
        if s and not s.startswith('-'):
            entries.append({"type": "systemctl", "name": s, "host": ssh_host})

if entries:
    with open(stopfile, "a") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")

sys.exit(0)
