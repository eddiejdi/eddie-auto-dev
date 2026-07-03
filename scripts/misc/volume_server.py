#!/usr/bin/env python3
"""Servidor HTTP local para controle de volume do notebook via pactl.

Endpoints:
  POST /volume/up          — aumenta +5%
  POST /volume/down        — diminui -5%
  POST /volume/set?pct=50  — define valor absoluto (0-100)
  GET  /volume             — retorna volume atual
"""

import http.server
import json
import subprocess
import urllib.parse
import sys

PORT = 9876
STEP = 5


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def get_volume() -> int:
    out = run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
    for part in out.split():
        if part.endswith("%"):
            return int(part.rstrip("%"))
    return -1


def set_volume(value: str) -> None:
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", value], check=True)


class Handler(http.server.BaseHTTPRequestHandler):
    def _reply(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/volume":
            pct = get_volume()
            self._reply(200, {"volume_pct": pct})
        else:
            self._reply(404, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/volume/up":
                set_volume(f"+{STEP}%")
                self._reply(200, {"volume_pct": get_volume(), "action": "up"})
            elif path == "/volume/down":
                set_volume(f"-{STEP}%")
                self._reply(200, {"volume_pct": get_volume(), "action": "down"})
            elif path == "/volume/set":
                pct = int(params.get("pct", ["50"])[0])
                pct = max(0, min(100, pct))
                set_volume(f"{pct}%")
                self._reply(200, {"volume_pct": get_volume(), "action": "set"})
            else:
                self._reply(404, {"error": "not found"})
        except Exception as e:
            self._reply(500, {"error": str(e)})

    def log_message(self, fmt, *args):
        print(f"[volume_server] {self.address_string()} {fmt % args}", file=sys.stderr)


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[volume_server] Escutando em 0.0.0.0:{PORT}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
