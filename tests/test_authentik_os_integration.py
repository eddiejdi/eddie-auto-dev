from __future__ import annotations

import importlib
import io
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import requests

from tools.authentik_management.authentik_os_login_guard import (
    AuthentikLoginSettings,
    authenticate_authentik_flow,
    authenticate_authentik_password,
    authenticate_authentik_user,
    ensure_local_account,
    inject_pam_guard,
    is_valid_local_username,
    pam_main,
    provision_local_account_for_authentik_user,
    validate_authentik_login,
)
from tools.authentik_management.install_authentik_os_login import _resolve_services, install_authentik_os_login


def _import_user_management(monkeypatch: pytest.MonkeyPatch):
    class DummyCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def execute(self, *args, **kwargs) -> None:
            return None

    class DummyConnection:
        def __init__(self) -> None:
            self.autocommit = False

        def cursor(self) -> DummyCursor:
            return DummyCursor()

        def close(self) -> None:
            return None

    fake_psycopg2 = ModuleType("psycopg2")
    fake_psycopg2.connect = lambda *args, **kwargs: DummyConnection()
    fake_psycopg2.extensions = SimpleNamespace(connection=object)
    monkeypatch.setitem(sys.modules, "psycopg2", fake_psycopg2)
    sys.modules.pop("specialized_agents.user_management", None)
    return importlib.import_module("specialized_agents.user_management")


class DummyResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, object]:
        return self._payload


def test_validate_authentik_login_accepts_allowlisted_user() -> None:
    settings = AuthentikLoginSettings(base_url="https://auth.example.com", token="token", allow_local_users=("root", "homelab"))
    allowed, reason = validate_authentik_login("root", settings)
    assert allowed is True
    assert reason == "allowlisted_local_user"


def test_validate_authentik_login_denies_missing_user() -> None:
    settings = AuthentikLoginSettings(base_url="https://auth.example.com", token="token")

    def fake_get(*args, **kwargs):
        return DummyResponse({"results": []})

    allowed, reason = validate_authentik_login("alice", settings, http_get=fake_get)
    assert allowed is False
    assert reason == "user_not_found"


def test_validate_authentik_login_denies_inactive_user() -> None:
    settings = AuthentikLoginSettings(base_url="https://auth.example.com", token="token")

    def fake_get(*args, **kwargs):
        return DummyResponse({"results": [{"username": "alice", "is_active": False}]})

    allowed, reason = validate_authentik_login("alice", settings, http_get=fake_get)
    assert allowed is False
    assert reason == "user_inactive"


def test_validate_authentik_login_denies_when_authentik_is_unreachable() -> None:
    settings = AuthentikLoginSettings(base_url="https://auth.example.com", token="token")

    def fake_get(*args, **kwargs):
        raise requests.ConnectionError("offline")

    allowed, reason = validate_authentik_login("alice", settings, http_get=fake_get)
    assert allowed is False
    assert reason == "authentik_unreachable"


def test_is_valid_local_username_rejects_unsafe_value() -> None:
    settings = AuthentikLoginSettings(base_url="https://auth.example.com", token="token")
    assert is_valid_local_username("alice-admin", settings) is True
    assert is_valid_local_username("Alice Admin", settings) is False
    assert is_valid_local_username("../../root", settings) is False


def test_inject_pam_guard_is_idempotent() -> None:
    original = "auth required pam_unix.so\naccount required pam_unix.so\n"
    updated = inject_pam_guard(original)
    assert updated.count("pam_exec.so") == 2
    auth_lines = [line for line in updated.splitlines() if line.startswith("auth ")]
    account_lines = [line for line in updated.splitlines() if line.startswith("account ")]
    assert auth_lines[0] == "auth sufficient pam_exec.so expose_authtok quiet /usr/local/bin/authentik-login-guard --pam-stage auth"
    assert account_lines[0] == "account requisite pam_exec.so quiet /usr/local/bin/authentik-login-guard --pam-stage account"
    assert inject_pam_guard(updated) == updated


def test_authenticate_authentik_password_accepts_valid_credentials() -> None:
    settings = AuthentikLoginSettings(
        base_url="https://auth.example.com",
        token="token",
        oidc_client_id="client-id",
        oidc_client_secret="client-secret",
        token_endpoint="https://auth.example.com/application/o/token/",
        userinfo_endpoint="https://auth.example.com/application/o/userinfo/",
    )

    def fake_post(*args, **kwargs):
        return DummyResponse({"access_token": "token-123"})

    def fake_get(*args, **kwargs):
        return DummyResponse({"preferred_username": "alice", "name": "Alice Example"})

    allowed, reason, userinfo = authenticate_authentik_password(
        "alice",
        "secret",
        settings,
        http_post=fake_post,
        http_get=fake_get,
    )

    assert allowed is True
    assert reason == "password_authenticated"
    assert userinfo == {"preferred_username": "alice", "name": "Alice Example"}


