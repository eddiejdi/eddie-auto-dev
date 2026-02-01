"""
Migration script: copy SQLite `conversations.db` schema and data into a Postgres DB.
Usage:
  DATABASE_URL=postgresql://user:pass@host:5432/dbname python3 tools/migrate_sqlite_to_postgres.py \
    --sqlite /path/to/conversations.db --yes

If `--yes` is not provided the script will only print what it would do.
"""

import argparse
import os
import sqlite3
import json

try:
    from sqlalchemy import create_engine, text
except Exception:
    raise SystemExit("SQLAlchemy required: pip install sqlalchemy psycopg2-binary")


def dump_sqlite_rows(sqlite_path):
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    tables = {}
    for tbl in ("conversations", "messages", "conversation_snapshots"):
        try:
            cur.execute(f"SELECT * FROM {tbl}")
            rows = [dict(r) for r in cur.fetchall()]
            tables[tbl] = rows
        except Exception:
            tables[tbl] = []

    conn.close()
    return tables


def ensure_pg_tables(engine):
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                started_at TIMESTAMP,
                ended_at TIMESTAMP,
                phase TEXT,
                participants TEXT,
                total_messages INTEGER,
                duration_seconds REAL,
                status TEXT
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                timestamp TIMESTAMP,
                message_type TEXT,
                source TEXT,
                target TEXT,
                content TEXT,
                metadata TEXT
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS conversation_snapshots (
                id SERIAL PRIMARY KEY,
                conversation_id TEXT,
                timestamp TIMESTAMP,
                phase TEXT,
                participants TEXT,
                message_count INTEGER,
                last_message TEXT
            )
        """))


def migrate(sqlite_path, database_url, dry_run=True):
    data = dump_sqlite_rows(sqlite_path)

    if dry_run:
        print(
            f"Would migrate {sum(len(v) for v in data.values())} rows to {database_url}"
        )
        for k, v in data.items():
            print(f" - {k}: {len(v)} rows")
        return 0

    engine = create_engine(database_url)
    ensure_pg_tables(engine)

    inserted = {"conversations": 0, "messages": 0, "conversation_snapshots": 0}
    with engine.begin() as conn:
        for row in data.get("conversations", []):
            conn.execute(
                text("""
                INSERT INTO conversations (id, started_at, ended_at, phase, participants, total_messages, duration_seconds, status)
                VALUES (:id, :started_at, :ended_at, :phase, :participants, :total_messages, :duration_seconds, :status)
                ON CONFLICT (id) DO NOTHING
            """),
                row,
            )
            inserted["conversations"] += 1

        for row in data.get("messages", []):
            # ensure metadata is string
            if isinstance(row.get("metadata"), dict):
                row["metadata"] = json.dumps(row["metadata"])
            conn.execute(
                text("""
                INSERT INTO messages (id, conversation_id, timestamp, message_type, source, target, content, metadata)
                VALUES (:id, :conversation_id, :timestamp, :message_type, :source, :target, :content, :metadata)
                ON CONFLICT (id) DO NOTHING
            """),
                row,
            )
            inserted["messages"] += 1

        for row in data.get("conversation_snapshots", []):
            conn.execute(
                text("""
                INSERT INTO conversation_snapshots (conversation_id, timestamp, phase, participants, message_count, last_message)
                VALUES (:conversation_id, :timestamp, :phase, :participants, :message_count, :last_message)
            """),
                row,
            )
            inserted["conversation_snapshots"] += 1

    print("Migration complete. Inserted:", inserted)
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--sqlite",
        required=False,
        help="Path to conversations.db (defaults to specialized_agents/interceptor_data/conversations.db)",
    )
    p.add_argument("--yes", action="store_true", help="Actually perform migration")
    args = p.parse_args()

    sqlite_path = args.sqlite or os.path.join(
        os.path.dirname(__file__),
        "..",
        "specialized_agents",
        "interceptor_data",
        "conversations.db",
    )
    sqlite_path = os.path.normpath(sqlite_path)

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "Set DATABASE_URL env var to target Postgres (postgresql://user:pass@host:5432/dbname)"
        )
        raise SystemExit(1)

    dry = not args.yes
    exit(migrate(sqlite_path, database_url, dry_run=dry))
