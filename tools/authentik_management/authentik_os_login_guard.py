#!/usr/bin/env python3
"""Integra validacao de login do SO com o Authentik."""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import pwd
import re
import shlex
import subprocess
import sys
from base64 import urlsafe_b64decode
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import requests

logger = logging.getLogger(__name__)

DEFAULT_ENV_FILE = Path("/etc/authentik/login-guard.env")
DEFAULT_COMMAND_PATH = "/usr/local/bin/authentik-login-guard"
PAM_GUARD_MARKER = "# Managed by Shared Auto-Dev: Authentik login guard"


def _parse_bool(raw_value: str, default: bool = False) -> bool:
    """Converte string de ambiente em booleano."""
    if not raw_value:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(raw_value: str) -> tuple[str, ...]:
    """Converte lista CSV em tupla limpa."""
    return tuple(item.strip() for item in raw_value.split(",") if item.strip())


def _load_env_file(env_file: Path) -> dict[str, str]:
    """Carrega arquivo simples KEY=VALUE usado pelo guard do PAM."""
    if not env_file.exists():
        return {}

    env_map: dict[str, str] = {}
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_map[key.strip()] = value.strip().strip('"').strip("'")
    return env_map


@dataclass(frozen=True)
class AuthentikLoginSettings:
    """Configuracao da validacao de login no Authentik."""

    base_url: str
    token: str
    verify_tls: bool = False
    timeout_seconds: float = 5.0
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_scopes: str = "openid profile email"
    token_endpoint: str = ""
    userinfo_endpoint: str = ""
    auth_mode: str = "auto"
    flow_slug: str = "default-authentication-flow"
    flow_executor_url: str = ""
    allow_local_users: tuple[str, ...] = ("root", "homelab")
    provision_local_users: bool = True
    local_user_shell: str = "/bin/bash"
    local_user_groups: tuple[str, ...] = ()
    local_username_pattern: str = r"^[a-z_][a-z0-9_-]{0,31}$"

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        env_file: Path | None = None,
    ) -> "AuthentikLoginSettings":
        """Monta configuracao a partir de variaveis de ambiente e arquivo local."""
        env_map: dict[str, str] = {}
        if env_file is not None:
            env_map.update(_load_env_file(env_file))
        if environ is not None:
            env_map.update(environ)
        else:
            env_map.update(os.environ)

        base_url = env_map.get("AUTHENTIK_URL", "https://auth.rpa4all.com").rstrip("/")
        token = env_map.get("AUTHENTIK_TOKEN", "")
        verify_tls = _parse_bool(env_map.get("AUTHENTIK_VERIFY_TLS", "false"))
        timeout_seconds = float(env_map.get("AUTHENTIK_LOGIN_TIMEOUT", "5"))
        oidc_client_id = env_map.get("AUTHENTIK_OS_CLIENT_ID", "").strip() or env_map.get("OIDC_CLIENT_ID", "").strip()
        oidc_client_secret = (
            env_map.get("AUTHENTIK_OS_CLIENT_SECRET", "").strip()
            or env_map.get("OIDC_CLIENT_SECRET", "").strip()
        )
        oidc_scopes = env_map.get("AUTHENTIK_OS_SCOPES", "openid profile email").strip() or "openid profile email"
        token_endpoint = (
            env_map.get("AUTHENTIK_OS_TOKEN_ENDPOINT", "").strip()
            or f"{base_url}/application/o/token/"
        )
        userinfo_endpoint = (
            env_map.get("AUTHENTIK_OS_USERINFO_ENDPOINT", "").strip()
            or f"{base_url}/application/o/userinfo/"
        )
        auth_mode = env_map.get("AUTHENTIK_OS_AUTH_MODE", "auto").strip().lower() or "auto"
        flow_slug = env_map.get("AUTHENTIK_OS_FLOW_SLUG", "default-authentication-flow").strip() or "default-authentication-flow"
        flow_executor_url = (
            env_map.get("AUTHENTIK_OS_FLOW_EXECUTOR_URL", "").strip()
            or f"{base_url}/api/v3/flows/executor/{flow_slug}/"
        )
        allow_local_users = _parse_csv(env_map.get("AUTHENTIK_LOGIN_ALLOW_LOCAL", "root,homelab"))
        provision_local_users = _parse_bool(
            env_map.get("AUTHENTIK_LOGIN_PROVISION_LOCAL_USER", "true"),
            default=True,
        )
        local_user_shell = env_map.get("AUTHENTIK_OS_LOCAL_SHELL", "/bin/bash").strip() or "/bin/bash"
        local_user_groups = _parse_csv(env_map.get("AUTHENTIK_OS_LOCAL_GROUPS", ""))
        local_username_pattern = (
            env_map.get("AUTHENTIK_OS_USERNAME_REGEX", r"^[a-z_][a-z0-9_-]{0,31}$").strip()
            or r"^[a-z_][a-z0-9_-]{0,31}$"
        )
        return cls(
            base_url=base_url,
            token=token,
            verify_tls=verify_tls,
            timeout_seconds=timeout_seconds,
            oidc_client_id=oidc_client_id,
            oidc_client_secret=oidc_client_secret,
            oidc_scopes=oidc_scopes,
            token_endpoint=token_endpoint,
            userinfo_endpoint=userinfo_endpoint,
            auth_mode=auth_mode,
            flow_slug=flow_slug,
            flow_executor_url=flow_executor_url,
            allow_local_users=allow_local_users or ("root", "homelab"),
            provision_local_users=provision_local_users,
            local_user_shell=local_user_shell,
            local_user_groups=local_user_groups,
            local_username_pattern=local_username_pattern,
        )


