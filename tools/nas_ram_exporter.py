#!/usr/bin/env python3
"""Exporter simples de RAM do host — usado pelo coordenador de GPUs para evitar OOM na NAS.

A NAS (RTX 2060 8GB) tem VRAM sobrando, mas RAM de sistema zerada + sem swap = risco crítico.
O Ollama só evicta por pressão de VRAM, nunca por RAM do host. Este exporter cobre a lacuna.

Endpoint:
    GET /ram → {"mem_total_mb": 7999.2, "mem_available_mb": 450.3}

Uso:
    systemctl start nas-ram-exporter
    curl http://localhost:11447/ram | jq .

Ver docs/variables-taxonomy/NAS_RAM_EXPORTER.md
"""

from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [nas-ram-exporter] %(message)s",
)
log = logging.getLogger("nas-ram-exporter")

PORT = int(os.environ.get("NAS_RAM_EXPORTER_PORT", "11447"))


def get_ram_from_proc() -> dict[str, float]:
    """Lê /proc/meminfo diretamente."""
    result = {"mem_total_mb": 0.0, "mem_available_mb": 0.0}
    try:
        with open("/proc/meminfo") as f:
            data = {}
            for line in f.readlines()[:30]:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(":")
                    value = int(parts[1])  # já está em kB
                    data[key] = value
            total_kb = data.get("MemTotal", 0)
            available_kb = data.get("MemAvailable", 0)
            result["mem_total_mb"] = round(total_kb / 1024, 1)
            result["mem_available_mb"] = round(available_kb / 1024, 1)
    except Exception as exc:
        log.warning("falha lendo /proc/meminfo: %s", exc)
    return result


class RamHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        pass

    def do_GET(self) -> None:
        if self.path == "/ram":
            ram = get_ram_from_proc()
            body = json.dumps(ram).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()


def main() -> None:
    server = HTTPServer(("127.0.0.1", PORT), RamHandler)
    log.info("exporter RAM iniciado em http://127.0.0.1:%d/ram", PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutdown solicitado")
        server.shutdown()


if __name__ == "__main__":
    main()
