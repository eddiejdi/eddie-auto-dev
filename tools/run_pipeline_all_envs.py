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

ENVS = {
    'PROD': {
        'app': 'homelab-tunnel-sparkling-sun-3565',
        'url': 'https://homelab-tunnel-sparkling-sun-3565.fly.dev'
    },
    'HOM': {
        'app': 'homelab-tunnel-hom',
        'url': 'https://homelab-tunnel-hom.fly.dev'
    },
    'CER': {
        'app': 'homelab-tunnel-cer',
        'url': 'https://homelab-tunnel-cer.fly.dev'
    }
}


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
    cmd = f"FLY_API_TOKEN='{token}' flyctl deploy -a {app}"
    log(f"Running: {cmd}")
    try:
        out = subprocess.check_output(['/bin/bash', '-c', cmd], stderr=subprocess.STDOUT, text=True)
        log(f"flyctl output: {out[:400]}")
        # If minimal mode requested, apply scale commands
        fly_minimal = os.environ.get('FLY_MINIMAL', os.environ.get('FLY_MINIMAL_ENV', '0'))
        if str(fly_minimal) == '1':
            try:
                sc1 = f"FLY_API_TOKEN='{token}' flyctl scale vm shared-cpu-1x -a {app}"
                log(f"Applying: {sc1}")
                subprocess.check_output(['/bin/bash', '-c', sc1], stderr=subprocess.STDOUT, text=True)
                sc2 = f"FLY_API_TOKEN='{token}' flyctl scale count 1 -a {app}"
                log(f"Applying: {sc2}")
                subprocess.check_output(['/bin/bash', '-c', sc2], stderr=subprocess.STDOUT, text=True)
            except subprocess.CalledProcessError as e:
                log(f"flyctl scale failed: {e.output}")
        return True
    except subprocess.CalledProcessError as e:
        log(f"flyctl failed: {e.output}")
        return False


if __name__ == '__main__':
    fly_token = os.environ.get('FLY_API_TOKEN')

    from tools import autonomous_remediator as rem

    for name, info in ENVS.items():
        url = info['url']
        app = info['app']
        ok, code = check_health(url)
        if ok:
            log(f"{name}: {url} healthy ({code})")
        else:
            log(f"{name}: {url} UNHEALTHY -> {code}")
            # try local tunnel test if available
            if os.path.exists('flyio-tunnel/fly-tunnel.sh'):
                log(f"Running local tunnel test script for {name} (if supports override)")
                try:
                    subprocess.run(['bash', 'flyio-tunnel/fly-tunnel.sh', 'test'], check=False)
                except Exception as e:
                    log(f"Local tunnel test failed: {e}")

            # attempt remediation via remediator commands
            cmds = rem.commands_for_remediation() + rem.extra_conditional_commands()
            dry = not (os.environ.get('AUTONOMOUS_MODE', '0') == '1')
            log(f"Executing remediation ({'dry-run' if dry else 'live'}) for {name}")
            for c in cmds:
                rem.run_cmd(c, dry_run=dry)

            # if fly token present and specific app env var exists, attempt flyctl deploy
            env_app_var = f'FLY_APP_{name}'
            app_override = os.environ.get(env_app_var)
            target_app = app_override or app
            if fly_token:
                success = run_fly_deploy(target_app, fly_token)
                if success:
                    log(f"flyctl deploy succeeded for {target_app}")
                else:
                    log(f"flyctl deploy failed for {target_app}")
            else:
                log('No FLY_API_TOKEN set — skipping flyctl deploy')

    log('Pipeline run complete')
