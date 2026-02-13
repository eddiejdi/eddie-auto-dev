#!/usr/bin/env python3
"""Audita repositório em busca de segredos hardcoded e gera relatório.

Uso:
  python3 scripts/audit_and_migrate_secrets.py --dry-run

Opções:
  --dry-run    : apenas reporta resultados (default)
  --apply      : tenta armazenar os segredos detectados no Secrets Agent (requer env vars)
  --mask       : comprimento mínimo do segredo para considerar (default 8)

AVISO: o modo --apply irá enviar valores ao Secrets Agent usando SECRETS_AGENT_URL e SECRETS_AGENT_API_KEY do ambiente.
"""
import os
import re
import sys
import json
from pathlib import Path
import argparse
import requests

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {'.git', '.venv', '.venv_selenium', '__pycache__', 'node_modules'}

PATTERNS = [
    r"(?i)\b(API[_-]?KEY)\b\s*[:=]\s*['\"]([A-Za-z0-9_\-\+=/.]{8,})['\"]",
    r"(?i)\b(API[_-]?SECRET)\b\s*[:=]\s*['\"]([A-Za-z0-9_\-\+=/.]{8,})['\"]",
    r"(?i)\b(ACCESS[_-]?TOKEN|ACCESS[_-]?KEY|TOKEN|SECRET|PASSWORD|PASS|PWD)\b\s*[:=]\s*['\"]([A-Za-z0-9_\-\+=/.]{8,})['\"]",
    r"(?i)['\"](eyJ[A-Za-z0-9_\-\.]{30,})['\"]",  # JWT-like
    r"(?i)['\"]([A-Za-z0-9]{32,})['\"]"  # long hex/alpha numeric
]

def iter_files(root: Path):
    for p in root.rglob('*'):
        if p.is_dir():
            if p.name in EXCLUDE_DIRS:
                # skip entire directory
                for _ in p.rglob('*'):
                    break
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.suffix in {'.pyc', '.db', '.sqlite', '.log'}:
            continue
        yield p

def mask(v: str):
    if len(v) <= 8:
        return '****'
    return v[:4] + '...' + v[-4:]

def scan(dry_run=True, min_len=8, apply=False):
    findings = []
    for f in iter_files(ROOT):
        try:
            text = f.read_text(encoding='utf-8')
        except Exception:
            continue
        for pat in PATTERNS:
            for m in re.finditer(pat, text):
                # capture the last group as value if exists
                groups = m.groups()
                if not groups:
                    continue
                # value may be in different positions
                val = None
                name = None
                if len(groups) == 1:
                    val = groups[0]
                elif len(groups) >= 2:
                    # prefer second group as value
                    name = groups[0]
                    val = groups[1]
                if not val or len(val) < min_len:
                    continue
                findings.append({
                    'file': str(f.relative_to(ROOT)),
                    'lineno': text[:m.start()].count('\n') + 1,
                    'name': name or '<match>',
                    'value_masked': mask(val),
                    'value_raw': val
                })
    # deduplicate by file+value
    uniq = {}
    for it in findings:
        key = (it['file'], it['value_raw'])
        if key not in uniq:
            uniq[key] = it

    results = list(uniq.values())

    print('\n== Secret audit report ==')
    print(f'Found {len(results)} candidate secrets (min_len={min_len}).')
    for r in results:
        print(f"- {r['file']}:{r['lineno']}  {r['name']}  -> {r['value_masked']}")

    if apply:
        sa_url = os.getenv('SECRETS_AGENT_URL', 'http://localhost:8088')
        sa_key = os.getenv('SECRETS_AGENT_API_KEY', '')
        if not sa_key:
            print('\nSECRETS_AGENT_API_KEY not set; aborting apply')
            return results
        headers = {'X-API-KEY': sa_key, 'Content-Type': 'application/json'}
        for r in results:
            # construct secret name: eddie/<file-path>/<name-or-unknown>
            fname = r['file'].replace('/', '_').replace('.py', '')
            sname = f"eddie/{fname}/{r['name'] or 'secret'}"
            payload = {'name': sname, 'field': 'password', 'value': r['value_raw'], 'notes': f"Imported from {r['file']}"}
            try:
                resp = requests.post(f"{sa_url}/secrets", headers=headers, json=payload, timeout=5)
                if resp.status_code in (200, 201):
                    print(f"Stored secret: {sname}")
                else:
                    print(f"Failed to store {sname}: {resp.status_code} {resp.text[:200]}")
            except Exception as e:
                print(f"Error storing {sname}: {e}")

    return results

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dry-run', action='store_true', default=True, help='Only scan and report')
    p.add_argument('--apply', action='store_true', help='Send detected secrets to Secrets Agent')
    p.add_argument('--min-len', type=int, default=8)
    args = p.parse_args()

    findings = scan(dry_run=args.dry_run, min_len=args.min_len, apply=args.apply)
    # write report
    out = ROOT / 'reports' / 'secret_audit.json'
    out.parent.mkdir(exist_ok=True)
    safe = [{k: v for k, v in f.items() if k != 'value_raw'} for f in findings]
    out.write_text(json.dumps({'count': len(findings), 'results': safe}, indent=2))
    print(f"\nReport saved to {out}")

if __name__ == '__main__':
    main()
