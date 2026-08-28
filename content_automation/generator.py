"""Geração de roteiro curto a partir de prompts estruturados."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from content_automation.models import GeneratedContent, TrendItem

logger = logging.getLogger(__name__)


def load_prompt_template(prompts_dir: Path, topic: str) -> dict[str, Any]:
    path = prompts_dir / f"{topic}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt não encontrado para tema '{topic}': {path}")
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _render_template(template: str, context: dict[str, str]) -> str:
    result = template
    for key, value in context.items():
        result = result.replace(f"{{{key}}}", value)
    return result.strip()


def generate_content(
    trend: TrendItem,
    *,
    prompts_dir: Path,
    max_script_seconds: int = 60,
) -> GeneratedContent:
    """Gera título, roteiro e CTA usando template YAML + dados da trend."""
    prompt = load_prompt_template(prompts_dir, trend.topic)
    context = {
        "topic": trend.topic,
        "trend_title": trend.title,
        "tags": ", ".join(trend.tags),
        "max_seconds": str(max_script_seconds),
        "score": f"{trend.score:.2f}",
    }

    title_tpl = prompt.get("title_template", "{trend_title}")
    script_tpl = prompt.get("script_template", "Roteiro sobre {trend_title}.")
    cta_tpl = prompt.get("cta_template", "Siga para mais conteúdo sobre {topic}!")

    title = _render_template(str(title_tpl), context)
    script = _render_template(str(script_tpl), context)
    cta = _render_template(str(cta_tpl), context)

    content = GeneratedContent(
        topic=trend.topic,
        title=title,
        script=script,
        cta=cta,
        trend_score=trend.score,
        metadata={
            "prompt_file": str(prompts_dir / f"{trend.topic}.yaml"),
            "trend_source": trend.source,
            "tags": trend.tags,
        },
    )
    logger.info(
        "content_generated",
        extra={
            "extra_fields": {
                "topic": content.topic,
                "title": content.title,
                "trend_score": content.trend_score,
            }
        },
    )
    return content