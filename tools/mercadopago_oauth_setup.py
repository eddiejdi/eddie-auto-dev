#!/usr/bin/env python3
"""
Mercado Pago — OAuth2 Production Setup

Script interativo para:
1. Guiar a ativação do modo produção no painel de desenvolvedor
2. Capturar client_secret do painel
3. Executar fluxo OAuth2 authorization_code com servidor de callback local
4. Trocar code por access_token autorizado
5. Testar endpoint de saldo
6. Salvar novo token no .env

Uso:
    python3 tools/mercadopago_oauth_setup.py
    python3 tools/mercadopago_oauth_setup.py --client-secret SEU_SECRET
    python3 tools/mercadopago_oauth_setup.py --skip-browser  # não abre navegador
"""

import argparse
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime
from pathlib import Path

# Configuração
APP_ID = "6949951091520165"
USER_ID = "286267368"
CALLBACK_PORT = 8765
CALLBACK_PATH = "/callback"
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"
MP_API_BASE = "https://api.mercadopago.com"
MP_AUTH_BASE = "https://auth.mercadopago.com"

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / "agent_data" / "banking" / ".env"

# Cores ANSI
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_header(text: str):
    print(f"\n{BOLD}{CYAN}{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}{RESET}\n")


def print_step(n: int, text: str):
    print(f"{BOLD}{GREEN}[Passo {n}]{RESET} {text}")


def print_warn(text: str):
    print(f"{YELLOW}⚠  {text}{RESET}")


def print_error(text: str):
    print(f"{RED}✖  {text}{RESET}")


def print_ok(text: str):
    print(f"{GREEN}✔  {text}{RESET}")


