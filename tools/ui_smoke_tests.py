#!/usr/bin/env python3
"""Smoke tests for Streamlit dashboards and API.

Checks main pages for expected content and API endpoints.
"""
import requests
from bs4 import BeautifulSoup
import json
import sys

import os

HOST = os.environ.get('HOMELAB_HOST', 'localhost')

PAGES = {
    "dashboard": f"http://{HOST}:8501/",
    "api_status": f"http://{HOST}:8503/status",
    "api_docs": f"http://{HOST}:8503/docs",
    "conversation_monitor": f"http://{HOST}:8505/",
}

EXPECT = {
    "dashboard": ["Agentes", "Agentes Programadores", "Agentes"],
    "api_status": ["timestamp", "active_agents", "llm_config"],
    "api_docs": ["Swagger", "OpenAPI", "paths"],
    "conversation_monitor": ["Conversations", "WS:", "Nenhuma conversa"],
}

def fetch(url, timeout=5):
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code, r.text
    except Exception as e:
        return None, str(e)

def check_page(name, url):
    code, body = fetch(url)
    ok = False
    details = {"url": url, "status_code": code}
    if code and code >= 200 and code < 400:
        lower = body.lower()
        found = []
        for token in EXPECT.get(name, []):
            found.append({"token": token, "present": token.lower() in lower})
        details["found"] = found
        ok = all(f["present"] for f in found if f["token"])
    else:
        details["error"] = body

    return ok, details

def main():
    results = {}
    for name, url in PAGES.items():
        ok, details = check_page(name, url)
        results[name] = {"ok": ok, "details": details}

    # Extra: check websocket endpoint availability (tcp) by attempting HTTP upgrade URL pattern
    # Not a full websocket test here; just report URL.
    results["websocket_interceptor"] = {"url": f"ws://{HOST}:8503/interceptor/ws/messages"}

    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(2)
