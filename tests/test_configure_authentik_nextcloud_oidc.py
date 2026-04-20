#!/usr/bin/env python3
"""Testes para o provisionamento OIDC do Nextcloud no Authentik."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULE_PATH = ROOT / "forks" / "rpa4all-nextcloud-authentik" / "scripts" / "configure_authentik_nextcloud_oidc.py"
spec = importlib.util.spec_from_file_location("configure_authentik_nextcloud_oidc", MODULE_PATH)
configure_authentik = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(configure_authentik)


def test_build_redirect_uris() -> None:
    redirect_uris = configure_authentik.build_redirect_uris("https://nextcloud.example.com")
    assert "https://nextcloud.example.com/apps/oidc_login/oidc" in redirect_uris
    assert "https://nextcloud.example.com/apps/user_oidc/code" in redirect_uris
    assert redirect_uris.count("\n") == 1


def test_build_provider_payload_contains_default_fields() -> None:
    configure_authentik.CLIENT_SECRET = "test-secret"

    payload = configure_authentik.build_provider_payload(
        flow_pk="10",
        mappings=["1", "2"],
        nextcloud_url="https://nextcloud.example.com",
    )

    assert payload["authorization_flow"] == "10"
    assert payload["client_id"] == "authentik-nextcloud"
    assert payload["client_secret"] == "test-secret"
    assert payload["redirect_uris"].startswith("https://nextcloud.example.com")
    assert payload["include_claims_in_id_token"] is True


def test_build_app_payload_contains_expected_fields() -> None:
    payload = configure_authentik.build_app_payload(provider_pk="15", nextcloud_url="https://nextcloud.example.com")
    assert payload["name"] == "Nextcloud"
    assert payload["slug"] == "nextcloud"
    assert payload["provider"] == "15"
    assert payload["meta_launch_url"] == "https://nextcloud.example.com"


@patch.object(configure_authentik, "_request")
def test_authorization_flow_pk_returns_first(mock_request: MagicMock) -> None:
    mock_request.return_value = {"results": [{"pk": 42}]}
    assert configure_authentik._authorization_flow_pk() == "42"
    mock_request.assert_called_once_with("GET", "/flows/instances/?designation=authorization")


@patch.object(configure_authentik, "_request")
def test_scope_mapping_pks_falls_back(mock_request: MagicMock) -> None:
    def fake_request(method: str, path: str, payload=None):
        if path.startswith("/propertymappings/provider/scope/"):
            raise RuntimeError("not found")
        return {"results": [{"pk": 5}, {"pk": 7}]}

    mock_request.side_effect = fake_request
    assert configure_authentik._scope_mapping_pks() == ["5", "7"]
    assert mock_request.call_count == 2
