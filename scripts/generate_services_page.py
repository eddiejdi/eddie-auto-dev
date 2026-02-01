#!/usr/bin/env python3
"""Generate a static services index page under `docs/` using dashboard config."""

from pathlib import Path
from datetime import datetime
import html
import ast
import os
import json
import re

# Try to extract URLS, PORTS and server ip by parsing the config file to avoid
# importing repo modules (which may require external deps).
CFG = Path(__file__).resolve().parents[1] / "dashboard" / "config.py"
URLS = {}
PORTS = {}
SERVER_IP = "127.0.0.1"
if CFG.exists():
    src = CFG.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                name = getattr(node.targets[0], "id", None)
                if name == "URLS" or name == "PORTS":
                    try:
                        val = ast.literal_eval(node.value)
                        if name == "URLS":
                            URLS = val
                        else:
                            PORTS = val
                    except Exception:
                        pass
        # Try regex-based extraction for SERVER ip or class-level default
        import re

        # Look for explicit SERVER = ServerConfig(..., ip: "x.x.x.x") patterns
        m = re.search(
            r"SERVER\s*=\s*ServerConfig\([^\)]*ip\s*=\s*['\"]([0-9a-fA-F:\.]+)['\"]",
            src,
        )
        if m:
            SERVER_IP = m.group(1)
        else:
            # Look for class-level default in ServerConfig definition: ip: str = "..."
            m2 = re.search(r"ip\s*:\s*str\s*=\s*['\"]([0-9a-fA-F:\.]+)['\"]", src)
            if m2:
                SERVER_IP = m2.group(1)
            else:
                # fallback to parsing any 'SERVER = .* ip = "..."' variant
                m3 = re.search(r"ip\s*=\s*['\"]([0-9a-fA-F:\.]+)['\"]", src)
                if m3:
                    SERVER_IP = m3.group(1)
    except Exception:
        pass

    # Load optional public URL overrides. If present, map private IPs or service keys
    # to public hostnames so the generated page lists public URLs instead of local IPs.
    OVERRIDES = {}
    overrides_path = os.path.join(
        os.path.dirname(__file__), "..", "docs", "public_url_overrides.json"
    )
    try:
        overrides_path = os.path.abspath(overrides_path)
        if os.path.exists(overrides_path):
            with open(overrides_path, "r") as fh:
                try:
                    OVERRIDES = json.load(fh)
                except Exception:
                    OVERRIDES = {}
    except Exception:
        OVERRIDES = {}

    def is_private_host(host):
        try:
            # IPv4 private ranges and localhost
            if re.match(
                r"^(127\.|10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)", host
            ):
                return True
            # IPv6 local addresses
            if host.startswith("::1") or host.startswith("fe80"):
                return True
        except Exception:
            return False
        return False

    def to_public_url(name_or_host, port=None, path="/"):
        # name_or_host may be a service key existing in URLS, an IP, or a hostname
        # First check overrides by exact key
        if name_or_host in OVERRIDES:
            return OVERRIDES[name_or_host]
        # check overrides by host/IP
        if name_or_host in OVERRIDES:
            return OVERRIDES[name_or_host]
        # If the host appears private and there's an override for the service name, use it
        if is_private_host(name_or_host):
            # try service-name based override
            if name_or_host in OVERRIDES:
                return OVERRIDES[name_or_host]
            # no override available
            return None
        # host seems public; construct a URL
        scheme = "https" if port in (443, None) else "http"
        host = name_or_host
        if port and port not in (80, 443):
            host = f"{host}:{port}"
        return f"{scheme}://{host}{path}"


class S:
    ip = SERVER_IP


SERVER = S()

OUT = Path(__file__).resolve().parents[1] / "docs" / "services_index.html"
OUT.parent.mkdir(parents=True, exist_ok=True)

now = datetime.utcnow().isoformat() + "Z"

lines = []
lines.append("<!doctype html>")
lines.append('<html><head><meta charset="utf-8"><title>Services Index</title>')
lines.append(
    "<style>body{font-family:Arial,Helvetica,sans-serif;padding:20px}h1{color:#0b5;}a{color:#0366d6}</style>"
)
lines.append("</head><body>")
lines.append("<h1>Services Index</h1>")
lines.append(f"<p>Generated: {html.escape(now)}</p>")
lines.append("<ul>")

for name, url in sorted(URLS.items()):
    try:
        display = html.escape(str(name))
        link = html.escape(str(url))
        extra = (
            f' (<a href="{link}" target="_blank">open</a>)'
            if str(url).startswith(("http://", "https://"))
            else ""
        )
        lines.append(
            f'<li><strong>{display}</strong>: <a href="{link}" target="_blank">{link}</a>{extra}</li>'
        )
    except Exception:
        continue

lines.append("</ul>")

if PORTS:
    lines.append("<h2>Ports</h2>")
    lines.append("<ul>")
    for svc, p in sorted(PORTS.items()):
        try:
            url = f"http://{SERVER.ip}:{p}/"
            lines.append(
                f'<li>{html.escape(str(svc))}: <a href="{html.escape(url)}" target="_blank">{html.escape(url)}</a></li>'
            )
        except Exception:
            continue
    lines.append("</ul>")

lines.append("<h2>Repository</h2>")
lines.append(
    '<p>See <a href="https://github.com/eddiejdi/eddie-auto-dev" target="_blank">Repository</a></p>'
)

lines.append("</body></html>")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {OUT}")
