#!/usr/bin/env python3
"""Auto-validate Fly redirect/login page and notify DIRETOR until login appears.
Saves success marker to /tmp/redirect_verified.json and logs to /tmp/auto_validate.log
"""
import time
import subprocess
import pathlib
import importlib.util
import json

URL = 'https://homelab-tunnel-sparkling-sun-3565.fly.dev/auth?redirect=%2F'
CHECK_PHRASE = 'Faça login em Open WebUI'
OUT_MARKER = '/tmp/redirect_verified.json'
LOG = '/tmp/auto_validate.log'

# load bus
bus_path = pathlib.Path(__file__).resolve().parents[1] / 'specialized_agents' / 'agent_communication_bus.py'
spec = importlib.util.spec_from_file_location('agent_bus_local', str(bus_path))
agent_bus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_bus)
get_communication_bus = agent_bus.get_communication_bus
MessageType = agent_bus.MessageType


def fetch_body():
    try:
        body = subprocess.check_output(['curl','-sS', URL], text=True, timeout=30)
        return body
    except Exception as e:
        return ''


def publish_to_diretor(status, note, body_snippet=''):
    bus = get_communication_bus()
    content = json.dumps({
        'status': status,
        'note': note,
        'url': URL,
        'snippet': body_snippet
    }, ensure_ascii=False)
    bus.publish(MessageType.REQUEST, 'auto-validator', 'DIRETOR', content, {})


def main(poll=30, timeout=3600):
    start = time.time()
    with open(LOG, 'a', encoding='utf-8') as logf:
        logf.write(f"[auto_validate] started, URL={URL}\n")
    while True:
        body = fetch_body()
        snippet = body[:2000] if body else ''
        found = CHECK_PHRASE in body
        ts = time.strftime('%Y-%m-%dT%H:%M:%S')
        with open(LOG, 'a', encoding='utf-8') as logf:
            logf.write(f"{ts} - found={found}\n")
        if found:
            publish_to_diretor('ok', 'Login page detected', snippet)
            marker = {
                'timestamp': ts,
                'url': URL,
                'status': 'login_detected'
            }
            with open(OUT_MARKER, 'w', encoding='utf-8') as f:
                json.dump(marker, f, ensure_ascii=False, indent=2)
            with open(LOG, 'a', encoding='utf-8') as logf:
                logf.write(f"{ts} - success marker written to {OUT_MARKER}\n")
            return 0
        else:
            publish_to_diretor('pending', 'Login page not yet detected', snippet[:500])
        if time.time() - start > timeout:
            publish_to_diretor('timeout', f'Validation timed out after {timeout}s', '')
            with open(LOG, 'a', encoding='utf-8') as logf:
                logf.write(f"{ts} - timeout after {timeout}s\n")
            return 2
        time.sleep(poll)


if __name__ == '__main__':
    exit(main())