class AuthentikLoginError(RuntimeError):
    """Erro fatal ao validar usuario no Authentik."""


def read_pam_password(stdin: io.TextIOBase | None = None) -> str:
    """Lê a senha exposta pelo pam_exec.so no stdin."""
    stream = stdin or sys.stdin
    raw_password = stream.buffer.read() if hasattr(stream, "buffer") else stream.read()
    if isinstance(raw_password, bytes):
        password = raw_password.decode("utf-8", errors="ignore")
    else:
        password = raw_password
    return password.rstrip("\r\n")


def _decode_authentik_session_cookie(raw_cookie: str) -> dict[str, Any]:
    """Decodifica o payload do cookie de sessao do Authentik sem validar assinatura."""
    if not raw_cookie or raw_cookie.count(".") < 2:
        return {}
    payload_b64 = raw_cookie.split(".")[1]
    padding = "=" * (-len(payload_b64) % 4)
    try:
        return json.loads(urlsafe_b64decode(payload_b64 + padding).decode("utf-8"))
    except Exception:
        return {}


def find_authentik_user(
    username: str,
    settings: AuthentikLoginSettings,
    http_get: Callable[..., requests.Response] | None = None,
) -> dict[str, Any] | None:
    """Busca usuario por username no Authentik."""
    if not settings.token:
        raise AuthentikLoginError("AUTHENTIK_TOKEN ausente")

    requester = http_get or requests.get
    response = requester(
        f"{settings.base_url}/api/v3/core/users/",
        headers={"Authorization": f"Bearer {settings.token}"},
        params={"search": username},
        timeout=settings.timeout_seconds,
        verify=settings.verify_tls,
    )
    response.raise_for_status()
    payload = response.json()
    for user in payload.get("results", []):
        if user.get("username") == username:
            return user
    return None


