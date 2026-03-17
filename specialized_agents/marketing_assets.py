"""Estúdio comercial da RPA4ALL para panfletos setoriais e cartões de visita."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import requests
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketing", tags=["marketing"])

AUTHENTIK_URL = os.getenv("AUTHENTIK_URL", "https://auth.rpa4all.com").rstrip("/")
AUTHENTIK_TOKEN = os.getenv("AUTHENTIK_TOKEN", "ak-homelab-authentik-api-2026").strip()
OLLAMA_MARKETING_MODEL = os.getenv("OLLAMA_MARKETING_MODEL", "phi4-mini:latest").strip() or "phi4-mini:latest"
OLLAMA_REQUEST_TIMEOUT = float(os.getenv("OLLAMA_REQUEST_TIMEOUT", "45"))
WIKIMEDIA_USER_AGENT = os.getenv(
    "WIKIMEDIA_USER_AGENT",
    "RPA4ALLMarketingStudio/1.0 (https://www.rpa4all.com; contato@rpa4all.com)",
).strip()

THEME_SANITIZE = re.compile(r"\s+")

DEFAULT_RPA4ALL_CAPABILITIES = [
    "automação de processos com agentes e integrações",
    "observabilidade com métricas e dashboards executivos",
    "IA aplicada para atendimento, classificação e triagem operacional",
    "storage gerenciado por temperatura com portal de gestão e restore com SLA",
]


class MarketingFlyerRequest(BaseModel):
    theme: str
    audience: str = ""
    notes: str = ""


def _candidate_ollama_hosts() -> list[str]:
    configured = [host.strip().rstrip("/") for host in os.getenv("OLLAMA_API_HOSTS", "").split(",") if host.strip()]
    defaults = [
        os.getenv("OLLAMA_API_HOST", "").rstrip("/"),
        "http://192.168.15.2:11434",
        "http://127.0.0.1:11434",
        "http://192.168.15.2:11435",
        "http://127.0.0.1:11435",
    ]
    hosts: list[str] = []
    for item in configured + defaults:
        if item and item not in hosts:
            hosts.append(item)
    return hosts


def _authentik_request(method: str, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.request(
        method,
        f"{AUTHENTIK_URL}/api/v3{endpoint}",
        json=payload,
        headers={
            "Authorization": f"Bearer {AUTHENTIK_TOKEN}",
            "Content-Type": "application/json",
        },
        timeout=20,
        verify=False,
    )
    response.raise_for_status()
    return response.json() if response.text else {}


def _safe_theme(value: str) -> str:
    return THEME_SANITIZE.sub(" ", (value or "").strip())[:120]


def _profile_from_headers(request: Request) -> dict[str, Any]:
    username = (request.headers.get("x-authentik-username") or "").strip()
    email = (request.headers.get("x-authentik-email") or "").strip()
    full_name = (
        request.headers.get("x-authentik-name")
        or request.headers.get("x-authentik-fullname")
        or request.headers.get("x-authentik-display-name")
        or ""
    ).strip()
    groups = [
        item.strip()
        for item in (request.headers.get("x-authentik-groups") or "").split(",")
        if item.strip()
    ]

    if (not full_name or not email) and AUTHENTIK_TOKEN and (email or username):
        query = email or username
        try:
            result = _authentik_request("GET", f"/core/users/?search={query}")
            for user in result.get("results", []):
                candidate_email = (user.get("email") or "").strip()
                candidate_username = (user.get("username") or "").strip()
                if email and candidate_email.lower() != email.lower():
                    continue
                if username and candidate_username and candidate_username != username and not email:
                    continue
                full_name = full_name or (user.get("name") or "").strip()
                email = email or candidate_email
                username = username or candidate_username
                break
        except Exception as exc:
            logger.warning("Falha ao enriquecer perfil de marketing via Authentik: %s", exc)

    fallback_name = full_name or username or (email.split("@", 1)[0] if email else "")
    title_guess = "Especialista RPA4ALL"
    if any("admin" in group.lower() for group in groups):
        title_guess = "Gestão e automação"
    elif any("sales" in group.lower() or "comercial" in group.lower() for group in groups):
        title_guess = "Comercial"

    return {
        "username": username,
        "email": email,
        "name": fallback_name,
        "groups": groups,
        "title_hint": title_guess,
    }


def _extract_json_object(raw: str) -> dict[str, Any]:
    if not raw:
        raise ValueError("Resposta vazia do Ollama.")
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON não encontrado na resposta do Ollama.")
    return json.loads(text[start : end + 1])


def _generate_ollama_json(prompt: str, *, model: str | None = None) -> dict[str, Any]:
    selected_model = (model or OLLAMA_MARKETING_MODEL).strip() or OLLAMA_MARKETING_MODEL
    last_error: Exception | None = None

    for host in _candidate_ollama_hosts():
        try:
            response = requests.post(
                f"{host}/api/generate",
                json={
                    "model": selected_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.55,
                        "num_predict": 900,
                    },
                },
                timeout=OLLAMA_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            data = _extract_json_object((payload.get("response") or "").strip())
            data["_ollama_host"] = host
            data["_ollama_model"] = selected_model
            return data
        except Exception as exc:
            last_error = exc
            continue

    raise HTTPException(status_code=502, detail=f"Falha ao gerar conteúdo com Ollama: {last_error}")


def _normalize_text(value: Any, fallback: str = "", *, max_length: int = 220) -> str:
    text = THEME_SANITIZE.sub(" ", str(value or "").replace("•", " ").strip())
    return text[:max_length] if text else fallback


def _normalize_text_list(
    value: Any,
    *,
    fallback: list[str],
    limit: int,
    max_length: int = 100,
) -> list[str]:
    if isinstance(value, str):
        raw_items = re.split(r"[\n;]+", value)
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []

    items: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = _normalize_text(item, "", max_length=max_length)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        items.append(text)
        if len(items) >= limit:
            break

    return items or fallback[:limit]


def _merge_distinct_texts(values: list[Any], *, limit: int, max_length: int = 100) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()

    for value in values:
        if isinstance(value, list):
            raw_items = value
        else:
            raw_items = [value]
        for item in raw_items:
            text = _normalize_text(item, "", max_length=max_length)
            key = text.lower()
            if not text or key in seen:
                continue
            seen.add(key)
            items.append(text)
            if len(items) >= limit:
                return items

    return items


def _default_research(theme: str, audience: str, notes: str) -> dict[str, Any]:
    audience_line = audience or theme
    notes_summary = _normalize_text(notes, "sem observações adicionais", max_length=160)
    return {
        "market_context": (
            f"Operações ligadas a {theme} normalmente exigem mais previsibilidade, atendimento mais rápido "
            f"e visibilidade sobre filas, documentos e indicadores."
        ),
        "pain_points": [
            "retrabalho operacional e baixa padronização",
            "pouca visibilidade em indicadores, SLA e gargalos",
            "atendimento manual com dificuldade para escalar",
        ],
        "value_angles": [
            "automação de processos e integrações",
            "observabilidade com métricas e dashboards",
            "IA aplicada para triagem, atendimento e classificação",
        ],
        "visual_keywords": [
            theme,
            audience_line,
            "equipe profissional",
            "tecnologia aplicada",
        ],
        "search_queries": [
            theme,
            f"{theme} business team",
            f"{theme} office",
            f"{theme} technology",
            f"{audience_line} professional",
        ],
        "business_card_focus": f"{theme}: automação, IA e previsibilidade operacional",
        "image_style": "fotografia editorial corporativa, pessoas reais, ambiente profissional, tecnologia visível",
        "color_hint": "azul petróleo, ciano e verde com contraste alto",
        "notes_summary": notes_summary,
    }


def _default_reasoning(theme: str, audience: str, research: dict[str, Any]) -> dict[str, Any]:
    audience_line = audience or theme
    return {
        "positioning": (
            f"Posicionar a RPA4ALL como parceira para ganhos rápidos de eficiência em {audience_line}, "
            f"com automação, IA e observabilidade no mesmo pacote."
        ),
        "message_strategy": (
            "Abrir com dor operacional, conectar com previsibilidade e fechar com CTA consultivo de baixo atrito."
        ),
        "proof_points": research.get("value_angles") or DEFAULT_RPA4ALL_CAPABILITIES[:3],
        "cta_rationale": "Convidar para diagnóstico ou proposta curta, sem promessas exageradas.",
        "flyer_layout": "headline forte à esquerda, prova de valor em chips e imagem de contexto em destaque",
        "business_card_layout": "frente com nome e proposta curta; verso com contato, site e especialidades",
        "flyer_format": "poster-portrait",
        "card_tone": f"Executivo, claro e orientado a {theme}",
    }


def _default_brief(theme: str, audience: str, notes: str, research: dict[str, Any], reasoning: dict[str, Any]) -> dict[str, Any]:
    audience_line = audience or theme
    value_angles = research.get("value_angles") or DEFAULT_RPA4ALL_CAPABILITIES[:3]
    return {
        "headline": f"Oferta RPA4ALL para {theme}",
        "subheadline": f"Automação, IA, observabilidade e storage gerenciado com foco em {theme}.",
        "intro": (
            f"A RPA4ALL combina automação, observabilidade, IA aplicada e storage gerenciado para operações ligadas a "
            f"{theme}, com desenho comercial orientado a produtividade, governança e previsibilidade."
        ),
        "offer_title": "O que a RPA4ALL pode oferecer",
        "offer_bullets": value_angles[:3] + DEFAULT_RPA4ALL_CAPABILITIES[:1],
        "image_queries": research.get("search_queries") or [theme, f"{theme} business", f"{theme} team", f"{theme} technology"],
        "cta_primary": "Solicitar proposta",
        "cta_secondary": "Agendar conversa",
        "business_card_tagline": research.get("business_card_focus") or f"RPA4ALL para {theme}",
        "business_card_back_note": "Automação, IA aplicada e observabilidade para operações exigentes.",
        "audience_label": audience_line,
        "notes_summary": notes[:220],
        "visual_direction": research.get("image_style") or "Fotografia corporativa com tecnologia e pessoas em operação.",
        "canvas_prompt": (
            f"Formato {reasoning.get('flyer_format') or 'poster-portrait'}, {reasoning.get('flyer_layout') or 'headline à esquerda'}."
        ),
    }


def _sanitize_research(defaults: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    candidate = candidate if isinstance(candidate, dict) else {}
    return {
        "market_context": _normalize_text(candidate.get("market_context"), defaults["market_context"], max_length=320),
        "pain_points": _normalize_text_list(candidate.get("pain_points"), fallback=defaults["pain_points"], limit=4),
        "value_angles": _normalize_text_list(candidate.get("value_angles"), fallback=defaults["value_angles"], limit=4),
        "visual_keywords": _normalize_text_list(
            candidate.get("visual_keywords"),
            fallback=defaults["visual_keywords"],
            limit=5,
        ),
        "search_queries": _normalize_text_list(candidate.get("search_queries"), fallback=defaults["search_queries"], limit=6),
        "business_card_focus": _normalize_text(
            candidate.get("business_card_focus"),
            defaults["business_card_focus"],
            max_length=120,
        ),
        "image_style": _normalize_text(candidate.get("image_style"), defaults["image_style"], max_length=180),
        "color_hint": _normalize_text(candidate.get("color_hint"), defaults["color_hint"], max_length=140),
        "notes_summary": _normalize_text(candidate.get("notes_summary"), defaults["notes_summary"], max_length=160),
    }


def _sanitize_reasoning(defaults: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    candidate = candidate if isinstance(candidate, dict) else {}
    return {
        "positioning": _normalize_text(candidate.get("positioning"), defaults["positioning"], max_length=260),
        "message_strategy": _normalize_text(
            candidate.get("message_strategy"),
            defaults["message_strategy"],
            max_length=220,
        ),
        "proof_points": _normalize_text_list(candidate.get("proof_points"), fallback=defaults["proof_points"], limit=4),
        "cta_rationale": _normalize_text(candidate.get("cta_rationale"), defaults["cta_rationale"], max_length=180),
        "flyer_layout": _normalize_text(candidate.get("flyer_layout"), defaults["flyer_layout"], max_length=160),
        "business_card_layout": _normalize_text(
            candidate.get("business_card_layout"),
            defaults["business_card_layout"],
            max_length=180,
        ),
        "flyer_format": _normalize_text(candidate.get("flyer_format"), defaults["flyer_format"], max_length=60),
        "card_tone": _normalize_text(candidate.get("card_tone"), defaults["card_tone"], max_length=120),
    }


def _sanitize_brief(defaults: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    candidate = candidate if isinstance(candidate, dict) else {}
    return {
        "headline": _normalize_text(candidate.get("headline"), defaults["headline"], max_length=110),
        "subheadline": _normalize_text(candidate.get("subheadline"), defaults["subheadline"], max_length=180),
        "intro": _normalize_text(candidate.get("intro"), defaults["intro"], max_length=360),
        "offer_title": _normalize_text(candidate.get("offer_title"), defaults["offer_title"], max_length=90),
        "offer_bullets": _normalize_text_list(candidate.get("offer_bullets"), fallback=defaults["offer_bullets"], limit=4),
        "image_queries": _normalize_text_list(candidate.get("image_queries"), fallback=defaults["image_queries"], limit=6),
        "cta_primary": _normalize_text(candidate.get("cta_primary"), defaults["cta_primary"], max_length=60),
        "cta_secondary": _normalize_text(candidate.get("cta_secondary"), defaults["cta_secondary"], max_length=60),
        "business_card_tagline": _normalize_text(
            candidate.get("business_card_tagline"),
            defaults["business_card_tagline"],
            max_length=120,
        ),
        "business_card_back_note": _normalize_text(
            candidate.get("business_card_back_note"),
            defaults["business_card_back_note"],
            max_length=140,
        ),
        "audience_label": _normalize_text(candidate.get("audience_label"), defaults["audience_label"], max_length=120),
        "notes_summary": _normalize_text(candidate.get("notes_summary"), defaults["notes_summary"], max_length=180),
        "visual_direction": _normalize_text(
            candidate.get("visual_direction"),
            defaults["visual_direction"],
            max_length=180,
        ),
        "canvas_prompt": _normalize_text(candidate.get("canvas_prompt"), defaults["canvas_prompt"], max_length=180),
    }


def _build_research_prompt(theme: str, audience: str, notes: str) -> str:
    audience_line = audience or "mercado relacionado ao tema informado"
    notes_line = notes or "sem observações adicionais"
    capabilities = "; ".join(DEFAULT_RPA4ALL_CAPABILITIES)
    return f"""
