#!/usr/bin/env python3
"""List Agents from Agents API and optionally save to eddie-copilot/known_agents.json

Usage:
  python scripts/list_agents.py [--write]
"""
import os
import sys
import json
import argparse
from urllib.parse import urljoin

import requests


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true", help="Write known agents to eddie-copilot/known_agents.json")
    args = p.parse_args()

    base = os.environ.get("AGENTS_API", os.environ.get("EDDIE_AGENTS_API", "http://localhost:8503"))
    url = urljoin(base.rstrip('/') + '/', 'agents')

    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"Erro ao consultar {url}: {e}")
        sys.exit(2)

    langs = data.get('available_languages') or data.get('available') or []
    print("Available languages/agents:")
    for l in langs:
        print(" -", l)

    if args.write:
        out_dir = os.path.join(os.path.dirname(__file__), '..', 'eddie-copilot')
        out_file = os.path.join(out_dir, 'known_agents.json')
        try:
            os.makedirs(out_dir, exist_ok=True)
            with open(out_file, 'w') as f:
                json.dump(langs, f, indent=2)
            print(f"Wrote {out_file}")
        except Exception as e:
            print(f"Failed to write {out_file}: {e}")


if __name__ == '__main__':
    main()
