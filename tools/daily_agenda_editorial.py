#!/usr/bin/env python3
"""Linha editorial da agenda diária — aliados e tom positivo à família Bolsonaro."""
from __future__ import annotations

import re
from typing import Any

DEFAULT_ALLY_YOUTUBE: tuple[dict[str, Any], ...] = (
    {
        "name": "Kim Pain",
        "search_terms": ("Kim Pain", "Kim Pain TV"),
        "channel_id": "",
        "handle": "@KimPain",
    },
    {
        "name": "Didi Newa",
        "search_terms": ("Didi Newa", "Didi News"),
        "channel_id": "",
        "handle": "@DidiNewa",
    },
    {
        "name": "Auriverde",
        "search_terms": ("Auriverde",),
        "channel_id": "",
        "handle": "@Auriverde",
    },
    {
        "name": "Claudio Dantas",
        "search_terms": ("Claudio Dantas", "Cláudio Dantas"),
        "channel_id": "",
        "handle": "@ClaudioDantas",
    },
    {
        "name": "Ancapsu",
        "search_terms": ("Ancapsu", "Ancap Su"),
        "channel_id": "",
        "handle": "@ancapsu",
    },
    {
        "name": "Flávio Bolsonaro",
        "search_terms": (
            "Flávio Bolsonaro",
            "Senador Flávio Bolsonaro",
            "Flavio Bolsonaro oficial",
        ),
        "channel_id": "",
        "handle": "@flaviobolsonaro",
    },
)

DEFAULT_EDITORIAL: dict[str, Any] = {
    "stance": "pro_bolsonaro_allies",
    "prefer_ally_youtube": True,
    "exclude_hostile_headlines": True,
    "include_bolsonaro_family_context": True,
}

HOSTILE_NEWS_MARKERS: tuple[str, ...] = (
    "taxado de",
    "chamado de traidor",
    "traidor",
    "briga com michelle",
    "briga com a michelle",
    "não apareceu em",
    "nao apareceu em",
    "ausente em",
    "abandono",
    "vergonha",
    "alvo da pf",
    "investigado",
    "escândalo",
    "escandalo",
    "derrota",
    "fracasso",
    "isolado",
    "rejeitado",
)

POSITIVE_NEWS_MARKERS: tuple[str, ...] = (
    "defende",
    "defesa",
    "destaca",
    "elogia",
    "apoia",
    "aliado",
    "verdade",
    "coragem",
    "liderança",
    "lideranca",
    "compromisso",
    "trabalho",
    "proposta",
    "relatoria",
    "discurso",
    "audiência nos eua",
    "audiencia nos eua",
)

BOLSONARO_FAMILY_TOKENS: tuple[str, ...] = (
    "flávio",
    "flavio",
    "bolsonaro",
    "jair",
    "michelle",
    "nikolas",
    "eduardo bolsonaro",
    "carla zambelli",
)


def load_editorial_config() -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    try:
        from daily_agenda_config import load_config

        cfg = load_config()
    except Exception:
        cfg = {}
    editorial = {**DEFAULT_EDITORIAL, **(cfg.get("editorial") or {})}
    allies = cfg.get("ally_youtube") or list(DEFAULT_ALLY_YOUTUBE)
    normalized: list[dict[str, Any]] = []
    for item in allies:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        terms = item.get("search_terms") or (name,)
        if isinstance(terms, str):
            terms = (terms,)
        normalized.append(
            {
                "name": name,
                "search_terms": tuple(str(t).strip() for t in terms if str(t).strip()),
                "channel_id": str(item.get("channel_id", "")).strip(),
                "handle": str(item.get("handle", "")).strip(),
            }
        )
    if not normalized:
        normalized = [dict(item) for item in DEFAULT_ALLY_YOUTUBE]
    return editorial, tuple(normalized)


