#!/usr/bin/env python3
"""Mock LLM HTTP server minimal para testes locais.

Fornece endpoints:
- GET /api/tags -> lista modelos
- POST /api/generate -> gera uma resposta simples com bloco de codigo
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class MockHandler(BaseHTTPRequestHandler):
    def _set_json(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/tags"):
            self._set_json()
            payload = {"models": [{"name": "mock-model"}]}
            self.wfile.write(json.dumps(payload).encode())
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path.startswith("/api/generate"):
            length = int(self.headers.get("content-length", 0))
            body = self.rfile.read(length).decode() if length else ""
            try:
                data = json.loads(body) if body else {}
            except Exception:
                data = {}

            # Resposta simples: retorna um snippet de codigo se pedir codigo
            prompt = data.get("prompt", "")
            # Um comportamento básico: se a palavra 'soma' estiver no prompt retornamos função
            if "soma" in prompt or "sum" in prompt:
                resp_text = "```python\ndef soma(a, b):\n    return a + b\n```"
            else:
                resp_text = "```python\n# Exemplo gerado pelo mock\ndef exemplo():\n    return True\n```"

            response = {"response": resp_text, "eval_count": 1}
            self._set_json()
            self.wfile.write(json.dumps(response).encode())
            return

        self.send_response(404)
        self.end_headers()


def run(server_class=HTTPServer, handler_class=MockHandler, port=5100):
    server_address = ("", port)
    httpd = server_class(server_address, handler_class)
    print(f"Mock LLM server running on http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down mock server")
        httpd.server_close()


if __name__ == "__main__":
    run()