Você é o agente de pesquisa comercial e visual da RPA4ALL.
Tema: {theme}
Público: {audience_line}
Observações: {notes_line}

Contexto da empresa:
- Marca: RPA4ALL
- Capacidades principais: {capabilities}
- Tom: executivo, confiável, moderno e direto
- Não invente certificações, logos ou números não fornecidos
- A pesquisa deve orientar tanto o panfleto quanto o cartão de visita

Responda somente em JSON com:
- market_context
- pain_points (array com 3 ou 4 itens)
- value_angles (array com 3 ou 4 itens)
- visual_keywords (array com 4 ou 5 itens curtos)
- search_queries (array com 5 ou 6 consultas curtas para fotos reais/profissionais)
- business_card_focus
- image_style
- color_hint
- notes_summary
""".strip()


def _build_reasoning_prompt(theme: str, audience: str, notes: str, research: dict[str, Any]) -> str:
    audience_line = audience or "mercado relacionado ao tema informado"
    notes_line = notes or "sem observações adicionais"
    return f"""
Você é o agente de raciocínio comercial da RPA4ALL.
Tema: {theme}
Público: {audience_line}
Observações: {notes_line}

Pesquisa consolidada:
{json.dumps(research, ensure_ascii=False)}

Transforme a pesquisa em decisão de comunicação. Responda somente em JSON com:
- positioning
- message_strategy
- proof_points (array com 3 ou 4 itens)
- cta_rationale
- flyer_layout
- business_card_layout
- flyer_format
- card_tone
""".strip()


def _build_marketing_prompt(theme: str, audience: str, notes: str, research: dict[str, Any], reasoning: dict[str, Any]) -> str:
    audience_line = audience or "mercado relacionado ao tema informado"
    notes_line = notes or "sem observações adicionais"
    capabilities = "; ".join(DEFAULT_RPA4ALL_CAPABILITIES)
    return f"""
