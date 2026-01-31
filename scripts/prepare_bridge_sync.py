#!/usr/bin/env python3
"""Prepare a sync payload for the webui_bus_chat_bridge function.
Usage:
  python3 scripts/prepare_bridge_sync.py --export /tmp/functions_export.json --out /tmp/sync_payload.json --bridge-file openwebui_chat_bridge_function.py --coordinator http://192.168.15.10:8503
"""
import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument('--export', required=True)
parser.add_argument('--out', required=True)
parser.add_argument('--bridge-file', default='openwebui_chat_bridge_function.py')
parser.add_argument('--coordinator', default='http://192.168.15.10:8503')
args = parser.parse_args()

with open(args.export, 'r') as f:
    data = json.load(f)

with open(args.bridge_file, 'r') as f:
    content = f.read()

found = None
for func in data:
    if func.get('id') == 'webui_bus_chat_bridge':
        func['content'] = content
        func['valves'] = {'COORDINATOR_API': args.coordinator}
        found = func
        break

if not found:
    raise SystemExit('webui_bus_chat_bridge not found in export')

out = {'functions': [found]}
with open(args.out, 'w') as f:
    json.dump(out, f, indent=2)

print('Prepared', args.out)
