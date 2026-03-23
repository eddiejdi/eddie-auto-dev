#!/usr/bin/env python3
"""
Reset de senha de usuário Google Workspace via Admin SDK.

Uso:
  python3 scripts/automation/gws_reset_password.py \
      --user antonio.carneiro@rpa4all.com \
      --new-password 'NovaSenha@2026'

Na primeira execução, abre o navegador para autorização do admin.
O token fica salvo em /tmp/gws_admin_token.json para reutilização.
"""

from __future__ import annotations

import argparse
import base64
import http.server
import json
import logging
import os
import secrets
import string
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
OAUTH_CLIENT_ID = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
OAUTH_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
ADMIN_SCOPE = "https://www.googleapis.com/auth/admin.directory.user"
OAUTH_PORT = 8765
OAUTH_REDIRECT_URI = f"http://localhost:{OAUTH_PORT}"
ADMIN_TOKEN_FILE = Path("/tmp/gws_admin_token.json")
ADMIN_LOGIN_HINT = "edenilson.paschoa@rpa4all.com"


# ─────────────────────────────────────────────────────────────────────────────
# OAuth helpers
# ─────────────────────────────────────────────────────────────────────────────


def _build_auth_url() -> str:
    """Gera URL de autorização OAuth2 para o admin do Google Workspace."""
    params = {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "scope": ADMIN_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "login_hint": ADMIN_LOGIN_HINT,
    }
    return "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(params)


