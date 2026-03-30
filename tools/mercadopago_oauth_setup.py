#!/usr/bin/env python3
"""
Mercado Pago / Mercado Livre — setup do Banking Agent

Suporta:
1. OAuth2 em `production` ou `sandbox`
2. Persistencia do ambiente e dos tokens no `.env` do banking
3. Teste de conectividade da conta
4. Listagem de meios de pagamento disponiveis
5. Criacao de checkout de teste para validar formas de cobranca
6. Consulta de cobrancas pendentes

Exemplos:
    python3 tools/mercadopago_oauth_setup.py --env sandbox
    python3 tools/mercadopago_oauth_setup.py --env sandbox --test-account
    python3 tools/mercadopago_oauth_setup.py --env sandbox --list-payment-methods
    python3 tools/mercadopago_oauth_setup.py --env sandbox --create-test-preference --amount 29.90
    python3 tools/mercadopago_oauth_setup.py --env sandbox --list-pending-charges --status pending,in_process
"""

import argparse
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

DEFAULT_APP_ID = "6949951091520165"
DEFAULT_USER_ID = "286267368"
CALLBACK_PORT = 8765
CALLBACK_PATH = "/callback"
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"
MP_API_BASE = "https://api.mercadopago.com"
MP_AUTH_BASE = "https://auth.mercadopago.com"
ENV_CHOICES = ("production", "sandbox")

PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / "agent_data" / "banking" / ".env"

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_header(text: str):
    print(f"\n{BOLD}{CYAN}{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}{RESET}\n")


def print_step(n: int, text: str):
    print(f"{BOLD}{GREEN}[Passo {n}]{RESET} {text}")


def print_warn(text: str):
    print(f"{YELLOW}⚠  {text}{RESET}")


def print_error(text: str):
    print(f"{RED}✖  {text}{RESET}")


def print_ok(text: str):
    print(f"{GREEN}✔  {text}{RESET}")


def mask_value(value: str, prefix: int = 8, suffix: int = 4) -> str:
    if not value:
        return "(vazio)"
    if suffix <= 0:
        return value[:prefix] + "..."
    if len(value) <= prefix + suffix:
        return value
    return f"{value[:prefix]}...{value[-suffix:]}"


def load_env_map() -> dict[str, str]:
    env_map: dict[str, str] = {}
    if not ENV_FILE.exists():
        return env_map
    for raw_line in ENV_FILE.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_map[key.strip()] = value.strip()
    return env_map


def get_env_value(key: str, env_map: dict[str, str] | None = None, default: str = "") -> str:
    if key in os.environ:
        return os.environ[key]
    if env_map is None:
        env_map = load_env_map()
    return env_map.get(key, default)


def determine_runtime_env(cli_value: str | None, env_map: dict[str, str]) -> str:
    raw = (cli_value or get_env_value("BANK_MERCADOPAGO_ENV", env_map, "production")).strip().lower()
    return raw if raw in ENV_CHOICES else "production"


def parse_decimal(amount_text: str) -> Decimal:
    normalized = amount_text.replace(",", ".").strip()
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"Valor invalido para cobranca: {amount_text}") from exc
    if amount <= 0:
        raise ValueError("O valor da cobranca deve ser maior que zero")
    return amount.quantize(Decimal("0.01"))