def ally_display_names(allies: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    return tuple(item["name"] for item in allies if item.get("name"))


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().lower()


def mentions_bolsonaro_family(title: str) -> bool:
    lowered = _normalize_title(title)
    return any(token in lowered for token in BOLSONARO_FAMILY_TOKENS)


def is_hostile_news_title(title: str) -> bool:
    lowered = _normalize_title(title)
    return any(marker in lowered for marker in HOSTILE_NEWS_MARKERS)


def is_positive_news_title(title: str) -> bool:
    lowered = _normalize_title(title)
    return any(marker in lowered for marker in POSITIVE_NEWS_MARKERS)


def match_ally_youtube_creator(
    *,
    title: str,
    outlet: str,
    url: str,
    allies: tuple[dict[str, Any], ...],
) -> str | None:
    blob = _normalize_title(f"{title} {outlet} {url}")
    if "youtube" not in blob and "youtu.be" not in blob:
        return None
    for ally in allies:
        name = str(ally.get("name", "")).strip()
        if name and name.lower() in blob:
            return name
        for term in ally.get("search_terms", ()):
            term_norm = str(term).strip().lower()
            if term_norm and term_norm in blob:
                return name or term
    return None


def is_ally_youtube_item(
    *,
    title: str,
    outlet: str,
    url: str,
    allies: tuple[dict[str, Any], ...],
) -> bool:
    return match_ally_youtube_creator(
        title=title,
        outlet=outlet,
        url=url,
        allies=allies,
    ) is not None


def is_relevant_ally_youtube_title(title: str) -> bool:
    return mentions_bolsonaro_family(title)


def build_ally_youtube_queries(
    allies: tuple[dict[str, Any], ...],
    *,
    deep: bool,
    senator_name: str,
) -> list[str]:
    window = "14d" if deep else "7d"
    queries: list[str] = []
    for ally in allies:
        name = str(ally.get("name", "")).strip()
        terms = ally.get("search_terms") or (name,)
        for term in terms:
            term = str(term).strip()
            if not term:
                continue
            queries.append(f'site:youtube.com "{term}" "{senator_name}" when:{window}')
            queries.append(f'site:youtube.com "{term}" Bolsonaro when:{window}')
    return list(dict.fromkeys(queries))


def news_editorial_score(
    *,
    title: str,
    outlet: str,
    url: str,
    allies: tuple[dict[str, Any], ...],
) -> int:
    score = 0
    if match_ally_youtube_creator(title=title, outlet=outlet, url=url, allies=allies):
        score += 100
    if is_positive_news_title(title):
        score += 25
    if is_hostile_news_title(title):
        score -= 80
    if mentions_bolsonaro_family(title):
        score += 10
    return score


def should_keep_news_item(
    *,
    title: str,
    outlet: str,
    url: str,
    allies: tuple[dict[str, Any], ...],
    editorial: dict[str, Any],
    relevance_checker,
) -> bool:
    if match_ally_youtube_creator(title=title, outlet=outlet, url=url, allies=allies):
        return is_relevant_ally_youtube_title(title)
    if editorial.get("exclude_hostile_headlines", True) and is_hostile_news_title(title):
        return False
    return bool(relevance_checker(title))


def rank_and_filter_news(
    snippets: list[Any],
    *,
    allies: tuple[dict[str, Any], ...],
    editorial: dict[str, Any],
    relevance_checker,
    max_items: int,
) -> list[Any]:
    kept: list[Any] = []
    for item in snippets:
        title = getattr(item, "title", "")
        outlet = getattr(item, "outlet", "")
        url = getattr(item, "url", "")
        if not should_keep_news_item(
            title=title,
            outlet=outlet,
            url=url,
            allies=allies,
            editorial=editorial,
            relevance_checker=relevance_checker,
        ):
            continue
        ally = match_ally_youtube_creator(
            title=title,
            outlet=outlet,
            url=url,
            allies=allies,
        )
        if ally and ally.lower() not in outlet.lower():
            object.__setattr__(
                item,
                "outlet",
                f"{ally} (YouTube)",
            )
        kept.append(item)

    kept.sort(
        key=lambda item: news_editorial_score(
            title=getattr(item, "title", ""),
            outlet=getattr(item, "outlet", ""),
            url=getattr(item, "url", ""),
            allies=allies,
        ),
        reverse=True,
    )
    return kept[:max_items]
