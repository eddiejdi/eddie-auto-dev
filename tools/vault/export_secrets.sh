#!/usr/bin/env bash
set -euo pipefail
# Export environment variables from a Bitwarden-compatible vault using the `bw` CLI.
# Requires: `bw` CLI installed and `BW_SESSION` set (unlocked session).

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
MAP_FILE="$ROOT_DIR/vault/secret_map.json"

if [ ! -x "$(command -v bw || true)" ]; then
  echo "ERROR: 'bw' CLI not found. Install bw and ensure a session is unlocked." >&2
  exit 2
fi

if [ -z "${BW_SESSION:-}" ]; then
  echo "ERROR: BW_SESSION not set. Run 'bw login' and 'bw unlock' (or export BW_SESSION)." >&2
  exit 2
fi

if [ ! -f "$MAP_FILE" ]; then
  echo "ERROR: secret map not found: $MAP_FILE" >&2
  exit 2
fi

python3 - <<'PY'
import json, os, subprocess, sys
mapf = os.path.join(os.path.dirname(__file__), 'secret_map.json')
with open(mapf) as f:
    mappings = json.load(f)

def get_field(item, field):
    # try bw get password <item>
    try:
        r = subprocess.run(["bw","get","password",item], capture_output=True, text=True, check=True)
        return r.stdout.strip()
    except subprocess.CalledProcessError:
        pass
    # fallback to item JSON
    r = subprocess.run(["bw","get","item",item], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"# ERROR fetching {item}: {r.stderr.strip()}", file=sys.stderr)
        return ""
    data = json.loads(r.stdout)
    if field == 'notes':
        return data.get('notes','')
    for f in data.get('fields',[]):
        if f.get('name')==field:
            return f.get('value','')
    login = data.get('login',{})
    if field in login:
        return login.get(field,'')
    return ''

for env, spec in mappings.items():
    val = get_field(spec['item'], spec.get('field','password'))
    if val:
        # print export lines for the caller to eval
        print(f'export {env}="{val.replace("\"","\\\"")}"')

PY
