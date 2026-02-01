#!/usr/bin/env python3
"""Trigger documentation agents: BPMAgent and ConfluenceAgent.

Publishes requests on the AgentCommunicationBus and to DB-IPC (if available).
Also attempts to export .drawio files to PNG using `drawio` CLI if present
and stages any exports for commit.
"""

import pathlib
import uuid
import time
import subprocess

from importlib import util

# load bus module by path
bus_path = (
    pathlib.Path(__file__).resolve().parents[1]
    / "specialized_agents"
    / "agent_communication_bus.py"
)
spec = util.spec_from_file_location("agent_bus_local", str(bus_path))
agent_bus = util.module_from_spec(spec)
spec.loader.exec_module(agent_bus)
get_communication_bus = agent_bus.get_communication_bus
MessageType = agent_bus.MessageType


def publish_request(target, message):
    bus = get_communication_bus()
    req_id = str(uuid.uuid4())
    meta = {"request_id": req_id}
    print(f"Publishing to {target} (id={req_id})...")
    bus.publish(MessageType.REQUEST, "assistant", target, message, meta)
    # try DB ipc
    try:
        from tools import agent_ipc

        rid = agent_ipc.publish_request("assistant", target, message, meta)
        print(f"DB publish id: {rid}")
    except Exception:
        pass


def export_drawio_files():
    diagrams = list(pathlib.Path("diagrams").glob("*.drawio"))
    if not diagrams:
        print("No .drawio files found in diagrams/")
        return

    drawio_cli = shutil.which("drawio") if "shutil" in globals() else None
    try:
        import shutil

        drawio_cli = shutil.which("drawio")
    except Exception:
        drawio_cli = None

    for d in diagrams:
        out_png = d.with_suffix(".png")
        if drawio_cli:
            print(f"Exporting {d} -> {out_png}")
            subprocess.run(
                [drawio_cli, "-x", "-f", "png", "-o", str(out_png), str(d)], check=False
            )
        else:
            print(f"drawio CLI not available; skipping export of {d}")


def main():
    msg = (
        "Please synchronize current system documentation: export diagrams from `diagrams/`, "
        "push updated Draw.io files to the repository, and publish pages to Confluence under space 'ED' with title 'Eddie Auto-Dev System Documentation'. "
        "Include architecture diagram, BPMN flow, and runbook for autonomous remediator."
    )

    publish_request("BPMAgent", msg + " (BPM/Draw.io actions)")
    time.sleep(0.2)
    publish_request("ConfluenceAgent", msg + " (Confluence publishing)")

    # Attempt local exports
    export_drawio_files()

    print("Trigger complete.")


if __name__ == "__main__":
    main()
