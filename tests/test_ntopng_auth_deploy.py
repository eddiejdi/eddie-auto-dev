"""Testes de regressao do deploy do ntopng em auth.rpa4all.com."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = REPO_ROOT / "docker/docker-compose.ntopng.yml"
NGINX_SNIPPET_PATH = REPO_ROOT / "site/deploy/auth-ntopng-location.nginx.conf"
REGISTER_SCRIPT_PATH = REPO_ROOT / "scripts/misc/register_ntopng_authentik.sh"
DEPLOY_SCRIPT_PATH = REPO_ROOT / "scripts/deployment/deploy_ntopng_auth.sh"


def test_ntopng_compose_uses_http_prefix_and_loopback_port() -> None:
    payload = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))

    ntopng = payload["services"]["ntopng"]
    redis = payload["services"]["ntopng-redis"]

    assert ntopng["network_mode"] == "host"
    assert "127.0.0.1:6380:6379" in redis["ports"]
    assert "--http-prefix" in ntopng["command"]
    assert "/ntopng" in ntopng["command"]
    assert ":8877" in ntopng["command"]
    assert "eth-onboard" in ntopng["command"]
    assert "wg0" in ntopng["command"]


def test_ntopng_nginx_snippet_is_protected_by_authentik() -> None:
    content = NGINX_SNIPPET_PATH.read_text(encoding="utf-8")

    assert "location ^~ /ntopng/" in content
    assert "auth_request /outpost.goauthentik.io/auth/nginx;" in content
    assert "error_page 401 = @goauthentik_proxy_signin;" in content
    assert "proxy_pass http://127.0.0.1:8877/ntopng/;" in content
    assert "X-Forwarded-Prefix /ntopng" in content


def test_register_script_points_to_auth_library_url() -> None:
    content = REGISTER_SCRIPT_PATH.read_text(encoding="utf-8")

    assert 'APP_SLUG="network-audit"' in content
    assert 'APP_URL="${AUTH_URL}/ntopng/"' in content
    assert 'APP_NAME="Network Audit"' in content
    assert 'if api_get "/core/applications/${APP_SLUG}/" >/dev/null 2>&1; then' in content
    assert 'api_patch "/core/applications/${APP_SLUG}/" "${PAYLOAD}" >/dev/null' in content
    assert 'echo "updated:${APP_SLUG}:${APP_URL}"' in content


def test_deploy_script_validates_public_auth_redirect_and_cleans_backups() -> None:
    content = DEPLOY_SCRIPT_PATH.read_text(encoding="utf-8")

    assert 'PUBLIC_URL="https://auth.rpa4all.com/ntopng/"' in content
    assert "find /etc/nginx/sites-enabled -maxdepth 1 -type f -name 'auth.rpa4all.com.bak-*' -delete" in content
    assert 'Falha: rota publica retornou status ${PUBLIC_STATUS}, esperado 302' in content
    assert 'https://auth.rpa4all.com/outpost.goauthentik.io/start*' in content