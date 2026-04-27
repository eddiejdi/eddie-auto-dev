#!/usr/bin/env python3
"""Testes unitários para btc_trading_agent/secrets_helper.py."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch


_BTC_DIR = Path(__file__).resolve().parent.parent / "btc_trading_agent"
if str(_BTC_DIR) not in sys.path:
    sys.path.insert(0, str(_BTC_DIR))

import secrets_helper


def test_get_kucoin_credentials_with_source_prefers_authentik_secret_fallback() -> None:
    """Fallback do Authentik no Agent Secrets deve vencer as env vars."""
    with patch.object(secrets_helper, "get_secret") as mock_get_secret, patch.dict(
        "os.environ",
        {
            "KUCOIN_API_KEY": "env-key",
            "KUCOIN_API_SECRET": "env-secret",
            "KUCOIN_API_PASSPHRASE": "env-pass",
        },
        clear=False,
    ):
        def _secret(name: str, field: str = "password", use_cache: bool = True):
            if name == "authentik/kucoin_homelab" and field == "api_key":
                return "vault-key"
            if name == "authentik/kucoin_homelab" and field == "api_secret":
                return "vault-secret"
            if name == "authentik/kucoin_homelab" and field == "passphrase":
                return "vault-pass"
            return None

        mock_get_secret.side_effect = _secret
        api_key, api_secret, passphrase, source = secrets_helper.get_kucoin_credentials_with_source()

    assert (api_key, api_secret, passphrase) == ("vault-key", "vault-secret", "vault-pass")
    assert source == "agent-secrets:authentik/kucoin_homelab"


def test_get_kucoin_credentials_with_source_accepts_authentik_path_namespace() -> None:
    """Secrets espelhadas em authentik/<path-original> também devem resolver."""
    with patch.object(secrets_helper, "get_secret") as mock_get_secret:
        def _secret(name: str, field: str = "password", use_cache: bool = True):
            if name == "authentik/kucoin/homelab" and field == "api_key":
                return "path-key"
            if name == "authentik/kucoin/homelab" and field == "api_secret":
                return "path-secret"
            if name == "authentik/kucoin/homelab" and field == "passphrase":
                return "path-pass"
            return None

        mock_get_secret.side_effect = _secret
        api_key, api_secret, passphrase, source = secrets_helper.get_kucoin_credentials_with_source()

    assert (api_key, api_secret, passphrase) == ("path-key", "path-secret", "path-pass")
    assert source == "agent-secrets:authentik/kucoin/homelab"


def test_configure_vault_runtime_env_sets_homelab_defaults(tmp_path: Path) -> None:
    """O helper deve preparar as env vars esperadas pelo cofre local."""
    project_root = tmp_path / "repo"
    passphrase_file = project_root / "tools" / "simple_vault" / "passphrase"
    passphrase_file.parent.mkdir(parents=True)
    passphrase_file.write_text("pw")

    expected_exists = {
        str(passphrase_file),
        "/var/lib/eddie/secrets_agent/.bw_master_password",
        "/var/lib/eddie/secrets_agent",
    }

    def fake_exists(self: Path) -> bool:
        return str(self) in expected_exists

    with patch.object(secrets_helper, "_PROJECT_ROOT", project_root), patch.dict("os.environ", {}, clear=True), patch(
        "pathlib.Path.exists",
        fake_exists,
    ):
        secrets_helper._configure_vault_runtime_env()
        assert Path(os.environ["SIMPLE_VAULT_PASSPHRASE_FILE"]) == passphrase_file
        assert os.environ["BW_PASSWORD_FILE"] == "/var/lib/eddie/secrets_agent/.bw_master_password"
        assert os.environ["SECRETS_AGENT_DATA"] == "/var/lib/eddie/secrets_agent"


def test_configure_vault_runtime_env_ignores_permission_error_on_homelab_paths(tmp_path: Path) -> None:
    """Paths opcionais do homelab não devem derrubar a configuração quando inacessíveis."""
    project_root = tmp_path / "repo"
    passphrase_file = project_root / "tools" / "simple_vault" / "passphrase"
    passphrase_file.parent.mkdir(parents=True)
    passphrase_file.write_text("pw")

    real_exists = Path.exists

    def fake_exists(self: Path) -> bool:
        if str(self) in {
            "/var/lib/eddie/secrets_agent/.bw_master_password",
            "/var/lib/eddie/secrets_agent",
        }:
            raise PermissionError("forbidden")
        return real_exists(self)

    with patch.object(secrets_helper, "_PROJECT_ROOT", project_root), patch.dict("os.environ", {}, clear=True), patch(
        "pathlib.Path.exists",
        fake_exists,
    ):
        secrets_helper._configure_vault_runtime_env()
        assert Path(os.environ["SIMPLE_VAULT_PASSPHRASE_FILE"]) == passphrase_file
        assert "BW_PASSWORD_FILE" not in os.environ
        assert "SECRETS_AGENT_DATA" not in os.environ


def test_import_tolerates_permission_error_on_optional_extra_root(tmp_path: Path) -> None:
    """O helper não deve quebrar se um path opcional estiver inacessível."""
    import importlib

    module_name = "secrets_helper"
    sys.modules.pop(module_name, None)

    real_exists = Path.exists

    def fake_exists(self: Path) -> bool:
        if str(self) == "/apps/crypto-trader/trading":
            raise PermissionError("forbidden")
        return real_exists(self)

    with patch("pathlib.Path.exists", fake_exists):
        module = importlib.import_module(module_name)

    assert hasattr(module, "get_secret")


def test_get_secret_uses_authentik_fallback() -> None:
    """Se Authentik estiver disponível, get_secret deve utilizar esse caminho como fallback."""
    with patch.object(secrets_helper, "_try_authentik_http") as mock_auth:
        mock_auth.return_value = "auth-value"
        # Clear env to avoid env var resolution
        with patch.dict("os.environ", {}, clear=True):
            val = secrets_helper.get_secret("authentik/some/path", "password", use_cache=False)

    assert val == "auth-value"
