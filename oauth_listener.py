#!/usr/bin/env python3
"""Servidor temporário para capturar callback OAuth na porta 8085."""
import http.server
import urllib.parse

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code = qs.get("code", [""])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        if code:
            self.wfile.write(b"<h1>OK! Codigo recebido. Pode fechar esta aba.</h1>")
            print(f"CODE:{code}")
        else:
            self.wfile.write(b"<h1>Erro - sem codigo</h1>")
    
    def log_message(self, *args):
        pass

if __name__ == "__main__":
    print("Aguardando callback OAuth na porta 8085...")
    s = http.server.HTTPServer(("localhost", 8085), Handler)
    s.handle_request()
    s.server_close()
    print("Done")
