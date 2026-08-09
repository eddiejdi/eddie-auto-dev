#!/usr/bin/env python3
import time
import subprocess
from prometheus_client import Gauge, start_http_server

RETRY_SECONDS = 15
METRIC_PORT = 9527

g_review_queue = Gauge("review_queue_pending", "Number of pending review items in agent_ipc (target=coordinator)")

def query_pending():
    try:
        cmd = ["docker", "exec", "-i", "eddie-postgres", "psql", "-U", "postgres", "-t", "-c", "SELECT count(*) FROM agent_ipc WHERE status='pending' AND target='coordinator';"]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        val = int(out.strip() or 0)
        return val
    except Exception:
        return -1

if __name__ == '__main__':
    start_http_server(METRIC_PORT)
    while True:
        v = query_pending()
        if v >= 0:
            g_review_queue.set(v)
        else:
            g_review_queue.set(-1)
        time.sleep(RETRY_SECONDS)