Você é o agente de oferta final da RPA4ALL.
Tema do panfleto: {theme}
Público: {audience_line}
Observações: {notes_line}

Contexto da empresa:
- Marca: RPA4ALL
- Capacidades principais: {capabilities}
- Tom: executivo, confiável, moderno, direto
- Não invente certificações ou números não fornecidos
- Evite promessas irreais e qualquer menção a infraestrutura interna

Pesquisa consolidada:
{json.dumps(research, ensure_ascii=False)}

Raciocínio comercial:
{json.dumps(reasoning, ensure_ascii=False)}

Responda somente em JSON com:
- headline
- subheadline
- intro
- offer_title
- offer_bullets (array com 4 itens)
- image_queries (array com 4 a 6 consultas curtas para buscar fotos de mercado/ambiente profissional relacionadas ao tema)
- cta_primary
- cta_secondary
- business_card_tagline
- business_card_back_note
- audience_label
- notes_summary
- visual_direction
- canvas_prompt
""".strip()


def _prepare_image_queries(theme: str, audience: str, research: dict[str, Any], brief: dict[str, Any]) -> list[str]:
    audience_line = audience or theme
    queries = _merge_distinct_texts(
        [
            research.get("search_queries"),
            brief.get("image_queries"),
            theme,
            f"{theme} business team",
            f"{theme} office",
            f"{theme} technology",
            f"{audience_line} professional",
        ],
        limit=6,
    )
    return queries or [theme, f"{theme} office", f"{theme} team", f"{theme} technology"]


def _is_viable_image_candidate(title: str, image_url: str) -> bool:
    haystack = f"{title} {image_url}".lower()
    if any(
        blocked in haystack
        for blocked in ("logo", "icon", "flag", "seal", "coat of arms", "map", "diagram", "infographic", "crest")
    ):
        return False
    if any(haystack.endswith(f".{ext}") for ext in ("svg", "tif", "tiff", "pdf", "djvu")):
        return False
    return bool(image_url)


def _score_image_candidate(title: str, query: str, query_index: int, author: str, license_name: str) -> int:
    score = max(0, 120 - query_index * 12)
    title_lower = title.lower()
    query_tokens = [token for token in query.lower().split() if len(token) > 2]
    score += sum(8 for token in query_tokens if token in title_lower)
    if author:
        score += 4
    if license_name:
        score += 4
    if any(token in title_lower for token in ("office", "team", "business", "technology", "clinic", "hospital", "workspace")):
        score += 6
    return score


def _search_wikimedia_images(queries: list[str], *, limit: int = 6) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    headers = {"User-Agent": WIKIMEDIA_USER_AGENT}

    for query_index, query in enumerate(queries):
        try:
            response = requests.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": query,
                    "gsrnamespace": "6",
                    "gsrlimit": "10",
                    "prop": "imageinfo",
                    "iiprop": "url|extmetadata",
                    "iiurlwidth": "1600",
                    "format": "json",
                },
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            logger.warning("Falha ao pesquisar imagens para %s: %s", query, exc)
            continue

        pages = list((payload.get("query") or {}).get("pages", {}).values())
        for page in pages:
            title = (page.get("title") or "").strip()
            if not title or title in seen_titles:
                continue
            image_info = (page.get("imageinfo") or [{}])[0]
            image_url = image_info.get("thumburl") or image_info.get("url") or ""
            metadata = image_info.get("extmetadata") or {}
            author = re.sub(r"<[^>]+>", "", metadata.get("Artist", {}).get("value", "")).strip()
            license_name = metadata.get("LicenseShortName", {}).get("value", "") or "Licença não informada"
            description = re.sub(r"<[^>]+>", "", metadata.get("ImageDescription", {}).get("value", "")).strip()
            if not _is_viable_image_candidate(title, image_url):
                continue
            items.append(
                {
                    "query": query,
                    "title": title.replace("File:", ""),
                    "image_url": image_url,
                    "source_page": image_info.get("descriptionurl"),
                    "author": author,
                    "license": license_name,
                    "description": description,
                    "score": _score_image_candidate(title, query, query_index, author, license_name),
                }
            )
            seen_titles.add(title)
            if len(items) >= limit * 3:
                break

    ranked = sorted(items, key=lambda item: item.get("score", 0), reverse=True)
    return ranked[:limit]


@router.get("/profile")
def marketing_profile(request: Request) -> dict[str, Any]:
    return {
        "status": "ok",
        "profile": _profile_from_headers(request),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/studio/generate")
def marketing_generate_flyer(payload: MarketingFlyerRequest, request: Request) -> dict[str, Any]:
    theme = _safe_theme(payload.theme)
    if not theme:
        raise HTTPException(status_code=400, detail="Informe um tema para gerar o panfleto.")

    audience = _safe_theme(payload.audience)
    notes = (payload.notes or "").strip()
    profile = _profile_from_headers(request)
    research = _default_research(theme, audience, notes)
    reasoning = _default_reasoning(theme, audience, research)
    brief = _default_brief(theme, audience, notes, research, reasoning)
    agent_sources = {
        "research": "fallback",
        "reasoning": "fallback",
        "brief": "fallback",
    }

    try:
        research_generated = _generate_ollama_json(_build_research_prompt(theme, audience, notes))
        research = _sanitize_research(research, research_generated)
        agent_sources["research"] = "ollama"
    except HTTPException:
        logger.exception("Pesquisa do estúdio comercial indisponível via Ollama, usando fallback.")

    reasoning = _default_reasoning(theme, audience, research)
    try:
        reasoning_generated = _generate_ollama_json(_build_reasoning_prompt(theme, audience, notes, research))
        reasoning = _sanitize_reasoning(reasoning, reasoning_generated)
        agent_sources["reasoning"] = "ollama"
    except HTTPException:
        logger.exception("Raciocínio do estúdio comercial indisponível via Ollama, usando fallback.")

    brief = _default_brief(theme, audience, notes, research, reasoning)
    try:
        brief_generated = _generate_ollama_json(_build_marketing_prompt(theme, audience, notes, research, reasoning))
        brief = _sanitize_brief(brief, brief_generated)
        brief["_ollama_host"] = brief_generated.get("_ollama_host")
        brief["_ollama_model"] = brief_generated.get("_ollama_model")
        agent_sources["brief"] = "ollama"
    except HTTPException:
        logger.exception("Oferta final do estúdio comercial indisponível via Ollama, usando fallback.")

    image_queries = _prepare_image_queries(theme, audience, research, brief)
    brief["image_queries"] = image_queries

    images = _search_wikimedia_images(image_queries, limit=6)
    if all(source == "ollama" for source in agent_sources.values()):
        narrative_source = "ollama"
    elif any(source == "ollama" for source in agent_sources.values()):
        narrative_source = "hybrid"
    else:
        narrative_source = "fallback"

    return {
        "status": "ok",
        "theme": theme,
        "audience": audience,
        "notes": notes,
        "profile": profile,
        "research": research,
        "reasoning": reasoning,
        "brief": brief,
        "agent_sources": agent_sources,
        "image_research": {
            "provider": "wikimedia_commons",
            "queries": image_queries,
            "items": images,
        },
        "narrative_source": narrative_source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
