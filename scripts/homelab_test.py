#!/usr/bin/env python3
"""Basic homelab checks via Agents API

Checks:
 - GET /health
 - GET /agents
 - GET /homelab/health (if available)

Usage:
  python scripts/homelab_test.py
"""
import os
import sys
import requests
from urllib.parse import urljoin


def call(base, path):
    url = urljoin(base.rstrip('/') + '/', path.lstrip('/'))
    try:
        r = requests.get(url, timeout=6)
        return r.status_code, r.text[:200]
    except Exception as e:
        return None, str(e)


def main():
    base = os.environ.get('AGENTS_API', os.environ.get('EDDIE_AGENTS_API', 'http://localhost:8503'))
    print('Agents API base:', base)

    for p in ('/health', '/agents', '/homelab/health', '/homelab'):
        code, text = call(base, p)
        print(f'{p} ->', code, '-', text)


if __name__ == '__main__':
    main()