def default_headers(access_token: str | None = None, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if idempotency_key:
        headers["X-Idempotency-Key"] = idempotency_key
    return headers


def mp_request(
    method: str,
    path: str,
    *,
    access_token: str | None = None,
    params: dict | None = None,
    payload: dict | None = None,
    timeout: int = 30,
    idempotency_key: str | None = None,
) -> tuple[int, dict | str]:
    import httpx

    url = f"{MP_API_BASE}{path}"
    with httpx.Client(timeout=timeout) as client:
        response = client.request(
            method,
            url,
            headers=default_headers(access_token, idempotency_key=idempotency_key),
            params=params,
            json=payload,
        )

    try:
        body = response.json()
    except ValueError:
        body = response.text[:500]
    return response.status_code, body


def generate_pkce() -> tuple[str, str]:
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
                self._send_error("Nenhum codigo de autorizacao recebido")
        else:
            self.send_response(404)
            self.end_headers()

    def _send_success(self):
        html = """<!DOCTYPE html><html><head><meta charset="utf-8">
        <title>Banking Agent — OAuth2 OK</title>
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
            <div class="icon">OK</div>
            <h1>Autorizacao concedida</h1>
            <p>Feche esta aba e volte ao terminal.</p>
            <p style="color:#555">Banking Agent - Mercado Pago</p>
        </div></body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def _send_error(self, msg: str):
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
        <title>Banking Agent — Erro OAuth2</title>
        <style>
            body {{ font-family: sans-serif; display: flex; justify-content: center;
                   align-items: center; height: 100vh; background: #1a1a2e; color: #eee; margin: 0; }}
            .card {{ background: #16213e; padding: 40px; border-radius: 16px;
                    text-align: center; box-shadow: 0 8px 32px rgba(0,0,0,.3); }}
            h1 {{ color: #ff4444; }}
        </style></head><body>
        <div class="card">
            <div style="font-size:64px">ERRO</div>
            <h1>Erro na autorizacao</h1>
            <p>{msg}</p>
            <p style="color:#555">Tente novamente executando o script.</p>
        </div></body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        pass


def start_callback_server():
    server = http.server.HTTPServer(("0.0.0.0", CALLBACK_PORT), OAuthCallbackHandler)
    server.timeout = 300
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    return server, thread


def exchange_code_for_token(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    code_verifier: str | None = None,
) -> dict:
    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    if code_verifier:
        payload["code_verifier"] = code_verifier
    _, body = mp_request("POST", "/oauth/token", payload=payload)
    return body if isinstance(body, dict) else {"error": "invalid_response", "message": body}


def refresh_token_flow(client_id: str, client_secret: str, refresh_token: str) -> dict:
    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }
    _, body = mp_request("POST", "/oauth/token", payload=payload)
    return body if isinstance(body, dict) else {"error": "invalid_response", "message": body}


def try_client_credentials(client_id: str, client_secret: str) -> dict:
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    _, body = mp_request("POST", "/oauth/token", payload=payload)
    return body if isinstance(body, dict) else {"error": "invalid_response", "message": body}


def test_account(access_token: str) -> dict[str, dict]:
    results: dict[str, dict] = {}

    status, body = mp_request("GET", "/users/me", access_token=access_token, timeout=15)
    results["users_me"] = {"status": status, "data": body}

    status, body = mp_request(
        "GET",
        "/users/me/mercadopago_account/balance",
        access_token=access_token,
        timeout=15,
    )
    results["balance"] = {"status": status, "data": body}

    status, body = mp_request(
        "GET",
        "/v1/payments/search",
        access_token=access_token,
        params={"limit": 1, "sort": "date_created", "criteria": "desc"},
        timeout=15,
    )
    payments_total = 0
    if status == 200 and isinstance(body, dict):
        payments_total = body.get("paging", {}).get("total", 0)
    results["payments"] = {"status": status, "total": payments_total, "data": body}

    status, body = mp_request(
        "GET",
        "/mercadopago_account/movements/search",
        access_token=access_token,
        params={"limit": 1},
        timeout=15,
    )
    results["movements"] = {"status": status, "data": body}

    return results


def list_payment_methods(access_token: str) -> tuple[int, list[dict] | dict | str]:
    return mp_request("GET", "/v1/payment_methods", access_token=access_token, timeout=20)


def create_test_preference(
    access_token: str,
    *,
    amount: Decimal,
    title: str,
    external_reference: str,
    runtime_env: str,
) -> tuple[int, dict | str]:
    payload = {
        "items": [
            {
                "id": "banking-agent-test-charge",
                "title": title,
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(amount),
            }
        ],
        "external_reference": external_reference,
        "statement_descriptor": "BANKINGAGENT",
        "metadata": {
            "source": "banking-agent",
            "environment": runtime_env,
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        },
    }
    return mp_request(
        "POST",
        "/checkout/preferences",
        access_token=access_token,
        payload=payload,
        timeout=30,
        idempotency_key=external_reference,
    )


def list_pending_charges(
    access_token: str,
    *,
    statuses: list[str],
    limit: int,
) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for status_name in statuses:
        status_code, body = mp_request(
            "GET",
            "/v1/payments/search",
            access_token=access_token,
            params={
                "status": status_name,
                "limit": limit,
                "sort": "date_created",
                "criteria": "desc",
            },
            timeout=20,
        )
        results[status_name] = {"status": status_code, "data": body}
    return results


def save_token_to_env(
    token_data: dict,
    *,
    client_id: str,
    client_secret: str,
    runtime_env: str,
) -> None:
    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 0)
    scope = token_data.get("scope", "")
    token_type = token_data.get("token_type", "Bearer")

    env_content = ""
    if ENV_FILE.exists():
        env_content = ENV_FILE.read_text()

    backup_path = ENV_FILE.with_suffix(f".env.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    if ENV_FILE.exists():
        backup_path.write_text(env_content)
        print_ok(f"Backup salvo em: {backup_path.name}")

    replacements = {
        "BANK_MERCADOPAGO_ACCESS_TOKEN": access_token,
        "BANK_MERCADOPAGO_REFRESH_TOKEN": refresh_token,
        "BANK_MERCADOPAGO_CLIENT_SECRET": client_secret,
        "BANK_MERCADOPAGO_CLIENT_ID": client_id,
        "BANK_MERCADOPAGO_ENV": runtime_env,
        "BANK_MERCADOPAGO_TOKEN_TYPE": token_type,
        "BANK_MERCADOPAGO_EXPIRES_IN": str(expires_in),
        "BANK_MERCADOPAGO_SCOPE": scope,
        "BANK_MERCADOPAGO_REDIRECT_URI": REDIRECT_URI,
    }

    updated_keys: set[str] = set()
    new_lines: list[str] = []
    for line in env_content.splitlines():
        stripped = line.strip()
        replaced = False
        for key, value in replacements.items():
            if stripped.startswith(f"{key}="):
                if key == "BANK_MERCADOPAGO_ACCESS_TOKEN" and value:
                    new_lines.append(f"# [OLD {datetime.now().strftime('%Y-%m-%d')}] {line}")
                new_lines.append(f"{key}={value}")
                updated_keys.add(key)
                replaced = True
                break
        if not replaced:
            new_lines.append(line)

    for key, value in replacements.items():
        if key not in updated_keys and value:
            new_lines.append(f"{key}={value}")

    if not new_lines or new_lines[-1].strip():
        new_lines.append("")
    new_lines.extend(
        [
            f"# === Mercado Pago metadata ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===",
            f"# Ambiente banking agent: {runtime_env}",
        ]
    )

    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text("\n".join(new_lines) + "\n")


def print_test_results(results: dict[str, dict]):
    balance_found = False
    for endpoint, data in results.items():
        status = data.get("status", "?")
        icon = "OK" if status == 200 else "ERRO"
        print(f"  {icon} {endpoint}: {status}")
        if status == 200 and endpoint == "balance" and isinstance(data.get("data"), dict):
            balance_found = True
            bal = data["data"]
            print(f"     saldo disponivel: R$ {bal.get('available_balance', '?')}")
            print(f"     saldo total:      R$ {bal.get('total_amount', '?')}")
            print(f"     saldo bloqueado:  R$ {bal.get('unavailable_balance', '?')}")
        elif status == 200 and endpoint == "users_me" and isinstance(data.get("data"), dict):
            user = data["data"]
            name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            print(f"     usuario: {name or user.get('nickname', '?')}")
        elif status == 200 and endpoint == "payments":
            print(f"     total de pagamentos: {data.get('total', 0)}")
        elif status == 200 and endpoint == "movements":
            print("     movimentacoes acessiveis")
    if not balance_found:
        print_warn("Saldo nao retornou. Em sandbox isso pode depender do tipo da conta/app.")


def print_payment_methods(status_code: int, body):
    if status_code != 200:
        print_error(f"Falha ao listar meios de pagamento: {status_code}")
        print(json.dumps(body, indent=2, ensure_ascii=False) if isinstance(body, dict) else body)
        return
    methods = body if isinstance(body, list) else []
    print_ok(f"Meios de pagamento encontrados: {len(methods)}")
    for method in methods:
        print(
            "  - "
            f"{method.get('id')} | "
            f"{method.get('name')} | "
            f"tipo={method.get('payment_type_id')} | "
            f"status={method.get('status')}"
        )


def print_pending_charges(results: dict[str, dict]):
    for status_name, response in results.items():
        status_code = response.get("status")
        body = response.get("data")
        print(f"\n  Status consultado: {status_name}")
        if status_code != 200 or not isinstance(body, dict):
            print(f"  ERRO {status_code}: {body}")
            continue
        items = body.get("results", [])
        total = body.get("paging", {}).get("total", len(items))
        print(f"  Total encontrado: {total}")
        for payment in items[:10]:
            print(
                "   - "
                f"id={payment.get('id')} | "
                f"status={payment.get('status')} | "
                f"detail={payment.get('status_detail')} | "
                f"valor={payment.get('transaction_amount')} | "
                f"metodo={payment.get('payment_method_id')} | "
                f"ref={payment.get('external_reference')} | "
                f"criado={payment.get('date_created')}"
            )


def run_post_auth_actions(args, access_token: str, runtime_env: str):
    if args.test_account:
        print_step(1, f"Testando conectividade da conta em {runtime_env}")
        print_test_results(test_account(access_token))

    if args.list_payment_methods:
        print_step(2, "Listando meios de pagamento disponiveis")
        status_code, body = list_payment_methods(access_token)
        print_payment_methods(status_code, body)

    if args.create_test_preference:
        amount = parse_decimal(args.amount)
        external_reference = args.external_reference or f"banking-{runtime_env}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        print_step(3, f"Criando checkout de teste de R$ {amount}")
        status_code, body = create_test_preference(
            access_token,
            amount=amount,
            title=args.title,
            external_reference=external_reference,
            runtime_env=runtime_env,
        )
        if status_code not in (200, 201) or not isinstance(body, dict):
            print_error(f"Falha ao criar checkout de teste: {status_code}")
            print(json.dumps(body, indent=2, ensure_ascii=False) if isinstance(body, dict) else body)
        else:
            print_ok("Checkout de teste criado")
            print(f"  external_reference: {external_reference}")
            print(f"  preference_id:      {body.get('id')}")
            print(f"  init_point:         {body.get('init_point')}")
            print(f"  sandbox_init_point: {body.get('sandbox_init_point')}")
            print("  Use o sandbox_init_point para validar as formas de cobranca em ambiente de teste.")

    if args.list_pending_charges:
        statuses = [item.strip() for item in args.status.split(",") if item.strip()]
        print_step(4, f"Consultando cobrancas pendentes: {', '.join(statuses)}")
        print_pending_charges(list_pending_charges(access_token, statuses=statuses, limit=args.limit))


def parse_args():
    parser = argparse.ArgumentParser(description="Mercado Pago Banking Agent Setup")
    parser.add_argument("--env", choices=ENV_CHOICES, help="Ambiente do Mercado Pago: sandbox ou production")
    parser.add_argument("--client-id", help="Client ID/App ID da aplicacao Mercado Pago")
    parser.add_argument("--client-secret", help="Client secret do painel Mercado Pago")
    parser.add_argument("--access-token", help="Access token para operacoes sem OAuth")
    parser.add_argument("--skip-browser", action="store_true", help="Nao abre navegador automaticamente")
    parser.add_argument("--refresh", help="Renova token usando refresh_token")
    parser.add_argument("--no-pkce", action="store_true", help="Desabilita PKCE")
    parser.add_argument("--test-account", action="store_true", help="Testa os endpoints basicos da conta atual")
    parser.add_argument("--list-payment-methods", action="store_true", help="Lista as formas de cobranca disponiveis")
    parser.add_argument("--create-test-preference", action="store_true", help="Cria um checkout de teste para validar cobrancas")
    parser.add_argument("--list-pending-charges", action="store_true", help="Consulta cobrancas pendentes")
    parser.add_argument("--amount", default="19.90", help="Valor da cobranca de teste")
    parser.add_argument("--title", default="Cobranca de teste Banking Agent", help="Titulo da cobranca de teste")
    parser.add_argument("--external-reference", help="Referencia externa para a cobranca de teste")
    parser.add_argument("--status", default="pending", help="Status para consulta de cobrancas, separados por virgula")
    parser.add_argument("--limit", type=int, default=20, help="Limite por consulta de cobrancas")
    return parser.parse_args()


def main():
    args = parse_args()
    env_map = load_env_map()
    runtime_env = determine_runtime_env(args.env, env_map)
    client_id = args.client_id or get_env_value("BANK_MERCADOPAGO_CLIENT_ID", env_map, DEFAULT_APP_ID)

    print_header("Banking Agent — Mercado Pago Setup")
    print(f"Ambiente:  {runtime_env}")
    print(f"Client ID: {client_id}")
    print(f"Arquivo:   {ENV_FILE}")

    access_token = args.access_token or get_env_value("BANK_MERCADOPAGO_ACCESS_TOKEN", env_map, "")
    client_secret = args.client_secret or get_env_value("BANK_MERCADOPAGO_CLIENT_SECRET", env_map, "")

    if args.refresh:
        print_step(1, "Renovando token")
        if not client_secret:
            print_error("Client secret necessario para renovar token. Use --client-secret.")
            sys.exit(1)
        token_data = refresh_token_flow(client_id, client_secret, args.refresh)
        if "access_token" not in token_data:
            print_error(f"Falha na renovacao: {json.dumps(token_data, indent=2, ensure_ascii=False)}")
            sys.exit(1)
        save_token_to_env(token_data, client_id=client_id, client_secret=client_secret, runtime_env=runtime_env)
        access_token = token_data["access_token"]
        print_ok(f"Token renovado: {mask_value(access_token)}")

    requested_runtime_actions = any(
        [
            args.test_account,
            args.list_payment_methods,
            args.create_test_preference,
            args.list_pending_charges,
        ]
    )

    if requested_runtime_actions and access_token:
        print_ok(f"Usando access token: {mask_value(access_token)}")
        run_post_auth_actions(args, access_token, runtime_env)
        return

    print_step(1, "Verificando credenciais OAuth")
    if not client_secret:
        print()
        print(f"  {BOLD}O client_secret e necessario para o fluxo OAuth2.{RESET}")
        print("  Para obte-lo, acesse o painel de desenvolvedor:")
        print(f"  {CYAN}https://www.mercadopago.com.br/developers/panel/app/{client_id}{RESET}")
        print()
        print(f"  1. Abra as credenciais do ambiente {runtime_env}")
        print('  2. Copie o campo "Client secret"')
        print()
        panel_url = f"https://www.mercadopago.com.br/developers/panel/app/{client_id}"
        if not args.skip_browser:
            print_warn("Abrindo painel no navegador...")
            webbrowser.open(panel_url)
        client_secret = input(f"  {BOLD}Cole o Client Secret aqui: {RESET}").strip()
        if not client_secret:
            print_error("Client secret nao fornecido. Abortando.")
            sys.exit(1)

    print_ok(f"Client Secret: {mask_value(client_secret)}")

    print_step(2, "Tentando fluxo client_credentials")
    cc_result = try_client_credentials(client_id, client_secret)
    if "access_token" in cc_result:
        cc_token = cc_result["access_token"]
        print_ok(f"Token obtido via client_credentials: {mask_value(cc_token)}")
        results = test_account(cc_token)
        print_test_results(results)
        save_token_to_env(cc_result, client_id=client_id, client_secret=client_secret, runtime_env=runtime_env)
        print_ok("Token salvo no .env")
        return

    error = cc_result.get("error", "unknown")
    message = cc_result.get("message", cc_result.get("error_description", ""))
    print_warn(f"client_credentials falhou: {error} - {message}")
    print_warn("Prosseguindo com authorization_code")

    print_step(3, "Configurando redirect URI")
    print(f"  Painel: {CYAN}https://www.mercadopago.com.br/developers/panel/app/{client_id}/edit{RESET}")
    print(f"  Redirect URI: {BOLD}{REDIRECT_URI}{RESET}")
    if runtime_env == "sandbox":
        print("  Confirme que o app e os usuarios de teste estao configurados para sandbox.")
    else:
        print('  Confirme que o "Modo sandbox" esta desativado para usar producao.')
    print("  Scopes recomendados: read, write, offline_access")
    input(f"  {BOLD}Pressione ENTER quando o painel estiver configurado...{RESET}")

    code_verifier = None
    code_challenge = None
    code_method = None
    if not args.no_pkce:
        code_verifier, code_challenge = generate_pkce()
        code_method = "S256"
        print_ok("PKCE gerado")

    print_step(4, "Gerando URL de autorizacao")
    state = secrets.token_urlsafe(32)
    auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "state": state,
    }
    if code_challenge:
        auth_params["code_challenge"] = code_challenge
        auth_params["code_challenge_method"] = code_method
    auth_url = f"{MP_AUTH_BASE}/authorization?{urllib.parse.urlencode(auth_params)}"
    print(f"  {CYAN}{auth_url}{RESET}")

    print_step(5, f"Iniciando callback em http://localhost:{CALLBACK_PORT}")
    _, thread = start_callback_server()
    if not args.skip_browser:
        print_warn("Abrindo navegador para autorizacao...")
        webbrowser.open(auth_url)
    else:
        print_warn("Abra a URL acima manualmente no navegador.")

    print("  Aguardando autorizacao por ate 5 minutos...")
    thread.join(timeout=300)

    if OAuthCallbackHandler.error:
        print_error(f"Erro na autorizacao: {OAuthCallbackHandler.error}")
        sys.exit(1)
    if not OAuthCallbackHandler.authorization_code:
        print_error("Timeout aguardando codigo de autorizacao.")
        sys.exit(1)
    if OAuthCallbackHandler.state_received != state:
        print_warn("State divergente no callback. Revise a execucao antes de usar em producao.")

    print_ok(f"Codigo recebido: {mask_value(OAuthCallbackHandler.authorization_code, 10, 0)}")

    print_step(6, "Trocando codigo por access token")
    token_data = exchange_code_for_token(
        client_id=client_id,
        client_secret=client_secret,
        code=OAuthCallbackHandler.authorization_code,
        redirect_uri=REDIRECT_URI,
        code_verifier=code_verifier,
    )
    if "access_token" not in token_data:
        print_error(f"Erro ao obter token: {json.dumps(token_data, indent=2, ensure_ascii=False)}")
        sys.exit(1)

    access_token = token_data["access_token"]
    print_ok(f"Access Token obtido: {mask_value(access_token)}")
    if token_data.get("refresh_token"):
        print(f"  Refresh Token: {mask_value(token_data['refresh_token'])}")
    print(f"  Expira em:     {token_data.get('expires_in', '?')} segundos")
    print(f"  Scope:         {token_data.get('scope', '')}")
    print(f"  User ID:       {token_data.get('user_id', DEFAULT_USER_ID)}")

    print_step(7, "Testando conta")
    print_test_results(test_account(access_token))

    print_step(8, "Salvando credenciais")
    save_token_to_env(token_data, client_id=client_id, client_secret=client_secret, runtime_env=runtime_env)
    print_ok("Token salvo no .env")
    print()
    print_header("Resumo Final")
    print(f"  Ambiente salvo: {runtime_env}")
    print(f"  Client ID:      {client_id}")
    print(f"  Access token:   {mask_value(access_token)}")
    print(f"  Arquivo .env:   {ENV_FILE}")
    print()
    print("  Comandos uteis:")
    print(f"  python3 {__file__} --env {runtime_env} --test-account")
    print(f"  python3 {__file__} --env {runtime_env} --list-payment-methods")
    print(f"  python3 {__file__} --env {runtime_env} --create-test-preference --amount 29.90")
    print(f"  python3 {__file__} --env {runtime_env} --list-pending-charges --status pending,in_process")

    if requested_runtime_actions:
        print()
        print_ok("Executando as acoes solicitadas com o token recem-obtido")
        run_post_auth_actions(args, access_token, runtime_env)


if __name__ == "__main__":
    main()
