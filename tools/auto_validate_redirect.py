#!/usr/bin/env python3
"""Auto-validate redirect/login page and notify DIRETOR until login appears.
Saves success marker to /tmp/redirect_verified.json and logs to /tmp/auto_validate.log
"""

import time
import subprocess
import pathlib
import importlib.util
import json

try:
    import requests
except Exception:
    requests = None
import os

URL = os.environ.get("VALIDATOR_URL")
if not URL:
    print(
        "VALIDATOR_URL not set — no public tunnel configured; auto_validate_redirect is a no-op"
    )
    exit(0)
CHECK_PHRASE = os.environ.get("VALIDATOR_CHECK_PHRASE", "Faça login em Open WebUI")
OUT_MARKER = "/tmp/redirect_verified.json"
LOG = "/tmp/auto_validate.log"

# load bus
bus_path = (
    pathlib.Path(__file__).resolve().parents[1]
    / "specialized_agents"
    / "agent_communication_bus.py"
)
spec = importlib.util.spec_from_file_location("agent_bus_local", str(bus_path))
agent_bus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_bus)
get_communication_bus = agent_bus.get_communication_bus
MessageType = agent_bus.MessageType


def fetch_body():
    # kept for backward compatibility; prefer streaming-check via fetch_stream_or_body
    try:
        body = subprocess.check_output(["curl", "-sS", URL], text=True, timeout=30)
        return body
    except Exception:
        return ""


def fetch_stream_or_body():
    """Try streaming the response and detect a server-streamed JSON chunk with type=="redirect".
    If streaming fails or no redirect is found, fall back to a full GET and return the body.
    Returns (found_redirect: bool, kind: str, payload: str)
    kind is 'redirect'|'body'|'' and payload is a short snippet or the JSON string for redirect.
    """
    # Try using requests stream first (preferred)
    if requests:
        try:
            with requests.get(URL, stream=True, timeout=(5, 30)) as r:
                # iterate lines as they arrive
                for raw in r.iter_lines(decode_unicode=True):
                    if not raw:
                        continue
                    line = raw.strip()
                    if '"type":"redirect"' in line or '"type": "redirect"' in line:
                        # try to safely extract JSON object from the line
                        try:
                            start = line.find("{")
                            end = line.rfind("}")
                            if start != -1 and end != -1 and end > start:
                                obj = json.loads(line[start : end + 1])
                                if (
                                    isinstance(obj, dict)
                                    and obj.get("type") == "redirect"
                                ):
                                    return (
                                        True,
                                        "redirect",
                                        json.dumps(obj, ensure_ascii=False),
                                    )
                        except Exception:
                            # if parsing fails, return the raw matched line as a best-effort snippet
                            return True, "redirect", line[:2000]
                # no redirect found in stream; fallthrough to full GET
        except Exception:
            # streaming attempt failed; fall back below
            pass

    # Fallback: do a full fetch (curl if requests not available or stream didn't find)
    try:
        if requests:
            body = requests.get(URL, timeout=30).text
        else:
            body = subprocess.check_output(["curl", "-sS", URL], text=True, timeout=30)
        found = CHECK_PHRASE in body
        return found, "body", (body[:2000] if body else "")
    except Exception:
        return False, "", ""


def publish_to_diretor(status, note, body_snippet=""):
    bus = get_communication_bus()
    content = json.dumps(
        {"status": status, "note": note, "url": URL, "snippet": body_snippet},
        ensure_ascii=False,
    )
    bus.publish(MessageType.REQUEST, "auto-validator", "DIRETOR", content, {})


def main(poll=30, timeout=3600):
    start = time.time()
    with open(LOG, "a", encoding="utf-8") as logf:
        logf.write(f"[auto_validate] started, URL={URL}\n")
    while True:
        found, kind, payload = fetch_stream_or_body()
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        with open(LOG, "a", encoding="utf-8") as logf:
            logf.write(f"{ts} - check result kind={kind} found={found}\n")

        if found and kind == "redirect":
            publish_to_diretor("ok", "Redirect event observed (server-stream)", payload)
            marker = {
                "timestamp": ts,
                "url": URL,
                "status": "redirect_detected",
                "payload": payload,
            }
            with open(OUT_MARKER, "w", encoding="utf-8") as f:
                json.dump(marker, f, ensure_ascii=False, indent=2)
            with open(LOG, "a", encoding="utf-8") as logf:
                logf.write(f"{ts} - redirect marker written to {OUT_MARKER}\n")
            return 0
        elif found and kind == "body":
            # Still useful: login page text found in body
            publish_to_diretor("ok", "Login page detected (body)", payload[:500])
            marker = {
                "timestamp": ts,
                "url": URL,
                "status": "login_detected",
                "snippet": payload[:2000],
            }
            with open(OUT_MARKER, "w", encoding="utf-8") as f:
                json.dump(marker, f, ensure_ascii=False, indent=2)
            with open(LOG, "a", encoding="utf-8") as logf:
                logf.write(f"{ts} - success marker written to {OUT_MARKER}\n")
            return 0
        else:
            publish_to_diretor(
                "pending",
                "Login page / redirect not yet detected",
                (payload or "")[:500],
            )
        if time.time() - start > timeout:
            publish_to_diretor("timeout", f"Validation timed out after {timeout}s", "")
            with open(LOG, "a", encoding="utf-8") as logf:
                logf.write(f"{ts} - timeout after {timeout}s\n")
            return 2
        time.sleep(poll)


if __name__ == "__main__":
    exit(main())