def generate_pkce():
    """Gera code_verifier e code_challenge para PKCE (S256)."""
    code_verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = (
        __import__("base64")
        .urlsafe_b64encode(digest)
        .rstrip(b"=")
        .decode("ascii")
    )
    return code_verifier, code_challenge


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Handler HTTP para capturar o callback OAuth2."""

    authorization_code = None
    state_received = None
    error = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == CALLBACK_PATH:
            if "code" in params:
                OAuthCallbackHandler.authorization_code = params["code"][0]
                OAuthCallbackHandler.state_received = params.get("state", [None])[0]
                self._send_success()
            elif "error" in params:
                OAuthCallbackHandler.error = params.get("error", ["unknown"])[0]
                error_desc = params.get("error_description", [""])[0]
                self._send_error(f"{OAuthCallbackHandler.error}: {error_desc}")
            else:
                self._send_error("Nenhum código de autorização recebido")
        else:
            self.send_response(404)
            self.end_headers()

    def _send_success(self):
        html = """<!DOCTYPE html><html><head><meta charset="utf-8">
        <title>Shared Banking — OAuth2 OK</title>
        <style>
            body { font-family: -apple-system, sans-serif; display: flex; 
                   justify-content: center; align-items: center; height: 100vh;
                   background: #1a1a2e; color: #eee; margin: 0; }
            .card { background: #16213e; padding: 40px; border-radius: 16px;
                    text-align: center; box-shadow: 0 8px 32px rgba(0,0,0,.3); }
            .icon { font-size: 64px; }
            h1 { color: #00d26a; }
            p { color: #aaa; }
        </style></head><body>
        <div class="card">
            <div class="icon">✅</div>
            <h1>Autorização concedida!</h1>
            <p>Pode fechar esta aba e voltar ao terminal.</p>
            <p style="color:#555">Shared Banking Agent — OAuth2 Setup</p>
        </div></body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def _send_error(self, msg):
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
        <title>Shared Banking — Erro OAuth2</title>
        <style>
            body {{ font-family: sans-serif; display: flex; justify-content: center;
                   align-items: center; height: 100vh; background: #1a1a2e; color: #eee; margin: 0; }}
            .card {{ background: #16213e; padding: 40px; border-radius: 16px;
                    text-align: center; box-shadow: 0 8px 32px rgba(0,0,0,.3); }}
            h1 {{ color: #ff4444; }}
        </style></head><body>
        <div class="card">
            <div style="font-size:64px">❌</div>
            <h1>Erro na autorização</h1>
            <p>{msg}</p>
            <p style="color:#555">Tente novamente executando o script.</p>
        </div></body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        """Silencia logs do HTTP server."""
        pass


def start_callback_server():
    """Inicia o servidor HTTP local para capturar o callback."""
    server = http.server.HTTPServer(("0.0.0.0", CALLBACK_PORT), OAuthCallbackHandler)
    server.timeout = 300  # 5 minutos
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    return server, thread


def exchange_code_for_token(client_id: str, client_secret: str, code: str,
                             redirect_uri: str, code_verifier: str | None = None) -> dict:
    """Troca o authorization_code por um access_token."""
    import httpx

    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    if code_verifier:
        data["code_verifier"] = code_verifier

    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{MP_API_BASE}/oauth/token", json=data)
        return resp.json()


def refresh_token_flow(client_id: str, client_secret: str, refresh_token: str) -> dict:
    """Renova o access_token usando refresh_token."""
    import httpx

    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{MP_API_BASE}/oauth/token", json=data)
        return resp.json()


def test_balance(access_token: str) -> dict:
    """Testa o endpoint de saldo com o novo token."""
    import httpx

    headers = {"Authorization": f"Bearer {access_token}"}
    results = {}

    with httpx.Client(timeout=15) as client:
        # Teste 1: /users/me
        try:
            r = client.get(f"{MP_API_BASE}/users/me", headers=headers)
            results["users_me"] = {
                "status": r.status_code,
                "data": r.json() if r.status_code == 200 else r.text[:200]
            }
        except Exception as e:
            results["users_me"] = {"status": "error", "data": str(e)}

        # Teste 2: balance
        try:
            r = client.get(
                f"{MP_API_BASE}/users/me/mercadopago_account/balance",
                headers=headers
            )
            results["balance"] = {
                "status": r.status_code,
                "data": r.json() if r.status_code == 200 else r.text[:200]
            }
        except Exception as e:
            results["balance"] = {"status": "error", "data": str(e)}

        # Teste 3: payments (como referência)
        try:
            r = client.get(
                f"{MP_API_BASE}/v1/payments/search",
                headers=headers,
                params={"limit": 1, "sort": "date_created", "criteria": "desc"}
            )
            results["payments"] = {
                "status": r.status_code,
                "total": r.json().get("paging", {}).get("total", 0) if r.status_code == 200 else 0
            }
        except Exception as e:
            results["payments"] = {"status": "error", "data": str(e)}

        # Teste 4: movimentos
        try:
            r = client.get(
                f"{MP_API_BASE}/mercadopago_account/movements/search",
                headers=headers,
                params={"limit": 1}
            )
            results["movements"] = {
                "status": r.status_code,
                "data": r.json() if r.status_code == 200 else r.text[:200]
            }
        except Exception as e:
            results["movements"] = {"status": "error", "data": str(e)}

    return results


def save_token_to_env(token_data: dict, client_secret: str):
    """Salva o novo token no arquivo .env."""
    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 0)
    scope = token_data.get("scope", "")
    token_type = token_data.get("token_type", "Bearer")

    # Ler .env atual
    env_content = ""
    if ENV_FILE.exists():
        env_content = ENV_FILE.read_text()

    # Backup
    backup_path = ENV_FILE.with_suffix(f".env.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    if ENV_FILE.exists():
        backup_path.write_text(env_content)
        print_ok(f"Backup salvo em: {backup_path.name}")

    # Substituir ou adicionar tokens
    lines = env_content.splitlines()
    new_lines = []
    keys_updated = set()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("BANK_MERCADOPAGO_ACCESS_TOKEN="):
            new_lines.append(f"# [OLD {datetime.now().strftime('%Y-%m-%d')}] {line}")
            new_lines.append(f"BANK_MERCADOPAGO_ACCESS_TOKEN={access_token}")
            keys_updated.add("access_token")
        elif stripped.startswith("BANK_MERCADOPAGO_REFRESH_TOKEN="):
            new_lines.append(f"BANK_MERCADOPAGO_REFRESH_TOKEN={refresh_token}")
            keys_updated.add("refresh_token")
        elif stripped.startswith("BANK_MERCADOPAGO_CLIENT_SECRET="):
            new_lines.append(f"BANK_MERCADOPAGO_CLIENT_SECRET={client_secret}")
            keys_updated.add("client_secret")
        else:
            new_lines.append(line)

    # Adicionar chaves não existentes
    if "refresh_token" not in keys_updated and refresh_token:
        new_lines.append(f"BANK_MERCADOPAGO_REFRESH_TOKEN={refresh_token}")
    if "client_secret" not in keys_updated and client_secret:
        new_lines.append(f"BANK_MERCADOPAGO_CLIENT_SECRET={client_secret}")

    # Adicionar metadados OAuth2
    oauth_meta = [
        "",
        f"# === OAuth2 Token Metadata (atualizado {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===",
        f"BANK_MERCADOPAGO_TOKEN_TYPE={token_type}",
        f"BANK_MERCADOPAGO_EXPIRES_IN={expires_in}",
        f"BANK_MERCADOPAGO_SCOPE={scope}",
        f"BANK_MERCADOPAGO_CLIENT_ID={APP_ID}",
        f"BANK_MERCADOPAGO_REDIRECT_URI={REDIRECT_URI}",
    ]

    # Remover linhas OAuth2 antigas antes de adicionar novas
    final_lines = []
    skip_oauth_section = False
    for line in new_lines:
        if "=== OAuth2 Token Metadata" in line:
            skip_oauth_section = True
            continue
        if skip_oauth_section:
            if line.strip() == "" or line.startswith("BANK_MERCADOPAGO_TOKEN_TYPE=") or \
               line.startswith("BANK_MERCADOPAGO_EXPIRES_IN=") or \
               line.startswith("BANK_MERCADOPAGO_SCOPE=") or \
               line.startswith("BANK_MERCADOPAGO_CLIENT_ID=") or \
               line.startswith("BANK_MERCADOPAGO_REDIRECT_URI="):
                continue
            else:
                skip_oauth_section = False
        final_lines.append(line)

    final_lines.extend(oauth_meta)
    ENV_FILE.write_text("\n".join(final_lines) + "\n")


def try_client_credentials(client_id: str, client_secret: str) -> dict:
    """Tenta obter token via client_credentials (sem interação do usuário)."""
    import httpx

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{MP_API_BASE}/oauth/token", json=data)
        return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Mercado Pago OAuth2 Production Setup")
    parser.add_argument("--client-secret", help="Client secret do painel MP")
    parser.add_argument("--skip-browser", action="store_true", help="Não abre navegador automaticamente")
    parser.add_argument("--test-only", help="Apenas testa um token existente")
    parser.add_argument("--refresh", help="Renova token usando refresh_token")
    parser.add_argument("--no-pkce", action="store_true", help="Desabilita PKCE")
    args = parser.parse_args()

    print_header("Shared Banking — Mercado Pago OAuth2 Setup")

    # ── Modo teste ──
    if args.test_only:
        print_step(1, "Testando token fornecido...")
        results = test_balance(args.test_only)
        for endpoint, data in results.items():
            status = data.get("status", "?")
            icon = "✅" if status == 200 else "❌"
            print(f"  {icon} {endpoint}: {status}")
            if status == 200 and endpoint == "balance":
                bal = data.get("data", {})
                avail = bal.get("available_balance", "?")
                print(f"     💰 Saldo disponível: R$ {avail}")
        return

    # ── Passo 1: Verificar/obter client_secret ──
    print_step(1, "Verificar credenciais")

    client_secret = args.client_secret or os.environ.get("BANK_MERCADOPAGO_CLIENT_SECRET", "")

    # Tentar ler do .env
    if not client_secret and ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.strip().startswith("BANK_MERCADOPAGO_CLIENT_SECRET="):
                client_secret = line.split("=", 1)[1].strip()
                break

    if not client_secret:
        print()
        print(f"  {BOLD}O client_secret é necessário para o fluxo OAuth2.{RESET}")
        print(f"  Para obtê-lo, acesse o painel de desenvolvedor:")
        print()
        print(f"  {CYAN}https://www.mercadopago.com.br/developers/panel/app/{APP_ID}{RESET}")
        print()
        print(f"  1. Clique em {BOLD}\"Credenciais de produção\"{RESET}")
        print(f"  2. Copie o {BOLD}\"Client secret\"{RESET} (começa com algo como \"client_...\")")
        print()

        panel_url = f"https://www.mercadopago.com.br/developers/panel/app/{APP_ID}"
        if not args.skip_browser:
            print_warn("Abrindo painel no navegador...")
            webbrowser.open(panel_url)

        client_secret = input(f"  {BOLD}Cole o Client Secret aqui: {RESET}").strip()

        if not client_secret:
            print_error("Client secret não fornecido. Abortando.")
            sys.exit(1)

    print_ok(f"Client Secret: {client_secret[:8]}...{client_secret[-4:]}")

    # ── Passo 2: Tentar client_credentials primeiro (mais simples) ──
    print_step(2, "Tentando fluxo client_credentials (sem interação)...")

    cc_result = try_client_credentials(APP_ID, client_secret)

    if "access_token" in cc_result:
        print_ok(f"Token obtido via client_credentials!")
        cc_token = cc_result["access_token"]
        print(f"  Token: {cc_token[:15]}...{cc_token[-6:]}")
        print(f"  Expira em: {cc_result.get('expires_in', '?')} segundos")

        # Testar saldo com este token
        print_step(3, "Testando endpoints com token client_credentials...")
        results = test_balance(cc_token)
        balance_ok = False

        for endpoint, data in results.items():
            status = data.get("status", "?")
            icon = "✅" if status == 200 else "❌"
            print(f"  {icon} {endpoint}: {status}")
            if status == 200 and endpoint == "balance":
                balance_ok = True
                bal = data.get("data", {})
                avail = bal.get("available_balance", "?")
                total = bal.get("total_amount", "?")
                print(f"     💰 Saldo disponível: R$ {avail}")
                print(f"     💰 Saldo total: R$ {total}")

        if balance_ok:
            print()
            print_ok("Saldo obtido com sucesso via client_credentials!")
            save_token_to_env(cc_result, client_secret)
            print_ok("Token salvo no .env")
            return
        else:
            print_warn("client_credentials não deu acesso ao saldo. Tentando authorization_code...")
    else:
        error = cc_result.get("error", "unknown")
        msg = cc_result.get("message", cc_result.get("error_description", ""))
        print_warn(f"client_credentials falhou: {error} — {msg}")
        print_warn("Prosseguindo com authorization_code flow...")

    # ── Passo 3: Configurar redirect_uri no app ──
    print_step(3, "Configuração do redirect_uri")
    print()
    print(f"  {BOLD}IMPORTANTE:{RESET} O redirect_uri precisa estar cadastrado na aplicação.")
    print(f"  No painel do Mercado Pago:")
    print()
    print(f"  {CYAN}https://www.mercadopago.com.br/developers/panel/app/{APP_ID}/edit{RESET}")
    print()
    print(f"  Adicione este redirect_uri:")
    print(f"  {BOLD}{REDIRECT_URI}{RESET}")
    print()
    print(f"  Também certifique-se que:")
    print(f"  • \"Modo sandbox\" está {BOLD}DESATIVADO{RESET} (modo produção)")
    print(f"  • Scopes incluem: {BOLD}read, write, offline_access{RESET}")
    print()
    input(f"  {BOLD}Pressione ENTER quando tiver configurado o redirect_uri...{RESET}")

    # ── Passo 4: PKCE ──
    code_verifier = None
    code_challenge = None
    code_method = None

    if not args.no_pkce:
        code_verifier, code_challenge = generate_pkce()
        code_method = "S256"
        print_ok("PKCE gerado (S256)")

    # ── Passo 5: Gerar URL de autorização ──
    print_step(4, "Gerando URL de autorização OAuth2...")

    state = secrets.token_urlsafe(32)

    auth_params = {
        "response_type": "code",
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "state": state,
    }
    if code_challenge:
        auth_params["code_challenge"] = code_challenge
        auth_params["code_challenge_method"] = code_method

    auth_url = f"{MP_AUTH_BASE}/authorization?{urllib.parse.urlencode(auth_params)}"

    print()
    print(f"  {BOLD}URL de autorização:{RESET}")
    print(f"  {CYAN}{auth_url}{RESET}")
    print()

    # ── Passo 6: Iniciar servidor de callback ──
    print_step(5, f"Iniciando servidor de callback em http://localhost:{CALLBACK_PORT}...")
    server, thread = start_callback_server()
    print_ok(f"Servidor ouvindo na porta {CALLBACK_PORT}")

    # Abrir navegador
    if not args.skip_browser:
        print_warn("Abrindo navegador para autorização...")
        webbrowser.open(auth_url)
    else:
        print_warn("Abra a URL acima no navegador manualmente.")

    print()
    print(f"  {YELLOW}Aguardando autorização... (timeout: 5 minutos){RESET}")
    print(f"  {YELLOW}Faça login no Mercado Pago e permita o acesso.{RESET}")

    # ── Passo 7: Aguardar callback ──
    thread.join(timeout=300)

    if OAuthCallbackHandler.error:
        print_error(f"Erro na autorização: {OAuthCallbackHandler.error}")
        sys.exit(1)

    if not OAuthCallbackHandler.authorization_code:
        print_error("Timeout — nenhum código recebido em 5 minutos.")
        print(f"  Tente novamente executando: python3 {__file__}")
        sys.exit(1)

    code = OAuthCallbackHandler.authorization_code
    received_state = OAuthCallbackHandler.state_received

    # Validar state
    if received_state != state:
        print_warn(f"State mismatch! Enviado: {state[:8]}... Recebido: {received_state[:8] if received_state else 'None'}...")
        print_warn("Continuando mesmo assim (pode ser ataque CSRF)...")

    print_ok(f"Código de autorização recebido: {code[:10]}...")

    # ── Passo 8: Trocar code por access_token ──
    print_step(6, "Trocando código por access_token...")

    token_data = exchange_code_for_token(
        client_id=APP_ID,
        client_secret=client_secret,
        code=code,
        redirect_uri=REDIRECT_URI,
        code_verifier=code_verifier,
    )

    if "access_token" not in token_data:
        print_error(f"Erro ao obter token: {json.dumps(token_data, indent=2)}")
        sys.exit(1)

    new_token = token_data["access_token"]
    refresh_tok = token_data.get("refresh_token", "")
    expires = token_data.get("expires_in", 0)
    scope = token_data.get("scope", "")
    user_id = token_data.get("user_id", "")

    print_ok(f"Access Token obtido!")
    print(f"  Token: {new_token[:15]}...{new_token[-6:]}")
    print(f"  Refresh Token: {refresh_tok[:10]}...{refresh_tok[-4:]}" if refresh_tok else "  Refresh Token: (não fornecido)")
    print(f"  Expira em: {expires} segundos ({expires // 3600} horas / {expires // 86400} dias)")
    print(f"  Scope: {scope}")
    print(f"  User ID: {user_id}")

    # ── Passo 9: Testar saldo ──
    print_step(7, "Testando endpoints com novo token...")

    results = test_balance(new_token)
    balance_found = False

    for endpoint, data in results.items():
        status = data.get("status", "?")
        icon = "✅" if status == 200 else "❌"
        print(f"  {icon} {endpoint}: {status}")
        if status == 200 and endpoint == "balance":
            balance_found = True
            bal = data.get("data", {})
            avail = bal.get("available_balance", "?")
            total = bal.get("total_amount", "?")
            blocked = bal.get("unavailable_balance", "?")
            print(f"     💰 Saldo disponível: R$ {avail}")
            print(f"     💰 Saldo total: R$ {total}")
            print(f"     🔒 Saldo bloqueado: R$ {blocked}")
        elif status == 200 and endpoint == "users_me":
            user = data.get("data", {})
            name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            print(f"     👤 Usuário: {name}")
        elif status == 200 and endpoint == "payments":
            print(f"     📊 Total de pagamentos: {data.get('total', 0)}")
        elif status == 200 and endpoint == "movements":
            print(f"     📋 Movimentações acessíveis")

    # ── Passo 10: Salvar token ──
    print_step(8, "Salvando credenciais...")

    save_token_to_env(token_data, client_secret)

    print_ok("Token salvo no .env")
    print()
    print_header("Resumo Final")
    print(f"  App ID:          {APP_ID}")
    print(f"  User ID:         {user_id or USER_ID}")
    print(f"  Token válido:    {expires // 86400} dias")
    print(f"  Saldo obtido:    {'✅ SIM' if balance_found else '❌ NÃO (pode precisar de certificação)'}")
    print(f"  Arquivo .env:    {ENV_FILE}")
    print()

    if refresh_tok:
        print(f"  {YELLOW}Para renovar o token antes de expirar:{RESET}")
        print(f"  python3 {__file__} --refresh {refresh_tok}")
        print()

    if not balance_found:
        print(f"  {YELLOW}O saldo ainda não está acessível. Possíveis causas:{RESET}")
        print(f"  1. App ainda em modo sandbox — desative no painel")
        print(f"  2. Conta não é 'vendedor' — precisa ativar Mercado Pago na conta")
        print(f"  3. App não certificada — solicite certificação no painel")
        print(f"  4. Scopes insuficientes — verifique no painel")
        print()
        print(f"  {CYAN}Painel: https://www.mercadopago.com.br/developers/panel/app/{APP_ID}{RESET}")

    # ── Modo refresh ──
    if args.refresh:
        print_header("Renovação de Token")
        if not client_secret:
            print_error("Client secret necessário para renovar. Use --client-secret")
            sys.exit(1)

        result = refresh_token_flow(APP_ID, client_secret, args.refresh)
        if "access_token" in result:
            print_ok(f"Token renovado! Novo token: {result['access_token'][:15]}...")
            save_token_to_env(result, client_secret)
            print_ok("Salvo no .env")
        else:
            print_error(f"Falha: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    main()
