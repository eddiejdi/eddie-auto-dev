#!/usr/bin/env python3
"""Simple DB-backed agent IPC helper using PostgreSQL.

Provides minimal publish/poll helpers so separate agent processes can
exchange remediation requests/responses via a shared Postgres instance.
"""

import os
import json
import time
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL")


def _get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(DATABASE_URL)


def init_table():
    sql = """
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
    """
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
    finally:
        conn.close()


def publish_request(
    source: str, target: str, content: str, metadata: dict = None
) -> int:
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
                cur.execute(
                    "SELECT status, response, responded_at FROM agent_ipc WHERE id=%s",
                    (request_id,),
                )
                row = cur.fetchone()
                if (
                    row
                    and row["status"] in ("done", "responded")
                    and row.get("response")
                ):
                    return {
                        "status": row["status"],
                        "response": row["response"],
                        "responded_at": row["responded_at"],
                    }
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


def fetch_pending(target: str = "OperationsAgent", limit: int = 10):
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
