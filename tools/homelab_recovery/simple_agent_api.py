#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from urllib.parse import urlparse
from pathlib import Path
import shutil

HOST = '127.0.0.1'
PORT = 8888
QUEUE = Path('/tmp/agent_queue')
CONSUMED = QUEUE / 'consumed'
CONSUMED.mkdir(parents=True, exist_ok=True)

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip('/').split('/')
        if self.path == '/rcas' or parsed.path == '/rcas':
            out = []
            for p in QUEUE.glob('rca_EA-*.json'):
                out.append({'issue': p.stem.split('_',1)[1], 'path': str(p), 'status': 'queued'})
            for p in CONSUMED.glob('rca_EA-*.json'):
                out.append({'issue': p.stem.split('_',1)[1], 'path': str(p), 'status': 'consumed'})
            return self._send(200, out)
        if len(parts) == 2 and parts[0] == 'rca':
            issue = parts[1]
            p1 = QUEUE / f'rca_{issue}.json'
            p2 = CONSUMED / f'rca_{issue}.json'
            if p1.exists():
                try:
                    return self._send(200, json.load(open(p1,'r',encoding='utf-8')))
                except Exception as e:
                    return self._send(500, {'error': str(e)})
            if p2.exists():
                try:
                    return self._send(200, json.load(open(p2,'r',encoding='utf-8')))
                except Exception as e:
                    return self._send(500, {'error': str(e)})
            return self._send(404, {'error':'not found'})
        return self._send(404, {'error':'not found'})

    def do_POST(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip('/').split('/')
        if len(parts) == 3 and parts[0] == 'rca' and parts[2] == 'ack':
            issue = parts[1]
            p1 = QUEUE / f'rca_{issue}.json'
            p2 = CONSUMED / f'rca_{issue}.json'
            target = p1 if p1.exists() else (p2 if p2.exists() else None)
            if not target:
                return self._send(404, {'error':'not found'})
            ack_path = QUEUE / f'rca_{issue}.ack'
            ack_path.write_text(json.dumps({'issue':issue,'ack':True}))
            if target.parent == QUEUE:
                shutil.move(str(target), str(CONSUMED / target.name))
            return self._send(200, {'status':'acknowledged','issue':issue})
        return self._send(404, {'error':'not found'})

    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    server = HTTPServer((HOST, PORT), Handler)
    print(f'serving on http://{HOST}:{PORT}')
    server.serve_forever()
