#!/usr/bin/env python3
import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/autocoinbot"
)
POLL_INTERVAL = int(os.environ.get("COORD_POLL_INTERVAL", "5"))


def connect():
    return psycopg2.connect(DATABASE_URL)


def iso_now():
    return datetime.now(timezone.utc)


def main(timeout=None):
    start_time = iso_now()
    last_seen = start_time

    print(
        f"Watching Postgres for coordinator messages since {last_seen.isoformat()} (poll {POLL_INTERVAL}s)"
    )
    conn = connect()
    conn.autocommit = True

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
    except Exception as e:
        print("DB cursor error:", e)
        return 2

    try:
        while True:
            cur.execute(
                """
                SELECT id, timestamp, message_type, source, target, content
                FROM messages
                WHERE (source = 'agent_coordinator' OR message_type = 'coordinator' OR target = 'DIRETOR')
                  AND timestamp > %s
                ORDER BY timestamp ASC
                LIMIT 10
                """,
                (last_seen,),
            )
            rows = cur.fetchall()
            if rows:
                for r in rows:
                    ts = r.get("timestamp")
                    print("---")
                    print("id:", r.get("id"))
                    print("timestamp:", ts)
                    print("type:", r.get("message_type"))
                    print("source:", r.get("source"))
                    print("target:", r.get("target"))
                    print("content:\n", r.get("content"))
                    last_seen = ts
                print("Coordinator message(s) received — exiting watcher")
                return 0

            # timeout handling
            if timeout is not None:
                elapsed = (iso_now() - start_time).total_seconds()
                if elapsed > timeout:
                    print("Timeout reached, no coordinator message")
                    return 3

            print("waiting for coordinator response...")
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\nWatcher interrupted by user")
        return 4
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--timeout", type=int, help="Timeout in seconds to stop watching")
    args = p.parse_args()
    exit(main(timeout=args.timeout))
