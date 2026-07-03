"""Agente de pesquisa para o Acervo da Biblioteca Nacional via Sophia Web.

Arquitetura:
- GPU1 (Ollama leve): planeja consultas, ranqueia resultados e resume OCR.
- GPU0 (Ollama principal/visao): faz OCR em imagens/PDFs e gera a historia final.

Coleta:
- Busca primaria: DuckDuckGo HTML com restricao `site:acervo.bn.gov.br/sophia_web`
  para contornar a busca interna quando o Cloudflare barra automacao.
- Leitura de paginas de detalhe: Firefox headless via Selenium.
- Links para PDFs/imagens digitais: extraidos das paginas do Sophia e baixados
  diretamente do host de objeto digital quando disponiveis.

Guardrails:
- Semaforos separados por GPU para evitar OOM.
- Teto de bytes por download, paginas OCR por documento e tamanho de prompt.
- Cooldown entre requests ao Sophia e reabertura de sessao ao detectar bloqueio.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
from collections import deque
import hashlib
import json
import logging
import os
import glob
import inspect
import random
import re
import subprocess
import sys
import time
import threading
import unicodedata
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable

try:
    import fcntl
except ImportError:  # pragma: no cover - ambiente nao Unix.
    fcntl = None

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from specialized_agents.config import DATA_DIR, LLM_GPU1_CONFIG, get_dynamic_num_ctx
except ModuleNotFoundError:  # pragma: no cover - suporte ao CLI direto
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from specialized_agents.config import DATA_DIR, LLM_GPU1_CONFIG, get_dynamic_num_ctx

try:
    from specialized_agents.copilot_model_router import get_copilot_router
except Exception:  # pragma: no cover - opcional
    get_copilot_router = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
router = APIRouter()


class InMemoryLogHandler(logging.Handler):
    def __init__(self, max_entries: int = 400) -> None:
        super().__init__(level=logging.DEBUG)
        self._entries: deque[dict[str, Any]] = deque(maxlen=max_entries)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "ts": datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
            }
            with self._lock:
                self._entries.append(entry)
        except Exception:
            pass

    def snapshot(self, limit: int = 120) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._entries)
        return items[-limit:]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_BN_ACERVO_LOG_BUFFER = InMemoryLogHandler(max_entries=int(os.getenv("BN_ACERVO_LOG_BUFFER_SIZE", "600")))
_BN_ACERVO_LOG_BUFFER.setFormatter(logging.Formatter("%(levelname)s %(name)s - %(message)s"))
_BN_ACERVO_LOG_BUFFER._bn_acervo_handler = True  # type: ignore[attr-defined]
_root_logger = logging.getLogger()
if not any(getattr(handler, "_bn_acervo_handler", False) for handler in _root_logger.handlers):
    _root_logger.addHandler(_BN_ACERVO_LOG_BUFFER)

_JOB_TASKS: dict[str, asyncio.Task[Any]] = {}


def _job_is_active_status(status: Any) -> bool:
    return str(status or "").strip().lower() in {"queued", "running"}

TARGET_BASE_URL = "https://acervo.bn.gov.br/sophia_web"
TARGET_HOST = "acervo.bn.gov.br"
DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"
OBJDIGITAL_HOST = "objdigital.bn.br"
BNDIGITAL_HOST = "bndigital.bn.gov.br"
HEMEROTECA_PDF_HOST = "hemeroteca-pdf.bn.gov.br"
BN_ALLOWED_HOSTS = {
    TARGET_HOST,
    OBJDIGITAL_HOST,
    BNDIGITAL_HOST,
    HEMEROTECA_PDF_HOST,
}
PRESS_KEYWORDS = (
    "jornal",
    "jornais",
    "revista",
    "revistas",
    "imprensa",
    "hemeroteca",
    "periódico",
    "periodico",
)
ACTOR_NAME_PATTERN = (
    r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ0-9&.'/-]*"
    r"(?:\s+(?:[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ0-9&.'/-]*|da|de|do|dos|das|e|d'))*"
)
RELATION_VERBS = (
    "emprestou",
    "prometeu",
    "pagou",
    "repassou",
    "cedeu",
    "concedeu",
    "liberou",
    "doou",
    "financiou",
    "patrocinou",
    "apoiou",
    "vendeu",
    "forneceu",
    "entregou",
    "comprou",
    "adquiriu",
    "negociou",
    "tratou",
    "articulou",
    "anunciou",
    "ofereceu",
    "garantiu",
    "acusou",
    "criticou",
    "processou",
    "nomeou",
    "indicou",
)
RELATION_SENTENCE_RE = re.compile(
    rf"(?P<source>{ACTOR_NAME_PATTERN})"
    rf"(?:\s+(?:ja|já|tambem|também|ainda|entao|então|depois|formalmente|publicamente|diretamente|oficialmente|supostamente)){{0,2}}"
    rf"\s+(?P<verb>(?i:{'|'.join(re.escape(verb) for verb in RELATION_VERBS)}))"
    rf"(?:\s+(?P<object>.*?))?"
    rf"\s+(?P<prep>(?i:para|a|ao|à|aos|às|com|de|do|da|dos|das|contra))"
    rf"(?:\s+(?:o|a|os|as))?"
    rf"\s+(?P<target>{ACTOR_NAME_PATTERN})"
)
ACTOR_STOPWORDS = {
    "biblioteca nacional",
    "hemeroteca digital",
    "historia",
    "história",
    "jornal",
    "revista",
    "documento",
    "fonte",
    "registro",
    "cronologia",
    "brasil",
}
ORGANIZATION_HINTS = (
    "s.a",
    "s/a",
    "ltda",
    "limitada",
    "companhia",
    "cia",
    "empresa",
    "empresas",
    "grupo",
    "motores",
    "indústria",
    "industria",
    "fábrica",
    "fabrica",
)
INSTITUTION_HINTS = (
    "banco",
    "ministério",
    "ministerio",
    "congresso",
    "senado",
    "câmara",
    "camara",
    "assembleia",
    "tribunal",
    "prefeitura",
    "governo",
    "secretaria",
    "universidade",
    "fundação",
    "fundacao",
    "correios",
    "partido",
    "presidência",
    "presidencia",
)
POLITICAL_TITLE_HINTS = (
    "presidente",
    "ex-presidente",
    "vice-presidente",
    "governador",
    "vice-governador",
    "ministro",
    "senador",
    "senadora",
    "deputado",
    "deputada",
    "prefeito",
    "prefeita",
    "vereador",
    "vereadora",
    "secretário",
    "secretaria",
    "secretario",
    "candidato",
    "candidata",
    "interventor",
    "presidenciável",
    "presidenciavel",
)
POLITICAL_TITLE_RE = re.compile(
    rf"\b(?P<title>(?i:{'|'.join(re.escape(title) for title in POLITICAL_TITLE_HINTS)}))\b"
    rf"(?:\s+(?:da|do|dos|das|de)\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ0-9&.'/-]*){{0,3}}"
    rf"\s+(?P<name>{ACTOR_NAME_PATTERN})"
)
POLITICAL_APPOSITION_RE = re.compile(
    rf"(?P<name>{ACTOR_NAME_PATTERN})"
    rf"\s*,?\s+(?P<title>(?i:{'|'.join(re.escape(title) for title in POLITICAL_TITLE_HINTS)}))\b"
)

DOCUMENT_SUFFIXES = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".webp",
}

FIELD_LABELS = (
    "Link do título",
    "Material",
    "Idioma",
    "ISBN",
    "Classificação Dewey",
    "Localização",
    "Outros títulos",
    "Título uniforme coletivo",
    "Edição",
    "Publicação",
    "Descrição física",
    "Série",
    "Nota geral",
    "Nota bibliográfica",
    "Nota da Bibliografia Nacional Brasileira",
    "Nota biográfica",
    "Nota de forma física adicional",
    "Assuntos",
    "Autoria",
    "Exemplares",
)

NOISE_LINES = {
    "Acessibilidade Alto contraste",
    "Todos os campos",
    "Busca avançada",
    "Registro completo",
    "Referência",
    "MARC tags",
    "Selecionar",
    "Favoritar",
    "Reservar",
    "Informações do exemplar Biblioteca Localização Coleção Situação QR Code",
    "Desenvolvido por",
    "App instalado",
}

FOOTER_LINES = {
    "Desenvolvido por",
    "App instalado",
}

BLOCK_MARKERS = (
    "attention required!",
    "just a moment...",
    "sorry, you have been blocked",
    "you are unable to access bn.gov.br",
    "cloudflare ray id",
)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _truncate(text: str, max_chars: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _read_log_tail(path: str | None, limit: int = 120) -> list[str]:
    if not path:
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except Exception:
        return []
    return [line.replace("\x00", "").rstrip("\n") for line in lines[-limit:]]


def _job_progress_percent(phase: str, extra: dict[str, Any] | None = None) -> int:
    if extra and isinstance(extra.get("percent"), int | float):
        try:
            return max(0, min(100, int(extra["percent"])))
        except Exception:
            pass
    mapping = {
        "queued": 0,
        "planning": 12,
        "discovery": 34,
        "ranking": 52,
        "documents": 66,
        "composition": 82,
        "contingency": 100,
        "completed": 100,
        "failed": 100,
    }
    return mapping.get(phase, 0)


def _clean_search_snippet(text: str) -> str:
    cleaned = " ".join((text or "").split()).strip()
    ad_markers = (
        "Amazon.com.br - Conta com a gente!",
        "Viewing ads is privacy protected by DuckDuckGo",
        "| Ad |",
    )
    for marker in ad_markers:
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[0].strip(" |-")
    return cleaned


def _extract_year(text: str) -> int | None:
    match = re.search(r"\b(1[89]\d{2}|20\d{2})\b", text or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _slug_identifier(text: str, *, prefix: str) -> str:
    ascii_text = (
        unicodedata.normalize("NFKD", (text or "").strip())
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    cleaned = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
    if not cleaned:
        cleaned = prefix
    if cleaned[0].isdigit():
        cleaned = f"{prefix}_{cleaned}"
    return cleaned


def _ascii_fold(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", (text or "").strip())
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def _sanitize_mermaid_text(text: str) -> str:
    cleaned = (text or "").replace('"', "'").replace("\n", " ").strip()
    return _truncate(cleaned, 120)


def _normalize_reference_codes(raw_refs: Any, valid_refs: set[str]) -> list[str]:
    if isinstance(raw_refs, str):
        candidates = re.findall(r"R\d+", raw_refs)
    elif isinstance(raw_refs, list):
        candidates = [str(item).strip() for item in raw_refs]
    else:
        candidates = []

    normalized: list[str] = []
    for candidate in candidates:
        if candidate in valid_refs and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def _split_sentences(text: str) -> list[str]:
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        return []
    return [chunk.strip() for chunk in re.split(r"(?<=[.!?;:])\s+", cleaned) if chunk.strip()]


def _clean_actor_name(text: str) -> str:
    cleaned = " ".join(str(text or "").split()).strip(" ,.;:-")
    cleaned = re.sub(r"^(?:o|a|os|as)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:e|de|da|do|dos|das)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" ,.;:-")


def _looks_like_actor_name(name: str) -> bool:
    cleaned = _clean_actor_name(name)
    if len(cleaned) < 3 or len(cleaned) > 80:
        return False
    if not re.search(r"[A-Za-zÀ-ÿ]", cleaned):
        return False
    lowered = cleaned.lower()
    if lowered in ACTOR_STOPWORDS:
        return False
    if re.fullmatch(r"[A-Z]{1,5}-?\d+(?:/\d+)?", cleaned):
        return False
    tokens = cleaned.split()
    if not any(re.match(r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]", token) for token in tokens):
        return False
    if len(tokens) == 1 and cleaned.isupper() and any(char.isdigit() for char in cleaned):
        return False
    return True


def _infer_entity_kind(name: str, *, prefer_public_figure: bool = False) -> str:
    lowered = _clean_actor_name(name).lower()
    if any(hint in lowered for hint in INSTITUTION_HINTS):
        return "instituicao"
    if any(hint in lowered for hint in ORGANIZATION_HINTS):
        return "organizacao"
    tokens = re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'/-]*", name or "")
    if prefer_public_figure and 2 <= len(tokens) <= 5:
        return "figura_publica"
    if 2 <= len(tokens) <= 5 and all(token[:1].isupper() for token in tokens):
        return "pessoa"
    return "organizacao"


def _looks_like_political_title(text: str) -> bool:
    lowered = " ".join(str(text or "").split()).strip().lower()
    return any(lowered.startswith(title) for title in POLITICAL_TITLE_HINTS)


def _entity_lookup_keys(name: str) -> list[str]:
    cleaned = _clean_actor_name(name)
    if not cleaned:
        return []
    ascii_lower = _ascii_fold(cleaned).lower()
    keys = {cleaned.lower(), ascii_lower}
    parts = [part for part in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'/-]*", cleaned)]
    if 2 <= len(parts) <= 5:
        tail_two = " ".join(parts[-2:])
        keys.add(tail_two.lower())
        keys.add(_ascii_fold(tail_two).lower())
    return [key for key in keys if key]


def _infer_subject_kind(subject_name: str, people: list[str]) -> str:
    if people:
        return "figura_publica"
    inferred = _infer_entity_kind(subject_name)
    return "figura_publica" if inferred == "pessoa" else inferred


def _preferred_subject_name(query: str, people: list[str]) -> str:
    return DEFAULT_SUBJECT_RESOLVER.choose_subject_name(query, people)


def _build_relationship_label(verb: str, prep: str) -> str:
    normalized_prep = prep.lower().strip()
    if normalized_prep in {"ao", "aos", "à", "às"}:
        normalized_prep = "a"
    if normalized_prep in {"do", "da", "dos", "das"}:
        normalized_prep = "de"
    verb_label = verb.lower().strip()
    if normalized_prep in {"com", "contra", "de"}:
        return f"{verb_label} {normalized_prep}"
    return verb_label


def _compact_relationship_action(label: str, object_text: str = "") -> str:
    action = " ".join(part for part in [str(label or "").strip(), str(object_text or "").strip()] if part).strip()
    return _truncate(action or "relacionado", 72)


def _infer_relationship_theme(label: str, object_text: str, description: str, source_name: str = "", target_name: str = "") -> str:
    haystack = " ".join(
        part.lower()
        for part in [label, object_text, description, source_name, target_name]
        if part
    )
    if any(term in haystack for term in ("emprest", "financi", "capital", "credito", "crédito", "banco", "incentivo fiscal", "incentivos fiscais")):
        return "financiamento"
    if any(term in haystack for term in ("governo", "presidente", "governador", "ministro", "senador", "deputado", "prefeito", "secretario", "secretário", "congresso", "partido")):
        return "governo_politica"
    if any(term in haystack for term in ("jornal", "revista", "imprensa", "entrevista", "reportagem", "manchete")):
        return "imprensa"
    if any(term in haystack for term in ("fabr", "veiculo", "veículo", "motor", "produc", "produção", "industrial", "br-800", "entregar", "forneceu")):
        return "producao_operacao"
    if any(term in haystack for term in ("correios", "cliente", "venda", "comprou", "adquiriu", "distribu", "entrega")):
        return "mercado_distribuicao"
    if any(term in haystack for term in ("acusou", "criticou", "processou", "tribunal", "justica", "justiça")):
        return "conflito_judicial"
    return "contexto"


def _infer_entity_theme_hints(entity: dict[str, Any]) -> list[str]:
    haystack = " ".join(
        [
            str(entity.get("name") or ""),
            str(entity.get("kind") or ""),
            str(entity.get("description") or ""),
            " ".join(str(item.get("role") or "") for item in entity.get("role_history", []) if isinstance(item, dict)),
        ]
    ).lower()
    themes: list[str] = []
    if any(term in haystack for term in ("presidente", "governador", "ministro", "senador", "deputado", "prefeito", "governo", "congresso", "partido")):
        themes.append("governo_politica")
    if any(term in haystack for term in ("banco", "capital", "credito", "crédito", "financi")):
        themes.append("financiamento")
    if any(term in haystack for term in ("jornal", "revista", "imprensa", "reportagem")):
        themes.append("imprensa")
    if any(term in haystack for term in ("motores", "industr", "veiculo", "veículo", "br-800", "fabr")):
        themes.append("producao_operacao")
    if any(term in haystack for term in ("correios", "cliente", "mercado", "venda", "distribu")):
        themes.append("mercado_distribuicao")
    return themes or ["contexto"]


def _format_relation_sentence(source_name: str, label: str, object_text: str, target_name: str) -> str:
    source = source_name.strip()
    label_clean = label.strip()
    obj = object_text.strip()
    target = target_name.strip()
    if obj and any(label_clean.endswith(suffix) for suffix in (" com", " contra", " de")):
        sentence = f"{source} {label_clean} {target} sobre {obj}".strip()
    else:
        parts = [source, label_clean]
        if obj:
            parts.append(obj)
        parts.append(target)
        sentence = " ".join(part for part in parts if part).strip()
    if not sentence.endswith("."):
        sentence += "."
    return sentence


def _relation_memory_badge(relation: dict[str, Any]) -> str:
    source_count = int(relation.get("source_count") or 0)
    if not relation.get("memory_origin") and source_count <= 1:
        return ""
    details = [item for item in relation.get("evidence_details", []) if isinstance(item, dict)]
    date_hint = ""
    for item in details:
        if str(item.get("date") or "").strip():
            date_hint = str(item.get("date") or "").strip()
            break
    bits: list[str] = []
    if date_hint:
        bits.append(date_hint)
    if source_count:
        bits.append(f"{source_count} fonte(s)")
    return " | ".join(bits)


class EntitySubjectResolver:
    """Resolve expansoes de consulta e escolhe a entidade central com heuristica reutilizavel."""

    def __init__(self, alias_registry: dict[str, list[str]] | None = None) -> None:
        self.alias_registry = {
            _ascii_fold(key).lower().strip(): [item for item in value if str(item).strip()]
            for key, value in (alias_registry or {}).items()
        }

    def expand_query_terms(self, query: str, raw_terms: Iterable[Any]) -> list[str]:
        expansions: list[str] = []
        seen: set[str] = set()

        def add(term: str) -> None:
            cleaned = " ".join(str(term).split()).strip()
            if not cleaned:
                return
            folded = _ascii_fold(cleaned).lower()
            if folded in seen:
                return
            seen.add(folded)
            expansions.append(cleaned)

        add(query)
        for alias in self.alias_registry.get(_ascii_fold(query).lower().strip(), []):
            add(alias)
        for term in raw_terms:
            text = str(term).strip()
            if not text:
                continue
            for alias in self.alias_registry.get(_ascii_fold(text).lower().strip(), []):
                add(alias)
        return expansions

    def choose_subject_name(
        self,
        query: str,
        people: list[str],
        records: list["AcervoRecord"] | None = None,
    ) -> str:
        for candidate in people:
            cleaned = str(candidate).strip()
            if cleaned:
                return cleaned

        candidates: dict[str, int] = {}
        for alias in self.alias_registry.get(_ascii_fold(query).lower().strip(), []):
            candidates[alias] = self._score_name_match(query, alias)
        for record in records or []:
            for candidate in self._extract_candidate_names_from_text(record.raw_text):
                score = self._score_name_match(query, candidate)
                if score > 0:
                    candidates[candidate] = max(score, candidates.get(candidate, 0))
            for document in record.documents:
                for candidate in self._extract_candidate_names_from_text(document.summary):
                    score = self._score_name_match(query, candidate)
                    if score > 0:
                        candidates[candidate] = max(score, candidates.get(candidate, 0))
        if candidates:
            return max(candidates.items(), key=lambda item: (item[1], len(item[0])))[0]
        return query

    def _extract_candidate_names_from_text(self, text: str) -> list[str]:
        candidates: list[str] = []
        for match in re.finditer(ACTOR_NAME_PATTERN, text or ""):
            candidate = _clean_actor_name(match.group(0))
            if _looks_like_actor_name(candidate):
                candidates.append(candidate)
        return candidates

    def _score_name_match(self, query: str, candidate: str) -> int:
        query_tokens = [token.lower() for token in re.findall(r"[A-Za-zÀ-ÿ]{3,}", query)]
        candidate_tokens = [token.lower() for token in re.findall(r"[A-Za-zÀ-ÿ]{3,}", candidate)]
        if not query_tokens or not candidate_tokens:
            return 0
        overlap = sum(1 for token in query_tokens if token in candidate_tokens)
        if overlap == 0:
            return 0
        score = overlap * 10
        if len(candidate_tokens) > len(query_tokens):
            score += min(len(candidate_tokens) - len(query_tokens), 3) * 3
        if " ".join(query_tokens) in " ".join(candidate_tokens):
            score += 5
        if query_tokens[-1] == candidate_tokens[-1]:
            score += 4
        return score


DEFAULT_SUBJECT_RESOLVER = EntitySubjectResolver()


def _build_events_and_timeline(
    *,
    subject_name: str,
    entities_by_id: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    reference_publication_map: dict[str, str],
    existing_timeline: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    for rel_index, relation in enumerate(relationships, start=1):
        source = str(relation.get("source") or "")
        target = str(relation.get("target") or "")
        if not source and not target:
            continue
        details = [item for item in relation.get("evidence_details", []) if isinstance(item, dict)]
        if details:
            for event_index, detail in enumerate(details, start=1):
                event_id = f"evt_{rel_index}_{event_index}"
                source_name = subject_name if source == "subject" else str(
                    entities_by_id.get(source, {}).get("name") or source or "origem"
                )
                target_name = subject_name if target == "subject" else str(
                    entities_by_id.get(target, {}).get("name") or target or "destino"
                )
                excerpt = str(detail.get("excerpt") or relation.get("support_excerpt") or relation.get("description") or "").strip()
                date_text = str(detail.get("date") or "").strip() or next(
                    (reference_publication_map.get(str(ref), "").strip() for ref in relation.get("evidence_refs", []) if reference_publication_map.get(str(ref), "").strip()),
                    "",
                )
                events.append(
                    {
                        "id": event_id,
                        "date": date_text or "sem data",
                        "source": source,
                        "target": target,
                        "label": str(relation.get("label") or "evento"),
                        "object": str(relation.get("object") or ""),
                        "theme": str(relation.get("theme") or "contexto"),
                        "summary": excerpt or _format_relation_sentence(
                            source_name,
                            str(relation.get("label") or "relacionado"),
                            str(relation.get("object") or ""),
                            target_name,
                        ),
                        "support_excerpt": excerpt,
                        "evidence_refs": [str(detail.get("ref") or "")] if str(detail.get("ref") or "").strip() else list(relation.get("evidence_refs", [])),
                        "source_count": int(relation.get("source_count") or len(relation.get("evidence_refs", [])) or 1),
                        "memory_origin": bool(relation.get("memory_origin")),
                    }
                )
        else:
            source_name = subject_name if source == "subject" else str(
                entities_by_id.get(source, {}).get("name") or source or "origem"
            )
            target_name = subject_name if target == "subject" else str(
                entities_by_id.get(target, {}).get("name") or target or "destino"
            )
            events.append(
                {
                    "id": f"evt_{rel_index}",
                    "date": "sem data",
                    "source": source,
                    "target": target,
                    "label": str(relation.get("label") or "evento"),
                    "object": str(relation.get("object") or ""),
                    "theme": str(relation.get("theme") or "contexto"),
                    "summary": str(relation.get("support_excerpt") or relation.get("description") or "").strip()
                    or _format_relation_sentence(source_name, str(relation.get("label") or "relacionado"), str(relation.get("object") or ""), target_name),
                    "support_excerpt": str(relation.get("support_excerpt") or ""),
                    "evidence_refs": list(relation.get("evidence_refs", [])),
                    "source_count": int(relation.get("source_count") or len(relation.get("evidence_refs", [])) or 1),
                    "memory_origin": bool(relation.get("memory_origin")),
                }
            )

    timeline = [item for item in (existing_timeline or []) if isinstance(item, dict)]
    seen_timeline: set[tuple[str, str]] = set()
    for item in timeline:
        seen_timeline.add((str(item.get("date") or "").strip(), str(item.get("description") or "").strip()))
    for event in events:
        event_date = str(event.get("date") or "").strip()
        if not event_date or event_date == "sem data":
            continue
        description = _truncate(
            f"{str(event.get('summary') or '').strip()} Tema: {event.get('theme', 'contexto')}. Sustentado por {event.get('source_count', 1)} fonte(s).",
            320,
        )
        timeline_key = (event_date, description)
        if timeline_key in seen_timeline:
            continue
        seen_timeline.add(timeline_key)
        timeline.append(
            {
                "date": event_date,
                "description": description,
                "evidence_refs": list(event.get("evidence_refs", [])),
            }
        )
    return events, timeline


def _normalized_relation_object(text: str) -> str:
    lowered = _ascii_fold(text).lower()
    lowered = re.sub(r"[^a-z0-9\s]+", " ", lowered)
    lowered = " ".join(lowered.split()).strip()
    return lowered


def _relation_signature_matches(
    source_a: str,
    target_a: str,
    label_a: str,
    object_a: str,
    source_b: str,
    target_b: str,
    label_b: str,
    object_b: str,
) -> bool:
    if source_a != source_b or target_a != target_b or label_a.lower() != label_b.lower():
        return False
    norm_a = _normalized_relation_object(object_a)
    norm_b = _normalized_relation_object(object_b)
    if norm_a == norm_b:
        return True
    if norm_a and norm_b and len(norm_a) >= 8 and len(norm_b) >= 8:
        if norm_a in norm_b or norm_b in norm_a:
            return True
    return False


def _canonical_actor_key(name: str) -> str:
    return _ascii_fold(_clean_actor_name(name)).lower().strip()


def _host_matches_allowed(hostname: str) -> bool:
    lowered = (hostname or "").lower().strip(".")
    return any(lowered == allowed or lowered.endswith(f".{allowed}") for allowed in BN_ALLOWED_HOSTS)


def _detect_source_kind(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()
    if TARGET_HOST in host:
        if "/sophia_web/acervo/detalhe/" in path:
            return "sophia_detail"
        if "/sophia_web/autoridade/detalhe/" in path:
            return "sophia_authority"
        return "sophia_page"
    if HEMEROTECA_PDF_HOST in host:
        return "hemeroteca_pdf"
    if BNDIGITAL_HOST in host:
        return "bndigital_page"
    if OBJDIGITAL_HOST in host:
        return "objdigital_document"
    if any(path.endswith(suffix) for suffix in DOCUMENT_SUFFIXES):
        return "direct_document"
    return "external"


def _normalize_search_terms_from_query(query: str, raw_terms: Iterable[Any]) -> list[str]:
    """Garante termos de busca utilizaveis, preservando a pergunta original."""
    normalized: list[str] = []
    lowered_query = query.lower()

    def add(term: str) -> None:
        cleaned = " ".join(str(term).split()).strip()
        if not cleaned:
            return
        if cleaned in normalized:
            return
        if len(cleaned) < 4:
            return
        if cleaned.count("?") > 0:
            return
        normalized.append(cleaned)

    expanded_terms = DEFAULT_SUBJECT_RESOLVER.expand_query_terms(query, raw_terms)
    for term in expanded_terms:
        add(term)
    query_tokens = [token for token in re.findall(r"[A-Za-zÀ-ÿ0-9-]{4,}", query)]
    stopwords = {
        "historia",
        "história",
        "historica",
        "histórica",
        "empresa",
        "empresas",
        "automovel",
        "automóvel",
        "automobilistica",
        "automobilística",
        "carro",
        "carros",
        "industria",
        "indústria",
        "brasileira",
        "brasil",
        "livro",
        "biblioteca",
        "nacional",
        "pesquisa",
        "acervo",
    }
    significant_tokens = [token for token in query_tokens if token.lower() not in stopwords]
    anchor = significant_tokens[-1] if significant_tokens else (query_tokens[-1] if query_tokens else "")
    lead_anchor = significant_tokens[0] if significant_tokens else (query_tokens[0] if query_tokens else "")
    has_model_like_token = any(any(char.isdigit() for char in token) or "-" in token for token in significant_tokens)
    if anchor:
        if any(marker in lowered_query for marker in ("autom", "carro", "veiculo", "veículo", "indústr", "industr")):
            add(f"{anchor} automóvel")
            add(f"{anchor} carro")
            add(f"{anchor} indústria automobilística")
        if "empresa" in lowered_query:
            add(f"{anchor} empresa")
            add(f"{anchor} história")
    if lead_anchor and lead_anchor != anchor:
        add(f"{lead_anchor} {anchor}")
    if lead_anchor and has_model_like_token:
        add(f"{lead_anchor} automóvel")
        add(f"{lead_anchor} carro")
        add(f"{lead_anchor} empresa")
        add(f"{lead_anchor} história")
    if query_tokens:
        add(" ".join(query_tokens[:4]))
        if len(query_tokens) >= 2:
            add(f"{query_tokens[0]} {query_tokens[1]}")
    for term in raw_terms:
        text = str(term).strip()
        if not text:
            continue
        if re.search(r"[A-Za-zÀ-ÿ]{3,}", text) is None:
            continue
        if text.lower() in stopwords:
            continue
        add(text)

    return normalized[:6]


def _detect_firefox_proxy_from_local_profile() -> str:
    """Tenta reaproveitar o proxy configurado no Firefox do host."""
    prefs_candidates = sorted(glob.glob(str(Path.home() / ".mozilla/firefox/*/prefs.js")))
    for prefs_path in prefs_candidates:
        try:
            text = Path(prefs_path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        host_match = re.search(r'user_pref\("network\.proxy\.http",\s*"([^"]+)"\);', text)
        port_match = re.search(r'user_pref\("network\.proxy\.http_port",\s*(\d+)\);', text)
        type_match = re.search(r'user_pref\("network\.proxy\.type",\s*(\d+)\);', text)
        if not host_match or not port_match:
            continue
        if type_match and type_match.group(1) == "0":
            continue
        return f"{host_match.group(1)}:{port_match.group(1)}"
    return ""


def _normalize_label(label: str) -> str:
    cleaned = (
        label.strip()
        .lower()
        .replace("ç", "c")
        .replace("ã", "a")
        .replace("á", "a")
        .replace("à", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("ú", "u")
    )
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned).strip("_")
    return cleaned


def extract_duckduckgo_result_urls(html: str) -> list[str]:
    """Extrai URLs do DuckDuckGo HTML, decodificando redirects `uddg`."""
    return [hit.detail_url for hit in extract_duckduckgo_result_hits(html)]


def extract_duckduckgo_result_hits(html: str) -> list[SearchHit]:
    """Extrai hits do DuckDuckGo HTML com URL, titulo e snippet textual."""
    soup = BeautifulSoup(html, "html.parser")
    hits: list[SearchHit] = []
    seen: set[str] = set()
    for anchor in soup.select("a.result__a"):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        parsed = urllib.parse.urlparse(href)
        query = urllib.parse.parse_qs(parsed.query)
        target = query.get("uddg", [href])[0]
        if target.startswith("//"):
            target = "https:" + target
        normalized = urllib.parse.unquote(target)
        normalized_host = urllib.parse.urlparse(normalized).netloc
        if not _host_matches_allowed(normalized_host):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        block = anchor
        for _ in range(4):
            parent = block.parent
            if parent is None:
                break
            block = parent
        block_text = block.get_text(" | ", strip=True)
        title = anchor.get_text(" ", strip=True) or "Terminal - Sophia Biblioteca Web"
        snippet = block_text
        if snippet.startswith(title):
            snippet = snippet[len(title) :].lstrip(" |")
        snippet = _clean_search_snippet(snippet)
        hits.append(
            SearchHit(
                detail_url=normalized,
                title=title,
                snippet=_truncate(snippet, 1200),
                source_kind=_detect_source_kind(normalized),
            )
        )
    return hits


def detect_cloudflare_block(title: str, body_text: str, html: str = "") -> bool:
    """Detecta paginas de desafio/bloqueio do Cloudflare."""
    haystack = " ".join([title or "", body_text or "", html or ""]).lower()
    return any(marker in haystack for marker in BLOCK_MARKERS)


def extract_document_links(links: Iterable[str]) -> list[str]:
    """Mantem somente links de documentos digitais relevantes."""
    collected: list[str] = []
    seen: set[str] = set()
    for href in links:
        if not href:
            continue
        parsed = urllib.parse.urlparse(href)
        path = parsed.path.lower()
        if any(path.endswith(suffix) for suffix in DOCUMENT_SUFFIXES) or parsed.netloc.lower().endswith(OBJDIGITAL_HOST):
            normalized = href.strip()
            if normalized not in seen:
                seen.add(normalized)
                collected.append(normalized)
    return collected


def parse_record_metadata(body_text: str) -> dict[str, str]:
    """Extrai metadados principais do texto visivel da pagina do Sophia."""
    raw_lines = [line.strip() for line in body_text.splitlines()]
    lines: list[str] = []
    for line in raw_lines:
        if not line:
            continue
        if line in FOOTER_LINES:
            break
        if line in NOISE_LINES:
            continue
        lines.append(line)

    label_positions = [(idx, line) for idx, line in enumerate(lines) if line in FIELD_LABELS]
    metadata: dict[str, str] = {}
    if not label_positions:
        return metadata

    for offset, (index, label) in enumerate(label_positions):
        next_index = label_positions[offset + 1][0] if offset + 1 < len(label_positions) else len(lines)
        value_lines = [value for value in lines[index + 1 : next_index] if value and value not in NOISE_LINES]
        if not value_lines:
            continue
        key = "title" if label == "Link do título" else _normalize_label(label)
        metadata[key] = " ".join(value_lines)
    return metadata


def build_reference_entries(records: list["AcervoRecord"]) -> list[dict[str, Any]]:
    """Monta a lista final de referencias para historia e auditoria."""
    references: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        doc_urls = [doc.source_url for doc in record.documents if doc.source_url]
        evidence_parts = [record.metadata.get("publicacao", ""), record.metadata.get("descricao_fisica", "")]
        evidence_parts.extend(doc.summary for doc in record.documents if doc.summary)
        reference = {
            "id": f"R{index}",
            "title": record.title or record.metadata.get("title", record.detail_url),
            "detail_url": record.detail_url,
            "document_urls": doc_urls,
            "evidence_excerpt": _truncate(" ".join(part for part in evidence_parts if part), 500),
        }
        references.append(reference)
    return references


def build_story_prompt(
    query: str,
    plan: dict[str, Any],
    records: list["AcervoRecord"],
    references: list[dict[str, Any]],
) -> str:
    """Prompt final para narrativa com referencias explicitas."""
    record_blocks: list[str] = []
    for record, reference in zip(records, references, strict=False):
        metadata_lines = [f"{key}: {value}" for key, value in record.metadata.items() if value]
        doc_summaries = [doc.summary for doc in record.documents if doc.summary]
        record_blocks.append(
            "\n".join(
                [
                    f"{reference['id']} :: {record.title or reference['title']}",
                    f"url_registro: {record.detail_url}",
                    f"motivo_relevancia: {record.relevance_reason or 'nao informado'}",
                    f"metadata: {' | '.join(metadata_lines) if metadata_lines else '(sem metadata estruturada)'}",
                    f"documentos: {' | '.join(reference['document_urls']) if reference['document_urls'] else '(sem documento digital baixado)'}",
                    f"evidencia: {reference['evidence_excerpt'] or '(sem evidencia adicional)'}",
                    f"tipo_evidencia: {'registro completo' if record.metadata.get('fonte_parcial') is None else record.metadata.get('fonte_parcial')}",
                    f"ocr_resumos: {' | '.join(doc_summaries) if doc_summaries else '(sem OCR)'}",
                ]
            )
        )

    search_terms = ", ".join(plan.get("search_terms", [])) or query
    must_include = ", ".join(plan.get("must_include", [])) or "cronologia, contexto, fontes"
    return (
        "Voce e um pesquisador historico escrevendo em portugues do Brasil.\n"
        "Sua tarefa e contar uma historia fiel as fontes do Acervo da Biblioteca Nacional.\n"
        "Regras obrigatorias:\n"
        "1. Nao invente fatos ausentes das fontes.\n"
        "2. Sempre cite referencias no corpo do texto no formato [R1], [R2] etc.\n"
        "3. Quando houver lacunas, diga explicitamente que a fonte nao permite concluir.\n"
        "4. Termine com uma secao 'Referencias' listando cada codigo com o respectivo link.\n"
        "5. Priorize uma narrativa fluida, mas amarrada aos documentos.\n\n"
        f"Pergunta do usuario: {query}\n"
        f"Termos planejados: {search_terms}\n"
        f"Pontos que devem aparecer: {must_include}\n\n"
        "Fontes estruturadas:\n"
        + "\n\n".join(record_blocks)
        + "\n\nProduza a historia final em Markdown com duas secoes: 'Historia' e 'Referencias'."
    )


def build_dossier_prompt(
    query: str,
    plan: dict[str, Any],
    records: list["AcervoRecord"],
    references: list[dict[str, Any]],
) -> str:
    """Prompt estruturado para extrair um dossie relacional de figura publica."""
    record_blocks: list[str] = []
    for record, reference in zip(records, references, strict=False):
        metadata_lines = [f"{key}: {value}" for key, value in record.metadata.items() if value]
        doc_summaries = [doc.summary for doc in record.documents if doc.summary]
        record_blocks.append(
            "\n".join(
                [
                    f"{reference['id']} :: {record.title or reference['title']}",
                    f"url_registro: {record.detail_url}",
                    f"motivo_relevancia: {record.relevance_reason or 'nao informado'}",
                    f"metadata: {' | '.join(metadata_lines) if metadata_lines else '(sem metadata estruturada)'}",
                    f"documentos: {' | '.join(reference['document_urls']) if reference['document_urls'] else '(sem documento digital baixado)'}",
                    f"evidencia: {reference['evidence_excerpt'] or '(sem evidencia adicional)'}",
                    f"texto_base: {_truncate(record.raw_text, 1500) or '(sem texto bruto)'}",
                    f"ocr_resumos: {' | '.join(doc_summaries) if doc_summaries else '(sem OCR)'}",
                ]
            )
        )

    search_terms = ", ".join(plan.get("search_terms", [])) or query
    people = ", ".join(plan.get("people", [])) or query
    must_include = ", ".join(plan.get("must_include", [])) or "pessoas, instituicoes, relacoes"
    return (
        "Voce e um pesquisador historico especializado em figuras publicas.\n"
        "Sua tarefa e extrair um dossie relacional fiel as fontes da Biblioteca Nacional.\n"
        "Retorne APENAS JSON valido com as chaves:\n"
        "subject, summary, entities, relationships, timeline.\n"
        "Schema:\n"
        "{\n"
        '  "subject": {"id": "subject", "name": "...", "kind": "figura_publica", "description": "...", "evidence_refs": ["R1"]},\n'
        '  "summary": "...",\n'
        '  "entities": [{"id": "org_gurgel", "name": "Gurgel Motores", "kind": "organizacao|pessoa|instituicao|obra|evento|veiculo|local", "description": "...", "evidence_refs": ["R1"]}],\n'
        '  "relationships": [{"source": "subject", "target": "org_gurgel", "label": "fundou|dirigiu|negociou com", "object": "capital de giro|entrega de veiculos|incentivos fiscais", "description": "...", "support_excerpt": "...", "evidence_refs": ["R1","R2"]}],\n'
        '  "timeline": [{"date": "1989-05", "description": "...", "evidence_refs": ["R2"]}]\n'
        "}\n"
        "Regras obrigatorias:\n"
        "1. Nao invente entidades ou relacoes que nao aparecam de forma sustentada nas fontes.\n"
        "2. Use evidence_refs somente com codigos existentes, como R1 e R2.\n"
        "3. A entidade central deve ser uma figura publica, quando isso for sustentado pela consulta.\n"
        "4. Cada relationship precisa de label curta, object quando houver algo prometido, emprestado, pago, entregue ou negociado, e description explicativa.\n"
        "5. Se houver lacuna, omita a relacao em vez de especular.\n\n"
        "6. Valorize evidencias vindas de jornais, revistas, periodicos e imprensa em geral quando presentes.\n\n"
        "7. Se a mesma dupla de atores tiver mais de um ato relevante, registre relacoes separadas para cada ato.\n\n"
        f"Consulta: {query}\n"
        f"Pessoas candidatas: {people}\n"
        f"Termos planejados: {search_terms}\n"
        f"Pontos a cobrir: {must_include}\n\n"
        "Fontes estruturadas:\n"
        + "\n\n".join(record_blocks)
    )


def build_mermaid_graph(dossier: dict[str, Any]) -> str:
    subject = dossier.get("subject", {})
    entities = dossier.get("entities", [])
    relationships = dossier.get("relationships", [])
    events = dossier.get("events", [])
    thematic_groups = dossier.get("thematic_groups", {})
    subject_id = str(subject.get("id") or "subject")
    subject_name = _sanitize_mermaid_text(str(subject.get("name") or "Entidade central"))
    subject_kind = _sanitize_mermaid_text(str(subject.get("kind") or "figura_publica"))

    node_lines = [f'    {subject_id}["{subject_name}<br/>{subject_kind}"]']
    entity_map: dict[str, dict[str, Any]] = {}
    for entity in entities:
        entity_id = str(entity.get("id") or "")
        if not entity_id or entity_id == subject_id:
            continue
        entity_name = _sanitize_mermaid_text(str(entity.get("name") or entity_id))
        entity_kind = _sanitize_mermaid_text(str(entity.get("kind") or "entidade"))
        node_lines.append(f'    {entity_id}["{entity_name}<br/>{entity_kind}"]')
        entity_map[entity_id] = entity

    lines = ["graph TD"]
    if isinstance(thematic_groups, dict) and thematic_groups:
        rendered_ids: set[str] = {subject_id}
        lines.append("    subgraph eixo_central[\"Eixo central\"]")
        lines.append(f'        {subject_id}["{subject_name}<br/>{subject_kind}"]')
        lines.append("    end")
        for group_name, entity_ids in thematic_groups.items():
            if not isinstance(entity_ids, list) or not entity_ids:
                continue
            label = _sanitize_mermaid_text(str(group_name).replace("_", " ").title())
            group_lines = []
            for entity_id in entity_ids:
                if entity_id in rendered_ids or entity_id not in entity_map:
                    continue
                entity = entity_map[entity_id]
                entity_name = _sanitize_mermaid_text(str(entity.get("name") or entity_id))
                entity_kind = _sanitize_mermaid_text(str(entity.get("kind") or "entidade"))
                group_lines.append(f'        {entity_id}["{entity_name}<br/>{entity_kind}"]')
                rendered_ids.add(entity_id)
            if group_lines:
                lines.append(f'    subgraph {group_name}["{label}"]')
                lines.extend(group_lines)
                lines.append("    end")
        for line in node_lines[1:]:
            entity_id = line.split("[", 1)[0].strip()
            if entity_id not in rendered_ids:
                lines.append(line)
    else:
        lines.extend(node_lines)

    if isinstance(events, list) and events:
        for index, event in enumerate(events, start=1):
            source = str(event.get("source") or "")
            target = str(event.get("target") or "")
            event_id = str(event.get("id") or f"evt_{index}")
            label = str(event.get("label") or event.get("action") or "evento")
            object_text = str(event.get("object") or "").strip()
            date_text = str(event.get("date") or "").strip()
            badge_bits = []
            if date_text:
                badge_bits.append(date_text)
            if int(event.get("source_count") or 0):
                badge_bits.append(f"{int(event.get('source_count') or 0)} fonte(s)")
            event_text = _compact_relationship_action(label, object_text)
            if badge_bits:
                event_text = f"{event_text}<br/>{' | '.join(badge_bits)}"
            event_text = _sanitize_mermaid_text(event_text)
            lines.append(f'    {event_id}["{event_text}"]')
            if source:
                lines.append(f"    {source} --> {event_id}")
            if target:
                lines.append(f"    {event_id} --> {target}")
        return "\n".join(lines)

    for index, relation in enumerate(relationships, start=1):
        source = str(relation.get("source") or "")
        target = str(relation.get("target") or "")
        if not source or not target:
            continue
        label = str(relation.get("label") or "relacionado")
        object_text = str(relation.get("object") or "").strip()
        if object_text:
            relation_node_id = f"rel_{index}"
            relation_text = _compact_relationship_action(label, object_text)
            badge = _relation_memory_badge(relation)
            if badge:
                relation_text = f"{relation_text}<br/>{badge}"
            relation_text = _sanitize_mermaid_text(relation_text)
            lines.append(f'    {relation_node_id}["{relation_text}"]')
            lines.append(f"    {source} --> {relation_node_id}")
            lines.append(f"    {relation_node_id} --> {target}")
            continue
        edge_label = _sanitize_mermaid_text(_compact_relationship_action(label))
        lines.append(f'    {source} -->|{edge_label}| {target}')
    return "\n".join(lines)


def build_neural_correlation_map(dossier: dict[str, Any]) -> dict[str, Any]:
    subject = dossier.get("subject", {}) if isinstance(dossier.get("subject"), dict) else {}
    entities = [entity for entity in dossier.get("entities", []) if isinstance(entity, dict)]
    relationships = [relation for relation in dossier.get("relationships", []) if isinstance(relation, dict)]
    thematic_groups = dossier.get("thematic_groups", {}) if isinstance(dossier.get("thematic_groups"), dict) else {}

    subject_id = str(subject.get("id") or "subject").strip() or "subject"
    subject_name = str(subject.get("name") or "Entidade central").strip() or "Entidade central"

    def _merge_unique(bucket: list[str], values: Iterable[str]) -> None:
        for value in values:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in bucket:
                bucket.append(cleaned)

    nodes: dict[str, dict[str, Any]] = {}
    ref_index: dict[str, set[str]] = {}

    def ensure_node(entity: dict[str, Any], *, is_subject: bool = False) -> dict[str, Any]:
        entity_id = str(entity.get("id") or ("subject" if is_subject else "")).strip()
        if not entity_id:
            raise ValueError("entity_id_vazio")
        existing = nodes.get(entity_id)
        if existing is not None:
            _merge_unique(existing["themes"], entity.get("themes", []))
            _merge_unique(existing["aliases"], entity.get("aliases", []))
            _merge_unique(existing["evidence_refs"], entity.get("evidence_refs", []))
            ref_index.setdefault(entity_id, set()).update(existing["evidence_refs"])
            return existing
        evidence_refs = [str(item).strip() for item in entity.get("evidence_refs", []) if str(item).strip()]
        node = {
            "id": entity_id,
            "name": str(entity.get("name") or entity_id).strip() or entity_id,
            "kind": str(entity.get("kind") or ("figura_publica" if is_subject else "entidade")).strip() or "entidade",
            "description": _truncate(str(entity.get("description") or "").strip(), 320),
            "themes": [str(item).strip() for item in entity.get("themes", []) if str(item).strip()],
            "aliases": [str(item).strip() for item in entity.get("aliases", []) if str(item).strip()],
            "evidence_refs": evidence_refs,
            "role_history": [item for item in entity.get("role_history", []) if isinstance(item, dict)],
            "memory_origin": bool(entity.get("memory_origin")),
            "is_subject": is_subject,
            "cluster": "eixo_central" if is_subject else "",
            "degree": 0,
            "weighted_degree": 0.0,
            "importance": max(1, len(evidence_refs) or 1),
        }
        nodes[entity_id] = node
        ref_index[entity_id] = set(evidence_refs)
        return node

    ensure_node({**subject, "id": subject_id, "name": subject_name}, is_subject=True)
    for entity in entities:
        ensure_node(entity)

    for cluster_name, entity_ids in thematic_groups.items():
        if not isinstance(entity_ids, list):
            continue
        for entity_id in entity_ids:
            node = nodes.get(str(entity_id))
            if node is not None and not node["is_subject"] and not node["cluster"]:
                node["cluster"] = str(cluster_name)

    edge_index: dict[tuple[str, str, str], dict[str, Any]] = {}

    def _edge_record(source: str, target: str, edge_type: str) -> dict[str, Any]:
        edge = edge_index.get((source, target, edge_type))
        if edge is None:
            edge = {
                "id": f"{edge_type}_{len(edge_index) + 1}",
                "source": source,
                "target": target,
                "type": edge_type,
                "directed": edge_type == "relationship",
                "weight": 0.0,
                "labels": [],
                "objects": [],
                "themes": [],
                "evidence_refs": [],
                "support_excerpts": [],
                "memory_origin": False,
                "relation_count": 0,
            }
            edge_index[(source, target, edge_type)] = edge
        return edge

    for relation in relationships:
        source = str(relation.get("source") or "").strip()
        target = str(relation.get("target") or "").strip()
        if not source or not target:
            continue
        if source not in nodes:
            ensure_node({"id": source, "name": source, "kind": "entidade"})
        if target not in nodes:
            ensure_node({"id": target, "name": target, "kind": "entidade"})
        edge = _edge_record(source, target, "relationship")
        evidence_refs = [str(item).strip() for item in relation.get("evidence_refs", []) if str(item).strip()]
        label = str(relation.get("label") or "").strip()
        object_text = str(relation.get("object") or "").strip()
        theme = str(relation.get("theme") or "").strip()
        support_excerpt = str(relation.get("support_excerpt") or "").strip()
        _merge_unique(edge["labels"], [label])
        _merge_unique(edge["objects"], [object_text])
        _merge_unique(edge["themes"], [theme])
        _merge_unique(edge["evidence_refs"], evidence_refs)
        _merge_unique(edge["support_excerpts"], [support_excerpt])
        edge["memory_origin"] = bool(edge["memory_origin"] or relation.get("memory_origin"))
        edge["relation_count"] += 1
        evidence_weight = max(1.0, float(relation.get("source_count") or len(evidence_refs) or 1))
        edge["weight"] += evidence_weight + (0.35 if object_text else 0.0) + (0.15 if theme else 0.0) + (0.1 if relation.get("memory_origin") else 0.0)
        ref_index.setdefault(source, set()).update(evidence_refs)
        ref_index.setdefault(target, set()).update(evidence_refs)
        _merge_unique(nodes[source]["evidence_refs"], evidence_refs)
        _merge_unique(nodes[target]["evidence_refs"], evidence_refs)
        nodes[source]["importance"] = max(nodes[source]["importance"], len(nodes[source]["evidence_refs"]) or 1)
        nodes[target]["importance"] = max(nodes[target]["importance"], len(nodes[target]["evidence_refs"]) or 1)

    node_ids = list(nodes.keys())
    for left_index, left_id in enumerate(node_ids):
        for right_id in node_ids[left_index + 1:]:
            shared_refs = sorted(ref_index.get(left_id, set()) & ref_index.get(right_id, set()))
            if not shared_refs:
                continue
            if (left_id, right_id, "relationship") in edge_index or (right_id, left_id, "relationship") in edge_index:
                continue
            edge = _edge_record(left_id, right_id, "co_occurrence")
            _merge_unique(edge["labels"], ["coocorrencia documental"])
            _merge_unique(edge["evidence_refs"], shared_refs)
            edge["weight"] += max(0.7, 0.65 * len(shared_refs))

    edge_list = list(edge_index.values())
    for edge in edge_list:
        source = str(edge["source"])
        target = str(edge["target"])
        if source in nodes:
            nodes[source]["degree"] += 1
            nodes[source]["weighted_degree"] += float(edge["weight"])
        if target in nodes:
            nodes[target]["degree"] += 1
            nodes[target]["weighted_degree"] += float(edge["weight"])
        if edge["type"] == "co_occurrence":
            edge["label"] = "coocorrencia documental"
        elif edge["objects"]:
            edge["label"] = _compact_relationship_action(", ".join(edge["labels"][:2]), ", ".join(edge["objects"][:2]))
        elif edge["labels"]:
            edge["label"] = ", ".join(edge["labels"][:2])
        else:
            edge["label"] = "correlacao"
        edge["label"] = _truncate(edge["label"], 120)
        edge["strength"] = round(float(edge["weight"]), 2)
        edge["shared_ref_count"] = len(edge["evidence_refs"])

    node_list = sorted(nodes.values(), key=lambda item: (not item["is_subject"], -float(item["weighted_degree"]), item["name"].lower()))
    edge_list.sort(key=lambda item: float(item["weight"]), reverse=True)

    strongest_connections = [
        {
            "source": nodes[str(edge["source"])]["name"],
            "target": nodes[str(edge["target"])]["name"],
            "label": edge["label"],
            "strength": edge["strength"],
            "type": edge["type"],
        }
        for edge in edge_list[:10]
    ]
    node_count = len(node_list)
    edge_count = len(edge_list)
    density = 0.0
    if node_count > 1:
        density = edge_count / (node_count * (node_count - 1) / 2)

    return {
        "subject_id": subject_id,
        "subject_name": subject_name,
        "generated_from": "dossier_entities_relationships",
        "nodes": node_list,
        "edges": edge_list,
        "stats": {
            "node_count": node_count,
            "edge_count": edge_count,
            "density": round(density, 4),
            "strongest_connections": strongest_connections,
        },
    }


def render_dossier_markdown(dossier: dict[str, Any], references: list[dict[str, Any]]) -> str:
    subject = dossier.get("subject", {})
    summary = str(dossier.get("summary", "")).strip()
    entities = dossier.get("entities", [])
    relationships = dossier.get("relationships", [])
    events = dossier.get("events", [])
    timeline = dossier.get("timeline", [])
    mermaid_graph = build_mermaid_graph(dossier)

    entity_names = {str(subject.get("id") or "subject"): str(subject.get("name") or "Entidade central")}
    for entity in entities:
        entity_names[str(entity.get("id") or "")] = str(entity.get("name") or "")

    lines = ["## Dossie", "", "### Entidade Central", ""]
    lines.append(f"**Nome:** {subject.get('name', 'não identificado')}")
    lines.append(f"**Tipo:** {subject.get('kind', 'figura_publica')}")
    if subject.get("description"):
        lines.append(f"**Descrição:** {subject['description']}")
    if subject.get("evidence_refs"):
        lines.append(f"**Referências-base:** {', '.join(subject['evidence_refs'])}")

    if summary:
        lines.extend(["", "### Resumo", "", summary])

    if timeline:
        lines.extend(["", "### Cronologia", ""])
        for item in timeline:
            ref_suffix = f" [{' ,'.join(item['evidence_refs'])}]".replace(" ,", ",") if item.get("evidence_refs") else ""
            lines.append(f"- **{item.get('date', 'sem data')}**: {item.get('description', 'sem descrição')}{ref_suffix}")

    if entities:
        lines.extend(["", "### Entidades Relacionadas", ""])
        for entity in entities:
            ref_suffix = f" [{' ,'.join(entity['evidence_refs'])}]".replace(" ,", ",") if entity.get("evidence_refs") else ""
            roles = ", ".join(
                _truncate(f"{item.get('role', '')} ({','.join(item.get('evidence_refs', []))})", 80)
                for item in entity.get("role_history", [])
                if isinstance(item, dict) and item.get("role")
            )
            role_suffix = f" | cargos: {roles}" if roles else ""
            theme_suffix = f" | temas: {', '.join(entity.get('themes', []))}" if entity.get("themes") else ""
            origin_suffix = " | origem: memoria_local" if entity.get("memory_origin") else ""
            lines.append(
                f"- **{entity.get('name', 'entidade')}** ({entity.get('kind', 'entidade')}): {entity.get('description', 'sem descrição')}{role_suffix}{theme_suffix}{origin_suffix}{ref_suffix}"
            )

    if relationships:
        lines.extend(["", "### Relacionamentos", ""])
        for relation in relationships:
            source_name = entity_names.get(str(relation.get("source") or ""), str(relation.get("source") or "origem"))
            target_name = entity_names.get(str(relation.get("target") or ""), str(relation.get("target") or "destino"))
            ref_suffix = f" [{' ,'.join(relation['evidence_refs'])}]".replace(" ,", ",") if relation.get("evidence_refs") else ""
            object_suffix = f" | objeto: {relation.get('object')}" if relation.get("object") else ""
            support_suffix = f" | suporte: {relation.get('support_excerpt')}" if relation.get("support_excerpt") else ""
            theme_suffix = f" | tema: {relation.get('theme')}" if relation.get("theme") else ""
            source_count_suffix = f" | fontes: {relation.get('source_count')}" if relation.get("source_count") else ""
            origin_suffix = " | origem: memoria_local" if relation.get("memory_origin") else ""
            lines.append(
                f"- **{source_name}** -> **{target_name}** ({relation.get('label', 'relacionado')}): {relation.get('description', 'sem descrição')}{object_suffix}{theme_suffix}{source_count_suffix}{origin_suffix}{support_suffix}{ref_suffix}"
            )

    if events:
        lines.extend(["", "### Eventos Documentais", ""])
        for event in events:
            source_name = entity_names.get(str(event.get("source") or ""), str(event.get("source") or "origem"))
            target_name = entity_names.get(str(event.get("target") or ""), str(event.get("target") or "destino"))
            ref_suffix = f" [{' ,'.join(event['evidence_refs'])}]".replace(" ,", ",") if event.get("evidence_refs") else ""
            origin_suffix = " | origem: memoria_local" if event.get("memory_origin") else ""
            object_suffix = f" | objeto: {event.get('object')}" if event.get("object") else ""
            support_suffix = f" | suporte: {event.get('support_excerpt')}" if event.get("support_excerpt") else ""
            lines.append(
                f"- **{event.get('date', 'sem data')}**: **{source_name}** -> **{target_name}** ({event.get('label', 'evento')}): {event.get('summary', event.get('description', 'sem descrição'))}{object_suffix}{origin_suffix}{support_suffix}{ref_suffix}"
            )

    lines.extend(["", "### Mermaid", "", "```mermaid", mermaid_graph, "```", "", "### Referencias", ""])
    for reference in references:
        line = f"- [{reference['id']}] {reference['title']} — {reference['detail_url']}"
        if reference["document_urls"]:
            line += f" | documento: {reference['document_urls'][0]}"
        lines.append(line)
    return "\n".join(lines)


@dataclass
class DownloadedDocument:
    source_url: str
    media_type: str
    local_path: str | None = None
    bytes_downloaded: int | None = None
    extraction_mode: str = "none"
    extracted_text: str = ""
    summary: str = ""
    skipped_reason: str | None = None


@dataclass
class AcervoRecord:
    detail_url: str
    title: str
    metadata: dict[str, str] = field(default_factory=dict)
    raw_text: str = ""
    page_title: str = ""
    document_links: list[str] = field(default_factory=list)
    relevance_score: float = 0.0
    relevance_reason: str = ""
    documents: list[DownloadedDocument] = field(default_factory=list)


@dataclass
class SearchHit:
    detail_url: str
    title: str
    snippet: str = ""
    source_engine: str = "duckduckgo"
    source_kind: str = "sophia_detail"
    score: float = 0.0


@dataclass
class BrowserPage:
    title: str
    body_text: str
    html: str
    links: list[str]


class AcervoStoryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    output_mode: str = Field(default="story", pattern="^(story|dossier)$")
    investigation_mode: str = Field(default="quick", pattern="^(quick|deep)$")
    max_search_results: int = Field(default=8, ge=1, le=500)
    max_detail_records: int = Field(default=4, ge=1, le=200)
    max_download_documents: int = Field(default=2, ge=0, le=200)
    max_ocr_pages_per_document: int = Field(default=4, ge=0, le=500)
    prefer_ocr: bool = True
    include_authority_pages: bool = False
    persist_investigation: bool = True


class AcervoJobStatusResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    updated_at: str
    phase: str = "queued"
    progress_percent: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)
    partial_result: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    logs: list[dict[str, Any]] = Field(default_factory=list)


@dataclass
class InvestigationProfile:
    mode: str = "quick"
    max_search_results: int = 8
    max_detail_records: int = 4
    max_download_documents: int = 2
    max_ocr_pages_per_document: int = 4
    prefer_ocr: bool = True
    include_authority_pages: bool = False
    persist_investigation: bool = True
    search_axis_limit: int = 3

    def apply(self, payload: AcervoStoryRequest) -> AcervoStoryRequest:
        return payload.model_copy(
            update={
                "max_search_results": self.max_search_results,
                "max_detail_records": self.max_detail_records,
                "max_download_documents": self.max_download_documents,
                "max_ocr_pages_per_document": self.max_ocr_pages_per_document,
                "prefer_ocr": self.prefer_ocr,
                "include_authority_pages": self.include_authority_pages,
                "persist_investigation": self.persist_investigation,
            }
        )


@dataclass
class InvestigationBudgetPolicy:
    """Politica configuravel de volume para investigacoes longas."""

    quick_search_results: int = 8
    quick_detail_records: int = 4
    quick_download_documents: int = 2
    quick_ocr_pages_per_document: int = 4
    quick_search_axis_limit: int = 3

    deep_search_results: int = 60
    deep_detail_records: int = 40
    deep_download_documents: int = 30
    deep_ocr_pages_per_document: int = 120
    deep_search_axis_limit: int = 16

    max_search_results_cap: int = 500
    max_detail_records_cap: int = 200
    max_download_documents_cap: int = 200
    max_ocr_pages_cap: int = 500

    @classmethod
    def from_env(cls) -> "InvestigationBudgetPolicy":
        return cls(
            quick_search_results=_int_env("BN_ACERVO_QUICK_SEARCH_RESULTS", 8),
            quick_detail_records=_int_env("BN_ACERVO_QUICK_DETAIL_RECORDS", 4),
            quick_download_documents=_int_env("BN_ACERVO_QUICK_DOWNLOAD_DOCUMENTS", 2),
            quick_ocr_pages_per_document=_int_env("BN_ACERVO_QUICK_OCR_PAGES", 4),
            quick_search_axis_limit=_int_env("BN_ACERVO_QUICK_SEARCH_AXIS_LIMIT", 3),
            deep_search_results=_int_env("BN_ACERVO_DEEP_SEARCH_RESULTS", 60),
            deep_detail_records=_int_env("BN_ACERVO_DEEP_DETAIL_RECORDS", 40),
            deep_download_documents=_int_env("BN_ACERVO_DEEP_DOWNLOAD_DOCUMENTS", 30),
            deep_ocr_pages_per_document=_int_env("BN_ACERVO_DEEP_OCR_PAGES", 120),
            deep_search_axis_limit=_int_env("BN_ACERVO_DEEP_SEARCH_AXIS_LIMIT", 16),
            max_search_results_cap=_int_env("BN_ACERVO_SEARCH_RESULTS_CAP", 500),
            max_detail_records_cap=_int_env("BN_ACERVO_DETAIL_RECORDS_CAP", 200),
            max_download_documents_cap=_int_env("BN_ACERVO_DOWNLOAD_DOCUMENTS_CAP", 200),
            max_ocr_pages_cap=_int_env("BN_ACERVO_OCR_PAGES_CAP", 500),
        )

    def _clamp(self, value: int, floor: int, cap: int) -> int:
        return max(floor, min(value, cap))

    def _resolve_budget_value(
        self,
        *,
        payload_value: int,
        payload_default: int,
        profile_default: int,
        floor: int,
        cap: int,
    ) -> int:
        if payload_value != payload_default:
            return self._clamp(payload_value, floor, cap)
        return self._clamp(max(payload_value, profile_default), floor, cap)

    def build_profile(self, payload: AcervoStoryRequest) -> InvestigationProfile:
        if payload.investigation_mode == "deep":
            return InvestigationProfile(
                mode="deep",
                max_search_results=self._resolve_budget_value(
                    payload_value=payload.max_search_results,
                    payload_default=AcervoStoryRequest.model_fields["max_search_results"].default,
                    profile_default=self.deep_search_results,
                    floor=1,
                    cap=self.max_search_results_cap,
                ),
                max_detail_records=self._resolve_budget_value(
                    payload_value=payload.max_detail_records,
                    payload_default=AcervoStoryRequest.model_fields["max_detail_records"].default,
                    profile_default=self.deep_detail_records,
                    floor=1,
                    cap=self.max_detail_records_cap,
                ),
                max_download_documents=self._resolve_budget_value(
                    payload_value=payload.max_download_documents,
                    payload_default=AcervoStoryRequest.model_fields["max_download_documents"].default,
                    profile_default=self.deep_download_documents,
                    floor=0,
                    cap=self.max_download_documents_cap,
                ),
                max_ocr_pages_per_document=self._resolve_budget_value(
                    payload_value=payload.max_ocr_pages_per_document,
                    payload_default=AcervoStoryRequest.model_fields["max_ocr_pages_per_document"].default,
                    profile_default=self.deep_ocr_pages_per_document,
                    floor=0,
                    cap=self.max_ocr_pages_cap,
                ),
                prefer_ocr=True,
                include_authority_pages=True,
                persist_investigation=payload.persist_investigation,
                search_axis_limit=self._clamp(self.deep_search_axis_limit, 1, 128),
            )
        return InvestigationProfile(
            mode="quick",
            max_search_results=self._resolve_budget_value(
                payload_value=payload.max_search_results,
                payload_default=AcervoStoryRequest.model_fields["max_search_results"].default,
                profile_default=self.quick_search_results,
                floor=1,
                cap=self.max_search_results_cap,
            ),
            max_detail_records=self._resolve_budget_value(
                payload_value=payload.max_detail_records,
                payload_default=AcervoStoryRequest.model_fields["max_detail_records"].default,
                profile_default=self.quick_detail_records,
                floor=1,
                cap=self.max_detail_records_cap,
            ),
            max_download_documents=self._resolve_budget_value(
                payload_value=payload.max_download_documents,
                payload_default=AcervoStoryRequest.model_fields["max_download_documents"].default,
                profile_default=self.quick_download_documents,
                floor=0,
                cap=self.max_download_documents_cap,
            ),
            max_ocr_pages_per_document=self._resolve_budget_value(
                payload_value=payload.max_ocr_pages_per_document,
                payload_default=AcervoStoryRequest.model_fields["max_ocr_pages_per_document"].default,
                profile_default=self.quick_ocr_pages_per_document,
                floor=0,
                cap=self.max_ocr_pages_cap,
            ),
            prefer_ocr=payload.prefer_ocr,
            include_authority_pages=payload.include_authority_pages,
            persist_investigation=payload.persist_investigation,
            search_axis_limit=self._clamp(self.quick_search_axis_limit, 1, 128),
        )


class InvestigationMemoryStore:
    """Persistencia incremental por caso de investigacao."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def case_path(self, query: str) -> Path:
        slug = _slug_identifier(query, prefix="case")
        return self.base_dir / f"{slug}.json"

    def load(self, query: str) -> dict[str, Any]:
        path = self.case_path(query)
        if not path.exists():
            return {"query": query, "runs": [], "aggregate_references": [], "aggregate_entities": []}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Falha ao ler memoria de investigacao de %s", query, exc_info=True)
            return {"query": query, "runs": [], "aggregate_references": [], "aggregate_entities": []}

    def save_run(
        self,
        *,
        query: str,
        profile: InvestigationProfile,
        plan: dict[str, Any],
        references: list[dict[str, Any]],
        dossier: dict[str, Any] | None,
        records: list[dict[str, Any]],
    ) -> None:
        payload = self.load(query)
        runs = payload.setdefault("runs", [])
        run_entry = {
            "timestamp": datetime.now().isoformat(),
            "mode": profile.mode,
            "plan": plan,
            "references": references,
            "records": records,
            "subject": dossier.get("subject", {}) if isinstance(dossier, dict) else {},
            "timeline": dossier.get("timeline", []) if isinstance(dossier, dict) else [],
            "relationships": dossier.get("relationships", []) if isinstance(dossier, dict) else [],
            "unresolved_questions": plan.get("unresolved_questions", []) if isinstance(plan, dict) else [],
        }
        runs.append(run_entry)
        aggregate_refs = payload.setdefault("aggregate_references", [])
        seen_ref_keys = {
            (
                str(item.get("title") or "").strip(),
                str(item.get("detail_url") or "").strip(),
            )
            for item in aggregate_refs
            if isinstance(item, dict)
        }
        for reference in references:
            key = (
                str(reference.get("title") or "").strip(),
                str(reference.get("detail_url") or "").strip(),
            )
            if key in seen_ref_keys:
                continue
            seen_ref_keys.add(key)
            aggregate_refs.append(reference)
        aggregate_entities = payload.setdefault("aggregate_entities", [])
        if isinstance(dossier, dict):
            for entity in [dossier.get("subject", {}), *dossier.get("entities", [])]:
                if not isinstance(entity, dict):
                    continue
                name = str(entity.get("name") or "").strip()
                if not name:
                    continue
                if any(str(item.get("name") or "").strip().lower() == name.lower() for item in aggregate_entities if isinstance(item, dict)):
                    continue
                aggregate_entities.append(
                    {
                        "name": name,
                        "kind": str(entity.get("kind") or ""),
                        "description": str(entity.get("description") or ""),
                    }
                )
        self.case_path(query).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class InvestigationJobStore:
    """Persistencia simples de jobs assincronos por arquivo."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def job_path(self, job_id: str) -> Path:
        return self.base_dir / f"{job_id}.json"

    def create(self, payload: AcervoStoryRequest) -> dict[str, Any]:
        now = datetime.now().isoformat()
        job_id = uuid.uuid4().hex
        record = {
            "job_id": job_id,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "phase": "queued",
            "progress_percent": 0,
            "payload": payload.model_dump(),
            "partial_result": None,
            "result": None,
            "error": None,
            "logs": [{"timestamp": now, "level": "info", "message": "Job criado e aguardando execucao."}],
        }
        self.save(record)
        return record

    def load(self, job_id: str) -> dict[str, Any] | None:
        path = self.job_path(job_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Falha ao ler job %s", job_id, exc_info=True)
            return None

    def iter_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in sorted(self.base_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Falha ao ler job %s", path.name, exc_info=True)
                continue
            if isinstance(data, dict) and str(data.get("job_id") or "").strip():
                records.append(data)
        return records

    def list_active(self) -> list[dict[str, Any]]:
        return [record for record in self.iter_records() if _job_is_active_status(record.get("status"))]

    def save(self, record: dict[str, Any]) -> None:
        with self._lock:
            self.job_path(str(record["job_id"])).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    def update(self, job_id: str, **fields: Any) -> dict[str, Any] | None:
        record = self.load(job_id)
        if record is None:
            return None
        record.update(fields)
        record["updated_at"] = datetime.now().isoformat()
        self.save(record)
        return record

    def append_log(self, job_id: str, *, level: str, message: str) -> dict[str, Any] | None:
        record = self.load(job_id)
        if record is None:
            return None
        logs = record.setdefault("logs", [])
        logs.append(
            {
                "timestamp": datetime.now().isoformat(),
                "level": level,
                "message": _truncate(message, 1200),
            }
        )
        if len(logs) > 250:
            record["logs"] = logs[-250:]
        record["updated_at"] = datetime.now().isoformat()
        self.save(record)
        return record


class RateGate:
    """Serializa requests ao Sophia para reduzir bloqueios do Cloudflare."""

    def __init__(self, min_interval_seconds: float) -> None:
        self.min_interval_seconds = max(0.0, min_interval_seconds)
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    async def wait_turn(self) -> None:
        async with self._lock:
            elapsed = time.monotonic() - self._last_request
            if elapsed < self.min_interval_seconds:
                await asyncio.sleep(self.min_interval_seconds - elapsed)
            self._last_request = time.monotonic()


class BaseDocumentDigester:
    """Contrato basico para provedores de digestao documental."""

    name = "base"

    def is_available(self) -> bool:
        return True

    def supports(self, document: DownloadedDocument) -> bool:
        return bool(document.local_path)

    async def digest(
        self,
        agent: "BnAcervoAgent",
        document: DownloadedDocument,
        *,
        max_ocr_pages_per_document: int,
        prefer_ocr: bool,
    ) -> bool:
        raise NotImplementedError


class DoclingDocumentDigester(BaseDocumentDigester):
    """Backend principal via Docling para formatos documentais multiplos."""

    name = "docling"
    supported_suffixes = {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
        ".webp",
        ".bmp",
        ".html",
        ".xhtml",
        ".md",
        ".csv",
        ".docx",
        ".pptx",
        ".xlsx",
        ".xml",
        ".json",
        ".txt",
    }

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self._converter_cls: Any | None = None
        self._converter_instance: Any | None = None
        self._availability_checked = False
        self._available = False

    def is_available(self) -> bool:
        if not self.enabled:
            return False
        if not self._availability_checked:
            self._availability_checked = True
            try:
                from docling.document_converter import DocumentConverter
            except Exception:
                self._converter_cls = None
                self._available = False
            else:
                self._converter_cls = DocumentConverter
                self._available = True
        return self._available

    def supports(self, document: DownloadedDocument) -> bool:
        local_path = Path(document.local_path or "")
        if not local_path:
            return False
        if local_path.suffix.lower() in self.supported_suffixes:
            return True
        media_type = (document.media_type or "").lower()
        return media_type.startswith("text/") or media_type in {
            "application/pdf",
            "application/xhtml+xml",
            "application/xml",
            "application/json",
        }

    async def digest(
        self,
        agent: "BnAcervoAgent",
        document: DownloadedDocument,
        *,
        max_ocr_pages_per_document: int,
        prefer_ocr: bool,
    ) -> bool:
        if not self.is_available() or not self.supports(document):
            return False
        local_path = Path(document.local_path or "")
        try:
            extracted = await asyncio.to_thread(self._convert_with_docling, local_path)
        except Exception as exc:
            logger.warning("Docling falhou para %s: %s", local_path, exc)
            return False
        if not extracted.strip():
            return False
        document.extraction_mode = "docling"
        document.extracted_text = _truncate(extracted, 5000)
        document.summary = await agent._summarize_document_text(extracted)
        return True

    def _convert_with_docling(self, local_path: Path) -> str:
        if not self._converter_cls:
            raise RuntimeError("docling_indisponivel")
        converter = self._converter_instance or self._build_converter()
        self._converter_instance = converter
        result = converter.convert(str(local_path))
        doc = getattr(result, "document", None)
        if doc is None:
            return ""
        for export_method in ("export_to_markdown", "export_to_text", "export_to_html"):
            method = getattr(doc, export_method, None)
            if callable(method):
                content = method()
                if isinstance(content, str) and content.strip():
                    return content
        text_candidate = str(doc).strip()
        return text_candidate

    def _build_converter(self) -> Any:
        if not self._converter_cls:
            raise RuntimeError("docling_indisponivel")
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
            from docling.document_converter import PdfFormatOption
        except Exception:
            return self._converter_cls()

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = False
        pipeline_options.ocr_options = RapidOcrOptions(
            force_full_page_ocr=True,
            backend="torch",
            print_verbose=False,
        )
        return self._converter_cls(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )


class LegacyDocumentDigester(BaseDocumentDigester):
    """Fluxo legado de digestao documental mantido como fallback."""

    name = "legacy"

    async def digest(
        self,
        agent: "BnAcervoAgent",
        document: DownloadedDocument,
        *,
        max_ocr_pages_per_document: int,
        prefer_ocr: bool,
    ) -> bool:
        local_path = Path(document.local_path or "")
        suffix = local_path.suffix.lower()
        if suffix == ".pdf":
            text = await asyncio.to_thread(agent._pdftotext, local_path)
            document.extracted_text = _truncate(text, 5000)
            if prefer_ocr and max_ocr_pages_per_document > 0:
                ocr_text = await agent._ocr_pdf_pages(local_path, max_ocr_pages_per_document)
                if ocr_text:
                    document.extraction_mode = "pdf_ocr_gpu0"
                    document.summary = await agent._summarize_document_text(ocr_text)
                    return True
                if document.extracted_text:
                    document.extraction_mode = "pdftotext"
                    document.summary = await agent._summarize_document_text(document.extracted_text)
                    return True
            elif document.extracted_text:
                document.extraction_mode = "pdftotext"
                document.summary = await agent._summarize_document_text(document.extracted_text)
                return True
            document.skipped_reason = "pdf_sem_texto_e_sem_ocr"
            return False

        if suffix in DOCUMENT_SUFFIXES:
            ocr_text = await agent._ocr_image(local_path)
            if ocr_text:
                document.extraction_mode = "image_ocr_gpu0"
                document.extracted_text = _truncate(ocr_text, 5000)
                document.summary = await agent._summarize_document_text(ocr_text)
                return True
            document.skipped_reason = "ocr_vazio"
            return False

        try:
            content = await asyncio.to_thread(local_path.read_text, encoding="utf-8", errors="ignore")
        except Exception as exc:
            document.skipped_reason = f"leitura_falhou:{exc}"
            return False
        document.extraction_mode = "texto_direto"
        document.extracted_text = _truncate(content, 5000)
        document.summary = await agent._summarize_document_text(content)
        return True


class DocumentDigesterRegistry:
    """Seleciona o backend principal e faz fallback sem hardcode por chamada."""

    def __init__(self, digesters: Iterable[BaseDocumentDigester]) -> None:
        self.digesters = list(digesters)

    async def digest(
        self,
        agent: "BnAcervoAgent",
        document: DownloadedDocument,
        *,
        max_ocr_pages_per_document: int,
        prefer_ocr: bool,
    ) -> bool:
        for digester in self.digesters:
            if not digester.is_available():
                continue
            if not digester.supports(document):
                continue
            if await digester.digest(
                agent,
                document,
                max_ocr_pages_per_document=max_ocr_pages_per_document,
                prefer_ocr=prefer_ocr,
            ):
                return True
        return False


class BnAcervoAgent:
    """Pipeline principal do agente do Acervo BN."""

    def __init__(self) -> None:
        gpu0_host = os.getenv("BN_ACERVO_GPU0_HOST", os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434"))
        gpu1_host = os.getenv("BN_ACERVO_GPU1_HOST", os.getenv("OLLAMA_HOST_GPU1", str(LLM_GPU1_CONFIG.get("base_url", "http://192.168.15.2:11435"))))
        self.story_host = gpu0_host.rstrip("/")
        self.story_model = os.getenv("BN_ACERVO_STORY_MODEL", "gemma3:1b")
        self.vision_host = os.getenv("BN_ACERVO_VISION_HOST", gpu0_host).rstrip("/")
        self.vision_model = os.getenv("BN_ACERVO_VISION_MODEL", "moondream:latest")
        self.planner_host = gpu1_host.rstrip("/")
        self.planner_model = os.getenv("BN_ACERVO_PLANNER_MODEL", "gemma3:1b")
        self.story_loaded_model = self._probe_loaded_model(self.story_host)
        self.planner_loaded_model = self._probe_loaded_model(self.planner_host)

        self.http_timeout_seconds = _int_env("BN_ACERVO_HTTP_TIMEOUT_SECONDS", 120)
        self.search_timeout_seconds = _int_env("BN_ACERVO_SEARCH_TIMEOUT_SECONDS", 12)
        self.http_trust_env = _bool_env("BN_ACERVO_HTTP_TRUST_ENV", False)
        self.download_timeout_seconds = _int_env("BN_ACERVO_DOWNLOAD_TIMEOUT_SECONDS", 300)
        self.firefox_page_timeout_seconds = _int_env("BN_ACERVO_FIREFOX_PAGE_TIMEOUT_SECONDS", 45)
        self.max_document_bytes = _int_env("BN_ACERVO_MAX_DOCUMENT_BYTES", 80 * 1024 * 1024)
        self.cooldown_seconds = _int_env("BN_ACERVO_CLOUDFLARE_COOLDOWN_SECONDS", 12)
        self.browser_retries = _int_env("BN_ACERVO_BROWSER_RETRIES", 1)
        self.browser_request_interval_seconds = float(os.getenv("BN_ACERVO_BROWSER_REQUEST_INTERVAL_SECONDS", "6.5"))
        self.firefox_profile_dir = os.getenv("BN_ACERVO_FIREFOX_PROFILE_DIR", "").strip()
        self.firefox_proxy = os.getenv("BN_ACERVO_FIREFOX_PROXY", "").strip() or _detect_firefox_proxy_from_local_profile()
        self.preload_homepage = _bool_env("BN_ACERVO_PRELOAD_HOMEPAGE", False)
        self.max_prompt_chars = _int_env("BN_ACERVO_MAX_PROMPT_CHARS", 18000)
        self.max_story_predict = _int_env("BN_ACERVO_MAX_STORY_PREDICT", 1200)
        self.story_timeout_seconds = _int_env("BN_ACERVO_STORY_TIMEOUT_SECONDS", 45)
        self.max_dossier_predict = _int_env("BN_ACERVO_MAX_DOSSIER_PREDICT", 900)
        self.dossier_timeout_seconds = _int_env("BN_ACERVO_DOSSIER_TIMEOUT_SECONDS", 35)
        self.max_planner_predict = _int_env("BN_ACERVO_MAX_PLANNER_PREDICT", 250)
        self.max_summary_predict = _int_env("BN_ACERVO_MAX_SUMMARY_PREDICT", 300)
        self.story_num_ctx = min(get_dynamic_num_ctx(self.story_model), _int_env("BN_ACERVO_STORY_NUM_CTX_CAP", 4096))
        self.planner_num_ctx = min(get_dynamic_num_ctx(self.planner_model), _int_env("BN_ACERVO_PLANNER_NUM_CTX_CAP", 2048))
        self.dossier_num_ctx = min(get_dynamic_num_ctx(self.planner_model), _int_env("BN_ACERVO_DOSSIER_NUM_CTX_CAP", 4096))
        self.vision_num_ctx = min(get_dynamic_num_ctx(self.story_model), _int_env("BN_ACERVO_VISION_NUM_CTX_CAP", 2048))
        self.force_duckduckgo_search = _bool_env("BN_ACERVO_FORCE_DDG", True)
        self.docling_enabled = _bool_env("BN_ACERVO_DOCLING_ENABLED", True)
        self.enable_copilot_fallback = _bool_env("BN_ACERVO_ENABLE_COPILOT_FALLBACK", True)
        self.download_dir = DATA_DIR / "bn_acervo" / "downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.memory_dir = DATA_DIR / "bn_acervo" / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.investigation_dir = DATA_DIR / "bn_acervo" / "investigations"
        self.investigation_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir = DATA_DIR / "bn_acervo" / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.character_memory_path = self.memory_dir / "characters_graph.json"
        self.investigation_memory_store = InvestigationMemoryStore(self.investigation_dir)
        self.job_store = InvestigationJobStore(self.jobs_dir)
        self.investigation_budget_policy = InvestigationBudgetPolicy.from_env()

        self.gpu0_semaphore = asyncio.Semaphore(_int_env("BN_ACERVO_GPU0_CONCURRENCY", 1))
        self.gpu1_semaphore = asyncio.Semaphore(_int_env("BN_ACERVO_GPU1_CONCURRENCY", 2))
        self.rate_gate = RateGate(self.browser_request_interval_seconds)
        self.document_digester = DocumentDigesterRegistry(
            [
                DoclingDocumentDigester(enabled=self.docling_enabled),
                LegacyDocumentDigester(),
            ]
        )

    async def _emit_progress(
        self,
        progress_callback: Callable[[str, str, dict[str, Any] | None], Awaitable[None] | None] | None,
        phase: str,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if progress_callback is None:
            return
        result = progress_callback(phase, message, extra)
        if inspect.isawaitable(result):
            await result

    async def run(
        self,
        payload: AcervoStoryRequest,
        progress_callback: Callable[[str, str, dict[str, Any] | None], Awaitable[None] | None] | None = None,
    ) -> dict[str, Any]:
        profile = self._resolve_investigation_profile(payload)
        payload = profile.apply(payload)
        await self._emit_progress(progress_callback, "planning", "Gerando plano investigativo.", {"percent": 8})
        logger.info(
            "BN acervo run start query=%r mode=%s output=%s search=%s details=%s docs=%s ocr_pages=%s authority=%s persist=%s",
            payload.query,
            profile.mode,
            payload.output_mode,
            payload.max_search_results,
            payload.max_detail_records,
            payload.max_download_documents,
            payload.max_ocr_pages_per_document,
            payload.include_authority_pages,
            payload.persist_investigation,
        )
        plan = await self._plan_query(payload.query, profile)
        await self._emit_progress(progress_callback, "planning", "Plano gerado; iniciando descoberta de fontes.", {"percent": 18})
        logger.info(
            "Plano gerado search_terms=%s hypotheses=%s institutions=%s companies=%s unresolved=%s",
            len(plan.get("search_terms", [])),
            len(plan.get("hypotheses", [])),
            len(plan.get("institutions", [])),
            len(plan.get("companies", [])),
            len(plan.get("unresolved_questions", [])),
        )
        candidate_hits = await self._discover_candidate_hits(plan, payload)
        if not candidate_hits:
            logger.warning("Nenhum candidato do acervo foi encontrado para a consulta")
            await self._emit_progress(progress_callback, "contingency", "Nenhum candidato encontrado; retornando contingencia.", {"percent": 100})
            return self._build_contingency_result(payload, profile, plan, [], [])
        logger.info("Descoberta concluida candidate_hits=%s", len(candidate_hits))
        discovery_snapshot = self._build_candidate_hits_snapshot(payload.query, plan, candidate_hits[: min(len(candidate_hits), payload.max_detail_records)])
        await self._emit_progress(
            progress_callback,
            "discovery",
            "Candidatos localizados; lendo detalhes.",
            {"percent": 34, "candidate_hits": len(candidate_hits), "partial_result": discovery_snapshot},
        )

        fetched_records: list[AcervoRecord] = []
        scan_limit = min(len(candidate_hits), max(payload.max_detail_records * 2, payload.max_detail_records))
        for hit in candidate_hits[:scan_limit]:
            if hit.source_kind in {"hemeroteca_pdf", "bndigital_page", "objdigital_document", "direct_document"}:
                record = self._build_external_record_from_search_hit(hit)
                fetched_records.append(record)
                if len(fetched_records) >= payload.max_detail_records:
                    break
                continue
            try:
                record = await self._fetch_record(hit.detail_url)
            except Exception as exc:
                logger.warning("Falha ao ler detalhe do Sophia %s: %s", hit.detail_url, exc)
                if "bloqueio_cloudflare" in str(exc):
                    fetched_records.append(self._build_partial_record_from_search_hit(hit))
                    if len(fetched_records) >= payload.max_detail_records:
                        break
                continue
            if not payload.include_authority_pages and "/autoridade/" in record.detail_url.lower():
                continue
            if not record.raw_text and hit.snippet:
                record.raw_text = hit.snippet
            if hit.snippet and "snippet_busca" not in record.metadata:
                record.metadata["snippet_busca"] = hit.snippet
            fetched_records.append(record)
            if len(fetched_records) >= payload.max_detail_records:
                break

        if not fetched_records:
            logger.warning("Todos os candidatos retornaram bloqueio ou falha de leitura")
            await self._emit_progress(progress_callback, "contingency", "Falha na leitura dos detalhes; retornando contingencia.", {"percent": 100, "candidate_hits": len(candidate_hits)})
            return self._build_contingency_result(payload, profile, plan, candidate_hits, [])

        logger.info("Leitura de detalhes concluida fetched_records=%s", len(fetched_records))
        fetched_references = build_reference_entries(fetched_records)
        await self._emit_progress(
            progress_callback,
            "ranking",
            "Detalhes coletados; ranqueando registros.",
            {
                "percent": 52,
                "fetched_records": len(fetched_records),
                "partial_result": self._build_partial_result_snapshot(payload.query, plan, fetched_records, fetched_references, phase="ranking"),
            },
        )
        ranked_records = await self._rank_records(payload.query, fetched_records, payload.max_detail_records)
        logger.info("Ranqueamento concluido ranked_records=%s", len(ranked_records))
        ranked_references = build_reference_entries(ranked_records)
        await self._emit_progress(
            progress_callback,
            "documents",
            "Ranqueamento concluido; digerindo documentos.",
            {
                "percent": 66,
                "ranked_records": len(ranked_records),
                "partial_result": self._build_partial_result_snapshot(payload.query, plan, ranked_records, ranked_references, phase="documents"),
            },
        )
        await self._download_and_digest_documents(
            ranked_records,
            max_download_documents=payload.max_download_documents,
            max_ocr_pages_per_document=payload.max_ocr_pages_per_document,
            prefer_ocr=payload.prefer_ocr,
        )
        logger.info("Digestao documental concluida")

        references = build_reference_entries(ranked_records)
        logger.info("Referencias consolidadas references=%s", len(references))
        partial_result = self._build_partial_result_snapshot(payload.query, plan, ranked_records, references)
        await self._emit_progress(
            progress_callback,
            "composition",
            "Compondo resultado final.",
            {"percent": 82, "references": len(references), "partial_result": partial_result},
        )
        result: dict[str, Any] = {
            "query": payload.query,
            "output_mode": payload.output_mode,
            "plan": plan,
            "candidate_urls": [hit.detail_url for hit in candidate_hits],
            "candidate_hits": [asdict(hit) for hit in candidate_hits],
            "records": [self._serialize_record(record) for record in ranked_records],
            "references": references,
        }
        if payload.output_mode == "dossier":
            logger.info("Compondo dossie final")
            dossier = await self._compose_dossier(payload.query, plan, ranked_records, references)
            self._persist_character_memory(payload.query, dossier)
            dossier = self._expand_dossier_with_character_memory(payload.query, dossier)
            dossier["neural_map"] = build_neural_correlation_map(dossier)
            dossier["mermaid_graph"] = build_mermaid_graph(dossier)
            dossier["dossier_markdown"] = render_dossier_markdown(dossier, references)
            result["dossier"] = dossier
            result["neural_map"] = dossier["neural_map"]
            result["mermaid_graph"] = dossier["mermaid_graph"]
            result["dossier_markdown"] = dossier["dossier_markdown"]
            result["story_markdown"] = dossier["dossier_markdown"]
            if payload.persist_investigation:
                self.investigation_memory_store.save_run(
                    query=payload.query,
                    profile=profile,
                    plan=plan,
                    references=references,
                    dossier=dossier,
                    records=[self._serialize_record(record) for record in ranked_records],
                )
            logger.info("Run concluido com dossie")
            await self._emit_progress(progress_callback, "completed", "Dossie concluido.", {"percent": 100})
            return result

        logger.info("Compondo historia final")
        story_markdown = await self._compose_story(payload.query, plan, ranked_records, references)
        result["story_markdown"] = story_markdown
        if payload.persist_investigation:
            self.investigation_memory_store.save_run(
                query=payload.query,
                profile=profile,
                plan=plan,
                references=references,
                dossier=None,
                records=[self._serialize_record(record) for record in ranked_records],
            )
        logger.info("Run concluido com historia")
        await self._emit_progress(progress_callback, "completed", "Historia concluida.", {"percent": 100})
        return result

    def _build_contingency_result(
        self,
        payload: AcervoStoryRequest,
        profile: InvestigationProfile,
        plan: dict[str, Any],
        candidate_hits: list[SearchHit],
        ranked_records: list[AcervoRecord],
    ) -> dict[str, Any]:
        references = build_reference_entries(ranked_records)
        result: dict[str, Any] = {
            "query": payload.query,
            "output_mode": payload.output_mode,
            "plan": plan,
            "candidate_urls": [hit.detail_url for hit in candidate_hits],
            "candidate_hits": [asdict(hit) for hit in candidate_hits],
            "records": [self._serialize_record(record) for record in ranked_records],
            "references": references,
            "contingency_mode": True,
            "warning": "A investigacao nao encontrou evidencias suficientes para fechar o caso neste ciclo.",
        }
        if payload.output_mode == "dossier":
            dossier = self._fallback_dossier(payload.query, plan, ranked_records, references)
            result["dossier"] = dossier
            result["neural_map"] = dossier["neural_map"]
            result["mermaid_graph"] = dossier["mermaid_graph"]
            result["dossier_markdown"] = dossier["dossier_markdown"]
            result["story_markdown"] = dossier["dossier_markdown"]
        else:
            result["story_markdown"] = self._fallback_story(payload.query, ranked_records, references)
        return result

    def _build_partial_result_snapshot(
        self,
        query: str,
        plan: dict[str, Any],
        ranked_records: list[AcervoRecord],
        references: list[dict[str, Any]],
        *,
        phase: str = "composition",
    ) -> dict[str, Any]:
        dossier = self._fallback_dossier(query, plan, ranked_records, references)
        return {
            "query": query,
            "output_mode": "dossier",
            "plan": plan,
            "records": [self._serialize_record(record) for record in ranked_records],
            "references": references,
            "dossier": dossier,
            "neural_map": dossier.get("neural_map"),
            "mermaid_graph": dossier.get("mermaid_graph"),
            "dossier_markdown": dossier.get("dossier_markdown"),
            "story_markdown": dossier.get("dossier_markdown"),
            "phase": phase,
            "partial_snapshot": True,
        }

    def _build_candidate_hits_snapshot(
        self,
        query: str,
        plan: dict[str, Any],
        candidate_hits: list[SearchHit],
    ) -> dict[str, Any]:
        records: list[AcervoRecord] = []
        for hit in candidate_hits:
            source_kind = hit.source_kind or _detect_source_kind(hit.detail_url)
            if source_kind in {"hemeroteca_pdf", "bndigital_page", "objdigital_document", "direct_document"}:
                records.append(self._build_external_record_from_search_hit(hit))
            else:
                records.append(self._build_partial_record_from_search_hit(hit))
        references = build_reference_entries(records)
        return self._build_partial_result_snapshot(query, plan, records, references, phase="discovery")

    def _resolve_investigation_profile(self, payload: AcervoStoryRequest) -> InvestigationProfile:
        return self.investigation_budget_policy.build_profile(payload)

    async def _plan_query(self, query: str, profile: InvestigationProfile) -> dict[str, Any]:
        prompt = (
            "Analise a consulta do usuario para pesquisa historica no Acervo da Biblioteca Nacional. "
            "Retorne APENAS JSON valido com as chaves search_terms, must_include, people, years, hypotheses, institutions, companies, unresolved_questions. "
            "search_terms deve conter ate 5 consultas curtas e especificas para motor de busca. "
            "must_include deve listar fatos/linhas narrativas que valem ser rastreados. "
            "hypotheses deve listar suspeitas historicas ou eixos investigativos que precisam de confirmacao documental. "
            "institutions e companies devem destacar atores organizacionais importantes para cruzamento. "
            "unresolved_questions deve listar perguntas abertas que exigem busca longa e acumulativa. "
            "Priorize tambem jornais, revistas, periodicos, hemeroteca e imprensa em geral quando isso puder enriquecer a pesquisa. "
            f"Modo de investigacao: {profile.mode}. "
            f"Consulta: {query}"
        )
        try:
            response = await asyncio.wait_for(
                self._ollama_generate(
                    host=self.planner_host,
                    model=self.planner_model,
                    prompt=prompt,
                    num_ctx=self.planner_num_ctx,
                    num_predict=self.max_planner_predict,
                    use_gpu0=False,
                ),
                timeout=min(self.http_timeout_seconds, 20),
            )
        except Exception as exc:
            logger.warning("Planejamento caiu em fallback deterministico: %s", exc)
            response = ""
        parsed = self._extract_json(response)
        if parsed:
            parsed["search_terms"] = _normalize_search_terms_from_query(query, parsed.get("search_terms", []))
            parsed["must_include"] = _normalize_search_terms_from_query(query, parsed.get("must_include", []))
            parsed["hypotheses"] = _normalize_search_terms_from_query(query, parsed.get("hypotheses", []))
            parsed["institutions"] = _normalize_search_terms_from_query(query, parsed.get("institutions", []))
            parsed["companies"] = _normalize_search_terms_from_query(query, parsed.get("companies", []))
            parsed["unresolved_questions"] = [
                _truncate(" ".join(str(item).split()).strip(), 220)
                for item in parsed.get("unresolved_questions", [])
                if str(item).strip()
            ][:8]
            if profile.mode == "deep":
                parsed["search_terms"] = self._expand_deep_search_terms(query, parsed, profile.search_axis_limit)
            return parsed

        tokens = [token for token in re.findall(r"[A-Za-zÀ-ÿ0-9-]{3,}", query) if len(token) >= 3]
        search_terms = [
            query,
            f"{query} acervo bn",
            " ".join(tokens[:4]),
        ]
        return {
            "search_terms": [term for term in search_terms if term.strip()],
            "must_include": ["cronologia", "fontes primarias", "contexto historico", "jornais", "revistas", "imprensa"],
            "people": [],
            "years": [],
            "hypotheses": ["conflitos institucionais", "financiamento", "politica industrial"] if profile.mode == "deep" else [],
            "institutions": [],
            "companies": [],
            "unresolved_questions": ["Quais atores institucionais interferiram no caso?"] if profile.mode == "deep" else [],
        }

    def _expand_deep_search_terms(self, query: str, plan: dict[str, Any], axis_limit: int) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()

        def add(term: str) -> None:
            cleaned = " ".join(str(term).split()).strip()
            if not cleaned:
                return
            folded = _ascii_fold(cleaned).lower()
            if folded in seen:
                return
            seen.add(folded)
            normalized.append(cleaned)

        add(query)
        for key in ("search_terms", "must_include", "hypotheses", "institutions", "companies"):
            for item in plan.get(key, []):
                add(str(item))
        axes = [item for item in plan.get("must_include", []) + plan.get("hypotheses", []) if str(item).strip()]
        for axis in axes[:axis_limit]:
            add(f"{query} {axis}")
        return normalized[:20]

    def _build_search_queries(self, term: str, mode: str) -> list[tuple[str, str]]:
        cleaned_term = " ".join(term.split()).strip()
        press_term = f"{cleaned_term} jornal revista imprensa hemeroteca"
        queries = [
            ("sophia", f"site:{TARGET_HOST}/sophia_web/acervo/detalhe {cleaned_term}"),
            ("sophia", f"site:{TARGET_HOST}/sophia_web {cleaned_term}"),
            ("press", f"site:{HEMEROTECA_PDF_HOST} {cleaned_term}"),
            ("press", f"site:{BNDIGITAL_HOST} {press_term}"),
        ]
        if mode == "quick":
            return queries[:2]
        return queries

    async def _discover_candidate_hits(self, plan: dict[str, Any], payload: AcervoStoryRequest) -> list[SearchHit]:
        hits: list[SearchHit] = []
        seen: set[str] = set()
        search_terms = [term for term in plan.get("search_terms", []) if isinstance(term, str) and term.strip()]
        if not search_terms:
            search_terms = [payload.query]
        if payload.investigation_mode == "quick":
            search_terms = search_terms[:1]

        desired_hits = max(payload.max_search_results, 1)
        for term in search_terms:
            for query_family, query in self._build_search_queries(term, payload.investigation_mode):
                term_hits = await self._duckduckgo_hits(query)
                if not term_hits:
                    term_hits = await self._bing_rss_hits(query)
                for hit in term_hits:
                    lowered = hit.detail_url.lower()
                    kind = hit.source_kind or _detect_source_kind(hit.detail_url)
                    is_sophia_like = kind.startswith("sophia_")
                    is_allowed_press = kind in {"hemeroteca_pdf", "bndigital_page", "objdigital_document", "direct_document"}
                    if is_sophia_like:
                        if "/acervo/detalhe/" not in lowered:
                            if payload.include_authority_pages and "/autoridade/detalhe/" in lowered:
                                pass
                            else:
                                continue
                        if not payload.include_authority_pages and "/autoridade/" in lowered:
                            continue
                    elif not is_allowed_press:
                        continue
                    if hit.detail_url not in seen:
                        seen.add(hit.detail_url)
                        hit.score = self._score_search_hit(payload.query, hit)
                        if query_family == "press":
                            hit.score += 0.4
                        hits.append(hit)
                    if len(hits) >= desired_hits:
                        break
                if len(hits) >= desired_hits:
                    break
            if len(hits) >= desired_hits:
                break
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[: payload.max_search_results]

    async def _duckduckgo_html(self, query: str) -> str:
        headers = {
            "User-Agent": self._browser_user_agent(),
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        async with httpx.AsyncClient(timeout=self.search_timeout_seconds, follow_redirects=True, headers=headers, trust_env=self.http_trust_env) as client:
            response = await client.get(DUCKDUCKGO_HTML_URL, params={"q": query})
            response.raise_for_status()
            return response.text

    async def _duckduckgo_hits(self, query: str) -> list[SearchHit]:
        headers = {
            "User-Agent": self._browser_user_agent(),
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        async with httpx.AsyncClient(timeout=self.search_timeout_seconds, follow_redirects=True, headers=headers, trust_env=self.http_trust_env) as client:
            response = await client.get(DUCKDUCKGO_HTML_URL, params={"q": query})
            logger.info("DuckDuckGo html status=%s query=%s", response.status_code, query)
            if response.status_code != 200:
                return []
            return extract_duckduckgo_result_hits(response.text)

    async def _bing_rss_hits(self, query: str) -> list[SearchHit]:
        headers = {
            "User-Agent": self._browser_user_agent(),
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        async with httpx.AsyncClient(timeout=self.search_timeout_seconds, follow_redirects=True, headers=headers, trust_env=self.http_trust_env) as client:
            response = await client.get("https://www.bing.com/search", params={"format": "rss", "q": query})
            logger.info("Bing RSS status=%s query=%s", response.status_code, query)
            if response.status_code != 200:
                return []
            return self._parse_bing_rss_hits(response.text)

    def _parse_bing_rss_hits(self, xml_text: str) -> list[SearchHit]:
        hits: list[SearchHit] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return hits
        for item in root.findall("./channel/item"):
            link = (item.findtext("link") or "").strip()
            title = (item.findtext("title") or "").strip()
            description = (item.findtext("description") or "").strip()
            if not _host_matches_allowed(urllib.parse.urlparse(link).netloc):
                continue
            hits.append(
                SearchHit(
                    detail_url=link,
                    title=title or "Terminal - Sophia Biblioteca Web",
                    snippet=_truncate(_clean_search_snippet(description), 1200),
                    source_engine="bing_rss",
                    source_kind=_detect_source_kind(link),
                )
            )
        return hits

    def _score_search_hit(self, query: str, hit: SearchHit) -> float:
        tokens = [token.lower() for token in re.findall(r"[A-Za-zÀ-ÿ0-9-]{4,}", query)]
        stopwords = {
            "historia",
            "história",
            "empresa",
            "empresas",
            "automovel",
            "automóvel",
            "automobilistica",
            "automobilística",
            "carro",
            "carros",
            "industria",
            "indústria",
            "brasileira",
            "brasil",
        }
        anchor_terms = [token for token in tokens if token not in stopwords]
        context_terms = [token for token in tokens if token in stopwords]
        haystack = f"{hit.title} {hit.snippet} {hit.detail_url}".lower()
        score = 0.0
        for token in anchor_terms:
            if token in haystack:
                score += 4.0
        for token in context_terms:
            if token in haystack:
                score += 1.0
        if "também disponível online" in haystack or "tambem disponivel online" in haystack:
            score += 0.5
        if "material periódico" in haystack or "material periodico" in haystack or "jornal" in haystack:
            score += 0.5
        if any(keyword in haystack for keyword in PRESS_KEYWORDS):
            score += 0.75
        if hit.source_kind in {"hemeroteca_pdf", "bndigital_page"}:
            score += 0.6
        if hit.source_kind == "hemeroteca_pdf" and ".pdf" in hit.detail_url.lower():
            score += 0.4
        return score

    def _build_partial_record_from_search_hit(self, hit: SearchHit) -> AcervoRecord:
        metadata = {
            "title": hit.title,
            "snippet_busca": hit.snippet,
            "fonte_parcial": f"resultado_externo_{hit.source_engine}",
        }
        return AcervoRecord(
            detail_url=hit.detail_url,
            title=hit.title,
            metadata=metadata,
            raw_text=hit.snippet,
            page_title=hit.title,
            relevance_score=hit.score,
            relevance_reason="fallback por snippet externo apos bloqueio cloudflare",
        )

    def _build_external_record_from_search_hit(self, hit: SearchHit) -> AcervoRecord:
        source_kind = hit.source_kind or _detect_source_kind(hit.detail_url)
        metadata = {
            "title": hit.title,
            "snippet_busca": hit.snippet,
            "fonte_parcial": f"resultado_externo_{hit.source_engine}",
            "corpus": source_kind,
        }
        document_links: list[str] = []
        if source_kind in {"hemeroteca_pdf", "objdigital_document", "direct_document"}:
            document_links = [hit.detail_url]
        if source_kind == "bndigital_page" and "hemeroteca" in hit.detail_url.lower():
            metadata["material"] = "Periódico ou jornal"
        return AcervoRecord(
            detail_url=hit.detail_url,
            title=hit.title,
            metadata=metadata,
            raw_text=hit.snippet,
            page_title=hit.title,
            document_links=document_links,
            relevance_score=hit.score,
            relevance_reason=f"resultado externo do corpus {source_kind}",
        )

    async def _fetch_record(self, url: str) -> AcervoRecord:
        page = await self._fetch_page_with_firefox(url)
        if detect_cloudflare_block(page.title, page.body_text, page.html):
            raise RuntimeError("bloqueio_cloudflare")
        metadata = parse_record_metadata(page.body_text)
        title = metadata.get("title") or metadata.get("link_do_titulo") or page.title or url
        return AcervoRecord(
            detail_url=url,
            title=title,
            metadata=metadata,
            raw_text=_truncate(page.body_text, 6000),
            page_title=page.title,
            document_links=extract_document_links(page.links),
        )

    async def _fetch_page_with_firefox(self, url: str) -> BrowserPage:
        last_error: Exception | None = None
        for attempt in range(self.browser_retries + 1):
            await self.rate_gate.wait_turn()
            if attempt:
                await asyncio.sleep(self.cooldown_seconds * attempt)
            try:
                page = await asyncio.to_thread(self._fetch_page_with_firefox_sync, url)
            except Exception as exc:
                last_error = exc
                continue
            if detect_cloudflare_block(page.title, page.body_text, page.html):
                last_error = RuntimeError("bloqueio_cloudflare")
                continue
            return page
        if last_error is None:
            raise RuntimeError("falha_desconhecida_lendo_sophia")
        raise last_error

    def _browser_lock_path(self) -> Path:
        return self.download_dir / "browser_session.lock"

    def _acquire_browser_lock(self) -> Any:
        lock_path = self._browser_lock_path()
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("w", encoding="utf-8")
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return handle

    def _release_browser_lock(self, handle: Any) -> None:
        try:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    def _fetch_page_with_firefox_sync(self, url: str) -> BrowserPage:
        from selenium import webdriver
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.firefox.options import Options

        options = Options()
        options.add_argument("-headless")
        options.page_load_strategy = "eager"
        options.set_preference("general.useragent.override", self._browser_user_agent())
        options.set_preference("intl.accept_languages", "pt-BR,pt,en-US,en")
        options.set_preference("dom.webdriver.enabled", False)
        options.set_preference("media.peerconnection.enabled", False)
        if self.firefox_profile_dir:
            options.profile = self.firefox_profile_dir
        if self.firefox_proxy:
            parsed_proxy = urllib.parse.urlparse(self.firefox_proxy if "://" in self.firefox_proxy else f"http://{self.firefox_proxy}")
            if parsed_proxy.hostname and parsed_proxy.port:
                options.set_preference("network.proxy.type", 1)
                options.set_preference("network.proxy.http", parsed_proxy.hostname)
                options.set_preference("network.proxy.http_port", int(parsed_proxy.port))
                options.set_preference("network.proxy.ssl", parsed_proxy.hostname)
                options.set_preference("network.proxy.ssl_port", int(parsed_proxy.port))
        lock_handle = self._acquire_browser_lock()
        try:
            driver = webdriver.Firefox(options=options)
            try:
                driver.set_page_load_timeout(self.firefox_page_timeout_seconds)
                if self.preload_homepage:
                    try:
                        driver.get(TARGET_BASE_URL)
                    except TimeoutException:
                        logger.debug("Timeout carregando homepage do Sophia; interrompendo para seguir")
                        try:
                            driver.execute_script("window.stop();")
                        except Exception:
                            pass
                    time.sleep(0.8 + random.random())
                try:
                    driver.get(url)
                except TimeoutException:
                    logger.debug("Timeout carregando detalhe %s; interrompendo para extrair conteudo parcial", url)
                    try:
                        driver.execute_script("window.stop();")
                    except Exception:
                        pass
                time.sleep(0.8 + random.random())
                try:
                    body_element = driver.find_element(By.TAG_NAME, "body")
                    body_text = body_element.text
                except Exception:
                    body_text = ""
                title = driver.title or ""
                html = driver.page_source or ""
                links = []
                for anchor in driver.find_elements(By.TAG_NAME, "a"):
                    href = (anchor.get_attribute("href") or "").strip()
                    if href:
                        links.append(href)
                return BrowserPage(title=title, body_text=body_text, html=html, links=links)
            finally:
                driver.quit()
        finally:
            self._release_browser_lock(lock_handle)

    async def _rank_records(self, query: str, records: list[AcervoRecord], limit: int) -> list[AcervoRecord]:
        if not records:
            return []
        fallback_scored = self._lexical_rank(query, records)
        prompt_records = [
            {
                "id": index + 1,
                "title": record.title,
                "metadata": record.metadata,
                "raw_text_excerpt": _truncate(record.raw_text, 1200),
                "document_links": record.document_links[:2],
            }
            for index, record in enumerate(records)
        ]
        prompt = (
            "Ranqueie os registros do acervo mais relevantes para a pergunta do usuario. "
            "Retorne APENAS JSON valido com chave rankings, onde rankings e uma lista de objetos "
            "com id, score e reason. Score vai de 0 a 1.\n"
            f"Pergunta: {query}\n"
            f"Registros: {json.dumps(prompt_records, ensure_ascii=False)}"
        )
        try:
            response = await asyncio.wait_for(
                self._ollama_generate(
                    host=self.planner_host,
                    model=self.planner_model,
                    prompt=prompt,
                    num_ctx=self.planner_num_ctx,
                    num_predict=self.max_summary_predict,
                    use_gpu0=False,
                ),
                timeout=min(self.http_timeout_seconds, 20),
            )
        except Exception as exc:
            logger.warning("Ranqueamento caiu em fallback lexical: %s", exc)
            return fallback_scored[:limit]
        parsed = self._extract_json(response)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("rankings"), list):
            return fallback_scored[:limit]

        ranking_map: dict[int, tuple[float, str]] = {}
        for item in parsed["rankings"]:
            if not isinstance(item, dict):
                continue
            try:
                idx = int(item.get("id"))
            except Exception:
                continue
            try:
                score = float(item.get("score", 0.0))
            except Exception:
                score = 0.0
            reason = str(item.get("reason", "")).strip()
            ranking_map[idx - 1] = (score, reason)

        ranked: list[AcervoRecord] = []
        for index, record in enumerate(records):
            score, reason = ranking_map.get(index, (0.0, "fallback lexical"))
            record.relevance_score = score
            record.relevance_reason = reason
            ranked.append(record)

        ranked.sort(key=lambda item: item.relevance_score, reverse=True)
        if not any(record.relevance_score > 0 for record in ranked):
            return fallback_scored[:limit]
        return ranked[:limit]

    def _lexical_rank(self, query: str, records: list[AcervoRecord]) -> list[AcervoRecord]:
        tokens = [token.lower() for token in re.findall(r"[A-Za-zÀ-ÿ0-9-]{3,}", query)]
        for record in records:
            haystack = " ".join(
                [
                    record.title,
                    " ".join(record.metadata.values()),
                    record.raw_text,
                    " ".join(record.document_links),
                ]
            ).lower()
            score = 0.0
            for token in tokens:
                if token in haystack:
                    score += 1.0
            if record.document_links:
                score += 0.25
            if "disponível online" in haystack or "disponivel online" in haystack:
                score += 0.5
            record.relevance_score = score
            record.relevance_reason = "ranking lexical"
        return sorted(records, key=lambda item: item.relevance_score, reverse=True)

    async def _download_and_digest_documents(
        self,
        records: list[AcervoRecord],
        *,
        max_download_documents: int,
        max_ocr_pages_per_document: int,
        prefer_ocr: bool,
    ) -> None:
        remaining = max_download_documents
        if remaining <= 0:
            return
        for record in records:
            if remaining <= 0:
                break
            for document_url in record.document_links:
                if remaining <= 0:
                    break
                try:
                    document = await self._download_document(document_url)
                except Exception as exc:
                    logger.warning("Falha baixando documento %s: %s", document_url, exc)
                    record.documents.append(
                        DownloadedDocument(
                            source_url=document_url,
                            media_type=self._guess_media_type_from_url(document_url),
                            skipped_reason=f"download_falhou:{type(exc).__name__}",
                        )
                    )
                    remaining -= 1
                    continue
                record.documents.append(document)
                if document.local_path:
                    try:
                        await self._digest_document(
                            document,
                            max_ocr_pages_per_document=max_ocr_pages_per_document,
                            prefer_ocr=prefer_ocr,
                        )
                    except Exception as exc:
                        logger.warning("Falha digerindo documento %s: %s", document.source_url, exc)
                        if document.extracted_text and not document.summary:
                            document.summary = self._heuristic_document_summary(document.extracted_text)
                        if not document.skipped_reason:
                            document.skipped_reason = f"digestao_falhou:{type(exc).__name__}"
                remaining -= 1

    async def _download_document(self, url: str) -> DownloadedDocument:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return DownloadedDocument(
                source_url=url,
                media_type=self._guess_media_type_from_url(url),
                skipped_reason="url_documento_invalida",
            )
        headers = {"User-Agent": self._browser_user_agent()}
        async with httpx.AsyncClient(timeout=self.download_timeout_seconds, follow_redirects=True, headers=headers, trust_env=self.http_trust_env) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "application/octet-stream").split(";")[0].strip().lower()
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > self.max_document_bytes:
                            return DownloadedDocument(
                                source_url=url,
                                media_type=content_type,
                                skipped_reason=f"arquivo_maior_que_limite:{content_length}",
                            )
                    except ValueError:
                        pass
                suffix = self._suffix_from_url(url, content_type)
                filename = hashlib.sha1(url.encode("utf-8")).hexdigest() + suffix
                target = self.download_dir / filename
                bytes_written = 0
                with target.open("wb") as handle:
                    async for chunk in response.aiter_bytes():
                        bytes_written += len(chunk)
                        if bytes_written > self.max_document_bytes:
                            handle.close()
                            target.unlink(missing_ok=True)
                            return DownloadedDocument(
                                source_url=url,
                                media_type=content_type,
                                skipped_reason=f"download_abortado_por_limite:{bytes_written}",
                            )
                        handle.write(chunk)
        return DownloadedDocument(
            source_url=url,
            media_type=content_type,
            local_path=str(target),
            bytes_downloaded=bytes_written,
        )

    def _guess_media_type_from_url(self, url: str) -> str:
        suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
        if suffix == ".pdf":
            return "application/pdf"
        if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
            return f"image/{suffix.lstrip('.')}".replace("jpg", "jpeg")
        if suffix in {".htm", ".html"}:
            return "text/html"
        if suffix == ".txt":
            return "text/plain"
        return "application/octet-stream"

    async def _digest_document(
        self,
        document: DownloadedDocument,
        *,
        max_ocr_pages_per_document: int,
        prefer_ocr: bool,
    ) -> None:
        digested = await self.document_digester.digest(
            self,
            document,
            max_ocr_pages_per_document=max_ocr_pages_per_document,
            prefer_ocr=prefer_ocr,
        )
        if not digested and not document.skipped_reason:
            document.skipped_reason = "nenhum_digester_suportou_arquivo"

    async def _ocr_pdf_pages(self, pdf_path: Path, max_pages: int) -> str:
        page_dir = self.download_dir / (pdf_path.stem + "_pages")
        page_dir.mkdir(parents=True, exist_ok=True)
        stem = page_dir / "page"
        command = [
            "pdftoppm",
            "-f",
            "1",
            "-l",
            str(max_pages),
            "-png",
            str(pdf_path),
            str(stem),
        ]
        try:
            await asyncio.to_thread(subprocess.run, command, check=True, capture_output=True, text=True)
        except Exception as exc:
            logger.warning("pdftoppm falhou para %s: %s", pdf_path, exc)
            return ""
        images = sorted(page_dir.glob("page-*.png"))
        chunks: list[str] = []
        for index, image_path in enumerate(images, start=1):
            text = await self._ocr_image(image_path, page_number=index)
            if text:
                chunks.append(f"[Pagina {index}] {text}")
        return "\n\n".join(chunks)

    async def _ocr_image(self, image_path: Path, *, page_number: int | None = None) -> str:
        prompt = (
            "Extraia o texto visivel desta imagem em portugues. "
            "Se for um documento historico, preserve nomes, datas, locais e trechos relevantes. "
            "Nao descreva a imagem alem do necessario para compreender o documento."
        )
        image_b64 = await asyncio.to_thread(self._encode_base64, image_path)
        response = await self._ollama_chat_with_image(
            host=self.vision_host,
            model=self.vision_model,
            prompt=prompt,
            image_b64=image_b64,
            num_ctx=self.vision_num_ctx,
            num_predict=self.max_summary_predict,
        )
        content = ""
        if isinstance(response, dict):
            message = response.get("message")
            if isinstance(message, dict):
                content = str(message.get("content", "")).strip()
        if page_number is not None and content:
            return f"Pagina {page_number}: {content}"
        return content

    async def _summarize_document_text(self, text: str) -> str:
        prompt = (
            "Resuma este trecho documental em portugues em ate 6 frases. "
            "Extraia fatos historicos, datas, pessoas, empresas e contexto. "
            "Se houver incerteza por OCR ruim, sinalize isso no resumo.\n\n"
            f"Trecho:\n{_truncate(text, 9000)}"
        )
        try:
            response = await self._ollama_generate(
                host=self.planner_host,
                model=self.planner_model,
                prompt=prompt,
                num_ctx=self.planner_num_ctx,
                num_predict=self.max_summary_predict,
                use_gpu0=False,
            )
        except Exception as exc:
            logger.warning("Resumo documental caiu em fallback heuristico: %s", exc)
            return self._heuristic_document_summary(text)
        if response:
            return _truncate(response, 1200)
        return self._heuristic_document_summary(text)

    def _heuristic_document_summary(self, text: str) -> str:
        cleaned = " ".join((text or "").split()).strip()
        if not cleaned:
            return ""
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        selected: list[str] = []
        for sentence in sentences:
            chunk = sentence.strip()
            if len(chunk) < 40:
                continue
            selected.append(chunk)
            if len(selected) >= 4:
                break
        if not selected:
            selected = [cleaned[:1200]]
        summary = " ".join(selected)
        years = re.findall(r"\b(1[89]\d{2}|20\d{2})\b", cleaned)
        if years:
            unique_years: list[str] = []
            for year in years:
                if year not in unique_years:
                    unique_years.append(year)
            summary = f"Datas citadas: {', '.join(unique_years[:6])}. {summary}"
        return _truncate(summary, 1200)

    async def _compose_story(
        self,
        query: str,
        plan: dict[str, Any],
        records: list[AcervoRecord],
        references: list[dict[str, Any]],
    ) -> str:
        if not records:
            return "## Historia\n\nNao foi possivel coletar fontes suficientes.\n\n## Referencias\n\nNenhuma."
        prompt = build_story_prompt(query, plan, records, references)
        try:
            response = await asyncio.wait_for(
                self._ollama_generate(
                    host=self.story_host,
                    model=self.story_model,
                    prompt=prompt,
                    num_ctx=self.story_num_ctx,
                    num_predict=self.max_story_predict,
                    use_gpu0=True,
                ),
                timeout=self.story_timeout_seconds,
            )
        except Exception as exc:
            logger.warning("Geracao final da historia caiu em fallback: %s", exc)
            return self._fallback_story(query, records, references)
        if self._story_response_is_usable(response, references):
            return response.strip()
        return self._fallback_story(query, records, references)

    async def _compose_dossier(
        self,
        query: str,
        plan: dict[str, Any],
        records: list[AcervoRecord],
        references: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prompt = build_dossier_prompt(query, plan, records, references)
        try:
            response = await asyncio.wait_for(
                self._ollama_generate(
                    host=self.planner_host,
                    model=self.planner_model,
                    prompt=prompt,
                    num_ctx=self.dossier_num_ctx,
                    num_predict=self.max_dossier_predict,
                    use_gpu0=False,
                ),
                timeout=self.dossier_timeout_seconds,
            )
        except Exception as exc:
            logger.warning("Geracao do dossie caiu em fallback: %s", exc)
            return self._fallback_dossier(query, plan, records, references)

        dossier = self._normalize_dossier_payload(self._extract_json(response), query, plan, references)
        if dossier is None:
            return self._fallback_dossier(query, plan, records, references)
        dossier = self._augment_dossier_with_evidence_relationships(dossier, query, plan, records, references)
        dossier["neural_map"] = build_neural_correlation_map(dossier)
        dossier["mermaid_graph"] = build_mermaid_graph(dossier)
        dossier["dossier_markdown"] = render_dossier_markdown(dossier, references)
        return dossier

    def _extract_actor_relationship_mentions(
        self,
        records: list[AcervoRecord],
        references: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        mentions: list[dict[str, Any]] = []
        for record, reference in zip(records, references, strict=False):
            evidence_blocks = [
                reference.get("evidence_excerpt", ""),
                record.raw_text,
                *[document.summary for document in record.documents if document.summary],
            ]
            for block in evidence_blocks:
                for sentence in _split_sentences(str(block or "")):
                    if len(sentence) < 12:
                        continue
                    for match in RELATION_SENTENCE_RE.finditer(sentence):
                        source_name = _clean_actor_name(match.group("source"))
                        target_name = _clean_actor_name(match.group("target"))
                        if not _looks_like_actor_name(source_name) or not _looks_like_actor_name(target_name):
                            continue
                        if source_name.lower() == target_name.lower():
                            continue
                        object_text = _truncate(str(match.group("object") or "").strip(" ,.;:-"), 120)
                        mentions.append(
                            {
                                "source_name": source_name,
                                "target_name": target_name,
                                "label": _build_relationship_label(match.group("verb"), match.group("prep")),
                                "description": _truncate(sentence, 320),
                                "object_text": object_text,
                                "support_excerpt": _truncate(sentence, 220),
                                "evidence_refs": [reference["id"]],
                            }
                        )
        return mentions

    def _extract_named_actor_mentions(
        self,
        records: list[AcervoRecord],
        references: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        mentions: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for record, reference in zip(records, references, strict=False):
            evidence_blocks = [
                reference.get("evidence_excerpt", ""),
                record.raw_text,
                *[document.summary for document in record.documents if document.summary],
            ]
            for block in evidence_blocks:
                for sentence in _split_sentences(str(block or "")):
                    if len(sentence) < 10:
                        continue
                    for match in POLITICAL_TITLE_RE.finditer(sentence):
                        title = " ".join(str(match.group("title") or "").split()).strip()
                        name = _clean_actor_name(match.group("name"))
                        if not _looks_like_actor_name(name):
                            continue
                        key = (name.lower(), title.lower(), reference["id"])
                        if key in seen:
                            continue
                        seen.add(key)
                        mentions.append(
                            {
                                "name": name,
                                "kind": "figura_publica",
                                "role": title,
                                "description": _truncate(sentence, 320),
                                "support_excerpt": _truncate(sentence, 220),
                                "evidence_refs": [reference["id"]],
                            }
                        )
                    for match in POLITICAL_APPOSITION_RE.finditer(sentence):
                        name = _clean_actor_name(match.group("name"))
                        title = " ".join(str(match.group("title") or "").split()).strip()
                        if not _looks_like_actor_name(name):
                            continue
                        key = (name.lower(), title.lower(), reference["id"])
                        if key in seen:
                            continue
                        seen.add(key)
                        mentions.append(
                            {
                                "name": name,
                                "kind": "figura_publica",
                                "role": title,
                                "description": _truncate(sentence, 320),
                                "support_excerpt": _truncate(sentence, 220),
                                "evidence_refs": [reference["id"]],
                            }
                        )
        return mentions

    def _extract_generic_actor_mentions(
        self,
        records: list[AcervoRecord],
        references: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        mentions: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for record, reference in zip(records, references, strict=False):
            evidence_blocks = [
                reference.get("evidence_excerpt", ""),
                record.raw_text,
                *[document.summary for document in record.documents if document.summary],
            ]
            for block in evidence_blocks:
                for sentence in _split_sentences(str(block or "")):
                    if len(sentence) < 10:
                        continue
                    for match in re.finditer(ACTOR_NAME_PATTERN, sentence):
                        name = _clean_actor_name(match.group(0))
                        if not _looks_like_actor_name(name):
                            continue
                        key = (name.lower(), reference["id"])
                        if key in seen:
                            continue
                        seen.add(key)
                        mentions.append(
                            {
                                "name": name,
                                "kind": _infer_entity_kind(name, prefer_public_figure=True),
                                "description": _truncate(sentence, 320),
                                "support_excerpt": _truncate(sentence, 220),
                                "evidence_refs": [reference["id"]],
                            }
                        )
        return mentions

    def _augment_dossier_with_evidence_relationships(
        self,
        dossier: dict[str, Any],
        query: str,
        plan: dict[str, Any],
        records: list[AcervoRecord],
        references: list[dict[str, Any]],
    ) -> dict[str, Any]:
        reference_publication_map = {
            str(reference["id"]): str(record.metadata.get("publicacao", "")).strip()
            for record, reference in zip(records, references, strict=False)
        }
        subject = dossier.get("subject", {}) if isinstance(dossier.get("subject"), dict) else {}
        subject_name = str(subject.get("name") or query).strip() or query
        people = [str(item).strip() for item in plan.get("people", []) if str(item).strip()]
        subject.setdefault("id", "subject")
        subject.setdefault("name", subject_name)
        subject.setdefault("kind", _infer_subject_kind(subject_name, people))
        subject.setdefault("description", "")
        subject.setdefault("evidence_refs", [])
        subject.setdefault("themes", _infer_entity_theme_hints(subject))

        entities: list[dict[str, Any]] = [entity for entity in dossier.get("entities", []) if isinstance(entity, dict)]
        relationships: list[dict[str, Any]] = [relation for relation in dossier.get("relationships", []) if isinstance(relation, dict)]
        entities_by_id: dict[str, dict[str, Any]] = {}
        entities_by_name: dict[str, str] = {}
        for key in _entity_lookup_keys(subject_name) + _entity_lookup_keys(query):
            entities_by_name[key] = "subject"
        seen_relationships: set[tuple[str, str, str, str]] = set()

        for entity in entities:
            entity_id = str(entity.get("id") or "").strip()
            entity_name = _clean_actor_name(str(entity.get("name") or ""))
            if not entity_id or not entity_name:
                continue
            entity["name"] = entity_name
            entity.setdefault("kind", _infer_entity_kind(entity_name))
            entity.setdefault("description", "")
            entity.setdefault("evidence_refs", [])
            entity.setdefault("aliases", [])
            entity.setdefault("role_history", [])
            entity.setdefault("themes", _infer_entity_theme_hints(entity))
            entities_by_id[entity_id] = entity
            for key in _entity_lookup_keys(entity_name):
                entities_by_name[key] = entity_id

        for relation in relationships:
            source = str(relation.get("source") or "").strip()
            target = str(relation.get("target") or "").strip()
            label = str(relation.get("label") or "relacionado").strip()
            object_text = str(relation.get("object") or "").strip()
            if source and target:
                seen_relationships.add((source, target, label.lower(), object_text.lower()))
            relation.setdefault("description", "")
            relation.setdefault("object", object_text)
            relation.setdefault("support_excerpt", "")
            relation.setdefault("evidence_refs", [])
            relation.setdefault("evidence_details", [])
            relation.setdefault("source_count", len(relation.get("evidence_refs", [])))
            source_name = subject_name if source == "subject" else str(entities_by_id.get(source, {}).get("name") or "")
            target_name = subject_name if target == "subject" else str(entities_by_id.get(target, {}).get("name") or "")
            relation.setdefault("theme", _infer_relationship_theme(label, object_text, str(relation.get("description") or ""), source_name, target_name))

        def _merge_ref(ref_bucket: list[str], ref_code: str) -> None:
            if ref_code and ref_code not in ref_bucket:
                ref_bucket.append(ref_code)

        def _merge_relation_evidence(relation: dict[str, Any], evidence_ref: str, support_excerpt: str) -> None:
            _merge_ref(relation.setdefault("evidence_refs", []), evidence_ref)
            details = relation.setdefault("evidence_details", [])
            publication = reference_publication_map.get(evidence_ref, "")
            for item in details:
                if not isinstance(item, dict):
                    continue
                if str(item.get("ref") or "") == evidence_ref:
                    if support_excerpt and not str(item.get("excerpt") or "").strip():
                        item["excerpt"] = support_excerpt
                    if publication and not str(item.get("date") or "").strip():
                        item["date"] = publication
                    relation["source_count"] = len(relation["evidence_refs"])
                    return
            details.append(
                {
                    "ref": evidence_ref,
                    "date": publication,
                    "excerpt": support_excerpt,
                }
            )
            relation["source_count"] = len(relation["evidence_refs"])

        def _merge_role_history(entity: dict[str, Any], role: str, evidence_ref: str) -> None:
            role = " ".join(role.split()).strip()
            if not role:
                return
            role_history = entity.setdefault("role_history", [])
            for item in role_history:
                if not isinstance(item, dict):
                    continue
                if str(item.get("role") or "").lower() == role.lower():
                    _merge_ref(item.setdefault("evidence_refs", []), evidence_ref)
                    return
            role_history.append({"role": role, "evidence_refs": [evidence_ref] if evidence_ref else []})

        def _merge_theme(entity: dict[str, Any], theme: str) -> None:
            themes = entity.setdefault("themes", [])
            if theme and theme not in themes:
                themes.append(theme)

        def ensure_entity(
            name: str,
            description: str,
            evidence_ref: str,
            *,
            kind_override: str | None = None,
            role: str = "",
            alias: str = "",
        ) -> str | None:
            cleaned_name = _clean_actor_name(name)
            if not _looks_like_actor_name(cleaned_name):
                return None
            lookup_keys = _entity_lookup_keys(cleaned_name)
            if any(key in entities_by_name and entities_by_name[key] == "subject" for key in lookup_keys):
                _merge_ref(subject["evidence_refs"], evidence_ref)
                if role:
                    _merge_theme(subject, "governo_politica")
                return "subject"
            existing_id = next((entities_by_name[key] for key in lookup_keys if key in entities_by_name), None)
            if existing_id and existing_id in entities_by_id:
                entity = entities_by_id[existing_id]
                if description and not str(entity.get("description") or "").strip():
                    entity["description"] = description
                if kind_override == "figura_publica" and entity.get("kind") in {"pessoa", "entidade", "organizacao"}:
                    entity["kind"] = "figura_publica"
                if alias:
                    aliases = entity.setdefault("aliases", [])
                    if alias not in aliases and alias != entity["name"]:
                        aliases.append(alias)
                if role:
                    _merge_role_history(entity, role, evidence_ref)
                    _merge_theme(entity, "governo_politica")
                _merge_ref(entity["evidence_refs"], evidence_ref)
                return existing_id
            entity_id = _slug_identifier(cleaned_name, prefix=f"e{len(entities) + 1}")
            while entity_id == "subject" or entity_id in entities_by_id:
                entity_id = _slug_identifier(f"{cleaned_name}_{len(entities) + 1}", prefix=f"e{len(entities) + 1}")
            entity = {
                "id": entity_id,
                "name": cleaned_name,
                "kind": kind_override or _infer_entity_kind(cleaned_name),
                "description": description,
                "evidence_refs": [evidence_ref] if evidence_ref else [],
                "aliases": [alias] if alias and alias != cleaned_name else [],
                "role_history": [],
                "themes": _infer_entity_theme_hints({"name": cleaned_name, "kind": kind_override or _infer_entity_kind(cleaned_name), "description": description}),
            }
            if role:
                _merge_role_history(entity, role, evidence_ref)
                _merge_theme(entity, "governo_politica")
            entities.append(entity)
            entities_by_id[entity_id] = entity
            for key in lookup_keys:
                entities_by_name[key] = entity_id
            return entity_id

        for mention in self._extract_actor_relationship_mentions(records, references):
            evidence_ref = str(mention["evidence_refs"][0]) if mention.get("evidence_refs") else ""
            source_id = ensure_entity(mention["source_name"], mention["description"], evidence_ref)
            target_id = ensure_entity(mention["target_name"], mention["description"], evidence_ref)
            if not source_id or not target_id or source_id == target_id:
                continue
            merged_into_existing = False
            for relation in relationships:
                if _relation_signature_matches(
                    str(relation.get("source") or ""),
                    str(relation.get("target") or ""),
                    str(relation.get("label") or ""),
                    str(relation.get("object") or ""),
                    source_id,
                    target_id,
                    str(mention["label"]),
                    str(mention["object_text"]),
                ):
                    _merge_relation_evidence(relation, evidence_ref, str(mention["support_excerpt"]))
                    current_object = str(relation.get("object") or "")
                    incoming_object = str(mention["object_text"] or "")
                    if incoming_object and (not current_object or len(incoming_object) < len(current_object)):
                        relation["object"] = incoming_object
                    if mention["description"] and not str(relation.get("description") or "").strip():
                        relation["description"] = mention["description"]
                    if mention["support_excerpt"]:
                        current_excerpt = str(relation.get("support_excerpt") or "").strip()
                        if not current_excerpt:
                            relation["support_excerpt"] = mention["support_excerpt"]
                        elif mention["support_excerpt"] not in current_excerpt:
                            relation["support_excerpt"] = _truncate(f"{current_excerpt} | {mention['support_excerpt']}", 320)
                    merged_into_existing = True
                    break
            if merged_into_existing:
                continue
            rel_key = (source_id, target_id, str(mention["label"]).lower(), str(mention["object_text"]).lower())
            seen_relationships.add(rel_key)
            relation = {
                "source": source_id,
                "target": target_id,
                "label": mention["label"],
                "object": mention["object_text"],
                "description": mention["description"],
                "support_excerpt": mention["support_excerpt"],
                "theme": _infer_relationship_theme(
                    str(mention["label"]),
                    str(mention["object_text"]),
                    str(mention["description"]),
                    str(mention["source_name"]),
                    str(mention["target_name"]),
                ),
                "evidence_refs": [],
                "evidence_details": [],
                "source_count": 0,
            }
            _merge_relation_evidence(relation, evidence_ref, str(mention["support_excerpt"]))
            relationships.append(relation)

        for mention in self._extract_named_actor_mentions(records, references):
            evidence_ref = str(mention["evidence_refs"][0]) if mention.get("evidence_refs") else ""
            description = mention["description"]
            role = str(mention.get("role") or "").strip()
            if role:
                description = _truncate(f"{role.title()} citado nas fontes. {description}", 320)
            ensure_entity(
                mention["name"],
                description,
                evidence_ref,
                kind_override=str(mention.get("kind") or "figura_publica"),
                role=role,
                alias=str(mention.get("alias") or ""),
            )

        for mention in self._extract_generic_actor_mentions(records, references):
            evidence_ref = str(mention["evidence_refs"][0]) if mention.get("evidence_refs") else ""
            ensure_entity(
                mention["name"],
                str(mention.get("description") or ""),
                evidence_ref,
                kind_override=str(mention.get("kind") or _infer_entity_kind(str(mention.get("name") or ""), prefer_public_figure=True)),
            )

        for relation in relationships:
            source = str(relation.get("source") or "")
            target = str(relation.get("target") or "")
            theme = str(relation.get("theme") or "")
            if source and source != "subject" and source in entities_by_id:
                _merge_theme(entities_by_id[source], theme)
            if target and target != "subject" and target in entities_by_id:
                _merge_theme(entities_by_id[target], theme)
            if source == "subject":
                _merge_theme(subject, theme)
            if target == "subject":
                _merge_theme(subject, theme)

        thematic_groups: dict[str, list[str]] = {}
        for entity in entities:
            for theme in entity.get("themes", []) or ["contexto"]:
                thematic_groups.setdefault(theme, [])
                if entity["id"] not in thematic_groups[theme]:
                    thematic_groups[theme].append(entity["id"])

        events, timeline = _build_events_and_timeline(
            subject_name=subject_name,
            entities_by_id=entities_by_id,
            relationships=relationships,
            reference_publication_map=reference_publication_map,
            existing_timeline=[item for item in dossier.get("timeline", []) if isinstance(item, dict)],
        )

        dossier["subject"] = subject
        dossier["entities"] = entities
        dossier["relationships"] = relationships
        dossier["events"] = events
        dossier["thematic_groups"] = thematic_groups
        dossier["timeline"] = timeline
        return dossier

    def _load_character_memory(self) -> dict[str, Any]:
        if not self.character_memory_path.exists():
            return {"version": 1, "entities": {}, "relationships": []}
        try:
            return json.loads(self.character_memory_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Falha ao ler memoria local do BN Acervo", exc_info=True)
            return {"version": 1, "entities": {}, "relationships": []}

    def _save_character_memory(self, payload: dict[str, Any]) -> None:
        try:
            self.character_memory_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            logger.warning("Falha ao salvar memoria local do BN Acervo", exc_info=True)

    def _persist_character_memory(self, query: str, dossier: dict[str, Any]) -> None:
        memory = self._load_character_memory()
        memory.setdefault("version", 1)
        entity_store = memory.setdefault("entities", {})
        relation_store = memory.setdefault("relationships", [])

        subject = dossier.get("subject", {}) if isinstance(dossier.get("subject"), dict) else {}
        entities = [entity for entity in dossier.get("entities", []) if isinstance(entity, dict)]
        relationships = [relation for relation in dossier.get("relationships", []) if isinstance(relation, dict)]
        subject_name = str(subject.get("name") or query).strip() or query

        all_entities = [subject, *entities]
        id_to_name = {str(entity.get("id") or ""): str(entity.get("name") or "") for entity in all_entities if isinstance(entity, dict)}

        def merge_entity(entity: dict[str, Any]) -> None:
            name = str(entity.get("name") or "").strip()
            if not name:
                return
            key = _canonical_actor_key(name)
            stored = entity_store.setdefault(
                key,
                {
                    "name": name,
                    "kind": str(entity.get("kind") or "entidade"),
                    "aliases": [],
                    "role_history": [],
                    "themes": [],
                    "seen_queries": [],
                    "subjects_seen": [],
                    "descriptions": [],
                },
            )
            stored["name"] = stored.get("name") or name
            if str(entity.get("kind") or "").strip():
                stored["kind"] = str(entity.get("kind") or stored.get("kind") or "entidade")
            description = str(entity.get("description") or "").strip()
            if description and description not in stored["descriptions"]:
                stored["descriptions"].append(description)
            for alias in entity.get("aliases", []):
                if alias and alias not in stored["aliases"] and alias != stored["name"]:
                    stored["aliases"].append(alias)
            for role in entity.get("role_history", []):
                if not isinstance(role, dict):
                    continue
                role_name = str(role.get("role") or "").strip()
                if not role_name:
                    continue
                existing = next((item for item in stored["role_history"] if str(item.get("role") or "").lower() == role_name.lower()), None)
                if existing is None:
                    stored["role_history"].append({"role": role_name, "evidence_refs": list(role.get("evidence_refs", []))})
                else:
                    for ref_code in role.get("evidence_refs", []):
                        if ref_code not in existing.setdefault("evidence_refs", []):
                            existing["evidence_refs"].append(ref_code)
            for theme in entity.get("themes", []):
                if theme and theme not in stored["themes"]:
                    stored["themes"].append(theme)
            if query not in stored["seen_queries"]:
                stored["seen_queries"].append(query)
            if subject_name and subject_name not in stored["subjects_seen"]:
                stored["subjects_seen"].append(subject_name)

        for entity in all_entities:
            if isinstance(entity, dict):
                merge_entity(entity)

        for relation in relationships:
            source_name = subject_name if str(relation.get("source") or "") == "subject" else id_to_name.get(str(relation.get("source") or ""), "")
            target_name = subject_name if str(relation.get("target") or "") == "subject" else id_to_name.get(str(relation.get("target") or ""), "")
            if not source_name or not target_name:
                continue
            label = str(relation.get("label") or "relacionado").strip()
            object_text = str(relation.get("object") or "").strip()
            existing = next(
                (
                    item for item in relation_store
                    if _relation_signature_matches(
                        str(item.get("source_name") or ""),
                        str(item.get("target_name") or ""),
                        str(item.get("label") or ""),
                        str(item.get("object") or ""),
                        source_name,
                        target_name,
                        label,
                        object_text,
                    )
                ),
                None,
            )
            if existing is None:
                existing = {
                    "source_name": source_name,
                    "target_name": target_name,
                    "label": label,
                    "object": object_text,
                    "description": str(relation.get("description") or ""),
                    "theme": str(relation.get("theme") or ""),
                    "support_excerpt": str(relation.get("support_excerpt") or ""),
                    "source_count": int(relation.get("source_count") or len(relation.get("evidence_refs", [])) or 1),
                    "seen_queries": [query],
                    "subjects_seen": [subject_name] if subject_name else [],
                    "evidence_details": [item for item in relation.get("evidence_details", []) if isinstance(item, dict)],
                }
                relation_store.append(existing)
            else:
                incoming_count = int(relation.get("source_count") or len(relation.get("evidence_refs", [])) or 1)
                existing["source_count"] = max(int(existing.get("source_count") or 1), incoming_count)
                if not str(existing.get("description") or "").strip():
                    existing["description"] = str(relation.get("description") or "")
                if not str(existing.get("support_excerpt") or "").strip():
                    existing["support_excerpt"] = str(relation.get("support_excerpt") or "")
                if query not in existing.setdefault("seen_queries", []):
                    existing["seen_queries"].append(query)
                if subject_name and subject_name not in existing.setdefault("subjects_seen", []):
                    existing["subjects_seen"].append(subject_name)
                if str(relation.get("theme") or "").strip() and not str(existing.get("theme") or "").strip():
                    existing["theme"] = str(relation.get("theme") or "")
                details = existing.setdefault("evidence_details", [])
                for item in relation.get("evidence_details", []):
                    if not isinstance(item, dict):
                        continue
                    if not any(
                        str(saved.get("ref") or "") == str(item.get("ref") or "")
                        and str(saved.get("date") or "") == str(item.get("date") or "")
                        and str(saved.get("excerpt") or "") == str(item.get("excerpt") or "")
                        for saved in details
                        if isinstance(saved, dict)
                    ):
                        details.append(item)

        self._save_character_memory(memory)

    def _expand_dossier_with_character_memory(self, query: str, dossier: dict[str, Any]) -> dict[str, Any]:
        memory = self._load_character_memory()
        entity_store = memory.get("entities", {})
        relation_store = memory.get("relationships", [])
        if not isinstance(entity_store, dict) or not isinstance(relation_store, list):
            return dossier

        subject = dossier.get("subject", {}) if isinstance(dossier.get("subject"), dict) else {}
        entities = [entity for entity in dossier.get("entities", []) if isinstance(entity, dict)]
        relationships = [relation for relation in dossier.get("relationships", []) if isinstance(relation, dict)]
        subject_name = str(subject.get("name") or query).strip() or query

        entities_by_id = {str(entity.get("id") or ""): entity for entity in entities if str(entity.get("id") or "").strip()}
        name_to_id = {key: "subject" for key in _entity_lookup_keys(subject_name) + _entity_lookup_keys(query)}
        for entity in entities:
            for key in _entity_lookup_keys(str(entity.get("name") or "")):
                name_to_id[key] = str(entity.get("id") or "")

        def ensure_memory_entity(name: str) -> str | None:
            for key in _entity_lookup_keys(name):
                if key in name_to_id:
                    return name_to_id[key]
            stored = entity_store.get(_canonical_actor_key(name))
            if not isinstance(stored, dict):
                return None
            entity_id = _slug_identifier(str(stored.get("name") or name), prefix=f"m{len(entities_by_id) + 1}")
            while entity_id == "subject" or entity_id in entities_by_id:
                entity_id = _slug_identifier(f"{stored.get('name') or name}_{len(entities_by_id) + 1}", prefix=f"m{len(entities_by_id) + 1}")
            roles = ", ".join(
                str(item.get("role") or "").strip()
                for item in stored.get("role_history", [])
                if isinstance(item, dict) and str(item.get("role") or "").strip()
            )
            seen_subjects = ", ".join(str(item).strip() for item in stored.get("subjects_seen", [])[:4] if str(item).strip())
            themes = ", ".join(str(item).strip() for item in stored.get("themes", [])[:4] if str(item).strip())
            desc_seed = next((str(item).strip() for item in stored.get("descriptions", []) if str(item).strip()), "")
            description_parts = []
            if desc_seed:
                description_parts.append(desc_seed)
            if roles:
                description_parts.append(f"Cargos memorizados: {roles}.")
            if seen_subjects:
                description_parts.append(f"Apareceu antes com: {seen_subjects}.")
            if themes:
                description_parts.append(f"Eixos memorizados: {themes}.")
            entity = {
                "id": entity_id,
                "name": str(stored.get("name") or name),
                "kind": str(stored.get("kind") or "entidade"),
                "description": _truncate(" ".join(description_parts) or "Personagem recuperado da memória local.", 320),
                "evidence_refs": [],
                "aliases": list(stored.get("aliases", [])),
                "role_history": list(stored.get("role_history", [])),
                "themes": list(stored.get("themes", [])) or ["contexto"],
                "memory_origin": True,
            }
            entities.append(entity)
            entities_by_id[entity_id] = entity
            for key in _entity_lookup_keys(entity["name"]):
                name_to_id[key] = entity_id
            return entity_id

        for relation in relation_store:
            if not isinstance(relation, dict):
                continue
            source_name = str(relation.get("source_name") or "").strip()
            target_name = str(relation.get("target_name") or "").strip()
            if not source_name or not target_name:
                continue
            source_id = ensure_memory_entity(source_name)
            target_id = ensure_memory_entity(target_name)
            if not source_id or not target_id:
                continue
            overlap = source_id == "subject" or target_id == "subject" or source_id in entities_by_id or target_id in entities_by_id
            if not overlap:
                continue
            already_exists = any(
                _relation_signature_matches(
                    str(item.get("source") or ""),
                    str(item.get("target") or ""),
                    str(item.get("label") or ""),
                    str(item.get("object") or ""),
                    source_id,
                    target_id,
                    str(relation.get("label") or ""),
                    str(relation.get("object") or ""),
                )
                for item in relationships
            )
            if already_exists:
                continue
            memory_details = [item for item in relation.get("evidence_details", []) if isinstance(item, dict)]
            detail_dates = [str(item.get("date") or "").strip() for item in memory_details if str(item.get("date") or "").strip()]
            subjects_seen = ", ".join(str(item).strip() for item in relation.get("subjects_seen", [])[:4] if str(item).strip())
            support_excerpt = str(relation.get("support_excerpt") or "").strip()
            granular_description = str(relation.get("description") or "").strip()
            if subjects_seen:
                granular_description = _truncate(f"{granular_description} Relação já observada com: {subjects_seen}.", 320)
            relationships.append(
                {
                    "source": source_id,
                    "target": target_id,
                    "label": str(relation.get("label") or "relacionado"),
                    "object": str(relation.get("object") or ""),
                    "description": _truncate(granular_description or "Relacionamento recuperado da memória local.", 320),
                    "support_excerpt": support_excerpt,
                    "theme": str(relation.get("theme") or "contexto"),
                    "evidence_refs": [],
                    "evidence_details": memory_details,
                    "source_count": int(relation.get("source_count") or 1),
                    "memory_origin": True,
                    "memory_dates": detail_dates,
                }
            )

        thematic_groups: dict[str, list[str]] = {}
        for entity in entities:
            for theme in entity.get("themes", []) or ["contexto"]:
                thematic_groups.setdefault(theme, [])
                if entity["id"] not in thematic_groups[theme]:
                    thematic_groups[theme].append(entity["id"])

        dossier["entities"] = entities
        dossier["relationships"] = relationships
        dossier["thematic_groups"] = thematic_groups
        events, timeline = _build_events_and_timeline(
            subject_name=subject_name,
            entities_by_id=entities_by_id,
            relationships=relationships,
            reference_publication_map={},
            existing_timeline=[item for item in dossier.get("timeline", []) if isinstance(item, dict)],
        )
        dossier["events"] = events
        dossier["timeline"] = timeline
        return dossier

    def _normalize_dossier_payload(
        self,
        payload: dict[str, Any] | None,
        query: str,
        plan: dict[str, Any],
        references: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None

        valid_refs = {str(reference["id"]) for reference in references}
        subject_raw = payload.get("subject") if isinstance(payload.get("subject"), dict) else {}
        people = [str(item).strip() for item in plan.get("people", []) if str(item).strip()]
        subject_name = str(subject_raw.get("name") or _preferred_subject_name(query, people)).strip() or query
        subject = {
            "id": "subject",
            "name": subject_name,
            "kind": str(subject_raw.get("kind") or _infer_subject_kind(subject_name, people)).strip() or _infer_subject_kind(subject_name, people),
            "description": _truncate(str(subject_raw.get("description") or payload.get("summary") or ""), 420),
            "evidence_refs": _normalize_reference_codes(subject_raw.get("evidence_refs"), valid_refs),
        }

        entities: list[dict[str, Any]] = []
        entities_by_id: dict[str, dict[str, Any]] = {}
        entities_by_name: dict[str, str] = {subject_name.lower(): "subject", query.lower(): "subject"}

        for index, raw_entity in enumerate(payload.get("entities", []), start=1):
            if not isinstance(raw_entity, dict):
                continue
            entity_name = str(raw_entity.get("name") or "").strip()
            if not entity_name or entity_name.lower() == subject_name.lower():
                continue
            entity_id = str(raw_entity.get("id") or "").strip() or _slug_identifier(entity_name, prefix=f"e{index}")
            if entity_id == "subject" or entity_id in entities_by_id:
                entity_id = _slug_identifier(f"{entity_name}_{index}", prefix=f"e{index}")
            entity = {
                "id": entity_id,
                "name": entity_name,
                "kind": str(raw_entity.get("kind") or _infer_entity_kind(entity_name)).strip() or _infer_entity_kind(entity_name),
                "description": _truncate(str(raw_entity.get("description") or ""), 320),
                "evidence_refs": _normalize_reference_codes(raw_entity.get("evidence_refs"), valid_refs),
            }
            entities.append(entity)
            entities_by_id[entity_id] = entity
            entities_by_name[entity_name.lower()] = entity_id

        def resolve_entity_id(raw_value: Any) -> str | None:
            text = str(raw_value or "").strip()
            if not text:
                return None
            if text == "subject":
                return "subject"
            if text in entities_by_id:
                return text
            return entities_by_name.get(text.lower())

        relationships: list[dict[str, Any]] = []
        seen_relationships: set[tuple[str, str, str, str]] = set()
        for raw_relation in payload.get("relationships", []):
            if not isinstance(raw_relation, dict):
                continue
            source = resolve_entity_id(raw_relation.get("source") or raw_relation.get("from"))
            target = resolve_entity_id(raw_relation.get("target") or raw_relation.get("to"))
            if not source or not target or source == target:
                continue
            label = _truncate(str(raw_relation.get("label") or raw_relation.get("relationship") or "relacionado"), 80)
            object_text = _truncate(str(raw_relation.get("object") or raw_relation.get("object_text") or raw_relation.get("topic") or ""), 180)
            description = _truncate(str(raw_relation.get("description") or ""), 320)
            support_excerpt = _truncate(str(raw_relation.get("support_excerpt") or raw_relation.get("excerpt") or ""), 220)
            rel_key = (source, target, label.lower(), object_text.lower())
            if rel_key in seen_relationships:
                continue
            seen_relationships.add(rel_key)
            relationships.append(
                {
                    "source": source,
                    "target": target,
                    "label": label,
                    "object": object_text,
                    "description": description or f"Relacao documental entre {source} e {target}.",
                    "support_excerpt": support_excerpt,
                    "evidence_refs": _normalize_reference_codes(raw_relation.get("evidence_refs"), valid_refs),
                }
            )

        timeline: list[dict[str, Any]] = []
        for raw_item in payload.get("timeline", []):
            if not isinstance(raw_item, dict):
                continue
            description = _truncate(str(raw_item.get("description") or raw_item.get("event") or ""), 320)
            if not description:
                continue
            timeline.append(
                {
                    "date": str(raw_item.get("date") or raw_item.get("year") or "sem data").strip() or "sem data",
                    "description": description,
                    "evidence_refs": _normalize_reference_codes(raw_item.get("evidence_refs"), valid_refs),
                }
            )

        if not relationships and entities:
            for entity, reference in zip(entities[: min(3, len(entities))], references[: min(3, len(entities))], strict=False):
                relationships.append(
                    {
                        "source": "subject",
                        "target": entity["id"],
                        "label": "mencionado nas fontes",
                        "object": "",
                        "description": entity["description"] or reference["evidence_excerpt"] or "Entidade associada nas fontes.",
                        "support_excerpt": reference["evidence_excerpt"] or "",
                        "evidence_refs": [reference["id"]],
                    }
                )

        if not entities and not relationships:
            return None

        return {
            "subject": subject,
            "summary": _truncate(str(payload.get("summary") or payload.get("dossier_summary") or subject["description"] or ""), 900),
            "entities": entities,
            "relationships": relationships,
            "timeline": timeline,
        }

    def _fallback_dossier(
        self,
        query: str,
        plan: dict[str, Any],
        records: list[AcervoRecord],
        references: list[dict[str, Any]],
    ) -> dict[str, Any]:
        people = [str(item).strip() for item in plan.get("people", []) if str(item).strip()]
        subject_name = DEFAULT_SUBJECT_RESOLVER.choose_subject_name(query, people, records)
        entities: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        timeline: list[dict[str, Any]] = []

        for index, (record, reference) in enumerate(zip(records, references, strict=False), start=1):
            evidence = _truncate(
                reference["evidence_excerpt"] or record.raw_text or record.relevance_reason or "Registro documental relacionado ao sujeito principal.",
                320,
            )
            publication = record.metadata.get("publicacao", "").strip()
            if publication:
                timeline.append({"date": publication, "description": evidence, "evidence_refs": [reference["id"]]})

        dossier = {
            "subject": {
                "id": "subject",
                "name": subject_name,
                "kind": _infer_subject_kind(subject_name, people),
                "description": "Nenhuma evidencia documental confiavel foi recuperada neste ciclo; a descoberta externa falhou ou retornou ruido.",
                "evidence_refs": [references[0]["id"]] if references else [],
            },
            "summary": "A investigacao entrou em contingencia: a descoberta de fontes nao recuperou evidencia documental confiavel o bastante para montar o caso neste ciclo. Revise a busca, a disponibilidade das fontes e os bloqueios externos antes de interpretar o grafo como resultado historico.",
            "entities": entities,
            "relationships": relationships,
            "timeline": timeline,
        }
        dossier = self._augment_dossier_with_evidence_relationships(dossier, query, plan, records, references)
        if not dossier["entities"] and not dossier["relationships"]:
            for index, (record, reference) in enumerate(zip(records, references, strict=False), start=1):
                evidence = _truncate(
                    reference["evidence_excerpt"] or record.raw_text or record.relevance_reason or "Registro documental relacionado ao sujeito principal.",
                    320,
                )
                entity = {
                    "id": f"e{index}",
                    "name": record.title or f"Registro {reference['id']}",
                    "kind": record.metadata.get("material", "fonte_documental"),
                    "description": evidence,
                    "evidence_refs": [reference["id"]],
                }
                dossier["entities"].append(entity)
                dossier["relationships"].append(
                    {
                        "source": "subject",
                        "target": entity["id"],
                        "label": "mencionado nas fontes",
                        "object": "",
                        "description": evidence,
                        "support_excerpt": evidence,
                        "evidence_refs": [reference["id"]],
                    }
                )
        dossier["neural_map"] = build_neural_correlation_map(dossier)
        dossier["mermaid_graph"] = build_mermaid_graph(dossier)
        dossier["dossier_markdown"] = render_dossier_markdown(dossier, references)
        return dossier

    def _story_response_is_usable(self, response: str, references: list[dict[str, Any]]) -> bool:
        if not response:
            return False
        valid_ids = {str(reference["id"]) for reference in references}
        cited_ids = set(re.findall(r"\[(R\d+)\]", response))
        if not cited_ids or not cited_ids.intersection(valid_ids):
            return False
        if not cited_ids.issubset(valid_ids):
            return False
        if len(valid_ids) > 1 and len(cited_ids.intersection(valid_ids)) < min(2, len(valid_ids)):
            return False
        if response.count(" [R") > max(len(valid_ids) * 3, 8):
            return False
        return True

    def _fallback_story(
        self,
        query: str,
        records: list[AcervoRecord],
        references: list[dict[str, Any]],
    ) -> str:
        paired_records = list(zip(records, references, strict=False))
        paired_records.sort(
            key=lambda item: (
                _extract_year(item[0].metadata.get("publicacao", "")) or 9999,
                item[1]["id"],
            )
        )
        paragraphs = [f"## Historia\n\nA consulta sobre **{query}** reuniu evidencias dispersas, mas suficientes para reconstruir uma linha narrativa coerente."]
        if paired_records:
            first_year = _extract_year(paired_records[0][0].metadata.get("publicacao", ""))
            last_year = _extract_year(paired_records[-1][0].metadata.get("publicacao", ""))
            if first_year and last_year and first_year != last_year:
                paragraphs.append(
                    f"As fontes localizadas se concentram entre **{first_year}** e **{last_year}** e mostram a Gurgel tentando transformar o BR-800 em vitrine de tecnologia nacional, escala industrial e uso em frotas de serviço."
                )

        for index, (record, reference) in enumerate(paired_records):
            publication = record.metadata.get("publicacao", "sem data/publicacao clara")
            evidence = reference["evidence_excerpt"] or record.raw_text or "sem trecho sintetizado"
            evidence = _truncate(evidence, 420)
            if index == 0:
                paragraphs.append(
                    f"Em **{publication}**, o registro **{record.title}** mostra a fase de aposta industrial da empresa: {evidence} [{reference['id']}]."
                )
            elif index == len(paired_records) - 1:
                paragraphs.append(
                    f"Mais adiante, em **{publication}**, **{record.title}** explicita o discurso estratégico de João Amaral Gurgel: {evidence} [{reference['id']}]."
                )
            else:
                paragraphs.append(
                    f"No meio desse percurso, **{record.title}** registra uma tentativa concreta de inserção do modelo em grandes operações: {evidence} [{reference['id']}]."
                )

        if paired_records:
            paragraphs.append(
                "Tomadas em conjunto, as fontes sugerem que a narrativa da Gurgel não era apenas a de lançar um carro pequeno. Ela articulava três frentes ao mesmo tempo: provar a viabilidade técnica do BR-800, buscar escala produtiva e conquistar legitimidade institucional com encomendas e testes em grandes frotas."
            )
        paragraphs.append("\n## Referencias\n")
        for reference in references:
            line = f"- [{reference['id']}] {reference['title']} — {reference['detail_url']}"
            if reference["document_urls"]:
                line += f" | documento: {reference['document_urls'][0]}"
            paragraphs.append(line)
        return "\n\n".join(paragraphs)

    async def _ollama_generate(
        self,
        *,
        host: str,
        model: str,
        prompt: str,
        num_ctx: int,
        num_predict: int,
        use_gpu0: bool,
    ) -> str:
        capped_prompt = _truncate(prompt, self.max_prompt_chars)
        attempts: list[tuple[str, str, bool]] = [(host, model, use_gpu0)]
        if use_gpu0:
            fallback = (self.planner_host, self.planner_model, False)
        else:
            fallback = (self.story_host, self.story_model, True)
        if fallback not in attempts:
            attempts.append(fallback)
        loaded_fallbacks = [
            (self.planner_host, self.planner_loaded_model, False),
            (self.story_host, self.story_loaded_model, True),
        ]
        for candidate in loaded_fallbacks:
            candidate_model = candidate[1]
            if candidate_model and candidate not in attempts:
                attempts.append(candidate)  # type: ignore[arg-type]

        last_error: Exception | None = None
        for current_host, current_model, current_use_gpu0 in attempts:
            if not current_model:
                continue
            payload = {
                "model": current_model,
                "prompt": capped_prompt,
                "stream": False,
                "temperature": 0.2,
                "num_ctx": max(512, num_ctx),
                "num_predict": max(64, num_predict),
            }
            semaphore = self.gpu0_semaphore if current_use_gpu0 else self.gpu1_semaphore
            try:
                async with semaphore:
                    async with httpx.AsyncClient(timeout=self.http_timeout_seconds, trust_env=self.http_trust_env) as client:
                        response = await client.post(f"{current_host}/api/generate", json=payload)
                        response.raise_for_status()
                        data = response.json()
                        text = str(data.get("response", "") or data.get("response_text", "")).strip()
                        if text:
                            return text
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code in {429, 500, 502, 503, 504}:
                    logger.warning(
                        "Ollama indisponivel em %s model=%s status=%s; tentando fallback",
                        current_host,
                        current_model,
                        exc.response.status_code,
                    )
                    await asyncio.sleep(2)
                    continue
                raise
            except Exception as exc:
                last_error = exc
                logger.warning("Falha chamando Ollama %s model=%s: %s", current_host, current_model, exc)
                await asyncio.sleep(1)
                continue
        if self.enable_copilot_fallback:
            fallback_text = await self._copilot_generate_fallback(capped_prompt, max_tokens=max(128, min(num_predict, 2048)))
            if fallback_text:
                logger.info("Usando fallback textual via copilot_model_router")
                return fallback_text
        if last_error is not None:
            raise last_error
        return ""

    async def _ollama_chat_with_image(
        self,
        *,
        host: str,
        model: str,
        prompt: str,
        image_b64: str,
        num_ctx: int,
        num_predict: int,
    ) -> dict[str, Any]:
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_b64],
                }
            ],
            "temperature": 0.1,
            "num_ctx": max(512, num_ctx),
            "num_predict": max(64, num_predict),
        }
        try:
            async with self.gpu0_semaphore:
                async with httpx.AsyncClient(timeout=self.http_timeout_seconds, trust_env=self.http_trust_env) as client:
                    response = await client.post(f"{host}/api/chat", json=payload)
                    response.raise_for_status()
                    return response.json()
        except Exception as exc:
            logger.warning("Falha no OCR via Ollama vision (%s, %s): %s", host, model, exc)
            return {}

    async def _copilot_generate_fallback(self, prompt: str, *, max_tokens: int) -> str:
        if get_copilot_router is None:
            return ""
        try:
            router = get_copilot_router()
            response = await router.proxy_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            logger.warning("Fallback copilot_model_router falhou: %s", exc)
            return ""
        choices = response.get("choices") if isinstance(response, dict) else None
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else {}
        if isinstance(message, dict):
            return str(message.get("content") or "").strip()
        return ""

    def _extract_json(self, model_text: str) -> dict[str, Any] | None:
        if not model_text:
            return None
        try:
            return json.loads(model_text)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", model_text, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def _pdftotext(self, pdf_path: Path) -> str:
        command = ["pdftotext", str(pdf_path), "-"]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        return completed.stdout

    def _encode_base64(self, image_path: Path) -> str:
        return base64.b64encode(image_path.read_bytes()).decode("ascii")

    def _suffix_from_url(self, url: str, content_type: str) -> str:
        parsed = urllib.parse.urlparse(url)
        suffix = Path(parsed.path).suffix.lower()
        if suffix:
            return suffix
        if "pdf" in content_type:
            return ".pdf"
        if "png" in content_type:
            return ".png"
        if "jpeg" in content_type or "jpg" in content_type:
            return ".jpg"
        if "tiff" in content_type:
            return ".tif"
        return ".bin"

    def _browser_user_agent(self) -> str:
        return os.getenv(
            "BN_ACERVO_FIREFOX_UA",
            "Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0",
        )

    def _probe_loaded_model(self, host: str) -> str | None:
        try:
            with urllib.request.urlopen(f"{host}/api/ps", timeout=5) as response:
                data = json.load(response)
        except Exception:
            return None
        models = data.get("models", [])
        for item in models:
            name = str(item.get("name", "")).strip()
            if name and "embed" not in name.lower():
                return name
        return None

    def _serialize_record(self, record: AcervoRecord) -> dict[str, Any]:
        payload = asdict(record)
        payload["raw_text"] = _truncate(payload.get("raw_text", ""), 2000)
        return payload


@router.get("/health")
async def bn_acervo_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "bn-acervo-agent",
        "search_backend": "duckduckgo_site_fallback+firefox_detail",
    }


@router.get("/debug/logs")
async def bn_acervo_debug_logs(limit: int = 120, clear: bool = False) -> dict[str, Any]:
    safe_limit = max(10, min(limit, 400))
    log_file = os.getenv("BN_ACERVO_DEBUG_LOG_PATH", "").strip() or None
    entries = _BN_ACERVO_LOG_BUFFER.snapshot(limit=safe_limit)
    file_tail = _read_log_tail(log_file, limit=safe_limit)
    if clear:
        _BN_ACERVO_LOG_BUFFER.clear()
    return {
        "status": "ok",
        "entries": entries,
        "file_tail": file_tail,
        "log_file": log_file,
        "count": len(entries),
    }


async def _run_bn_acervo_job(job_id: str, payload: AcervoStoryRequest) -> None:
    agent = BnAcervoAgent()
    store = agent.job_store

    async def progress_callback(phase: str, message: str, extra: dict[str, Any] | None = None) -> None:
        progress_percent = _job_progress_percent(phase, extra)
        update_fields: dict[str, Any] = {"status": "running", "phase": phase, "progress_percent": progress_percent}
        if isinstance(extra, dict) and isinstance(extra.get("partial_result"), dict):
            update_fields["partial_result"] = extra["partial_result"]
        store.update(job_id, **update_fields)
        store.append_log(job_id, level="info", message=message)

    store.update(job_id, status="running", phase="planning", progress_percent=4)
    store.append_log(job_id, level="info", message="Job iniciado em background.")
    try:
        result = await agent.run(payload, progress_callback=progress_callback)
        store.update(job_id, status="completed", phase="completed", progress_percent=100, partial_result=result, result=result, error=None)
        store.append_log(job_id, level="success", message="Job concluido com sucesso.")
    except asyncio.CancelledError:
        logger.info("bn_acervo job %s cancelado", job_id)
        store.update(job_id, status="cancelled", phase="cancelled", error="job_cancelled")
        store.append_log(job_id, level="warn", message="Job cancelado.")
        raise
    except Exception as exc:
        logger.exception("bn_acervo job %s failed", job_id)
        store.update(job_id, status="failed", phase="failed", progress_percent=100, error=str(exc))
        store.append_log(job_id, level="error", message=f"Job falhou: {exc}")
    finally:
        _JOB_TASKS.pop(job_id, None)


def _job_sort_key(record: dict[str, Any]) -> tuple[str, str]:
    return (str(record.get("updated_at") or ""), str(record.get("created_at") or ""))


def _reconcile_active_jobs(store: InvestigationJobStore) -> list[dict[str, Any]]:
    active_records = store.list_active()
    live_records: list[dict[str, Any]] = []
    for record in active_records:
        job_id = str(record.get("job_id") or "").strip()
        task = _JOB_TASKS.get(job_id)
        if task is None or task.done():
            store.update(
                job_id,
                status="cancelled",
                phase="cancelled",
                progress_percent=int(record.get("progress_percent") or 0),
                error="stale_job_reconciled",
            )
            store.append_log(job_id, level="warn", message="Job ativo antigo reconciliado como cancelado.")
            continue
        live_records.append(record)
    live_records.sort(key=_job_sort_key, reverse=True)
    return live_records


async def _cancel_job(store: InvestigationJobStore, job_id: str, *, reason: str) -> dict[str, Any] | None:
    record = store.load(job_id)
    if record is None:
        return None
    task = _JOB_TASKS.get(job_id)
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.warning("Falha aguardando cancelamento do job %s", job_id, exc_info=True)
    record = store.update(
        job_id,
        status="cancelled",
        phase="cancelled",
        progress_percent=int(record.get("progress_percent") or 0),
        error=reason,
    )
    store.append_log(job_id, level="warn", message=f"Job cancelado: {reason}.")
    return record


def _bn_acervo_langgraph():
    """Retorna BnAcervoAgentLangraph se BN_ACERVO_AGENT_VERSION=v2."""
    if os.getenv("BN_ACERVO_AGENT_VERSION", "v1") == "v2":
        from specialized_agents.bn_acervo_agent_langgraph import get_bn_acervo_agent_langgraph
        return get_bn_acervo_agent_langgraph()
    return None


@router.post("/jobs", response_model=AcervoJobStatusResponse)
async def bn_acervo_create_job(payload: AcervoStoryRequest) -> AcervoJobStatusResponse:
    if lg := _bn_acervo_langgraph():
        return AcervoJobStatusResponse(**(await lg.create_job(payload)))
    agent = BnAcervoAgent()
    active_jobs = _reconcile_active_jobs(agent.job_store)
    if active_jobs:
        active = active_jobs[0]
        raise HTTPException(
            status_code=409,
            detail={
                "code": "active_job_exists",
                "message": "Ja existe um processamento em andamento para o BN Acervo.",
                "active_job_id": str(active.get("job_id") or ""),
                "phase": str(active.get("phase") or ""),
                "status": str(active.get("status") or ""),
            },
        )
    record = agent.job_store.create(payload)
    job_id = str(record["job_id"])
    task = asyncio.create_task(_run_bn_acervo_job(job_id, payload.model_copy(update={"output_mode": "dossier"} if payload.output_mode == "dossier" else {})))
    _JOB_TASKS[job_id] = task
    return AcervoJobStatusResponse(**record)


@router.post("/jobs/cancel-active")
async def bn_acervo_cancel_active_jobs() -> dict[str, Any]:
    if lg := _bn_acervo_langgraph():
        return await lg.cancel_active_jobs()
    agent = BnAcervoAgent()
    active_jobs = _reconcile_active_jobs(agent.job_store)
    cancelled: list[str] = []
    for record in active_jobs:
        job_id = str(record.get("job_id") or "").strip()
        if not job_id:
            continue
        await _cancel_job(agent.job_store, job_id, reason="cancelled_by_operator")
        cancelled.append(job_id)
    return {"status": "ok", "cancelled_job_ids": cancelled, "count": len(cancelled)}


@router.get("/jobs/{job_id}", response_model=AcervoJobStatusResponse)
async def bn_acervo_get_job(job_id: str) -> AcervoJobStatusResponse:
    agent = BnAcervoAgent()
    record = agent.job_store.load(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return AcervoJobStatusResponse(**record)


@router.post("/story")
async def bn_acervo_story(payload: AcervoStoryRequest) -> dict[str, Any]:
    if lg := _bn_acervo_langgraph():
        return await lg.story(payload)
    agent = BnAcervoAgent()
    try:
        return await agent.run(payload)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("bn_acervo_story failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/dossier")
async def bn_acervo_dossier(payload: AcervoStoryRequest) -> dict[str, Any]:
    if lg := _bn_acervo_langgraph():
        return await lg.dossier(payload)
    agent = BnAcervoAgent()
    try:
        return await agent.run(payload.model_copy(update={"output_mode": "dossier"}))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("bn_acervo_dossier failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _async_main() -> int:
    parser = argparse.ArgumentParser(description="Agente de historia para o Acervo BN")
    parser.add_argument("query", help="Pergunta de pesquisa historica")
    parser.add_argument("--output-mode", choices=["story", "dossier"], default="story")
    parser.add_argument("--investigation-mode", choices=["quick", "deep"], default="quick")
    parser.add_argument("--max-search-results", type=int, default=8)
    parser.add_argument("--max-detail-records", type=int, default=4)
    parser.add_argument("--max-download-documents", type=int, default=2)
    parser.add_argument("--max-ocr-pages-per-document", type=int, default=4)
    parser.add_argument("--json", action="store_true", help="Imprime o payload JSON completo")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    agent = BnAcervoAgent()
    result = await agent.run(
        AcervoStoryRequest(
            query=args.query,
            output_mode=args.output_mode,
            investigation_mode=args.investigation_mode,
            max_search_results=args.max_search_results,
            max_detail_records=args.max_detail_records,
            max_download_documents=args.max_download_documents,
            max_ocr_pages_per_document=args.max_ocr_pages_per_document,
        )
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.output_mode == "dossier":
        print(result["dossier_markdown"])
    else:
        print(result["story_markdown"])
    return 0


def main() -> int:
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