def test_authenticate_authentik_flow_accepts_authenticated_session_cookie() -> None:
    settings = AuthentikLoginSettings(
        base_url="https://auth.example.com",
        token="token",
        flow_executor_url="https://auth.example.com/api/v3/flows/executor/default-authentication-flow/",
    )

    class FakeFlowResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self._payload

    class FakeSession:
        def __init__(self) -> None:
            self.cookies = {
                "authentik_session": "a.eyJhdXRoZW50aWNhdGVkIjp0cnVlLCJzdWIiOiJhbGljZSJ9.b"
            }
            self.calls: list[tuple[str, dict[str, object]]] = []

        def get(self, *args, **kwargs):
            return FakeFlowResponse({"user_fields": ["username"], "component": "ak-stage-identification"})

        def post(self, *args, **kwargs):
            payload = kwargs.get("json", {})
            self.calls.append(("post", payload))
            if payload.get("component") == "ak-stage-identification":
                return FakeFlowResponse({"component": "ak-stage-password", "pending_user": "alice"})
            return FakeFlowResponse({"component": "ak-stage-user-write"})

    session = FakeSession()
    allowed, reason, payload = authenticate_authentik_flow(
        "alice",
        "secret",
        settings,
        session_factory=lambda: session,
    )

    assert allowed is True
    assert reason == "password_authenticated_via_flow"
    assert payload == {"component": "ak-stage-user-write"}
    assert session.calls == [
        ("post", {"component": "ak-stage-identification", "uid_field": "alice"}),
        ("post", {"component": "ak-stage-password", "password": "secret", "username": "alice"}),
    ]


def test_authenticate_authentik_user_falls_back_to_flow_when_oidc_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = AuthentikLoginSettings(
        base_url="https://auth.example.com",
        token="token",
        auth_mode="auto",
        oidc_client_id="client-id",
        oidc_client_secret="client-secret",
        token_endpoint="https://auth.example.com/application/o/token/",
        userinfo_endpoint="https://auth.example.com/application/o/userinfo/",
        flow_executor_url="https://auth.example.com/api/v3/flows/executor/default-authentication-flow/",
    )

    monkeypatch.setattr(
        "tools.authentik_management.authentik_os_login_guard.authenticate_authentik_password",
        lambda *args, **kwargs: (False, "invalid_credentials", None),
    )
    monkeypatch.setattr(
        "tools.authentik_management.authentik_os_login_guard.authenticate_authentik_flow",
        lambda *args, **kwargs: (True, "password_authenticated_via_flow", {"component": "done"}),
    )

    allowed, reason, payload = authenticate_authentik_user("alice", "secret", settings)
    assert allowed is True
    assert reason == "password_authenticated_via_flow"
    assert payload == {"component": "done"}


def test_ensure_local_account_creates_user_and_groups() -> None:
    calls: list[list[str]] = []
    accounts: dict[str, SimpleNamespace] = {}

    def fake_runner(args, capture_output, text, check):
        calls.append(args)
        if args[0] == "useradd":
            accounts[args[-1]] = SimpleNamespace(pw_dir=f"/home/{args[-1]}", pw_shell=args[3])
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    def fake_getpwnam(username: str):
        if username not in accounts:
            raise KeyError(username)
        return accounts[username]

    result = ensure_local_account(
        "alice",
        "Alice Example",
        local_groups=("developers", "docker"),
        runner=fake_runner,
        pwd_getpwnam=fake_getpwnam,
    )

    assert result["created"] is True
    assert calls[0] == ["useradd", "-m", "-s", "/bin/bash", "-c", "Alice Example", "alice"]
    assert calls[1] == ["usermod", "-aG", "developers,docker", "alice"]


