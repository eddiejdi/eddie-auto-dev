"""Regression tests for the CMDB stack artifacts."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = REPO_ROOT / "deploy/cmdb/docker-compose.yml"
NGINX_TEMPLATE_PATH = REPO_ROOT / "deploy/cmdb/nginx/templates/default.conf.template"
README_PATH = REPO_ROOT / "deploy/cmdb/README.md"
GLPI_APACHE_CONF_PATH = REPO_ROOT / "deploy/cmdb/glpi/apache/000-default.conf"
NETBOX_EXTRA_PATH = REPO_ROOT / "deploy/cmdb/netbox/extra.py"
AUTH_NGINX_SNIPPET_PATH = REPO_ROOT / "site/deploy/auth-cmdb-location.nginx.conf"
AUTH_PUBLIC_NGINX_PATH = REPO_ROOT / "site/deploy/auth-public-server.nginx.conf"


def test_cmdb_compose_contains_expected_services_and_bindings() -> None:
    payload = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    services = payload["services"]

    assert {
        "netbox",
        "netbox-worker",
        "netbox-postgres",
        "netbox-redis",
        "netbox-redis-cache",
        "glpi",
        "glpi-db",
        "proxy",
    }.issubset(services)

    assert "${NETBOX_BIND:-127.0.0.1}:${NETBOX_DIRECT_PORT:-18091}:8080" in services["netbox"]["ports"]
    assert "${GLPI_BIND:-127.0.0.1}:${GLPI_DIRECT_PORT:-18092}:80" in services["glpi"]["ports"]
    assert "${CMDB_PROXY_BIND:-127.0.0.1}:${CMDB_PROXY_HTTP_PORT:-18090}:80" in services["proxy"]["ports"]


def test_cmdb_compose_wires_netbox_and_glpi_bootstrap_variables() -> None:
    payload = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    netbox_env = payload["services"]["netbox"]["environment"]
    glpi_env = payload["services"]["glpi"]["environment"]
    netbox_volumes = payload["services"]["netbox"]["volumes"]
    glpi_volumes = payload["services"]["glpi"]["volumes"]
    netbox_healthcheck = payload["services"]["netbox"]["healthcheck"]["test"][1]

    assert netbox_env["DB_HOST"] == "netbox-postgres"
    assert netbox_env["REDIS_HOST"] == "netbox-redis"
    assert "NETBOX_SECRET_KEY" in netbox_env["SECRET_KEY"]
    assert "NETBOX_SUPERUSER_PASSWORD" in netbox_env["SUPERUSER_PASSWORD"]
    assert "NETBOX_REMOTE_AUTH_ENABLED" in netbox_env["REMOTE_AUTH_ENABLED"]
    assert "NETBOX_REMOTE_AUTH_GROUP_HEADER" in netbox_env["REMOTE_AUTH_GROUP_HEADER"]
    assert "NETBOX_REMOTE_AUTH_SUPERUSER_GROUPS" in netbox_env["REMOTE_AUTH_SUPERUSER_GROUPS"]
    assert "NETBOX_CSRF_TRUSTED_ORIGINS" in netbox_env["CSRF_TRUSTED_ORIGINS"]
    assert "NETBOX_BASE_PATH" in netbox_env["NETBOX_BASE_PATH"]
    assert "NETBOX_BASE_PATH" in netbox_healthcheck
    assert "./netbox/extra.py:/etc/netbox/config/extra.py:ro" in netbox_volumes

    assert glpi_env["GLPI_DB_HOST"] == "glpi-db"
    assert glpi_env["GLPI_DB_PORT"] == "3306"
    assert "GLPI_DB_PASSWORD" in glpi_env["GLPI_DB_PASSWORD"]
    assert "GLPI_CRONTAB_ENABLED" in glpi_env["GLPI_CRONTAB_ENABLED"]
    assert "./glpi/apache/000-default.conf:/etc/apache2/sites-available/000-default.conf:ro" in glpi_volumes


def test_nginx_template_routes_both_vhosts() -> None:
    content = NGINX_TEMPLATE_PATH.read_text(encoding="utf-8")

    assert "${NETBOX_SERVER_NAME}" in content
    assert "${GLPI_SERVER_NAME}" in content
    assert "proxy_pass http://netbox:8080;" in content
    assert "proxy_pass http://glpi:80;" in content


def test_cmdb_readme_references_baseline_generator_and_safe_deploy() -> None:
    content = README_PATH.read_text(encoding="utf-8")

    assert "generate_cmdb_baseline.py" in content
    assert "deploy_cmdb_stack.sh" in content
    assert "deploy_cmdb_auth.sh" in content
    assert "NetBox direto" in content
    assert "install_glpi_schema.sh" in content
    assert "seed_netbox_minimal.sh" in content
    assert "configure_glpi_sso.sh" in content
    assert "ensure_glpi_admin_users.sh" in content


def test_cmdb_auth_publication_artifacts_exist() -> None:
    apache_conf = GLPI_APACHE_CONF_PATH.read_text(encoding="utf-8")
    netbox_extra = NETBOX_EXTRA_PATH.read_text(encoding="utf-8")
    auth_snippet = AUTH_NGINX_SNIPPET_PATH.read_text(encoding="utf-8")
    auth_public = AUTH_PUBLIC_NGINX_PATH.read_text(encoding="utf-8")

    assert "Alias /cmdb/glpi" in apache_conf
    assert "RewriteRule ^(.*)$ index.php" in apache_conf
    assert 'NETBOX_BASE_PATH' in netbox_extra
    assert "location ^~ /cmdb/netbox/static/" in auth_snippet
    assert "proxy_pass http://127.0.0.1:18091/static/;" in auth_snippet
    assert "location ^~ /cmdb/netbox/media/" in auth_snippet
    assert "proxy_pass http://127.0.0.1:18091/media/;" in auth_snippet
    assert "location ^~ /cmdb/netbox/" in auth_snippet
    assert "location ^~ /cmdb/glpi/" in auth_snippet
    assert "alias /var/www/cmdb-auth/;" in auth_snippet
    assert "index index.html;" in auth_snippet
    assert "server_name auth.rpa4all.com;" in auth_public
    assert "proxy_pass http://127.0.0.1:9001;" in auth_public
    assert "/etc/letsencrypt/live/auth.rpa4all.com/fullchain.pem" in auth_public
