#!/usr/bin/env python3
"""Simple DB-backed agent IPC helper using PostgreSQL.

Provides minimal publish/poll helpers so separate agent processes can
exchange remediation requests/responses via a shared Postgres instance.

CLI usage (used by .githooks/post-commit and copilot hooks):
    python3 tools/agent_ipc.py publish --agent wiki_rpa4all --task-type wiki_update --message 'texto'
    python3 tools/agent_ipc.py poll --id 42 --timeout 30
    python3 tools/agent_ipc.py fetch --agent wiki_rpa4all
"""
import argparse
import os
import json
import sys
import time
from datetime import datetime
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get('DATABASE_URL')


def _get_conn():
    if not DATABASE_URL:
        raise RuntimeError('DATABASE_URL not set')
    return psycopg2.connect(DATABASE_URL)


def init_table():
    sql = '''
    CREATE TABLE IF NOT EXISTS agent_ipc (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
        source TEXT,
        target TEXT,
        content TEXT,
        metadata JSONB,
        status TEXT DEFAULT 'pending',
        response TEXT,
        responded_at TIMESTAMP WITH TIME ZONE
    );
    CREATE INDEX IF NOT EXISTS idx_agent_ipc_target_status ON agent_ipc(target, status);
    '''
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
    finally:
        conn.close()


def publish_request(source: str, target: str, content: str, metadata: dict = None) -> int:
    init_table()
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO agent_ipc (source, target, content, metadata) VALUES (%s,%s,%s,%s) RETURNING id",
                    (source, target, content, json.dumps(metadata or {})),
                )
                row = cur.fetchone()
                return row[0]
    finally:
        conn.close()


def poll_response(request_id: int, timeout: int = 30, poll: int = 2):
    conn = _get_conn()
    try:
        waited = 0
        while waited < timeout:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT status, response, responded_at FROM agent_ipc WHERE id=%s", (request_id,))
                row = cur.fetchone()
                if row and row['status'] in ('done', 'responded') and row.get('response'):
                    return {'status': row['status'], 'response': row['response'], 'responded_at': row['responded_at']}
            time.sleep(poll)
            waited += poll
        return None
    finally:
        conn.close()


def respond(request_id: int, responder: str, response_text: str):
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE agent_ipc SET status='done', response=%s, responded_at=now() WHERE id=%s",
                    (response_text, request_id),
                )
    finally:
        conn.close()


def fetch_pending(target: str = 'OperationsAgent', limit: int = 10):
    """Return a list of pending requests for the given target.

    Each item is a dict: {'id', 'source', 'content', 'metadata'}
    """
    init_table()
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, source, content, metadata FROM agent_ipc WHERE target=%s AND status='pending' ORDER BY id LIMIT %s",
                (target, limit),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli_main() -> int:
    parser = argparse.ArgumentParser(
        description="Agent IPC CLI — publica e consome mensagens via PostgreSQL"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pub = sub.add_parser("publish", help="Publica mensagem para um agent")
    p_pub.add_argument("--agent", required=True, help="Nome do agent destino")
    p_pub.add_argument("--source", default="claude_code", help="Fonte da mensagem")
    p_pub.add_argument("--task-type", default="task", dest="task_type")
    p_pub.add_argument("--priority", default="normal")
    p_pub.add_argument("--message", required=True, help="Conteúdo da mensagem")
    p_pub.add_argument("--meta", default="{}", help="JSON de metadados extras")

    p_poll = sub.add_parser("poll", help="Aguarda resposta de um request")
    p_poll.add_argument("--id", type=int, required=True, dest="req_id")
    p_poll.add_argument("--timeout", type=int, default=30)

    p_fetch = sub.add_parser("fetch", help="Lista mensagens pendentes para um agent")
    p_fetch.add_argument("--agent", required=True)
    p_fetch.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()

    if args.cmd == "publish":
        try:
            meta = json.loads(args.meta)
        except json.JSONDecodeError:
            meta = {}
        meta.update({"task_type": args.task_type, "priority": args.priority})
        req_id = publish_request(
            source=args.source,
            target=args.agent,
            content=args.message,
            metadata=meta,
        )
        print(req_id)
        return 0

    if args.cmd == "poll":
        result = poll_response(args.req_id, timeout=args.timeout)
        if result:
            print(json.dumps(result, default=str))
            return 0
        print("timeout", file=sys.stderr)
        return 1

    if args.cmd == "fetch":
        rows = fetch_pending(target=args.agent, limit=args.limit)
        print(json.dumps(rows, default=str))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(_cli_main())
