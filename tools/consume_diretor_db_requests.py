#!/usr/bin/env python3
"""Consume pending DIRETOR requests from agent_ipc (Postgres) and respond with checklist.

Usage: DATABASE_URL=... python3 tools/consume_diretor_db_requests.py
"""

import importlib.util
import pathlib

# load agent_ipc by path to avoid package import issues
repo = pathlib.Path(__file__).resolve().parents[1]
ipc_path = repo / "tools" / "agent_ipc.py"
spec = importlib.util.spec_from_file_location("agent_ipc_local", str(ipc_path))
agent_ipc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_ipc)

CHECKLIST = (
    "Diretor authorization:\n"
    "1) Confirm backup of DB and Open WebUI assets.\n"
    "2) Confirm tunnel API token present and valid.\n"
    "3) Confirm maintenance window and expected downtime.\n"
    "4) Confirm rollback image/tag available.\n"
    "5) Confirm monitoring/alerting configured post-deploy.\n"
    "If all OK, respond with 'approve' and list any additional steps."
)


def main():
    print("Checking for pending DIRETOR requests...")
    rows = agent_ipc.fetch_pending("DIRETOR", limit=10)
    if not rows:
        print("No pending requests")
        return 0
    for r in rows:
        rid = r["id"]
        src = r.get("source")
        content = r.get("content")
        print(f"Processing DB request {rid} from {src}: {str(content)[:200]}")
        agent_ipc.respond(rid, "DIRETOR", CHECKLIST)
        print("Responded to", rid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