def _wait_for_oauth_code() -> str:
    """Sobe servidor HTTP local e aguarda callback do Google com o código."""
    captured: dict[str, str] = {}
    event = threading.Event()

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            if "code" in params:
                captured["code"] = params["code"][0]
                body = b"<html><body><h2>Autorizado! Pode fechar esta janela.</h2></body></html>"
            elif "error" in params:
                captured["error"] = params.get("error", ["desconhecido"])[0]
                body = b"<html><body><h2>Erro. Tente novamente.</h2></body></html>"
            else:
                body = b"<html><body><h2>Aguardando...</h2></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
            event.set()

        def log_message(self, *args: Any) -> None:
            pass

    server = http.server.HTTPServer(("", OAUTH_PORT), _Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    event.wait(timeout=120)
    server.server_close()

    if "error" in captured:
        raise RuntimeError(f"Erro OAuth: {captured['error']}")
    if "code" not in captured:
        raise RuntimeError("Timeout aguardando autorização (120s)")
    return captured["code"]


def _exchange_code(code: str) -> dict[str, Any]:
    """Troca código OAuth por access + refresh token."""
    payload = urllib.parse.urlencode(
        {
            "code": code.strip(),
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
    ).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        raise RuntimeError(f"Erro ao trocar código: {exc.code} — {body}") from exc


def _refresh_access_token(refresh_token: str) -> str:
    """Renova o access_token usando o refresh_token."""
    payload = urllib.parse.urlencode(
        {
            "refresh_token": refresh_token,
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "grant_type": "refresh_token",
        }
    ).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data["access_token"]
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        raise RuntimeError(f"Erro ao renovar token: {exc.code} — {body}") from exc


def get_access_token() -> str:
    """
    Obtém um access_token válido para o Admin SDK.

    - Se já existir token salvo com refresh_token, renova automaticamente.
    - Caso contrário, conduz fluxo OAuth interativo.
    """
    if ADMIN_TOKEN_FILE.exists():
        data = json.loads(ADMIN_TOKEN_FILE.read_text())
        if "refresh_token" in data:
            logger.info("Renovando access_token com refresh_token existente...")
            try:
                access = _refresh_access_token(data["refresh_token"])
                logger.info("Token renovado com sucesso.")
                return access
            except RuntimeError as exc:
                logger.warning("Falha ao renovar: %s — iniciando novo fluxo OAuth.", exc)
                ADMIN_TOKEN_FILE.unlink(missing_ok=True)

    # Fluxo OAuth interativo
    url = _build_auth_url()
    print("\n" + "─" * 70)
    print("  AUTORIZAÇÃO NECESSÁRIA — Admin Google Workspace")
    print("─" * 70)
    print(f"\n  Faça login com: {ADMIN_LOGIN_HINT}")
    print(f"\n  Se o navegador não abrir, acesse:\n  {url}\n")
    print(f"  Aguardando callback em http://localhost:{OAUTH_PORT} ...", flush=True)
    webbrowser.open(url)

    code = _wait_for_oauth_code()
    print("\n  Código recebido! Trocando por tokens...", end=" ", flush=True)
    token_data = _exchange_code(code)
    ADMIN_TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    print("OK ✓")
    return token_data["access_token"]


# ─────────────────────────────────────────────────────────────────────────────
# Admin Directory API
# ─────────────────────────────────────────────────────────────────────────────


def _admin_api(
    method: str,
    path: str,
    access_token: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Executa chamada à Admin SDK Directory API."""
    url = f"https://admin.googleapis.com/admin/directory/v1{path}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_body = json.loads(resp.read().decode()) if resp.length != 0 else {}
            return resp.status, resp_body
    except urllib.error.HTTPError as exc:
        body_err = exc.read().decode()
        try:
            return exc.code, json.loads(body_err)
        except Exception:
            return exc.code, {"error": body_err}


def get_user_info(user_email: str, access_token: str) -> dict[str, Any]:
    """Obtém informações do usuário no Google Workspace."""
    code, data = _admin_api("GET", f"/users/{urllib.parse.quote(user_email)}", access_token)
    if code != 200:
        raise RuntimeError(f"Erro ao buscar usuário: {code} — {data}")
    return data


def reset_password(user_email: str, new_password: str, access_token: str) -> None:
    """
    Reseta a senha de um usuário no Google Workspace via Admin SDK.

    Args:
        user_email: E-mail do usuário (ex: antonio.carneiro@rpa4all.com).
        new_password: Nova senha a definir.
        access_token: Token de acesso com scope admin.directory.user.
    """
    payload = {
        "password": new_password,
        "changePasswordAtNextLogin": True,
    }
    code, data = _admin_api(
        "PUT",
        f"/users/{urllib.parse.quote(user_email)}",
        access_token,
        body=payload,
    )
    if code in (200, 204):
        return
    raise RuntimeError(f"Falha ao resetar senha: {code} — {data}")


# ─────────────────────────────────────────────────────────────────────────────
# Geração de senha segura
# ─────────────────────────────────────────────────────────────────────────────


def generate_secure_password(length: int = 14) -> str:
    """Gera senha segura com letras, números e símbolos."""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        # Garantir pelo menos 1 de cada categoria
        if (
            any(c.isupper() for c in pwd)
            and any(c.islower() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%&*" for c in pwd)
        ):
            return pwd


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Ponto de entrada: reseta senha de usuário Google Workspace."""
    parser = argparse.ArgumentParser(
        description="Reseta senha de usuário no Google Workspace via Admin SDK"
    )
    parser.add_argument(
        "--user",
        default="antonio.carneiro@rpa4all.com",
        help="E-mail do usuário (default: antonio.carneiro@rpa4all.com)",
    )
    parser.add_argument(
        "--new-password",
        default=None,
        help="Nova senha (se não fornecida, gera automaticamente)",
    )
    args = parser.parse_args()

    new_password = args.new_password or generate_secure_password()

    print()
    print("╔" + "═" * 60 + "╗")
    print("║{:^60}║".format("RESET DE SENHA — Google Workspace"))
    print("║{:^60}║".format(f"Usuário: {args.user}"))
    print("╚" + "═" * 60 + "╝\n")

    # 1. Obter token admin
    print("[1/3] Autenticando como admin...", flush=True)
    try:
        access_token = get_access_token()
    except (RuntimeError, KeyboardInterrupt) as exc:
        logger.error("Falha na autenticação: %s", exc)
        sys.exit(1)

    # 2. Verificar que o usuário existe
    print(f"\n[2/3] Verificando usuário {args.user}...", flush=True)
    try:
        info = get_user_info(args.user, access_token)
        print(f"  ✓ Usuário encontrado: {info.get('name', {}).get('fullName', '?')}")
        print(f"  Status: {'Ativo' if not info.get('suspended') else 'Suspenso'}")
        print(f"  Último login: {info.get('lastLoginTime', 'nunca')}")
    except RuntimeError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    # 3. Resetar senha
    print(f"\n[3/3] Resetando senha...", flush=True)
    try:
        reset_password(args.user, new_password, access_token)
    except RuntimeError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    print()
    print("╔" + "═" * 60 + "╗")
    print("║{:^60}║".format("SENHA RESETADA COM SUCESSO ✓"))
    print("╠" + "═" * 60 + "╣")
    print(f"║  Usuário:  {args.user:<47}║")
    print(f"║  Senha:    {new_password:<47}║")
    print(f"║  Obs:      Deverá trocar no próximo login{' ' * 17}║")
    print("╚" + "═" * 60 + "╝")
    print()
    print("  ⚠  Comunique a nova senha ao usuário por canal seguro.")
    print()


if __name__ == "__main__":
    main()
