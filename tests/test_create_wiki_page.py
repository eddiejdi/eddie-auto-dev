from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import create_wiki_page as cwp


def test_get_page_id_returns_none_when_page_is_missing(monkeypatch):
    """A consulta de página ausente não deve levantar erro."""
    monkeypatch.setattr(
        cwp,
        "graphql",
        lambda payload, api_token: {"data": {"pages": {"singleByPath": None}}},
    )

    assert cwp.get_page_id(None) is None


def test_build_wiki_url_includes_locale_prefix():
    """A URL pública deve refletir o locale pt configurado no script."""
    assert cwp.build_wiki_url("operations/ltfs-selfheal-system") == (
        "https://wiki.rpa4all.com/pt/operations/ltfs-selfheal-system"
    )