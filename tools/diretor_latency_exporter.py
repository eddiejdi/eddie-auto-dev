#!/usr/bin/env python3
"""Prometheus exporter: Diretor response latency (reads agent_ipc).

Run as: DATABASE_URL=... python3 tools/diretor_latency_exporter.py
Exposes /metrics on port 9410 by default.
"""
import os
import time
import sys
try:
    from prometheus_client import start_http_server, Histogram, Gauge
except Exception:
    print('prometheus_client not installed')
    raise
import psycopg2

DATABASE_URL = os.getenv('DATABASE_URL')
PORT = int(os.getenv('PORT', '9410'))
POLL = int(os.getenv('POLL', '30'))

HIST = Histogram('diretor_response_seconds', 'Director response latency in seconds')
LAST = Gauge('diretor_last_response_seconds', 'Last director response seconds')


def query_and_update():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT extract(epoch from (responded_at - created_at))::double precision AS latency
                FROM agent_ipc
                WHERE responded_at IS NOT NULL
                  AND target='DIRETOR'
                  AND created_at > now() - interval '7 days'
                ORDER BY id DESC
                LIMIT 1000
                """
            )
            rows = cur.fetchall()
            for (lat,) in rows:
                if lat is None:
                    continue
                HIST.observe(lat)
                LAST.set(lat)
    finally:
        conn.close()


def main():
    if not DATABASE_URL:
        print('DATABASE_URL not set', file=sys.stderr)
        sys.exit(2)

    start_http_server(PORT)
    print(f'diretor_latency_exporter listening on :{PORT}', file=sys.stderr)

    while True:
        try:
            query_and_update()
        except Exception as e:
            print('query error', e, file=sys.stderr)
        time.sleep(POLL)


if __name__ == '__main__':
    main()
