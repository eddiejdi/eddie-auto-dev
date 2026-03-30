#!/usr/bin/env python3
"""Instala o guard de login do Authentik no PAM do SO."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
from pathlib import Path

from tools.authentik_management.authentik_os_login_guard import (
    DEFAULT_COMMAND_PATH,
    DEFAULT_ENV_FILE,
    inject_pam_guard,
)

DEFAULT_SERVICE_CANDIDATES = ("login", "sshd", "lightdm")


def _write_env_file(env_file: Path) -> None:
    """Cria arquivo de ambiente do guard sem expor segredo no repositorio."""
    env_file.parent.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("AUTHENTIK_TOKEN", "")
    url = os.environ.get("AUTHENTIK_URL", "https://auth.rpa4all.com")
    verify_tls = os.environ.get("AUTHENTIK_VERIFY_TLS", "false")
    allow_local = os.environ.get("AUTHENTIK_LOGIN_ALLOW_LOCAL", "root,homelab")
    timeout = os.environ.get("AUTHENTIK_LOGIN_TIMEOUT", "5")
    oidc_client_id = os.environ.get("AUTHENTIK_OS_CLIENT_ID", os.environ.get("OIDC_CLIENT_ID", ""))
    oidc_client_secret = os.environ.get("AUTHENTIK_OS_CLIENT_SECRET", os.environ.get("OIDC_CLIENT_SECRET", ""))
    oidc_scopes = os.environ.get("AUTHENTIK_OS_SCOPES", os.environ.get("OIDC_SCOPES", "openid profile email"))
    auth_mode = os.environ.get("AUTHENTIK_OS_AUTH_MODE", "auto")
    flow_slug = os.environ.get("AUTHENTIK_OS_FLOW_SLUG", "default-authentication-flow")
    token_endpoint = os.environ.get("AUTHENTIK_OS_TOKEN_ENDPOINT", f"{url.rstrip('/')}/application/o/token/")
    userinfo_endpoint = os.environ.get("AUTHENTIK_OS_USERINFO_ENDPOINT", f"{url.rstrip('/')}/application/o/userinfo/")
    flow_executor_url = os.environ.get(
        "AUTHENTIK_OS_FLOW_EXECUTOR_URL",
        f"{url.rstrip('/')}/api/v3/flows/executor/{flow_slug}/",
    )
    provision_local = os.environ.get("AUTHENTIK_LOGIN_PROVISION_LOCAL_USER", "true")
    local_shell = os.environ.get("AUTHENTIK_OS_LOCAL_SHELL", "/bin/bash")
    local_groups = os.environ.get("AUTHENTIK_OS_LOCAL_GROUPS", "")
    username_regex = os.environ.get("AUTHENTIK_OS_USERNAME_REGEX", r"^[a-z_][a-z0-9_-]{0,31}$")
    content = (
        f"AUTHENTIK_URL={url}\n"
        f"AUTHENTIK_TOKEN={token}\n"
        f"AUTHENTIK_VERIFY_TLS={verify_tls}\n"
        f"AUTHENTIK_LOGIN_ALLOW_LOCAL={allow_local}\n"
        f"AUTHENTIK_LOGIN_TIMEOUT={timeout}\n"
        f"AUTHENTIK_OS_CLIENT_ID={oidc_client_id}\n"
        f"AUTHENTIK_OS_CLIENT_SECRET={oidc_client_secret}\n"
        f"AUTHENTIK_OS_SCOPES={oidc_scopes}\n"
        f"AUTHENTIK_OS_AUTH_MODE={auth_mode}\n"
        f"AUTHENTIK_OS_FLOW_SLUG={flow_slug}\n"
        f"AUTHENTIK_OS_TOKEN_ENDPOINT={token_endpoint}\n"
        f"AUTHENTIK_OS_USERINFO_ENDPOINT={userinfo_endpoint}\n"
        f"AUTHENTIK_OS_FLOW_EXECUTOR_URL={flow_executor_url}\n"
        f"AUTHENTIK_LOGIN_PROVISION_LOCAL_USER={provision_local}\n"
        f"AUTHENTIK_OS_LOCAL_SHELL={local_shell}\n"
        f"AUTHENTIK_OS_LOCAL_GROUPS={local_groups}\n"
        f"AUTHENTIK_OS_USERNAME_REGEX={username_regex}\n"
    )
    env_file.write_text(content, encoding="utf-8")
    env_file.chmod(0o600)


def _install_guard_binary(source_script: Path, target_script: Path) -> None:
    """Instala o guard Python em caminho executavel do sistema."""
    target_script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_script, target_script)
    target_script.chmod(target_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _patch_pam_service(service_file: Path, command_path: str) -> None:
    """Atualiza um arquivo de servico PAM com a validacao do Authentik."""
    original = service_file.read_text(encoding="utf-8")
    updated = inject_pam_guard(original, command_path=command_path)
    service_file.write_text(updated, encoding="utf-8")


def _resolve_services(target_root: Path, services: tuple[str, ...]) -> tuple[str, ...]:
    """Filtra servicos PAM existentes para uma instalacao padrao mais segura."""
    resolved: list[str] = []
    for service in services:
        service_file = target_root / "etc" / "pam.d" / service
        if service_file.exists():
            resolved.append(service)
    return tuple(resolved)


def install_authentik_os_login(
    target_root: Path,
    source_script: Path,
    command_path: str,
    env_file_path: Path,
    services: tuple[str, ...],
) -> None:
    """Instala guard, arquivo de ambiente e linhas PAM em servicos selecionados."""
    resolved_target_script = target_root / Path(command_path).relative_to("/")
    resolved_env_file = target_root / env_file_path.relative_to("/")
    _install_guard_binary(source_script, resolved_target_script)
    _write_env_file(resolved_env_file)

    for service in services:
        service_file = target_root / "etc" / "pam.d" / service
        _patch_pam_service(service_file, command_path=command_path)


def main() -> int:
    """CLI de instalacao do guard de login Authentik."""
    parser = argparse.ArgumentParser(description="Instala guard PAM para Authentik")
    parser.add_argument("--target-root", default="/", help="Raiz do sistema a ser alterado")
    parser.add_argument("--command-path", default=DEFAULT_COMMAND_PATH)
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--services", default=",".join(DEFAULT_SERVICE_CANDIDATES))
    args = parser.parse_args()

    source_script = Path(__file__).with_name("authentik_os_login_guard.py")
    requested_services = tuple(item.strip() for item in args.services.split(",") if item.strip())
    services = _resolve_services(Path(args.target_root), requested_services)
    if not services:
        raise FileNotFoundError("nenhum servico PAM encontrado para integrar com o guard do Authentik")
    install_authentik_os_login(
        target_root=Path(args.target_root),
        source_script=source_script,
        command_path=args.command_path,
        env_file_path=Path(args.env_file),
        services=services,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
