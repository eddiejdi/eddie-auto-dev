"""Script para adicionar variável profile e filtro profile=~$profile ao dashboard Grafana.

Modifica o JSON do dashboard para:
1. Adicionar variável template 'profile' (custom: Todos, conservative, aggressive)
2. Adicionar label profile=~"$profile" em todas as queries que usam coin="$coin"
"""
import json
import re
from pathlib import Path

DASHBOARD_PATH = Path("/home/edenilson/eddie-auto-dev/grafana/btc_trading_dashboard_v3_prometheus.json")

with open(DASHBOARD_PATH) as f:
    dashboard = json.load(f)

# 1. Adicionar variável profile ao templating
profile_var = {
    "current": {
        "selected": True,
        "text": "Todos",
        "value": ".*"
    },
    "hide": 0,
    "includeAll": False,
    "label": "Profile",
    "multi": False,
    "name": "profile",
    "options": [
        {"selected": True, "text": "Todos", "value": ".*"},
        {"selected": False, "text": "conservative", "value": "conservative"},
        {"selected": False, "text": "aggressive", "value": "aggressive"},
        {"selected": False, "text": "default", "value": "default"},
    ],
    "query": ".*,conservative,aggressive,default",
    "queryValue": "",
    "skipUrlSync": False,
    "type": "custom"
}

# Verificar se já existe
existing_vars = dashboard.get("templating", {}).get("list", [])
has_profile = any(v.get("name") == "profile" for v in existing_vars)

if not has_profile:
    existing_vars.append(profile_var)
    dashboard["templating"]["list"] = existing_vars
    print("1/2 Profile variable added to templating")
else:
    print("1/2 SKIP (profile variable already exists)")

# 2. Adicionar profile=~"$profile" em todas as queries que têm coin="$coin"
raw = json.dumps(dashboard)

# Replace: coin="$coin" → coin="$coin",profile=~"$profile"
# Precisa evitar duplicação se profile já estiver lá
old_pattern = 'coin=\\"$coin\\"'
new_pattern = 'coin=\\"$coin\\",profile=~\\"$profile\\"'

if new_pattern not in raw:
    count = raw.count(old_pattern)
    raw = raw.replace(old_pattern, new_pattern)
    print(f"2/2 Updated {count} queries with profile filter")
else:
    print("2/2 SKIP (profile filter already in queries)")

dashboard = json.loads(raw)

# Salvar
with open(DASHBOARD_PATH, 'w') as f:
    json.dump(dashboard, f, indent=2)

print(f"\nDone! Dashboard saved ({DASHBOARD_PATH})")
