#!/usr/bin/env python3
"""Bus listener: subscribe to in-process bus and poll DB-IPC every 3s.

Writes concise JSON lines to /tmp/agent_bus_listener.log and prints brief events to stdout.
"""
import time
import json
import logging
from datetime import datetime
import os

LOG_PATH = os.environ.get('AGENT_BUS_LISTENER_LOG', '/tmp/agent_bus_listener.log')

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format='%(asctime)s %(message)s',
)


def _safe_to_dict(m):
    try:
        return m.to_dict()
    except Exception:
        # fallback
        return {
            'id': getattr(m, 'id', None),
            'timestamp': getattr(m, 'timestamp', None),
            'type': getattr(m, 'message_type', None),
            'source': getattr(m, 'source', None),
            'target': getattr(m, 'target', None),
            'content': getattr(m, 'content', None),
            'metadata': getattr(m, 'metadata', None),
        }


def main(poll_seconds: int = 3):
    # Import here to avoid import-time side-effects when used as module
    try:
        from specialized_agents.agent_communication_bus import get_communication_bus
    except Exception as e:
        print('ERROR: cannot import communication bus:', e)
        return

    # Try optional DB-backed IPC helper
    agent_ipc = None
    try:
        from tools import agent_ipc as agent_ipc_mod
        agent_ipc = agent_ipc_mod
    except Exception:
        try:
            import tools.agent_ipc as agent_ipc_mod2
            agent_ipc = agent_ipc_mod2
        except Exception:
            agent_ipc = None

    bus = get_communication_bus()

    seen_ipc_ids = set()

    def on_message(msg):
        data = _safe_to_dict(msg)
        line = json.dumps({'bus_message': data}, default=str, ensure_ascii=False)
        logging.info(line)
        print(f"[bus] {data.get('type')} {data.get('source')}→{data.get('target')} id={data.get('id')}")

    # subscribe
    try:
        bus.subscribe(on_message)
    except Exception as e:
        print('WARN: bus.subscribe failed:', e)

    print(f"Listening to bus; logging -> {LOG_PATH}")

    # Main loop: every poll_seconds, optionally check DB-IPC for pending
    while True:
        try:
            # snapshot current buffer (also logs to file for persistence)
            msgs = bus.get_messages(limit=50)
            for m in msgs:
                # log each as JSON line to ensure persisted record (avoid duplicates)
                data = _safe_to_dict(m)
                line = json.dumps({'bus_snapshot': data}, default=str, ensure_ascii=False)
                logging.info(line)

            # check DB-backed IPC pending requests
            if agent_ipc:
                try:
                    pending = agent_ipc.fetch_pending(limit=20)
                    for p in pending:
                        pid = p.get('id')
                        if pid in seen_ipc_ids:
                            continue
                        seen_ipc_ids.add(pid)
                        entry = {
                            'ipc_id': pid,
                            'source': p.get('source'),
                            'content': p.get('content'),
                            'metadata': p.get('metadata'),
                        }
                        logging.info(json.dumps({'agent_ipc_pending': entry}, default=str, ensure_ascii=False))
                        print(f"[ipc] pending id={pid} from={entry['source']}")
                except Exception as e:
                    logging.info(json.dumps({'ipc_error': str(e)}))

        except KeyboardInterrupt:
            print('Interrupted, exiting')
            break
        except Exception as e:
            logging.exception('Listener loop error:')

        time.sleep(poll_seconds)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Agent bus listener (polls every N seconds)')
    parser.add_argument('--poll', type=int, default=3, help='poll interval seconds')
    args = parser.parse_args()
    main(poll_seconds=args.poll)
