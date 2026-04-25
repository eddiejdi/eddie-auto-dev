"""Unit tests for tools/authentik_management/authentik_secret_fetcher.py."""
from __future__ import annotations

from unittest.mock import patch, Mock
import json
import requests

import sys
from pathlib import Path

# Ensure repository root is on sys.path for imports
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.authentik_management import authentik_secret_fetcher as fetcher


def _mock_response(json_data: dict, status: int = 200) -> Mock:
    m = Mock()
    m.status_code = status
    m.json = Mock(return_value=json_data)
    m.text = json.dumps(json_data)
    return m


def test_get_secret_from_authentik_local_success() -> None:
    name = "authentik/mysecret"
    value = "s3cr3t"
    with patch("requests.get") as mock_get:
        mock_get.return_value = _mock_response({"value": value}, 200)
        res = fetcher.get_secret_from_authentik(name, "password", auth_url="https://auth.example.com", token="ak-1")
    assert res == value


def test_get_secret_from_authentik_fallback_app_client_secret() -> None:
    name = "myapp"
    with patch("requests.get") as mock_get:
        # First call -> secrets/local returns 404
        def side_effect(url, headers=None, params=None, timeout=None, verify=None):
            if "/secrets/local/" in url:
                return _mock_response({}, 404)
            if "/secrets/" in url and "/secrets/local/" not in url:
                return _mock_response({}, 404)
            if "/core/applications/" in url:
                return _mock_response({"results": [{"client_secret": "app-secret"}]}, 200)
            return _mock_response({}, 404)

        mock_get.side_effect = side_effect
        res = fetcher.get_secret_from_authentik(name, "password", auth_url="https://auth.example.com", token="ak-1")

    assert res == "app-secret"


def test_get_secret_from_authentik_no_result_returns_none() -> None:
    name = "unknown"
    with patch("requests.get") as mock_get:
        mock_get.return_value = _mock_response({}, 404)
        res = fetcher.get_secret_from_authentik(name, "password", auth_url="https://auth.example.com", token="ak-1")
    assert res is None
