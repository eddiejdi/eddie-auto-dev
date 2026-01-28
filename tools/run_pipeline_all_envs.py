#!/usr/bin/env python3
"""Run pipeline across known environments: health checks, tests, optional deploys.

Usage: set environment variables as needed (see tools/systemd/autonomous_remediator.env.example)
and run: python3 tools/run_pipeline_all_envs.py
"""
import os
import time
import requests
import subprocess
from urllib.parse import urljoin

# Fly.io environments removed — system no longer uses Fly.io tunnels.
# Keep ENVS empty to avoid attempts to operate on non-existent Fly apps.
ENVS = {}


def log(msg: str):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def check_health(url: str, timeout=10):
    try:
        h = urljoin(url, '/health')
        r = requests.get(h, timeout=timeout)
        return r.status_code == 200, r.status_code
    except Exception as e:
        return False, str(e)


def run_fly_deploy(app: str, token: str):
    # Fly.io deployment disabled: this function is a no-op to avoid calling flyctl.
    log(f"run_fly_deploy called for app={app} but Fly.io support is disabled in this repository")
    return False


if __name__ == '__main__':
    fly_token = os.environ.get('TUNNEL_API_TOKEN')

    from tools import autonomous_remediator as rem

    # No Fly.io environments configured — nothing to check here.
    if not ENVS:
        log('No environments configured in ENVS — skipping pipeline checks')
    else:
        for name, info in ENVS.items():
            url = info['url']
            app = info['app']
            ok, code = check_health(url)
            if ok:
                log(f"{name}: {url} healthy ({code})")
            else:
                log(f"{name}: {url} UNHEALTHY -> {code}")
                # attempt remediation via remediator commands (no flyctl steps by default)
                cmds = rem.commands_for_remediation() + rem.extra_conditional_commands()
                dry = not (os.environ.get('AUTONOMOUS_MODE', '0') == '1')
                log(f"Executing remediation ({'dry-run' if dry else 'live'}) for {name}")
                for c in cmds:
                    rem.run_cmd(c, dry_run=dry)

    log('Pipeline run complete')
