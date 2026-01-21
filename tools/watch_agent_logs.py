#!/usr/bin/env python3
"""Watch agent stdout (systemd + local log files) and stream updates.

Usage: ./tools/watch_agent_logs.py

By default monitors systemd services: coordinator.service, diretor.service,
autonomous_remediator.service and local logs: /tmp/coordinator.log, /tmp/diretor.log,
/tmp/agent_logs_watcher.log (rotates by append). Writes combined output to stdout
and to /tmp/agent_logs_watcher.log.
"""
import subprocess
import threading
import time
import sys
import os

SERVICES = [
    'coordinator.service',
    'diretor.service',
    'autonomous_remediator.service'
]

LOCAL_LOGS = [
    '/tmp/coordinator.log',
    '/tmp/diretor.log',
    '/tmp/streamlit_dashboard.log'
]

OUT_LOG = '/tmp/agent_logs_watcher.log'


def run_cmd_stream(cmd, source):
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except Exception as e:
        print(f"[{source}] failed to start stream: {e}")
        return

    with open(OUT_LOG, 'a', encoding='utf-8') as out:
        while True:
            line = p.stdout.readline()
            if not line:
                if p.poll() is not None:
                    break
                time.sleep(0.1)
                continue
            ts = time.strftime('%Y-%m-%d %H:%M:%S')
            formatted = f"[{ts}] {source}: {line.rstrip()}"
            print(formatted)
            out.write(formatted + '\n')
            out.flush()


def tail_file(path):
    # Ensure file exists
    open(path, 'a').close()
    cmd = ['tail', '-F', '-n', '0', path]
    run_cmd_stream(cmd, f'file:{os.path.basename(path)}')


def journal_follow(unit):
    cmd = ['journalctl', '-u', unit, '-f', '-n', '0']
    run_cmd_stream(cmd, f'systemd:{unit}')


def main():
    print('Starting agent logs watcher; combined log at', OUT_LOG)
    # Start journal threads
    threads = []
    for s in SERVICES:
        t = threading.Thread(target=journal_follow, args=(s,), daemon=True)
        t.start()
        threads.append(t)

    # Start tail threads
    for f in LOCAL_LOGS:
        t = threading.Thread(target=tail_file, args=(f,), daemon=True)
        t.start()
        threads.append(t)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('Watcher interrupted, exiting')


if __name__ == '__main__':
    main()
