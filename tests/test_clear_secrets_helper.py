#!/usr/bin/env python3
"""Testes unitarios para clear_trading_agent.secrets_helper."""
from __future__ import annotations

from unittest.mock import patch

from clear_trading_agent import secrets_helper


def test_get_clear_broker_credentials_prefers_secret_store() -> None:
    """Credenciais devem priorizar vault e manter fallback de env."""
    with patch.object(secrets_helper, "get_secret") as mock_get_secret, patch.dict(
        "os.environ",
        {
            "CLEAR_BROKER_LOGIN_USERNAME": "env-user",
            "CLEAR_BROKER_LOGIN": "env-pass",
        },
        clear=False,
    ):
        def _secret(name: str, field: str = "password", use_cache: bool = True):
            if name == "clear/broker_login" and field == "username":
                return "vault-user"
            if name == "clear/broker_login" and field == "password":
                return "vault-pass"
            return None

        mock_get_secret.side_effect = _secret
        username, password = secrets_helper.get_clear_broker_credentials()

    assert username == "vault-user"
    assert password == "vault-pass"


def test_get_clear_integration_status_sanitized() -> None:
    """Status nao pode conter valores sensiveis, apenas flags booleanas."""
    with patch.object(secrets_helper, "get_mt5_bridge_credentials", return_value=("http://x", "api-key")), patch.object(
        secrets_helper,
        "get_clear_broker_credentials",
        return_value=("user@example.com", "123"),
    ):
        status = secrets_helper.get_clear_integration_status()

    assert status["bridge_url"] == "http://x"
    assert status["bridge_api_key_configured"] is True
    assert status["broker_username_configured"] is True
    assert status["broker_password_configured"] is True
    assert "password" not in status
