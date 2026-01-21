#!/usr/bin/env python3
"""Autonomous Remediator

Monitora health endpoints configurados para o túnel Fly.io e executa ações de
remediação (restart do túnel, WireGuard, services) quando detecta indisponibilidade.

Por segurança o modo padrão é `--dry-run` (não executa comandos, apenas registra).
Para permitir ações reais defina `AUTONOMOUS_MODE=1` no ambiente e execute sem
`--dry-run` somente após revisar os comandos.
"""
import argparse
import os
import time
import subprocess
import requests
from urllib.parse import urljoin

DEFAULT_URLS = [
    "https://homelab-tunnel-sparkling-sun-3565.fly.dev",
]

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, os.pardir))
LOGFILE = os.environ.get("AUTONOMOUS_LOG", os.path.join(REPO_ROOT, "autonomous_remediator.log"))


def log(msg: str):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
    try:
        d = os.path.dirname(LOGFILE)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
        with open(LOGFILE, "a") as f:
            f.write(line)
    except Exception:
        # best-effort: if writing to logfile fails, continue and print
        pass
    print(line, end="")


def check_health(url: str, timeout: int = 5) -> bool:
    try:
        h = urljoin(url, "/health")
        r = requests.get(h, timeout=timeout)
        log(f"Checked {h} -> {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        log(f"Health check failed for {url}: {e}")
        return False


def commands_for_remediation() -> list:
    cmds = []
    # Try restart helper in repo if exists
    if os.path.exists("flyio-tunnel/fly-tunnel.sh"):
        cmds.append(("Restart fly-tunnel app", ["bash", "flyio-tunnel/fly-tunnel.sh", "restart"]))
    # Try common script path
    if os.path.exists("flyio-tunnel/scripts/flyio-tunnel.sh"):
        cmds.append(("Restart fly-tunnel (scripts)", ["bash", "flyio-tunnel/scripts/flyio-tunnel.sh", "restart"]))

    # WireGuard restart (requires sudo)
    cmds.append(("Restart fly0 WireGuard", ["sudo", "wg-quick", "down", "fly0"]))
    cmds.append(("Restart fly0 WireGuard up", ["sudo", "wg-quick", "up", "fly0"]))

    # Restart services
    cmds.append(("Restart specialized-agents service", ["sudo", "systemctl", "restart", "specialized-agents"]))
    cmds.append(("Restart eddie-telegram-bot service", ["sudo", "systemctl", "restart", "eddie-telegram-bot"]))

    return cmds


def extra_conditional_commands():
    """Return optional commands requiring external credentials or tools.

    - If `FLY_API_TOKEN` and `FLY_APP` are set, add `flyctl deploy` command.
    - If `DNS_UPDATE_SCRIPT` is set and executable, add it as remediation step.
    """
    cmds = []
    fly_token = os.environ.get("FLY_API_TOKEN")
    fly_app = os.environ.get("FLY_APP")
    if fly_token and fly_app:
        # Use a wrapper that calls flyctl with token env
        cmds.append((
            f"flyctl deploy {fly_app}",
            ["/bin/bash", "-c", f"FLY_API_TOKEN='{fly_token}' flyctl deploy -a {fly_app}"],
        ))

    dns_script = os.environ.get("DNS_UPDATE_SCRIPT")
    if dns_script and os.path.exists(dns_script) and os.access(dns_script, os.X_OK):
        cmds.append(("Run DNS update script", ["bash", dns_script]))

    return cmds


def run_cmd(cmd, dry_run=True):
    name, argv = cmd
    log(f"Action: {name} -> {' '.join(argv)}")
    if dry_run:
        log(f"Dry-run: not executing {argv}")
        try:
            notify_bus(f"Dry-run would execute: {name}")
        except Exception:
            pass
        return 0, "dry-run"
    try:
        out = subprocess.check_output(argv, stderr=subprocess.STDOUT, text=True)
        log(f"Command output: {out.strip()}")
        try:
            notify_bus(f"Executed: {name} -> success")
        except Exception:
            pass
        return 0, out
    except subprocess.CalledProcessError as e:
        log(f"Command failed (code {e.returncode}): {e.output}")
        try:
            notify_bus(f"Executed: {name} -> failed (code {e.returncode})")
        except Exception:
            pass
        return e.returncode, e.output


def notify_bus(message: str):
    """Try to publish a coordinator notification to the local communication bus.

    This is optional and best-effort: if the remediator runs outside of the
    project context the import may fail and we silently ignore it.
    """
    try:
        import sys
        sys.path.insert(0, os.getcwd())
        from specialized_agents.agent_communication_bus import get_communication_bus, MessageType
        bus = get_communication_bus()
        bus.publish(MessageType.COORDINATOR, 'autonomous_remediator', 'agent_coordinator', message)
        log('Notified communication bus')
    except Exception:
        # best-effort only
        pass


def request_agent_remediation(url: str, suggested_cmds: list, timeout: int = 30) -> bool:
    """Publish a remediation request to the OperationsAgent and wait briefly for a response.

    Returns True if an agent response was observed in the bus within the timeout.
    """
    try:
        import sys
        sys.path.insert(0, os.getcwd())
        from specialized_agents.agent_communication_bus import get_communication_bus, MessageType

        bus = get_communication_bus()
        content = f"Detected unhealthy URL {url}. Suggested remediation steps: { [c[0] for c in suggested_cmds] }"
        msg = bus.publish(MessageType.REQUEST, 'autonomous_remediator', 'OperationsAgent', content, {'url': url})
        log(f"Published remediation request to OperationsAgent: {msg.id if msg else 'nil'}")

        # Wait for a response message from OperationsAgent addressing this URL
        waited = 0
        poll = 2
        while waited < timeout:
            msgs = bus.get_messages(limit=50, source='OperationsAgent')
            for m in msgs:
                if url in m.content or m.metadata.get('url') == url:
                    log(f"Observed OperationsAgent response: {m.id} -> {m.content[:200]}")
                    return True
            time.sleep(poll)
            waited += poll
        log("No OperationsAgent response within timeout")
        # If no response observed on the in-memory bus, try DB-backed IPC if available
        try:
            from tools import agent_ipc
            if os.environ.get('DATABASE_URL'):
                req_id = agent_ipc.publish_request('autonomous_remediator', 'OperationsAgent', content, {'url': url})
                log(f"Published remediation request to DB (id={req_id})")
                resp = agent_ipc.poll_response(req_id, timeout=timeout)
                if resp:
                    log(f"Observed DB response for request {req_id}: {resp.get('response')[:200]}")
                    return True
        except Exception as e:
            log(f"DB IPC attempt failed: {e}")

        return False
    except Exception as e:
        log(f"Failed to request agent remediation: {e}")
        return False


def main(timeout: int = None, poll: int = 10, dry_run: bool = True):
    # Attempt to load an in-process OperationsAgent handler so delegation works
    try:
        import sys
        sys.path.insert(0, os.getcwd())
        from tools.operations_agent import handle_message as _ops_handle
        from specialized_agents.agent_communication_bus import get_communication_bus
        get_communication_bus().subscribe(_ops_handle)
        log("Loaded in-process OperationsAgent handler")
    except Exception:
        # If not available or fails, delegation will still publish to bus
        pass

    urls = DEFAULT_URLS[:]
    # Try to read URL from fly-tunnel.sh if present
    ft = "flyio-tunnel/fly-tunnel.sh"
    if os.path.exists(ft):
        try:
            for line in open(ft):
                line = line.strip()
                if line.startswith("URL="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    urls = [val]
                    log(f"Discovered URL from {ft}: {val}")
                    break
        except Exception:
            pass

        # Prefer the canonical URL returned by the script when possible
        try:
            out = subprocess.check_output(["bash", ft, "url"], text=True).strip()
            if out:
                urls = [out]
                log(f"Discovered URL from {ft} command: {out}")
        except Exception as e:
            log(f"Could not execute {ft} url command: {e}")

    start = time.time()
    while True:
        for url in urls:
            healthy = check_health(url)
            if not healthy:
                log(f"Detected unhealthy URL: {url}")
                cmds = commands_for_remediation()
                # First try delegating to OperationsAgent via the communication bus
                delegated = False
                if os.environ.get('AUTONOMOUS_MODE', '0') == '1':
                    try:
                        delegated = request_agent_remediation(url, cmds, timeout=30)
                    except Exception:
                        delegated = False

                if delegated:
                    log(f"Delegated remediation for {url} to OperationsAgent; waiting to verify")
                    # give agent a short time to act before checking
                    time.sleep(5)
                else:
                    log(f"No agent response; performing local remediation (dry_run={dry_run})")
                    for c in cmds:
                        run_cmd(c, dry_run=dry_run)

                # after remediation (agent or local), short wait then recheck
                time.sleep(5)
                healthy_after = check_health(url)
                if healthy_after:
                    log(f"Remediation succeeded for {url}")
                else:
                    log(f"Remediation did not restore {url}")

        if timeout is not None and (time.time() - start) > timeout:
            log("Timeout reached, exiting monitor")
            return

        time.sleep(poll)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--timeout', type=int, help='Seconds to run before exiting')
    p.add_argument('--poll', type=int, default=10, help='Poll interval seconds')
    p.add_argument('--dry-run', action='store_true', help='Do not execute remediation commands')
    args = p.parse_args()

    autonomous_mode = os.environ.get('AUTONOMOUS_MODE', '0') == '1'
    dry = args.dry_run or not autonomous_mode
    if not autonomous_mode:
        log('AUTONOMOUS_MODE not enabled — running in dry-run mode')

    main(timeout=args.timeout, poll=args.poll, dry_run=dry)
