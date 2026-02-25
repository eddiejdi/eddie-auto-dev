#!/usr/bin/env python3
"""
Small DB maintenance helper for the trading_agent SQLite DB.
Usage:
  python3 tools/db_maintenance.py --db /path/to/trading_agent.db --vacuum --analyze --backup /tmp/backup.db
"""
import argparse
import shutil
import sqlite3
from pathlib import Path


def vacuum(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("VACUUM;")
        conn.execute("ANALYZE;")
        print(f"✅ Vacuum and Analyze completed on {db_path}")
    finally:
        conn.close()


def backup(db_path: Path, out_path: Path):
    # Simple file copy backup (recommended to stop writer processes first or use sqlite online backup API)
    shutil.copy2(str(db_path), str(out_path))
    print(f"✅ Backup created: {out_path}")


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--db', required=True, help='Path to trading_agent.db')
    p.add_argument('--vacuum', action='store_true')
    p.add_argument('--analyze', action='store_true')
    p.add_argument('--backup', help='Path to write backup file')
    args = p.parse_args()

    dbp = Path(args.db).expanduser().resolve()
    if not dbp.exists():
        print(f"ERROR: DB not found: {dbp}")
        raise SystemExit(2)

    if args.backup:
        backup(dbp, Path(args.backup).expanduser().resolve())

    if args.vacuum or args.analyze:
        vacuum(dbp)
