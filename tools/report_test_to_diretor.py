#!/usr/bin/env python3
import pathlib
import importlib.util
import json

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

# read results
body_path = "/tmp/fly_body.html"
URL = None
import os

# Allow explicit override via env; fallback to local homelab host mapping
URL = os.environ.get("VALIDATOR_URL")
if not URL:
    URL = "http://192.168.15.2:3000/auth?redirect=%2F"
    print(f"VALIDATOR_URL not set — using fallback URL: {URL}")

# fetch page body for analysis
import subprocess

try:
    subprocess.run(["curl", "-sS", URL, "-o", body_path], check=True, timeout=20)
except Exception:
    # continue even if fetch fails; body file may not exist
    pass
summary = ""
try:
    with open(body_path, "r", encoding="utf-8") as f:
        body = f.read()
except Exception as e:
    body = ""
    summary += f"ERROR reading body: {e}\n"

# status line from first curl saved to stdout; re-run quick status fetch for clarity
import subprocess

try:
    status = subprocess.check_output(
        [
            "curl",
            "-s",
            "-S",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code} %{url_effective}",
            URL,
        ],
        text=True,
    ).strip()
except Exception as e:
    status = f"ERROR: {e}"

# basic analysis
analysis = []
if status.startswith("200"):
    analysis.append(
        "HTTP 200 returned for /auth?redirect=%2F — login page displayed (expected for unauthenticated requests)."
    )
else:
    analysis.append(f"Non-200 status: {status}")

if "Faça login em Open WebUI" in body:
    analysis.append(
        "Login prompt detected in HTML body — redirect is not occurring without authentication."
    )
else:
    analysis.append("Login prompt not found in body — verify content manually.")
# Suggested next steps for DIRETOR
suggestions = (
    "1) Confirm that the reverse-proxy passes original redirect parameter through and preserves cookies.\n"
    "2) Check Open WebUI auth flow: after POST login, ensure it issues a 302/303 to the original redirect path.\n"
    "3) Verify ipv6-proxy and nft persistence (sysctl net.ipv6.conf.all.forwarding=1 persisted in /etc/sysctl.d and nft rule saved).\n"
    "4) Reproduce locally: capture a login flow with developer tools and verify Set-Cookie and Location headers.\n"
    "5) If required, add a small client-side script to perform window.location when successful login occurs.\n"
)

content = {
    "status": status,
    "short_analysis": analysis,
    "suggestions": suggestions,
}

bus = get_communication_bus()
msg_text = "Agent Tester report for redirect URL:\n" + json.dumps(
    content, ensure_ascii=False, indent=2
)
bus.publish(MessageType.REQUEST, "agent-tester", "DIRETOR", msg_text, {"url": URL})
print("Published tester report to DIRETOR")
