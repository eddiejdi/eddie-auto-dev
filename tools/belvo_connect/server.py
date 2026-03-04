#!/usr/bin/env python3
"""
Belvo Connect Widget — Servidor local.

Fluxo:
  1. Gera Widget Access Token via API Belvo
  2. Serve página HTML com o Connect Widget
  3. Widget retorna link_id via callback
  4. Servidor testa o link: accounts, balances, transactions
  5. Salva link_id no .env para uso futuro

Uso:
  python3 tools/belvo_connect/server.py [--production]
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import date, timedelta

# Adicionar root do projeto ao path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import httpx
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import threading

# ──────────── Config ────────────

ENV_FILE = ROOT / "agent_data" / "banking" / ".env"

# Carregar .env
def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

load_env()

PRODUCTION = "--production" in sys.argv
SECRET_ID = os.getenv("BELVO_SECRET_ID", "")
SECRET_PWD = os.getenv("BELVO_SECRET_PASSWORD", "")

BASE_URL = "https://api.belvo.com" if PRODUCTION else "https://sandbox.belvo.com"
WIDGET_URL = "https://widget.belvo.io" if PRODUCTION else "https://widget.sandbox.belvo.io"
ENV_NAME = "production" if PRODUCTION else "sandbox"
PORT = 8766

print(f"🏦 Belvo Connect — Ambiente: {ENV_NAME}")
print(f"   Base URL: {BASE_URL}")
print(f"   Widget URL: {WIDGET_URL}")


# ──────────── Widget Token ────────────

def get_widget_token() -> str:
    """Obtém Widget Access Token da API Belvo."""
    resp = httpx.post(
        f"{BASE_URL}/api/token/",
        auth=(SECRET_ID, SECRET_PWD),
        json={
            "id": SECRET_ID,
            "password": SECRET_PWD,
            "scopes": "read_institutions,write_links,read_links",
        },
        timeout=30.0,
    )
    if resp.status_code in (200, 201):
        token = resp.json().get("access", "")
        print(f"   ✅ Widget Token obtido ({len(token)} chars)")
        return token
    else:
        print(f"   ❌ Erro ao obter token: {resp.status_code} — {resp.text[:200]}")
        sys.exit(1)


# ──────────── Test Link ────────────

async def test_link(link_id: str):
    """Testa o link criado: accounts, balances, transactions."""
    print(f"\n🔍 Testando link {link_id}...")
    
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        auth=(SECRET_ID, SECRET_PWD),
        timeout=60.0,
    ) as client:
        # Link info
        r = await client.get(f"/api/links/{link_id}/")
        if r.status_code == 200:
            link = r.json()
            print(f"   Instituição: {link.get('institution')}")
            print(f"   Status: {link.get('status')}")
            print(f"   Modo: {link.get('access_mode')}")
        
        # Accounts
        r = await client.post("/api/accounts/", json={"link": link_id})
        print(f"\n   📋 Contas ({r.status_code}):")
        if r.status_code in (200, 201):
            accounts = r.json()
            if isinstance(accounts, list):
                for acc in accounts:
                    name = acc.get("name", "?")
                    acc_type = acc.get("type", "?")
                    number = acc.get("number", "?")
                    currency = acc.get("currency", "BRL")
                    bal = acc.get("balance", {})
                    current = bal.get("current", "?") if isinstance(bal, dict) else bal
                    print(f"      {name} | {acc_type} | {number} | {currency} | saldo={current}")
        else:
            print(f"      {r.text[:200]}")
        
        # Transactions (último mês)
        date_from = (date.today() - timedelta(days=90)).isoformat()
        date_to = date.today().isoformat()
        r = await client.post("/api/transactions/", json={
            "link": link_id,
            "date_from": date_from,
            "date_to": date_to,
        })
        print(f"\n   💳 Transações ({r.status_code}) [{date_from} → {date_to}]:")
        if r.status_code in (200, 201):
            txs = r.json()
            if isinstance(txs, list):
                print(f"      Total: {len(txs)}")
                for tx in txs[:5]:
                    vdate = tx.get("value_date", "?")
                    amount = tx.get("amount", "?")
                    desc = str(tx.get("description", ""))[:50]
                    tx_type = tx.get("type", "?")
                    print(f"      {vdate} | {amount} BRL | {tx_type} | {desc}")
                if len(txs) > 5:
                    print(f"      ... +{len(txs)-5} transações")
        else:
            print(f"      {r.text[:200]}")
        
        # Balances
        r = await client.post("/api/br/balances/", json={
            "link": link_id,
            "date_from": date.today().isoformat(),
        })
        print(f"\n   💰 Saldos ({r.status_code}):")
        if r.status_code in (200, 201):
            bals = r.json()
            if isinstance(bals, list):
                for b in bals[:3]:
                    current = b.get("current_balance", "?")
                    available = b.get("available_balance", "?")
                    print(f"      Atual: {current} | Disponível: {available}")
        else:
            print(f"      {r.text[:200]}")
    
    print(f"\n✅ Teste do link {link_id} concluído!")


def save_link_id(link_id: str, institution: str):
    """Salva link_id no .env."""
    key = f"BELVO_LINK_{institution.upper().replace('-', '_').replace(' ', '_')}"
    
    if ENV_FILE.exists():
        content = ENV_FILE.read_text()
    else:
        content = ""
    
    # Verificar se já existe
    if f"{key}=" in content:
        lines = content.splitlines()
        new_lines = []
        for line in lines:
            if line.startswith(f"{key}="):
                new_lines.append(f"{key}={link_id}")
            else:
                new_lines.append(line)
        content = "\n".join(new_lines)
    else:
        content = content.rstrip() + f"\n\n# Belvo Link — {institution}\n{key}={link_id}\n"
    
    ENV_FILE.write_text(content)
    print(f"   💾 Salvo {key}={link_id} em {ENV_FILE}")


# ──────────── HTTP Server ────────────

class BelvoHandler(SimpleHTTPRequestHandler):
    widget_token = ""
    
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = self.get_widget_html()
            self.wfile.write(html.encode())
        
        elif parsed.path == "/callback":
            params = parse_qs(parsed.query)
            link_id = params.get("link", [None])[0]
            institution = params.get("institution", ["unknown"])[0]
            
            if link_id:
                print(f"\n🎉 Link criado com sucesso!")
                print(f"   Link ID: {link_id}")
                print(f"   Instituição: {institution}")
                
                # Salvar
                save_link_id(link_id, institution)
                
                # Testar
                asyncio.run(test_link(link_id))
                
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:600px;margin:50px auto;text-align:center">
<h1>✅ Conta Vinculada!</h1>
<p><strong>Instituição:</strong> {institution}</p>
<p><strong>Link ID:</strong> <code>{link_id}</code></p>
<p>O link foi salvo e testado. Você pode fechar esta janela.</p>
<p style="color:green;font-size:1.2em">Verifique o terminal para os resultados do teste.</p>
</body></html>""".encode())
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing link_id")
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/api/callback":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
            except:
                data = {}
            
            link_id = data.get("link", "")
            institution = data.get("institution", "unknown")
            
            print(f"\n🎉 Link criado via POST callback!")
            print(f"   Link ID: {link_id}")
            print(f"   Institution: {institution}")
            print(f"   Data: {json.dumps(data, indent=2, default=str)[:300]}")
            
            if link_id:
                save_link_id(link_id, institution)
                asyncio.run(test_link(link_id))
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def get_widget_html(self):
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Eddie Banking — Conectar Banco via Belvo</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a1a;
            color: #e0e0e0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 30px 20px;
        }}
        h1 {{ color: #4fc3f7; margin-bottom: 10px; }}
        .subtitle {{ color: #888; margin-bottom: 30px; }}
        .info {{
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 20px;
            max-width: 500px;
            width: 100%;
            margin-bottom: 20px;
        }}
        .info p {{ margin: 8px 0; }}
        .info .label {{ color: #888; }}
        .info .value {{ color: #4fc3f7; font-weight: bold; }}
        #belvo-widget {{
            width: 100%;
            max-width: 500px;
            min-height: 600px;
            border-radius: 12px;
            overflow: hidden;
        }}
        .status {{
            margin-top: 20px;
            padding: 15px;
            border-radius: 8px;
            max-width: 500px;
            width: 100%;
            display: none;
        }}
        .status.success {{ background: #1b5e20; display: block; }}
        .status.error {{ background: #b71c1c; display: block; }}
        .btn {{
            background: #4fc3f7;
            color: #000;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            font-size: 1.1em;
            cursor: pointer;
            margin-top: 15px;
        }}
        .btn:hover {{ background: #29b6f6; }}
    </style>
</head>
<body>
    <h1>🏦 Eddie Banking Agent</h1>
    <p class="subtitle">Conectar banco via Belvo Open Finance</p>
    
    <div class="info">
        <p><span class="label">Ambiente:</span> <span class="value">{ENV_NAME.upper()}</span></p>
        <p><span class="label">Servidor:</span> <span class="value">localhost:{PORT}</span></p>
        <p><span class="label">Permissões:</span> Contas, Saldos, Transações, Cartões</p>
    </div>
    
    <div id="belvo-widget"></div>
    
    <div id="status" class="status"></div>

    <script src="https://cdn.belvo.io/belvo-widget-1-stable.js"></script>
    <script>
        function startWidget() {{
            const widget = window.belvoSDK.createWidget('{self.widget_token}', {{
                // Configuração
                locale: 'pt',
                country_codes: ['BR'],
                institution_types: ['bank'],
                
                // Callbacks
                callback: function(link, institution) {{
                    console.log('✅ Link criado:', link, institution);
                    
                    // Notificar servidor
                    fetch('/api/callback', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ link: link, institution: institution }})
                    }}).then(r => r.json()).then(data => {{
                        console.log('Server response:', data);
                    }});
                    
                    // Mostrar sucesso
                    const status = document.getElementById('status');
                    status.className = 'status success';
                    status.innerHTML = '<p>✅ <strong>Banco conectado com sucesso!</strong></p>' +
                        '<p>Link ID: ' + link + '</p>' +
                        '<p>Instituição: ' + institution + '</p>' +
                        '<p>Verifique o terminal para os dados bancários.</p>';
                }},
                onExit: function(data) {{
                    console.log('Widget fechado:', data);
                }},
                onEvent: function(event) {{
                    console.log('Widget event:', event);
                }},
                onError: function(error) {{
                    console.error('Widget error:', error);
                    const status = document.getElementById('status');
                    status.className = 'status error';
                    status.innerHTML = '<p>❌ <strong>Erro:</strong> ' + JSON.stringify(error) + '</p>';
                }}
            }});
            
            widget.build();
        }}

        // Iniciar quando SDK carregar
        if (window.belvoSDK) {{
            startWidget();
        }} else {{
            document.getElementById('belvo-widget').innerHTML = 
                '<p style="text-align:center;padding:20px;color:#f44336">Erro ao carregar Belvo Widget SDK. Verifique sua conexão.</p>';
        }}
    </script>
</body>
</html>"""
    
    def log_message(self, format, *args):
        # Silenciar logs HTTP normais
        if "200" in str(args) or "GET / " in str(args):
            return
        print(f"   HTTP: {args[0] if args else ''}")


def main():
    if not SECRET_ID or not SECRET_PWD:
        print("❌ Credenciais Belvo não configuradas!")
        print(f"   Configure BELVO_SECRET_ID e BELVO_SECRET_PASSWORD em {ENV_FILE}")
        sys.exit(1)
    
    # Obter widget token
    token = get_widget_token()
    BelvoHandler.widget_token = token
    
    # Iniciar servidor
    server = HTTPServer(("0.0.0.0", PORT), BelvoHandler)
    print(f"\n🌐 Servidor rodando em http://localhost:{PORT}")
    print(f"   Abra no navegador para conectar seu banco via Belvo.")
    print(f"   Pressione Ctrl+C para parar.\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹  Servidor parado.")
        server.server_close()


if __name__ == "__main__":
    main()
