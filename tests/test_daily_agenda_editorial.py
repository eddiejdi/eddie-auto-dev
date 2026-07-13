from __future__ import annotations

import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import daily_agenda_editorial as editorial  # noqa: E402


def test_build_ally_youtube_queries_inclui_criadores() -> None:
    _, allies = editorial.load_editorial_config()
    queries = editorial.build_ally_youtube_queries(
        allies,
        deep=True,
        senator_name="Flávio Bolsonaro",
    )
    blob = " ".join(queries).lower()
    assert "site:youtube.com" in blob
    assert "kim pain" in blob
    assert "didi newa" in blob
    assert "auriverde" in blob
    assert "claudio dantas" in blob
    assert "ancapsu" in blob
    assert "flávio bolsonaro" in blob or "flavio bolsonaro" in blob


def test_rank_and_filter_news_prioriza_aliado_e_remove_hostil() -> None:
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Item:
        title: str
        outlet: str
        url: str

    _, allies = editorial.load_editorial_config()
    editorial_cfg = {"exclude_hostile_headlines": True}
    items = [
        Item(
            title="Taxado de traidor, Flávio Bolsonaro propõe adiamento de tarifas",
            outlet="Portal X",
            url="https://news.example/1",
        ),
        Item(
            title="Kim Pain analisa defesa de Flávio Bolsonaro no Senado",
            outlet="YouTube",
            url="https://www.youtube.com/watch?v=abc",
        ),
        Item(
            title="Flávio Bolsonaro discursa em audiência nos EUA sobre tarifas",
            outlet="G1",
            url="https://news.example/2",
        ),
    ]

    ranked = editorial.rank_and_filter_news(
        items,
        allies=allies,
        editorial=editorial_cfg,
        relevance_checker=lambda title: "senado" in title.lower() or "eua" in title.lower(),
        max_items=5,
    )

    titles = [item.title for item in ranked]
    assert "Kim Pain analisa defesa de Flávio Bolsonaro no Senado" in titles
    assert "Taxado de traidor" not in titles
    assert titles[0].startswith("Kim Pain")