def test_install_authentik_os_login_patches_login_and_sshd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target_root = tmp_path / "rootfs"
    (target_root / "etc" / "pam.d").mkdir(parents=True)
    (target_root / "etc" / "pam.d" / "login").write_text("auth required pam_unix.so\n", encoding="utf-8")
    (target_root / "etc" / "pam.d" / "sshd").write_text("auth required pam_unix.so\n", encoding="utf-8")
    (target_root / "etc" / "pam.d" / "lightdm").write_text("@include common-auth\n@include common-account\n", encoding="utf-8")
    source_script = tmp_path / "authentik_os_login_guard.py"
    source_script.write_text("#!/usr/bin/env python3\nprint('guard')\n", encoding="utf-8")

    monkeypatch.setenv("AUTHENTIK_URL", "https://auth.example.com")
    monkeypatch.setenv("AUTHENTIK_TOKEN", "secret-token")
    monkeypatch.setenv("AUTHENTIK_LOGIN_ALLOW_LOCAL", "root,homelab")
    monkeypatch.setenv("AUTHENTIK_OS_CLIENT_ID", "authentik-os-login")
    monkeypatch.setenv("AUTHENTIK_OS_CLIENT_SECRET", "os-login-secret")

    install_authentik_os_login(
        target_root=target_root,
        source_script=source_script,
        command_path="/usr/local/bin/authentik-login-guard",
        env_file_path=Path("/etc/authentik/login-guard.env"),
        services=("login", "sshd", "lightdm"),
    )

    login_pam = (target_root / "etc" / "pam.d" / "login").read_text(encoding="utf-8")
    sshd_pam = (target_root / "etc" / "pam.d" / "sshd").read_text(encoding="utf-8")
    lightdm_pam = (target_root / "etc" / "pam.d" / "lightdm").read_text(encoding="utf-8")
    env_file = (target_root / "etc" / "authentik" / "login-guard.env").read_text(encoding="utf-8")
    installed_script = target_root / "usr" / "local" / "bin" / "authentik-login-guard"

    assert "pam_exec.so expose_authtok quiet /usr/local/bin/authentik-login-guard --pam-stage auth" in login_pam
    assert "pam_exec.so quiet /usr/local/bin/authentik-login-guard --pam-stage account" in login_pam
    assert "pam_exec.so expose_authtok quiet /usr/local/bin/authentik-login-guard --pam-stage auth" in sshd_pam
    assert "pam_exec.so quiet /usr/local/bin/authentik-login-guard --pam-stage account" in sshd_pam
    assert "pam_exec.so expose_authtok quiet /usr/local/bin/authentik-login-guard --pam-stage auth" in lightdm_pam
    assert "pam_exec.so quiet /usr/local/bin/authentik-login-guard --pam-stage account" in lightdm_pam
    assert "AUTHENTIK_TOKEN=secret-token" in env_file
    assert "AUTHENTIK_OS_CLIENT_ID=authentik-os-login" in env_file
    assert "AUTHENTIK_OS_CLIENT_SECRET=os-login-secret" in env_file
    assert "AUTHENTIK_OS_AUTH_MODE=auto" in env_file
    assert "AUTHENTIK_OS_FLOW_SLUG=default-authentication-flow" in env_file
    assert "AUTHENTIK_LOGIN_PROVISION_LOCAL_USER=true" in env_file
    assert "AUTHENTIK_OS_USERNAME_REGEX=^[a-z_][a-z0-9_-]{0,31}$" in env_file
    assert installed_script.exists()


def test_resolve_services_skips_missing_pam_targets(tmp_path: Path) -> None:
    target_root = tmp_path / "rootfs"
    (target_root / "etc" / "pam.d").mkdir(parents=True)
    (target_root / "etc" / "pam.d" / "lightdm").write_text("@include common-auth\n", encoding="utf-8")

    assert _resolve_services(target_root, ("login", "sshd", "lightdm")) == ("lightdm",)


def test_provision_local_account_for_authentik_user_denies_invalid_username() -> None:
    settings = AuthentikLoginSettings(base_url="https://auth.example.com", token="token")

    allowed, reason = provision_local_account_for_authentik_user(
        "Alice Admin",
        settings,
        user={"username": "Alice Admin", "name": "Alice Admin", "is_active": True},
    )

    assert allowed is False
    assert reason == "invalid_local_username"


