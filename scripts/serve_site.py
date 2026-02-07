#!/usr/bin/env python3
"""Servidor HTTP simples para desenvolvimento que serve a pasta `site/` em :3000.

Uso:
  python3 scripts/serve_site.py

O servidor usa http.server e loga requisições. Projetado apenas para desenvolvimento local.
"""
import http.server
import socketserver
import os
import sys

PORT = int(os.environ.get('DEV_SITE_PORT', '3000'))
ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'site')

if __name__ == '__main__':
    if not os.path.isdir(ROOT):
        print(f'Erro: diretório de site não encontrado: {ROOT}', file=sys.stderr)
        sys.exit(2)

    os.chdir(ROOT)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(('0.0.0.0', PORT), handler) as httpd:
        print(f'Serving {ROOT} at http://0.0.0.0:{PORT} (Ctrl+C to stop)')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nServidor interrompido pelo usuário')
            httpd.server_close()
