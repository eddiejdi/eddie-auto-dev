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


def test_direitaja_tem_prioridade_editorial() -> None:
    _, allies = editorial.load_editorial_config()
    score_dj = editorial.news_editorial_score(
        title="Flávio lidera em SP",
        outlet="Direita Já",
        url="https://direitaja.com/?material=1",
        allies=allies,
    )
    score_ally = editorial.news_editorial_score(
        title="Kim Pain destaca defesa de Flávio Bolsonaro no Senado",
        outlet="YouTube",
        url="https://www.youtube.com/watch?v=abc",
        allies=allies,
    )
    assert editorial.is_direitaja_truth_item(
        title="x", outlet="Direita Já", url="https://direitaja.com/?material=1"
    )
    assert score_dj > score_ally
    assert editorial.should_keep_news_item(
        title="Flávio lidera em SP",
        outlet="Direita Já",
        url="https://direitaja.com/?material=1",
        allies=allies,
        editorial={"exclude_hostile_headlines": True},
        relevance_checker=lambda _t: False,
    )


def test_is_hostile_news_title_bloqueia_repete_pai_e_urnas() -> None:
    """Proíbe enquadramentos do tipo 'repete o pai e ataca urnas eletrônicas'."""
    assert editorial.is_hostile_news_title(
        "Flávio Bolsonaro repete o pai e ataca urnas eletrônicas"
    )
    assert editorial.is_hostile_news_title(
        "Senador copia o pai e questiona as urnas no Senado"
    )
    assert editorial.is_hostile_news_title(
        "Bolsonaro volta a falar em fraude nas urnas"
    )
    assert editorial.is_hostile_news_title(
        "Flávio Bolsonaro deixa de votar na maioria das decisões e só emplaca duas propostas em 7 anos"
    )
    assert editorial.is_hostile_news_title(
        'Flávio Bolsonaro, ou "zero-um" para o pai, quer ser o próximo presidente do Brasil'
    )
    assert editorial.is_hostile_news_title(
        "PF cancela depoimento de Flávio Bolsonaro após defesa apresentar documentos em investigação por suposta calúnia"
    )
    assert not editorial.is_hostile_news_title(
        "Flávio Bolsonaro discursa em audiência nos EUA sobre tarifas"
    )


def test_rank_and_filter_remove_repete_pai_mesmo_de_aliado() -> None:
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Item:
        title: str
        outlet: str
        url: str

    _, allies = editorial.load_editorial_config()
    items = [
        Item(
            title="Flávio Bolsonaro repete o pai e ataca urnas eletrônicas",
            outlet="G1",
            url="https://news.example/hostile",
        ),
        Item(
            title="Kim Pain: Flávio Bolsonaro repete o pai e ataca urnas eletrônicas",
            outlet="YouTube",
            url="https://www.youtube.com/watch?v=hostile",
        ),
        Item(
            title="Kim Pain destaca defesa de Flávio Bolsonaro no Senado",
            outlet="YouTube",
            url="https://www.youtube.com/watch?v=ok",
        ),
    ]
    ranked = editorial.rank_and_filter_news(
        items,
        allies=allies,
        editorial={"exclude_hostile_headlines": True},
        relevance_checker=lambda title: True,
        max_items=10,
    )
    titles = " | ".join(item.title for item in ranked)
    assert "repete o pai" not in titles
    assert "urnas" not in titles.lower()
    assert "Kim Pain destaca defesa de Flávio Bolsonaro no Senado" in titles
