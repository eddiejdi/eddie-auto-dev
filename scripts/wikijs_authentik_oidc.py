#!/usr/bin/env python3
"""Configura autenticação OIDC (Authentik) no Wiki.js.

Registra a estratégia Generic OpenID Connect no Wiki.js via GraphQL,
apontando para o Authentik SSO em auth.rpa4all.com.

Pré-requisito: Criar provider OAuth2 'authentik-wikijs' no Authentik Admin:
  1. Admin → Providers → Create → OAuth2/OpenID Connect
     - Name: Wiki.js
     - Client ID: authentik-wikijs
     - Client Secret: (gerar)
     - Redirect URIs: https://wiki.rpa4all.com/login/oidc/callback
     - Scopes: openid, email, profile
  2. Admin → Applications → Create
     - Name: Wiki.js
     - Slug: wikijs
     - Provider: Wiki.js (criado acima)
"""

import json
import logging
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Secrets Agent
SECRETS_URL = os.getenv("SECRETS_AGENT_URL", "http://192.168.15.2:8088")
SECRETS_KEY = os.getenv("SECRETS_AGENT_KEY", "")


def _get_secret(name: str, field: str) -> str:
    """Busca secret no Secrets Agent."""
    headers = {"X-API-KEY": SECRETS_KEY}
    req = Request(f"{SECRETS_URL}/secrets/local/{name}?field={field}", headers=headers)
    try:
        with urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("value", "")
    except Exception as e:
        log.warning("Secret %s/%s não encontrada: %s", name, field, e)
        return ""


WIKIJS_URL = "http://localhost:3009/graphql"
ADMIN_EMAIL = _get_secret("wikijs/admin", "username") or "admin@rpa4all.com"
ADMIN_PASS = _get_secret("wikijs/admin", "password") or ""

# Authentik OIDC endpoints
AUTHENTIK_BASE = "https://auth.rpa4all.com"
OIDC_DISCOVERY = f"{AUTHENTIK_BASE}/application/o/wikijs/.well-known/openid-configuration"
AUTHORIZE_URL = f"{AUTHENTIK_BASE}/application/o/authorize/"
TOKEN_URL = f"{AUTHENTIK_BASE}/application/o/token/"
USERINFO_URL = f"{AUTHENTIK_BASE}/application/o/userinfo/"
LOGOUT_URL = f"{AUTHENTIK_BASE}/application/o/wikijs/end-session/"

# Client credentials via Secrets Agent
CLIENT_ID = _get_secret("authentik/oidc_wikijs", "client_id") or "authentik-wikijs"
CLIENT_SECRET = _get_secret("authentik/oidc_wikijs", "client_secret") or ""


def graphql(query: str, variables: dict | None = None, token: str | None = None) -> dict:
    """Executa query GraphQL no Wiki.js."""
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(WIKIJS_URL, data=payload, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        log.error("GraphQL HTTP %d: %s", e.code, e.read().decode()[:300])
        raise


def login() -> str:
    """Autentica no Wiki.js e retorna JWT."""
    query = """mutation($email: String!, $password: String!) {
        authentication {
            login(username: $email, password: $password, strategy: "local") {
                responseResult { succeeded message }
                jwt
            }
        }
    }"""
    result = graphql(query, {"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    login_data = result["data"]["authentication"]["login"]
    if not login_data["responseResult"]["succeeded"]:
        log.error("Login falhou: %s", login_data["responseResult"]["message"])
        sys.exit(1)
    log.info("Login OK")
    return login_data["jwt"]


def get_auth_strategies(token: str) -> list[dict]:
    """Lista estratégias de autenticação atuais."""
    query = """{ authentication { activeStrategies { key strategy { key title } config { key value } } } }"""
    result = graphql(query, token=token)
    return result["data"]["authentication"]["activeStrategies"]


def configure_oidc(token: str) -> bool:
    """Configura a estratégia OIDC no Wiki.js."""
    # Wiki.js v2 usa a mutation authentication.updateStrategies
    # A estratégia OIDC se chama "oidc" no Wiki.js
    query = """mutation($strategies: [AuthenticationStrategyInput]!) {
        authentication {
            updateStrategies(strategies: $strategies) {
                responseResult { succeeded message }
            }
        }
    }"""

    strategies = [
        # Manter estratégia local ativa
        {
            "key": "local",
            "strategyKey": "local",
            "displayName": "Local",
            "order": 1,
            "isEnabled": True,
            "config": [],
            "selfRegistration": False,
            "domainWhitelist": [],
            "autoEnrollGroups": [],
        },
        # Adicionar OIDC Authentik
        {
            "key": "oidc",
            "strategyKey": "oidc",
            "displayName": "Authentik SSO",
            "order": 0,
            "isEnabled": True,
            "config": [
                {"key": "clientId", "value": json.dumps(CLIENT_ID)},
                {"key": "clientSecret", "value": json.dumps(CLIENT_SECRET)},
                {"key": "authorizationURL", "value": json.dumps(AUTHORIZE_URL)},
                {"key": "tokenURL", "value": json.dumps(TOKEN_URL)},
                {"key": "userInfoURL", "value": json.dumps(USERINFO_URL)},
                {"key": "issuer", "value": json.dumps(f"{AUTHENTIK_BASE}/application/o/wikijs/")},
                {"key": "emailClaim", "value": json.dumps("email")},
                {"key": "displayNameClaim", "value": json.dumps("name")},
                {"key": "mapGroups", "value": json.dumps(False)},
                {"key": "groupsClaim", "value": json.dumps("groups")},
                {"key": "logoutURL", "value": json.dumps(LOGOUT_URL)},
                {"key": "callbackURL", "value": json.dumps("https://wiki.rpa4all.com/login/oidc/callback")},
                {"key": "scope", "value": json.dumps("openid email profile")},
            ],
            "selfRegistration": True,
            "domainWhitelist": ["rpa4all.com"],
            "autoEnrollGroups": [1],  # Grupo padrão (Users)
        },
    ]

    result = graphql(query, {"strategies": strategies}, token)
    resp = result["data"]["authentication"]["updateStrategies"]["responseResult"]
    if resp["succeeded"]:
        log.info("Estratégia OIDC configurada com sucesso")
    else:
        log.error("Falha ao configurar OIDC: %s", resp["message"])
    return resp["succeeded"]


def main() -> None:
    """Configura Authentik OIDC no Wiki.js."""
    log.info("=== Configurando Authentik OIDC para Wiki.js ===")

    token = login()

    # Listar estratégias atuais
    strategies = get_auth_strategies(token)
    log.info("Estratégias atuais: %s", [s["key"] for s in strategies])

    # Configurar OIDC
    success = configure_oidc(token)

    if success:
        log.info("")
        log.info("✅ OIDC configurado! Próximos passos:")
        log.info("   1. No Authentik Admin, crie o provider OAuth2:")
        log.info("      - Client ID: %s", CLIENT_ID)
        log.info("      - Client Secret: %s", CLIENT_SECRET)
        log.info("      - Redirect URI: https://wiki.rpa4all.com/login/oidc/callback")
        log.info("   2. Crie a Application 'Wiki.js' (slug: wikijs)")
        log.info("   3. Teste o login em https://wiki.rpa4all.com/login")
    else:
        log.error("Falha na configuração. Verifique os logs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