def test_pam_main_provisions_local_account_for_valid_authentik_user(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / "login-guard.env"
    env_file.write_text(
        "\n".join(
            [
                "AUTHENTIK_URL=https://auth.example.com",
                "AUTHENTIK_TOKEN=secret-token",
                "AUTHENTIK_LOGIN_PROVISION_LOCAL_USER=true",
                "AUTHENTIK_OS_LOCAL_SHELL=/bin/zsh",
                "AUTHENTIK_OS_LOCAL_GROUPS=developers,docker",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PAM_USER", "alice")
    captured: dict[str, object] = {}

    def fake_get(*args, **kwargs):
        return DummyResponse({"results": [{"username": "alice", "name": "Alice Example", "is_active": True}]})

    def fake_ensure_local_account(username: str, full_name: str, shell: str, local_groups: tuple[str, ...] | list[str]):
        captured["username"] = username
        captured["full_name"] = full_name
        captured["shell"] = shell
        captured["local_groups"] = tuple(local_groups)
        return {"created": True, "username": username, "home": f"/home/{username}", "shell": shell}

    monkeypatch.setattr("tools.authentik_management.authentik_os_login_guard.requests.get", fake_get)
    monkeypatch.setattr(
        "tools.authentik_management.authentik_os_login_guard.ensure_local_account",
        fake_ensure_local_account,
    )

    assert pam_main(["--env-file", str(env_file)]) == 0
    assert captured == {
        "username": "alice",
        "full_name": "Alice Example",
        "shell": "/bin/zsh",
        "local_groups": ("developers", "docker"),
    }


def test_pam_main_auth_stage_accepts_valid_authentik_password(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / "login-guard.env"
    env_file.write_text(
        "\n".join(
            [
                "AUTHENTIK_URL=https://auth.example.com",
                "AUTHENTIK_TOKEN=secret-token",
                "AUTHENTIK_OS_CLIENT_ID=authentik-os-login",
                "AUTHENTIK_OS_CLIENT_SECRET=os-login-secret",
                "AUTHENTIK_OS_TOKEN_ENDPOINT=https://auth.example.com/application/o/token/",
                "AUTHENTIK_OS_USERINFO_ENDPOINT=https://auth.example.com/application/o/userinfo/",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PAM_USER", "alice")

    def fake_post(*args, **kwargs):
        return DummyResponse({"access_token": "token-123"})

    def fake_get(*args, **kwargs):
        return DummyResponse({"preferred_username": "alice"})

    monkeypatch.setattr("tools.authentik_management.authentik_os_login_guard.requests.post", fake_post)
    monkeypatch.setattr("tools.authentik_management.authentik_os_login_guard.requests.get", fake_get)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"secret-password\n"), encoding="utf-8"))

    assert pam_main(["--env-file", str(env_file), "--pam-stage", "auth"]) == 0


def test_pam_main_denies_login_when_local_provisioning_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / "login-guard.env"
    env_file.write_text(
        "AUTHENTIK_URL=https://auth.example.com\nAUTHENTIK_TOKEN=secret-token\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PAM_USER", "alice")

    def fake_get(*args, **kwargs):
        return DummyResponse({"results": [{"username": "alice", "name": "Alice Example", "is_active": True}]})

    def fake_ensure_local_account(username: str, full_name: str, shell: str, local_groups: tuple[str, ...] | list[str]):
        raise RuntimeError("useradd failed")

    monkeypatch.setattr("tools.authentik_management.authentik_os_login_guard.requests.get", fake_get)
    monkeypatch.setattr(
        "tools.authentik_management.authentik_os_login_guard.ensure_local_account",
        fake_ensure_local_account,
    )

    assert pam_main(["--env-file", str(env_file)]) == 1


def test_step_setup_env_provisions_local_account(monkeypatch: pytest.MonkeyPatch) -> None:
    user_management = _import_user_management(monkeypatch)
    captured: dict[str, object] = {}

    def fake_ensure_local_account(username: str, full_name: str, shell: str, local_groups: tuple[str, ...] | list[str]):
        captured["username"] = username
        captured["full_name"] = full_name
        captured["shell"] = shell
        captured["local_groups"] = list(local_groups)
        return {"created": True, "username": username, "home": f"/home/{username}", "shell": shell}

    monkeypatch.setattr(user_management, "CREATE_OS_USERS", True)
    monkeypatch.setattr(user_management, "LOCAL_USER_SHELL", "/bin/zsh")
    monkeypatch.setattr(user_management, "LOCAL_USER_GROUPS", ["developers"])
    monkeypatch.setattr(user_management, "ensure_local_account", fake_ensure_local_account)

    config = user_management.UserConfig(
        username="alice",
        email="alice@example.com",
        full_name="Alice Example",
        password="secret",
    )

    result = user_management._step_setup_env(config)
    assert result["success"] is True
    assert captured == {
        "username": "alice",
        "full_name": "Alice Example",
        "shell": "/bin/zsh",
        "local_groups": ["developers"],
    }


def test_step_setup_env_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    user_management = _import_user_management(monkeypatch)
    monkeypatch.setattr(user_management, "CREATE_OS_USERS", False)
    monkeypatch.setattr(user_management, "LOCAL_USER_GROUPS", [])

    config = user_management.UserConfig(
        username="alice",
        email="alice@example.com",
        full_name="Alice Example",
        password="secret",
    )

    result = user_management._step_setup_env(config)
    assert result == {"success": True, "skipped": True}
