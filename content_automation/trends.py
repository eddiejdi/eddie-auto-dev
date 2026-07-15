"""Detecção de tendências (mock inicial)."""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime

from content_automation.models import TrendItem

logger = logging.getLogger(__name__)

MOCK_TRENDS: dict[str, list[dict[str, object]]] = {
    "cripto": [
        {"title": "Bitcoin rompe resistência e mercado reage", "tags": ["btc", "halving"], "base": 0.92},
        {"title": "Altcoins em alta: o que observar hoje", "tags": ["altcoin", "defi"], "base": 0.78},
        {"title": "ETF de cripto: impacto no varejo brasileiro", "tags": ["etf", "investimento"], "base": 0.71},
    ],
    "curiosidades": [
        {"title": "Fato científico que poucos conhecem", "tags": ["ciência", "fato"], "base": 0.85},
        {"title": "História curiosa que viralizou na internet", "tags": ["história", "viral"], "base": 0.80},
        {"title": "Por que seu cérebro toma decisões erradas", "tags": ["psicologia"], "base": 0.74},
    ],
    "viral_trends": [
        {"title": "Desafio em 15 segundos que está bombando", "tags": ["challenge", "tiktok"], "base": 0.95},
        {"title": "Áudio viral: como usar no seu vídeo", "tags": ["audio", "trend"], "base": 0.88},
        {"title": "Formato de hook que reteve 3x mais", "tags": ["hook", "retenção"], "base": 0.83},
    ],
}


def _jitter(score: float) -> float:
    return round(min(max(score + random.uniform(-0.05, 0.05), 0.0), 1.0), 3)


def collect_trends(topics: list[str], *, seed: int | None = None) -> list[TrendItem]:
    """Coleta tendências mock e calcula score de relevância."""
    if seed is not None:
        random.seed(seed)

    items: list[TrendItem] = []
    hour_boost = datetime.now(UTC).hour / 24 * 0.1

    for topic in topics:
        pool = MOCK_TRENDS.get(topic, [])
        for entry in pool:
            base = float(entry.get("base", 0.5))
            score = _jitter(base + hour_boost)
            items.append(
                TrendItem(
                    topic=topic,
                    title=str(entry["title"]),
                    score=score,
                    source="mock_feed",
                    tags=[str(tag) for tag in entry.get("tags", [])],
                )
            )

    items.sort(key=lambda item: item.score, reverse=True)
    logger.info("trends_collected", extra={"extra_fields": {"count": len(items)}})
    return items


def pick_best_trend(topics: list[str], *, exclude_topics: set[str] | None = None) -> TrendItem | None:
    trends = collect_trends(topics)
    exclude = exclude_topics or set()
    for trend in trends:
        if trend.topic not in exclude:
            return trend
    return trends[0] if trends else None