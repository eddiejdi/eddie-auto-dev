#!/usr/bin/env python3
"""OperationsAgent (standalone) - DB-backed and bus-backed remediation handler.

This process listens on the in-memory `AgentCommunicationBus` (when running
in the same Python process) and also polls a Postgres-backed queue using
`tools.agent_ipc` so it can run as a separate process in production.

Behavior: dry-run by default; set `AUTONOMOUS_MODE=1` to allow real actions.
"""

import os
import time
import threading
import subprocess

from specialized_agents.agent_communication_bus import get_communication_bus, MessageType


AUTONOMOUS = os.environ.get('AUTONOMOUS_MODE', '0') == '1'
POLL = int(os.environ.get('OPS_AGENT_POLL', '5'))
USE_DB = bool(os.environ.get('DATABASE_URL'))

try:
    from tools import agent_ipc
except Exception:
    agent_ipc = None

# Optional HTTP API client for RCA queue (disabled by default).
try:
    from tools import agent_api_client
except Exception:
    agent_api_client = None


def _run_actions(url: str):
    actions = []
    # Fly.io removed: no fly-tunnel actions are configured.

    results = []
    for name, argv in actions:
        if AUTONOMOUS:
            try:
                out = subprocess.check_output(argv, stderr=subprocess.STDOUT, text=True)
                results.append((name, 0, out.strip()))
            except subprocess.CalledProcessError as e:
                results.append((name, e.returncode, e.output))
        else:
            results.append((name, None, 'dry-run'))

    summary = '\n'.join([f"{n}: code={c} out={o[:200]}" for (n, c, o) in results])
    return summary


def handle_message(msg):
    try:
        if msg.message_type != MessageType.REQUEST or msg.target != 'OperationsAgent':
            return
        url = msg.metadata.get('url') if msg.metadata else None
        print(f"[OperationsAgent] Bus request from {msg.source}: {msg.content}")
        summary = _run_actions(url or 'unknown')
        # publish response on bus
        bus = get_communication_bus()
        bus.publish(MessageType.RESPONSE, 'OperationsAgent', msg.source, f"Actions for {url}:\n{summary}", {'url': url})
        # if DB request id provided, mark it done
        try:
            rid = msg.metadata.get('request_id')
            if rid and agent_ipc:
                agent_ipc.respond(rid, 'OperationsAgent', summary)
        except Exception:
            pass
    except Exception as e:
        print(f"[OperationsAgent] handler error: {e}")


def db_loop():
    if not agent_ipc:
        return
    print('[OperationsAgent] Starting DB poll loop')
    while True:
        try:
            rows = agent_ipc.fetch_pending('OperationsAgent', limit=5)
            for r in rows:
                rid = r['id']
                src = r.get('source')
                content = r.get('content')
                print(f"[OperationsAgent] DB request {rid} from {src}: {content[:200]}")
                summary = _run_actions(r.get('metadata', {}).get('url') if r.get('metadata') else None)
                try:
                    agent_ipc.respond(rid, 'OperationsAgent', summary)
                except Exception as e:
                    print(f"[OperationsAgent] failed to respond to {rid}: {e}")
        except Exception:
            pass
        time.sleep(POLL)


def api_loop():
    """Poll the lightweight Agent API if configured (AGENT_API_URL + ALLOW_AGENT_API=1).

    This loop is safe for local development: by default the client is disabled
    unless explicitly enabled via environment variables. Do not enable until
    after deploy on homelab.
    """
    if not agent_api_client:
        return
    print('[OperationsAgent] Starting API poll loop')
    while True:
        try:
            rows = agent_api_client.fetch_pending(limit=10)
            for r in rows:
                issue = r.get('issue')
                print(f"[OperationsAgent] API RCA available: {issue}")
                # dry-run: do not perform destructive actions unless AUTONOMOUS
                summary = _run_actions(None)
                # acknowledge via API if allowed
                try:
                    ok = agent_api_client.ack_rca(issue)
                    print(f"[OperationsAgent] ack {issue}: {ok}")
                except Exception as e:
                    print(f"[OperationsAgent] failed ack {issue}: {e}")
        except Exception:
            pass
        time.sleep(POLL)


def main():
    bus = get_communication_bus()
    bus.subscribe(handle_message)
    if agent_ipc:
        t = threading.Thread(target=db_loop, daemon=True)
        t.start()
    # start API loop if client available
    if agent_api_client:
        t2 = threading.Thread(target=api_loop, daemon=True)
        t2.start()
    print('[OperationsAgent] Ready')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('Exiting')


if __name__ == '__main__':
    main()
