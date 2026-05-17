from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wiki_agent import Config, WikiClient


def test_config_defaults_locale_to_pt(monkeypatch):
    """O agente raiz deve assumir locale pt por padrão."""
    monkeypatch.delenv("WIKI_LOCALE", raising=False)

    config = Config()

    assert config.locale == "pt"


def test_create_page_returns_locale_aware_public_url():
    """A URL pública deve incluir o prefixo de locale quando não for en."""
    config = Config(
        wiki_api="http://wiki.local/graphql",
        wiki_public="https://wiki.rpa4all.com",
        wiki_token="token",
        ollama_api="http://ollama.local",
        locale="pt",
    )
    client = WikiClient(config, "token")

    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "data": {
            "pages": {
                "create": {
                    "responseResult": {
                        "succeeded": True,
                        "errorCode": 0,
                        "message": "",
                    },
                    "page": {
                        "id": 7,
                        "path": "operations/ltfs-selfheal-system",
                    },
                }
            }
        }
    }

    with patch("wiki_agent.requests.post", return_value=response) as mocked_post:
        ok, message = client.create_page(
            path="operations/ltfs-selfheal-system",
            title="LTFS Self-Heal System",
            description="Referência operacional",
            content="# LTFS",
            tags=["ltfs"],
        )

    assert ok is True
    assert message == (
        "ID=7 → https://wiki.rpa4all.com/pt/operations/ltfs-selfheal-system"
    )
    mocked_post.assert_called_once()