def authenticate_authentik_password(
    username: str,
    password: str,
    settings: AuthentikLoginSettings,
    *,
    http_post: Callable[..., requests.Response] | None = None,
    http_get: Callable[..., requests.Response] | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    """Valida credenciais no Authentik via password grant."""
    normalized_username = username.strip()
    if not normalized_username:
        return False, "empty_username", None
    if not password:
        return False, "empty_password", None
    if normalized_username in settings.allow_local_users:
        return False, "allowlisted_local_user", None
    if not settings.oidc_client_id or not settings.oidc_client_secret:
        logger.error("Client ID/secret do Authentik OS nao configurados")
        return False, "authentik_misconfigured", None

    requester_post = http_post or requests.post
    requester_get = http_get or requests.get

    try:
        token_response = requester_post(
            settings.token_endpoint,
            data={
                "grant_type": "password",
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
                "username": normalized_username,
                "password": password,
                "scope": settings.oidc_scopes,
            },
            timeout=settings.timeout_seconds,
            verify=settings.verify_tls,
        )
        if token_response.status_code >= 400:
            return False, "invalid_credentials", None
        token_payload = token_response.json()
        access_token = str(token_payload.get("access_token") or "").strip()
        if not access_token:
            return False, "invalid_token_response", None

        userinfo_response = requester_get(
            settings.userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=settings.timeout_seconds,
            verify=settings.verify_tls,
        )
        userinfo_response.raise_for_status()
        userinfo = userinfo_response.json()
    except requests.RequestException as exc:
        logger.error("Falha autenticando %s no Authentik: %s", normalized_username, exc)
        return False, "authentik_unreachable", None

    claim_username = (
        str(userinfo.get("preferred_username") or userinfo.get("nickname") or userinfo.get("sub") or "").strip()
    )
    if claim_username and claim_username != normalized_username:
        logger.error(
            "Username autenticado no Authentik nao coincide: esperado=%s recebido=%s",
            normalized_username,
            claim_username,
        )
        return False, "userinfo_mismatch", None

    if userinfo.get("email_verified") is False:
        logger.info("Usuario %s autenticou com email ainda nao verificado", normalized_username)
    return True, "password_authenticated", userinfo


def authenticate_authentik_flow(
    username: str,
    password: str,
    settings: AuthentikLoginSettings,
    *,
    session_factory: Callable[[], requests.Session] | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    """Valida credenciais usando o executor oficial do flow web do Authentik."""
    normalized_username = username.strip()
    if not normalized_username:
        return False, "empty_username", None
    if not password:
        return False, "empty_password", None
    if normalized_username in settings.allow_local_users:
        return False, "allowlisted_local_user", None

    session_builder = session_factory or requests.Session
    session = session_builder()

    try:
        initial_response = session.get(
            settings.flow_executor_url,
            timeout=settings.timeout_seconds,
            verify=settings.verify_tls,
        )
        initial_response.raise_for_status()
        initial_payload = initial_response.json()
        user_fields = tuple(initial_payload.get("user_fields") or ())
        if "username" in user_fields and "@" not in normalized_username:
            uid_field = "username"
        elif "email" in user_fields:
            uid_field = "email"
        else:
            uid_field = user_fields[0] if user_fields else "username"

        identify_response = session.post(
            settings.flow_executor_url,
            json={"component": initial_payload.get("component"), "uid_field": normalized_username},
            timeout=settings.timeout_seconds,
            verify=settings.verify_tls,
        )
        identify_response.raise_for_status()
        identify_payload = identify_response.json()
        if identify_payload.get("response_errors"):
            return False, "user_not_found", identify_payload

        password_response = session.post(
            settings.flow_executor_url,
            json={
                "component": identify_payload.get("component"),
                "password": password,
                "username": str(identify_payload.get("pending_user") or normalized_username),
            },
            timeout=settings.timeout_seconds,
            verify=settings.verify_tls,
        )
        password_response.raise_for_status()
        password_payload = password_response.json()
    except requests.RequestException as exc:
        logger.error("Falha autenticando %s via flow do Authentik: %s", normalized_username, exc)
        return False, "authentik_unreachable", None

    password_errors = password_payload.get("response_errors", {}).get("password", [])
    if password_errors:
        return False, "invalid_credentials", password_payload

    session_state = _decode_authentik_session_cookie(session.cookies.get("authentik_session", ""))
    if session_state.get("authenticated") is True:
        return True, "password_authenticated_via_flow", password_payload

    return False, "flow_auth_incomplete", password_payload


def authenticate_authentik_user(
    username: str,
    password: str,
    settings: AuthentikLoginSettings,
) -> tuple[bool, str, dict[str, Any] | None]:
    """Autentica usuario no Authentik usando backend configurado."""
    mode = settings.auth_mode
    if mode not in {"auto", "oidc_password", "flow"}:
        logger.error("Modo de autenticacao Authentik invalido: %s", mode)
        return False, "authentik_misconfigured", None

    if mode in {"auto", "oidc_password"}:
        authenticated, reason, userinfo = authenticate_authentik_password(username, password, settings)
        if authenticated:
            return authenticated, reason, userinfo
        if mode == "oidc_password":
            return authenticated, reason, userinfo

    return authenticate_authentik_flow(username, password, settings)


def validate_authentik_login(
    username: str,
    settings: AuthentikLoginSettings,
    http_get: Callable[..., requests.Response] | None = None,
) -> tuple[bool, str]:
    """Valida se um usuario pode abrir sessao no SO."""
    normalized_username = username.strip()
    if not normalized_username:
        return False, "empty_username"

    if normalized_username in settings.allow_local_users:
        return True, "allowlisted_local_user"

    try:
        user = find_authentik_user(normalized_username, settings, http_get=http_get)
    except requests.RequestException as exc:
        logger.error("Falha consultando Authentik para %s: %s", normalized_username, exc)
        return False, "authentik_unreachable"
    except AuthentikLoginError as exc:
        logger.error("Configuracao invalida do guard Authentik: %s", exc)
        return False, "authentik_misconfigured"

    if user is None:
        return False, "user_not_found"
    if not user.get("is_active", False):
        return False, "user_inactive"
    return True, "user_active"


def is_valid_local_username(username: str, settings: AuthentikLoginSettings) -> bool:
    """Valida se o username e seguro para provisionamento no SO."""
    return re.fullmatch(settings.local_username_pattern, username.strip()) is not None


def provision_local_account_for_authentik_user(
    username: str,
    settings: AuthentikLoginSettings,
    *,
    user: dict[str, Any] | None = None,
    ensure_account: Callable[..., dict[str, Any]] | None = None,
    http_get: Callable[..., requests.Response] | None = None,
) -> tuple[bool, str]:
    """Provisiona conta local idempotente para um usuario validado no Authentik."""
    normalized_username = username.strip()
    if not normalized_username:
        return False, "empty_username"

    if normalized_username in settings.allow_local_users:
        return True, "allowlisted_local_user"

    if not settings.provision_local_users:
        return True, "provisioning_disabled"

    if not is_valid_local_username(normalized_username, settings):
        logger.error("Username %s rejeitado para provisionamento local", normalized_username)
        return False, "invalid_local_username"

    target_user = user
    if target_user is None:
        try:
            target_user = find_authentik_user(normalized_username, settings, http_get=http_get)
        except requests.RequestException as exc:
            logger.error("Falha consultando Authentik para provisionar %s: %s", normalized_username, exc)
            return False, "authentik_unreachable"
        except AuthentikLoginError as exc:
            logger.error("Configuracao invalida do guard Authentik: %s", exc)
            return False, "authentik_misconfigured"

    if target_user is None:
        return False, "user_not_found"
    if not target_user.get("is_active", False):
        return False, "user_inactive"

    account_provisioner = ensure_account or ensure_local_account

    try:
        account_provisioner(
            normalized_username,
            str(target_user.get("name") or normalized_username),
            shell=settings.local_user_shell,
            local_groups=settings.local_user_groups,
        )
    except Exception as exc:
        logger.error("Falha ao provisionar conta local para %s: %s", normalized_username, exc)
        return False, "local_provision_failed"

    return True, "local_account_ready"


def render_pam_exec_auth_line(command_path: str = DEFAULT_COMMAND_PATH) -> str:
    """Renderiza a linha do PAM para autenticacao via Authentik."""
    return f"auth sufficient pam_exec.so expose_authtok quiet {command_path} --pam-stage auth"


def render_pam_exec_account_line(command_path: str = DEFAULT_COMMAND_PATH) -> str:
    """Renderiza a linha do PAM para validacao/provisionamento de conta."""
    return f"account requisite pam_exec.so quiet {command_path} --pam-stage account"


def inject_pam_guard(config_text: str, command_path: str = DEFAULT_COMMAND_PATH) -> str:
    """Adiciona as linhas do guard Authentik a um arquivo PAM."""
    auth_line = render_pam_exec_auth_line(command_path)
    account_line = render_pam_exec_account_line(command_path)
    lines = config_text.splitlines()

    if auth_line not in lines:
        auth_index = next((idx for idx, line in enumerate(lines) if line.lstrip().startswith("auth ")), 0)
        lines.insert(auth_index, auth_line)
        lines.insert(auth_index, PAM_GUARD_MARKER)

    if account_line not in lines:
        account_index = next((idx for idx, line in enumerate(lines) if line.lstrip().startswith("account ")), len(lines))
        lines.insert(account_index, account_line)
        lines.insert(account_index, PAM_GUARD_MARKER)

    return "\n".join(lines).rstrip("\n") + "\n"


def _run_command(
    args: Sequence[str],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    """Executa comando do sistema e converte falhas em excecao."""
    result = runner(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "erro desconhecido"
        raise RuntimeError(f"comando falhou ({' '.join(shlex.quote(item) for item in args)}): {stderr}")
    return result


def ensure_local_account(
    username: str,
    full_name: str,
    shell: str = "/bin/bash",
    local_groups: Sequence[str] = (),
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    pwd_getpwnam: Callable[[str], pwd.struct_passwd] = pwd.getpwnam,
) -> dict[str, Any]:
    """Garante que exista uma conta local para o usuario provisionado no Authentik."""
    try:
        account = pwd_getpwnam(username)
        return {
            "created": False,
            "username": username,
            "home": account.pw_dir,
            "shell": account.pw_shell,
        }
    except KeyError:
        pass

    _run_command(["useradd", "-m", "-s", shell, "-c", full_name, username], runner=runner)
    if local_groups:
        group_list = ",".join(local_groups)
        _run_command(["usermod", "-aG", group_list, username], runner=runner)

    account = pwd_getpwnam(username)
    return {
        "created": True,
        "username": username,
        "home": account.pw_dir,
        "shell": account.pw_shell,
    }


def pam_main(argv: Sequence[str] | None = None) -> int:
    """Entry point usado pelo pam_exec.so."""
    parser = argparse.ArgumentParser(description="Authentik PAM login guard")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--pam-stage", choices=("auth", "account"))
    args = parser.parse_args(argv)

    settings = AuthentikLoginSettings.from_env(env_file=Path(args.env_file))
    pam_user = os.environ.get("PAM_USER", "")
    pam_stage = args.pam_stage or os.environ.get("PAM_TYPE", "account").strip().lower()

    if pam_stage == "auth":
        authenticated, reason, _ = authenticate_authentik_user(
            pam_user,
            read_pam_password(),
            settings,
        )
        if not authenticated:
            return 1
        logger.info("Autenticacao Authentik liberada para %s (%s)", pam_user, reason)
        return 0

    allowed, reason = validate_authentik_login(pam_user, settings)
    if not allowed:
        return 1
    provisioned, provision_reason = provision_local_account_for_authentik_user(pam_user, settings)
    if not provisioned:
        logger.error("Login negado para %s: %s", pam_user, provision_reason)
        return 1
    logger.info("Login liberado para %s (%s, %s)", pam_user, reason, provision_reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(pam_main())
