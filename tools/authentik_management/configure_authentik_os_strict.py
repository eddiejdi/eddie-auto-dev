#!/usr/bin/env python3
"""Endurece a configuracao do login Linux via Authentik."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authentik_management.authentik_os_login_guard import DEFAULT_ENV_FILE


def load_env_lines(env_file: Path) -> list[str]:
    """Le o arquivo preservando a ordem e comentarios simples."""
    if not env_file.exists():
        return []
    return env_file.read_text(encoding="utf-8").splitlines()


def _parse_env(lines: list[str]) -> tuple[list[str], dict[str, str]]:
    ordered_keys: list[str] = []
    values: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in values:
            ordered_keys.append(key)
        values[key] = value.strip()
    return ordered_keys, values


def render_strict_env(
    lines: list[str],
    *,
    keep_local_users: tuple[str, ...] = ("root", "homelab"),
    auth_mode: str = "flow",
    verify_tls: str = "true",
) -> str:
    """Atualiza o arquivo .env do guard para modo estrito."""
    ordered_keys, values = _parse_env(lines)
    desired = {
        "AUTHENTIK_VERIFY_TLS": verify_tls,
        "AUTHENTIK_LOGIN_ALLOW_LOCAL": ",".join(keep_local_users),
        "AUTHENTIK_OS_AUTH_MODE": auth_mode,
        "AUTHENTIK_LOGIN_PROVISION_LOCAL_USER": "true",
        "AUTHENTIK_OS_USERNAME_REGEX": r"^[a-z_][a-z0-9_-]{0,31}$",
    }
    for key, value in desired.items():
        if key not in values:
            ordered_keys.append(key)
        values[key] = value

    rendered_lines: list[str] = []
    rendered_keys: set[str] = set()
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            rendered_lines.append(raw_line)
            continue
        key, _ = raw_line.split("=", 1)
        clean_key = key.strip()
        if clean_key in rendered_keys:
            continue
        rendered_lines.append(f"{clean_key}={values[clean_key]}")
        rendered_keys.add(clean_key)

    for key in ordered_keys:
        if key not in rendered_keys:
            rendered_lines.append(f"{key}={values[key]}")

    return "\n".join(rendered_lines).rstrip("\n") + "\n"


def configure_authentik_os_strict(
    env_file: Path,
    *,
    keep_local_users: tuple[str, ...] = ("root", "homelab"),
    auth_mode: str = "flow",
    verify_tls: str = "true",
    make_backup: bool = True,
) -> Path | None:
    """Aplica a configuracao estrita e cria backup opcional."""
    original_lines = load_env_lines(env_file)
    updated = render_strict_env(
        original_lines,
        keep_local_users=keep_local_users,
        auth_mode=auth_mode,
        verify_tls=verify_tls,
    )

    backup_path: Path | None = None
    if make_backup and env_file.exists():
        backup_path = env_file.with_suffix(env_file.suffix + ".bak")
        backup_path.write_text(env_file.read_text(encoding="utf-8"), encoding="utf-8")

    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(updated, encoding="utf-8")
    return backup_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Configura login Linux estrito via Authentik")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--keep-local-users", default="root,homelab")
    parser.add_argument("--auth-mode", default="flow", choices=("auto", "oidc_password", "flow"))
    parser.add_argument("--verify-tls", default="true")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    keep_local_users = tuple(item.strip() for item in args.keep_local_users.split(",") if item.strip())
    backup = configure_authentik_os_strict(
        Path(args.env_file),
        keep_local_users=keep_local_users or ("root", "homelab"),
        auth_mode=args.auth_mode,
        verify_tls=args.verify_tls,
        make_backup=not args.no_backup,
    )
    print(f"Arquivo atualizado: {args.env_file}")
    if backup:
        print(f"Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
