from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authentik_management.configure_authentik_os_strict import (
    configure_authentik_os_strict,
    render_strict_env,
)


def test_render_strict_env_removes_user_bypass_and_preserves_other_keys() -> None:
    original = [
        "AUTHENTIK_URL=https://auth.rpa4all.com",
        "AUTHENTIK_LOGIN_ALLOW_LOCAL=root,edenilson",
        "AUTHENTIK_OS_AUTH_MODE=auto",
        "AUTHENTIK_LOGIN_TIMEOUT=10",
    ]

    rendered = render_strict_env(original, keep_local_users=("root", "homelab"))

    assert "AUTHENTIK_LOGIN_ALLOW_LOCAL=root,homelab\n" in rendered
    assert "AUTHENTIK_OS_AUTH_MODE=flow\n" in rendered
    assert "AUTHENTIK_LOGIN_TIMEOUT=10\n" in rendered
    assert "AUTHENTIK_VERIFY_TLS=true\n" in rendered
    assert "AUTHENTIK_LOGIN_PROVISION_LOCAL_USER=true\n" in rendered


def test_render_strict_env_adds_missing_required_keys() -> None:
    rendered = render_strict_env(["AUTHENTIK_URL=https://auth.rpa4all.com"])

    assert "AUTHENTIK_LOGIN_ALLOW_LOCAL=root,homelab\n" in rendered
    assert "AUTHENTIK_OS_AUTH_MODE=flow\n" in rendered
    assert "AUTHENTIK_OS_USERNAME_REGEX=^[a-z_][a-z0-9_-]{0,31}$\n" in rendered


def test_configure_authentik_os_strict_writes_backup(tmp_path: Path) -> None:
    env_file = tmp_path / "login-guard.env"
    env_file.write_text(
        "AUTHENTIK_URL=https://auth.rpa4all.com\nAUTHENTIK_LOGIN_ALLOW_LOCAL=root,edenilson\n",
        encoding="utf-8",
    )

    backup = configure_authentik_os_strict(env_file)

    assert backup == env_file.with_suffix(".env.bak")
    assert backup.read_text(encoding="utf-8") == (
        "AUTHENTIK_URL=https://auth.rpa4all.com\nAUTHENTIK_LOGIN_ALLOW_LOCAL=root,edenilson\n"
    )
    updated = env_file.read_text(encoding="utf-8")
    assert "AUTHENTIK_LOGIN_ALLOW_LOCAL=root,homelab\n" in updated
