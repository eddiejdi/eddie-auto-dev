#!/usr/bin/env python3
"""Gera texto-fonte contextualizado para locucao sobre a agenda publica.

Modo de operacao:
- `auto`: tenta coleta ao vivo em varias fontes e cai para snapshot
- `live`: exige coleta ao vivo
- `snapshot`: usa dados consolidados locais

Fontes (oficiais e nao oficiais):
- Agenda do Congresso Nacional (congressonacional.leg.br)
- Paginas de comissoes do Senado (legis.senado.leg.br)
- Pauta do plenario do Senado
- Google Noticias RSS (contexto da imprensa)
"""
from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


DEFAULT_DATE = "2026-06-17"
DEFAULT_OUTPUT = Path("artifacts/audio_cpu_test/generated_locution_source.txt")
SENATOR_NAME = "Flávio Bolsonaro"
SENATOR_SLUG = "Flávio Bolsonaro"
PROFILE_URL = "https://www25.senado.leg.br/web/senadores/senador/-/perfil/5894"
COMMITTEES_URL = f"{PROFILE_URL}/comissoes"
CONGRESS_AGENDA_URL = (
    "https://www.congressonacional.leg.br/sessoes/"
    "agenda-do-congresso-senado-e-camara/-/agenda/{date}"
)
GOOGLE_NEWS_RSS_URL = (
    "https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
)

# Comissoes ativas do senador (atualizado via perfil; fallback local).
ACTIVE_COMMITTEES: dict[str, dict[str, str]] = {
    "CDR": {
        "name": "Comissão de Desenvolvimento Regional e Turismo",
        "url": "https://legis.senado.leg.br/atividade/comissoes/comissao/1306/",
        "codcol": "1306",
    },
    "CDH": {
        "name": "Comissão de Direitos Humanos e Legislação Participativa",
        "url": "https://legis.senado.leg.br/atividade/comissoes/comissao/834/",
        "codcol": "834",
    },
    "CCJ": {
        "name": "Comissão de Constituição, Justiça e Cidadania",
        "url": "https://legis.senado.leg.br/atividade/comissoes/comissao/34/",
        "codcol": "34",
    },
}

PT_WEEKDAYS = {
    0: "segunda-feira",
    1: "terça-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sábado",
    6: "domingo",
}
PT_MONTHS = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}


@dataclass(frozen=True)
class MaterialContext:
    code: str
    role: str
    title: str
    plain_summary: str
    source_url: str


@dataclass(frozen=True)
class AgendaEntry:
    time_label: str
    committee_name: str
    committee_sigla: str
    summary: str
    source_url: str
    materials: tuple[MaterialContext, ...] = field(default_factory=tuple)
    source_kind: str = "official"
    source_label: str = "Senado Federal"
    entry_type: str = "committee"


@dataclass(frozen=True)
class NewsSnippet:
    title: str
    outlet: str
    url: str
    published: str = ""
    summary: str = ""


@dataclass(frozen=True)
class CollectedAgenda:
    entries: tuple[AgendaEntry, ...]
    news: tuple[NewsSnippet, ...] = field(default_factory=tuple)
    sources_used: tuple[str, ...] = field(default_factory=tuple)
    sources_failed: tuple[str, ...] = field(default_factory=tuple)


AGENDA_BY_DATE: dict[str, tuple[AgendaEntry, ...]] = {
    "2026-06-17": (
        AgendaEntry(
            time_label="9h30",
            committee_name="Comissão de Desenvolvimento Regional e Turismo",
            committee_sigla="CDR",
            summary=(
                "A comissão tem deliberação prevista sobre indicações de emendas RP-8 "
                "da Lei Orçamentária de 2026, etapa ligada à definição de destinação "
                "de recursos orçamentários da comissão."
            ),
            source_url=ACTIVE_COMMITTEES["CDR"]["url"],
        ),
        AgendaEntry(
            time_label="11h",
            committee_name="Comissão de Direitos Humanos e Legislação Participativa",
            committee_sigla="CDH",
            summary=(
                "A reunião extraordinária da comissão inclui na pauta projetos ligados "
                "ao senador por autoria e por relatoria."
            ),
            source_url="https://legis.senado.leg.br/atividade/comissoes/comissao/834/reuniao/14728",
            materials=(
                MaterialContext(
                    code="PL 4598/2025",
                    role="autoria",
                    title="agravantes penais para crimes contra pessoas com deficiência ou neurodivergentes",
                    plain_summary=(
                        "O projeto propõe incluir no Código Penal uma circunstância agravante "
                        "para crimes cometidos contra pessoas com deficiência ou neurodivergentes. "
                        "A proposta também amplia uma causa de aumento de pena para lesão corporal, "
                        "retirando a limitação ligada ao local do crime."
                    ),
                    source_url="https://www25.senado.leg.br/web/atividade/materias/-/materia/170486",
                ),
                MaterialContext(
                    code="PL 3980/2025",
                    role="autoria",
                    title="prioridade no SUS para exames ligados ao diagnóstico precoce de autismo",
                    plain_summary=(
                        "A proposta estabelece que o Sistema Único de Saúde ofereça exames "
                        "diagnósticos especializados de forma integral e prioritária para "
                        "identificação precoce do transtorno do espectro autista. A explicação "
                        "oficial do Senado cita exames como BERA, ressonância magnética, "
                        "eletroencefalograma e avaliações clínicas multiprofissionais."
                    ),
                    source_url="https://www25.senado.leg.br/web/atividade/materias/-/materia/169904",
                ),
                MaterialContext(
                    code="PL 3283/2025",
                    role="relatoria",
                    title="transparência na remoção de conteúdo por provedores de internet",
                    plain_summary=(
                        "Na relatoria de Flávio Bolsonaro, a proposta do senador Esperidião Amin "
                        "estabelece que, quando um provedor de internet remover conteúdo sem ordem "
                        "judicial, deve comunicar o fato a órgãos públicos e instituições de controle."
                    ),
                    source_url="https://www25.senado.leg.br/web/atividade/materias/-/materia/169474",
                ),
            ),
        ),
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera texto-fonte contextualizado da agenda de Flavio Bolsonaro."
    )
    parser.add_argument(
        "--date",
        default=DEFAULT_DATE,
        help="Data da agenda em YYYY-MM-DD.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Arquivo de saida para o texto-fonte.",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "live", "snapshot"),
        default="auto",
        help="Origem dos dados: coleta ao vivo, snapshot local, ou auto.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=35,
        help="Timeout HTTP em segundos para coleta ao vivo.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Tentativas por URL em caso de falha transitoria.",
    )
    parser.add_argument(
        "--trust-env",
        action="store_true",
        help="Permite que requests use proxies e configuracoes do ambiente.",
    )
    parser.add_argument(
        "--no-news",
        action="store_true",
        help="Desativa coleta de contexto em Google Noticias.",
    )
    parser.add_argument(
        "--print-sources",
        action="store_true",
        help="Imprime as URLs oficiais usadas para consolidar o texto.",
    )
    return parser.parse_args()


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def lowercase_first(text: str) -> str:
    if not text:
        return text
    return text[:1].lower() + text[1:]


def format_date_label(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = PT_WEEKDAYS[dt.weekday()]
    month = PT_MONTHS[dt.month]
    return f"esta {weekday}, {dt.day} de {month} de {dt.year}"


def date_to_ddmm(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.day:02d}/{dt.month:02d}"


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return normalize_whitespace(soup.get_text(" ", strip=True))


def fetch_html(url: str, *, timeout: int, trust_env: bool, retries: int = 0) -> str:
    last_error: Exception | None = None
    attempts = max(1, retries + 1)
    for attempt in range(attempts):
        session = requests.Session()
        session.trust_env = trust_env
        try:
            response = session.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 agenda-source-bot"},
            )
            response.raise_for_status()
            return response.text
        except Exception as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                break
    assert last_error is not None
    raise last_error


def fetch_text(url: str, *, timeout: int, trust_env: bool, retries: int = 0) -> str:
    return fetch_html(url, timeout=timeout, trust_env=trust_env, retries=retries)


def parse_time_label(raw: str) -> str:
    cleaned = normalize_whitespace(raw).replace(" ", "").lower()
    cleaned = cleaned.replace("h00", "h").replace("h0", "h")
    match = re.match(r"(\d{1,2})h(\d{2})?", cleaned)
    if not match:
        return cleaned
    hour = int(match.group(1))
    minute = match.group(2) or "00"
    if minute == "00":
        return f"{hour}h"
    return f"{hour}h{minute}"


def time_sort_key(time_label: str) -> tuple[int, int]:
    match = re.match(r"(\d{1,2})h(\d{2})?", time_label)
    if not match:
        return (99, 99)
    return (int(match.group(1)), int(match.group(2) or "0"))


def find_meeting_link(html: str, *, date_token: str, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        label = normalize_whitespace(anchor.get_text(" ", strip=True))
        if date_token in label and "Reunião" in label:
            return urljoin(base_url, anchor["href"])
    return None


def summarize_committee_meeting(meeting_label: str, committee_sigla: str) -> str:
    label = normalize_whitespace(meeting_label)
    if committee_sigla == "CDR" and "RP8/2026" in label:
        return (
            "A comissão tem deliberação prevista sobre indicações de emendas RP-8 "
            "da Lei Orçamentária de 2026, etapa ligada à definição de destinação "
            "de recursos orçamentários da comissão."
        )
    if committee_sigla == "CDH" and "Deliberativa" in label:
        return (
            "A reunião extraordinária da comissão inclui na pauta projetos ligados "
            "ao senador por autoria e por relatoria."
        )
    if "Audiência Pública" in label or "Audiência Pública" in meeting_label:
        focus = label if "Audiência" in label else meeting_label
        return (
            f"A comissão realiza audiência pública: {lowercase_first(focus)}."
        )
    return f"A reunião agendada da comissão tem como foco {lowercase_first(label)}."


def extract_committee_entry(
    html: str,
    *,
    date_token: str,
    committee_name: str,
    committee_sigla: str,
    source_url: str,
) -> AgendaEntry:
    text = html_to_text(html)
    pattern = re.compile(
        rf"{re.escape(date_token)}\s+\w+\s+(\d{{1,2}}\s*h\d{{2}})\s+(.+?)\s+Agendada"
    )
    match = pattern.search(text)
    if not match:
        raise ValueError(f"Reunião não encontrada para {committee_sigla} em {date_token}")
    time_label = parse_time_label(match.group(1))
    meeting_label = match.group(2)
    return AgendaEntry(
        time_label=time_label,
        committee_name=committee_name,
        committee_sigla=committee_sigla,
        summary=summarize_committee_meeting(meeting_label, committee_sigla),
        source_url=source_url,
        source_label="Comissões do Senado",
    )


def extract_matter_blocks(html: str, *, meeting_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    link_map: dict[str, str] = {}
    for anchor in soup.find_all("a", href=True):
        label = normalize_whitespace(anchor.get_text(" ", strip=True))
        match = re.match(r"Ver\s+([A-Z]{2,6}\s*\d+/\d+)", label)
        if match:
            link_map[normalize_whitespace(match.group(1))] = urljoin(meeting_url, anchor["href"])

    text = html_to_text(html)
    pattern = re.compile(
        r"(\d+)\s*-\s*([A-Z]{2,6}\s*\d+/\d+)\s+Ver\s+[A-Z]{2,6}\s*\d+/\d+\s+"
        r"Ementa\s+(.*?)\s+Relator\s+(.*?)\s+Relatório\s+(.*?)\s+Observação\s+(.*?)(?=\s+\d+\s*-\s*[A-Z]{2,6}\s*\d+/\d+|\Z)"
    )
    materials: list[dict[str, str]] = []
    for match in pattern.finditer(text):
        code = normalize_whitespace(match.group(2))
        materials.append(
            {
                "code": code,
                "ementa": normalize_whitespace(match.group(3)),
                "relator": normalize_whitespace(match.group(4)),
                "relatorio": normalize_whitespace(match.group(5)),
                "observacao": normalize_whitespace(match.group(6)),
                "matter_url": link_map.get(code, ""),
            }
        )
    return materials


def extract_matter_detail(html: str) -> dict[str, str]:
    text = html_to_text(html)
    author_match = re.search(r"Autoria:\s+(.*?)\s+Assunto:", text)
    ementa_match = re.search(
        r"Ementa:\s+(.*?)\s+(Entenda a proposta|Texto inicial|Situação Atual)",
        text,
    )
    what_is_match = re.search(
        r"O que é\s+(.*?)\s+O que diz o autor",
        text,
    )
    return {
        "author": normalize_whitespace(author_match.group(1)) if author_match else "",
        "ementa": normalize_whitespace(ementa_match.group(1)) if ementa_match else "",
        "what_is": normalize_whitespace(what_is_match.group(1)) if what_is_match else "",
    }


def render_relatoria_summary(author: str, explanation: str) -> str:
    summary = explanation or ""
    author_label = author or "outro senador"
    if summary.startswith("A proposta "):
        return (
            f"Na relatoria de {SENATOR_NAME}, a proposta de {author_label} "
            f"{lowercase_first(summary[len('A proposta '):])}"
        )
    return (
        f"Na relatoria de {SENATOR_NAME}, a proposta de {author_label} trata do seguinte: "
        f"{summary}"
    )


def build_material_context(item: dict[str, str], detail: dict[str, str]) -> MaterialContext | None:
    author = detail.get("author", "")
    relator = item.get("relator", "")
    explanation = detail.get("what_is") or detail.get("ementa") or item.get("ementa", "")
    title = detail.get("ementa") or item.get("ementa", "")
    if SENATOR_NAME in author:
        return MaterialContext(
            code=item["code"],
            role="autoria",
            title=title,
            plain_summary=explanation,
            source_url=item["matter_url"],
        )
    if SENATOR_NAME in relator:
        return MaterialContext(
            code=item["code"],
            role="relatoria",
            title=title,
            plain_summary=render_relatoria_summary(author, explanation),
            source_url=item["matter_url"],
        )
    return None


def enrich_entry_with_materials(
    entry: AgendaEntry,
    *,
    meeting_html: str,
    meeting_url: str,
    timeout: int,
    trust_env: bool,
    retries: int,
) -> AgendaEntry:
    materials: list[MaterialContext] = []
    for item in extract_matter_blocks(meeting_html, meeting_url=meeting_url):
        matter_url = item.get("matter_url")
        if not matter_url:
            continue
        try:
            detail_html = fetch_html(
                matter_url,
                timeout=timeout,
                trust_env=trust_env,
                retries=retries,
            )
        except Exception:
            continue
        material = build_material_context(item, extract_matter_detail(detail_html))
        if material is not None:
            materials.append(material)
    if not materials:
        return entry
    return AgendaEntry(
        time_label=entry.time_label,
        committee_name=entry.committee_name,
        committee_sigla=entry.committee_sigla,
        summary=entry.summary,
        source_url=meeting_url,
        materials=tuple(materials),
        source_kind=entry.source_kind,
        source_label=entry.source_label,
        entry_type=entry.entry_type,
    )


def _congress_event_context(anchor) -> str:
    for parent in anchor.parents:
        if parent.name not in {"div", "li", "section", "article", "td"}:
            continue
        parent_text = normalize_whitespace(parent.get_text(" ", strip=True))
        if re.search(r"\d{1,2}\s*h\s*\d{2}", parent_text, flags=re.IGNORECASE):
            return parent_text
    return ""


def _is_congress_event_anchor(href: str, title: str) -> bool:
    if "camara.leg.br" in href:
        return False
    if "reuniao" in href or "sessao-plenaria" in href:
        return True
    return any(
        token in title
        for token in ("Reunião", "Sessão", "Audiência", "Seminário")
    )


def parse_congress_agenda(
    html: str,
    *,
    date_str: str,
    committee_siglas: set[str],
) -> list[AgendaEntry]:
    soup = BeautifulSoup(html, "html.parser")
    entries: list[AgendaEntry] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        title = normalize_whitespace(anchor.get_text(" ", strip=True))
        if not title or not _is_congress_event_anchor(href, title):
            continue

        parent_text = _congress_event_context(anchor)
        if not parent_text:
            continue

        time_match = re.search(r"(\d{1,2})\s*h\s*(\d{2})", parent_text, flags=re.IGNORECASE)
        if not time_match:
            continue
        time_label = parse_time_label(f"{time_match.group(1)}h{time_match.group(2)}")

        is_plenary = "sessao-plenaria" in href or (
            re.search(r"\bSF\b", parent_text) and "Sessão" in title
        )
        sigla = ""
        if not is_plenary:
            for candidate in committee_siglas:
                if re.search(rf"\b{re.escape(candidate)}\b", parent_text):
                    sigla = candidate
                    break
        if not sigla and not is_plenary:
            continue

        if sigla:
            committee = ACTIVE_COMMITTEES.get(sigla, {})
            committee_name = committee.get("name", sigla)
            entry_type = "committee"
            source_label = "Congresso Nacional"
            detail = ""
            for token in ("Audiência Pública", "Deliberativa", "Seminário"):
                if token in parent_text:
                    detail = token
                    break
            meeting_label = f"{title} {detail}".strip()
            summary = summarize_committee_meeting(meeting_label, sigla)
        else:
            committee_name = "Plenário do Senado Federal"
            sigla = "PLEN"
            entry_type = "plenary"
            source_label = "Congresso Nacional"
            detail = ""
            detail_match = re.search(
                rf"{re.escape(title)}\s+(.*?)\s+Agendada",
                parent_text,
                flags=re.IGNORECASE,
            )
            if detail_match:
                detail = normalize_whitespace(detail_match.group(1))
            if detail and detail != "Plenário do Senado Federal":
                summary = (
                    f"O plenário do Senado tem sessão prevista: {lowercase_first(title)}. "
                    f"{detail}"
                )
            else:
                summary = (
                    f"O plenário do Senado tem sessão prevista: {lowercase_first(title)}."
                )

        status_cancelled = any(
            token in parent_text
            for token in ("Cancelada", "Encerrada", "Suspensa")
        )
        if status_cancelled:
            continue

        dedupe_key = f"{time_label}|{sigla}|{title}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        source_url = href if href.startswith("http") else urljoin(
            CONGRESS_AGENDA_URL.format(date=date_str),
            href,
        )
        entries.append(
            AgendaEntry(
                time_label=time_label,
                committee_name=committee_name,
                committee_sigla=sigla,
                summary=summary,
                source_url=source_url,
                source_label=source_label,
                entry_type=entry_type,
            )
        )
    return entries


def parse_plenary_pauta_for_senator(html: str, *, pauta_url: str) -> AgendaEntry | None:
    text = html_to_text(html)
    if SENATOR_NAME not in text and "Flavio Bolsonaro" not in text:
        return None

    senator_mentions: list[str] = []
    for match in re.finditer(
        rf"(PROJETO|PROPOSTA|REQ|Requerimento|Relator[a]?):?\s*.{{0,220}}?{re.escape(SENATOR_NAME)}",
        text,
        flags=re.IGNORECASE,
    ):
        senator_mentions.append(normalize_whitespace(match.group(0)))

    if not senator_mentions:
        return None

    time_match = re.search(r"Início previsto:\s*(\d{1,2}:\d{2})", text)
    time_label = "14h"
    if time_match:
        hour, minute = time_match.group(1).split(":")
        time_label = parse_time_label(f"{hour}h{minute}")

    summary = (
        "Na pauta do plenário há matérias ligadas ao senador. "
        + " ".join(senator_mentions[:2])
    )
    return AgendaEntry(
        time_label=time_label,
        committee_name="Plenário do Senado Federal",
        committee_sigla="PLEN",
        summary=summary[:500],
        source_url=pauta_url,
        source_label="Pauta do Plenário",
        entry_type="plenary",
    )


def parse_google_news_rss(xml_text: str, *, date_str: str) -> list[NewsSnippet]:
    root = ET.fromstring(xml_text)
    target_day = datetime.strptime(date_str, "%Y-%m-%d").date()
    snippets: list[NewsSnippet] = []

    for item in root.findall(".//item"):
        title = normalize_whitespace(item.findtext("title", default=""))
        link = normalize_whitespace(item.findtext("link", default=""))
        pub_date = normalize_whitespace(item.findtext("pubDate", default=""))
        source_el = item.find("source")
        outlet = normalize_whitespace(source_el.text if source_el is not None else "")

        if not title or SENATOR_SLUG.split()[0] not in title:
            continue
        if "Bolsonaro" not in title and SENATOR_NAME not in title:
            continue

        published_day = None
        if pub_date:
            try:
                published_day = datetime.strptime(
                    pub_date[:16], "%a, %d %b %Y"
                ).date()
            except ValueError:
                published_day = None
        if published_day and abs((published_day - target_day).days) > 7:
            continue

        snippets.append(
            NewsSnippet(
                title=title,
                outlet=outlet or "Google Notícias",
                url=link,
                published=pub_date,
            )
        )
    return snippets[:6]


def collect_committee_page_entries(
    date_str: str,
    *,
    timeout: int,
    trust_env: bool,
    retries: int,
    skip_siglas: set[str] | None = None,
) -> list[AgendaEntry]:
    date_token = date_to_ddmm(date_str)
    entries: list[AgendaEntry] = []
    ignored = skip_siglas or set()

    for sigla, committee in ACTIVE_COMMITTEES.items():
        if sigla in ignored:
            continue
        try:
            committee_html = fetch_html(
                committee["url"],
                timeout=timeout,
                trust_env=trust_env,
                retries=retries,
            )
            entry = extract_committee_entry(
                committee_html,
                date_token=date_token,
                committee_name=committee["name"],
                committee_sigla=sigla,
                source_url=committee["url"],
            )
            meeting_url = find_meeting_link(
                committee_html,
                date_token=date_token,
                base_url=committee["url"],
            )
            if meeting_url:
                try:
                    meeting_html = fetch_html(
                        meeting_url,
                        timeout=timeout,
                        trust_env=trust_env,
                        retries=retries,
                    )
                    entry = enrich_entry_with_materials(
                        entry,
                        meeting_html=meeting_html,
                        meeting_url=meeting_url,
                        timeout=timeout,
                        trust_env=trust_env,
                        retries=retries,
                    )
                except Exception:
                    pass
            entries.append(entry)
        except Exception:
            continue
    return entries


def collect_congress_agenda_entries(
    date_str: str,
    *,
    timeout: int,
    trust_env: bool,
    retries: int,
) -> list[AgendaEntry]:
    url = CONGRESS_AGENDA_URL.format(date=date_str)
    html = fetch_html(url, timeout=timeout, trust_env=trust_env, retries=retries)
    return parse_congress_agenda(
        html,
        date_str=date_str,
        committee_siglas=set(ACTIVE_COMMITTEES),
    )


def collect_plenary_entries(
    date_str: str,
    entries: list[AgendaEntry],
    *,
    timeout: int,
    trust_env: bool,
    retries: int,
    max_urls: int = 2,
) -> list[AgendaEntry]:
    plenary_urls = [
        entry.source_url
        for entry in entries
        if entry.entry_type == "plenary" and "sessao-plenaria" in entry.source_url
    ]
    if not plenary_urls:
        url = CONGRESS_AGENDA_URL.format(date=date_str)
        try:
            html = fetch_html(url, timeout=timeout, trust_env=trust_env, retries=retries)
            soup = BeautifulSoup(html, "html.parser")
            for anchor in soup.find_all("a", href=True):
                if "sessao-plenaria" in anchor["href"]:
                    plenary_urls.append(urljoin(url, anchor["href"]))
        except Exception:
            return []

    found: list[AgendaEntry] = []
    seen: set[str] = set()
    for pauta_url in plenary_urls[:max_urls]:
        if pauta_url in seen:
            continue
        seen.add(pauta_url)
        try:
            pauta_html = fetch_html(
                pauta_url,
                timeout=timeout,
                trust_env=trust_env,
                retries=retries,
            )
            entry = parse_plenary_pauta_for_senator(pauta_html, pauta_url=pauta_url)
            if entry is not None:
                found.append(entry)
        except Exception:
            continue
    return found


def collect_news_snippets(
    date_str: str,
    *,
    timeout: int,
    trust_env: bool,
    retries: int,
) -> list[NewsSnippet]:
    queries = [
        f'"{SENATOR_NAME}" senado agenda when:7d',
        f'"{SENATOR_NAME}" comissão senado when:7d',
        f'"{SENATOR_NAME}" plenário when:7d',
    ]
    snippets: list[NewsSnippet] = []
    seen_titles: set[str] = set()
    for query in queries:
        url = GOOGLE_NEWS_RSS_URL.format(query=requests.utils.quote(query))
        try:
            xml_text = fetch_text(url, timeout=timeout, trust_env=trust_env, retries=retries)
            for item in parse_google_news_rss(xml_text, date_str=date_str):
                key = item.title.lower()
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                snippets.append(item)
        except Exception:
            continue
    return snippets[:5]


def merge_agenda_entries(entries: list[AgendaEntry]) -> tuple[AgendaEntry, ...]:
    merged: dict[str, AgendaEntry] = {}
    for entry in entries:
        key = f"{entry.time_label}|{entry.committee_sigla}|{entry.entry_type}"
        current = merged.get(key)
        if current is None:
            merged[key] = entry
            continue
        if current.source_kind == "official" and entry.source_kind != "official":
            continue
        if len(entry.materials) > len(current.materials):
            merged[key] = entry
        elif len(entry.summary) > len(current.summary):
            merged[key] = entry
    return tuple(sorted(merged.values(), key=lambda item: time_sort_key(item.time_label)))


def collect_live_agenda(
    date_str: str,
    *,
    timeout: int,
    trust_env: bool,
    retries: int,
    include_news: bool,
) -> CollectedAgenda:
    entries: list[AgendaEntry] = []
    news: list[NewsSnippet] = []
    used: list[str] = []
    failed: list[str] = []

    congress_entries: list[AgendaEntry] = []
    try:
        congress_entries = collect_congress_agenda_entries(
            date_str, timeout=timeout, trust_env=trust_env, retries=retries
        )
        if congress_entries:
            entries.extend(congress_entries)
            used.append("congresso_nacional")
        else:
            failed.append("congresso_nacional")
    except Exception:
        failed.append("congresso_nacional")

    covered_siglas = {entry.committee_sigla for entry in congress_entries}
    for index, entry in enumerate(entries):
        if entry.entry_type != "committee" or entry.materials:
            continue
        if "reuniao" not in entry.source_url:
            continue
        if "Audiência Pública" in entry.summary:
            continue
        try:
            meeting_html = fetch_html(
                entry.source_url,
                timeout=min(10, timeout),
                trust_env=trust_env,
                retries=0,
            )
            entries[index] = enrich_entry_with_materials(
                entry,
                meeting_html=meeting_html,
                meeting_url=entry.source_url,
                timeout=timeout,
                trust_env=trust_env,
                retries=retries,
            )
            used.append("pauta_comissao")
        except Exception:
            continue

    committee_timeout = min(12, timeout)
    try:
        committee_entries = collect_committee_page_entries(
            date_str,
            timeout=committee_timeout,
            trust_env=trust_env,
            retries=0,
            skip_siglas=covered_siglas,
        )
        if committee_entries:
            entries.extend(committee_entries)
            used.append("comissoes_senado")
        elif not covered_siglas:
            failed.append("comissoes_senado")
    except Exception:
        failed.append("comissoes_senado")

    try:
        plenary_entries = collect_plenary_entries(
            date_str,
            entries,
            timeout=min(15, timeout),
            trust_env=trust_env,
            retries=0,
            max_urls=1,
        )
        if plenary_entries:
            entries.extend(plenary_entries)
            used.append("pauta_plenario")
    except Exception:
        failed.append("pauta_plenario")

    if include_news:
        try:
            news = collect_news_snippets(
                date_str,
                timeout=timeout,
                trust_env=trust_env,
                retries=retries,
            )
            if news:
                used.append("google_noticias")
            else:
                failed.append("google_noticias")
        except Exception:
            failed.append("google_noticias")

    merged_entries = merge_agenda_entries(entries)
    return CollectedAgenda(
        entries=merged_entries,
        news=tuple(news),
        sources_used=tuple(used),
        sources_failed=tuple(failed),
    )


def load_live_entries(
    date_str: str,
    *,
    timeout: int,
    trust_env: bool,
    retries: int = 0,
    include_news: bool = True,
) -> CollectedAgenda:
    return collect_live_agenda(
        date_str,
        timeout=timeout,
        trust_env=trust_env,
        retries=retries,
        include_news=include_news,
    )


def load_entries(
    date_str: str,
    *,
    mode: str,
    timeout: int,
    trust_env: bool,
    retries: int = 0,
    include_news: bool = True,
) -> CollectedAgenda:
    if mode == "snapshot":
        entries = AGENDA_BY_DATE.get(date_str)
        if entries is None:
            raise ValueError(f"Sem agenda consolidada para {date_str}")
        return CollectedAgenda(entries=entries, sources_used=("snapshot",))

    if mode == "live":
        collected = load_live_entries(
            date_str,
            timeout=timeout,
            trust_env=trust_env,
            retries=retries,
            include_news=include_news,
        )
        if not collected.entries:
            raise ValueError(f"Nenhum compromisso encontrado para {date_str}")
        return collected

    try:
        collected = load_live_entries(
            date_str,
            timeout=timeout,
            trust_env=trust_env,
            retries=retries,
            include_news=include_news,
        )
        if collected.entries:
            return collected
    except Exception:
        pass

    entries = AGENDA_BY_DATE.get(date_str)
    if entries is None:
        raise ValueError(f"Sem agenda ao vivo nem snapshot para {date_str}")
    return CollectedAgenda(entries=entries, sources_used=("snapshot",))


def ordinal_pt(index: int) -> str:
    labels = {1: "primeiro", 2: "segundo", 3: "terceiro", 4: "quarto", 5: "quinto"}
    return labels.get(index, f"{index}º")


def render_commitment_paragraph(entry: AgendaEntry, *, index: int, total: int) -> str:
    if index == 1:
        opener = (
            f"No Senado Federal, {SENATOR_NAME} tem {total} "
            f"{'compromisso público previsto' if total == 1 else 'compromissos públicos previstos'}"
        )
    else:
        opener = f"O {ordinal_pt(index)} compromisso"

    if entry.entry_type == "plenary":
        body = (
            f"{opener} no plenário, previsto para as {entry.time_label}. "
            f"{entry.summary}"
        )
    else:
        connector = f"{opener} ocorre às {entry.time_label}, na {entry.committee_name}."
        if index == 1:
            connector = (
                f"{opener}. O primeiro ocorre às {entry.time_label}, "
                f"na {entry.committee_name}."
            )
        body = f"{connector} {entry.summary}"
    return body


def render_materials_paragraphs(entries: tuple[AgendaEntry, ...]) -> list[str]:
    paragraphs: list[str] = []
    authored: list[MaterialContext] = []
    reported: list[MaterialContext] = []
    for entry in entries:
        for material in entry.materials:
            if material.role == "autoria":
                authored.append(material)
            elif material.role == "relatoria":
                reported.append(material)

    if authored:
        lead = (
            "Entre as matérias de sua autoria em pauta, estão "
            f"{'uma proposta' if len(authored) == 1 else f'{len(authored)} propostas'}."
        )
        paragraphs.append(lead + " " + " ".join(item.plain_summary for item in authored))

    if reported:
        lead = (
            "Há também "
            f"{'matéria' if len(reported) == 1 else 'matérias'} sob sua relatoria, "
            "distinta das propostas de sua autoria."
        )
        paragraphs.append(lead + " " + " ".join(item.plain_summary for item in reported))
    return paragraphs


def render_news_paragraph(news: tuple[NewsSnippet, ...]) -> str | None:
    if not news:
        return None
    lines = [
        "Na cobertura da imprensa, há menções recentes que ajudam a contextualizar "
        "a atuação do senador:"
    ]
    for item in news[:3]:
        lines.append(f"- {item.title} ({item.outlet}).")
    return " ".join(lines)


def build_source_text(
    collected: CollectedAgenda | tuple[AgendaEntry, ...],
    *,
    date_label: str,
) -> str:
    if isinstance(collected, tuple):
        entries = collected
        news: tuple[NewsSnippet, ...] = ()
    else:
        entries = collected.entries
        news = collected.news

    if not entries and not news:
        raise ValueError("Nenhuma informação de agenda encontrada para montar a matéria.")

    paragraphs: list[str] = []
    if entries:
        total = len(entries)
        for index, entry in enumerate(entries, start=1):
            paragraphs.append(
                render_commitment_paragraph(entry, index=index, total=total)
            )
        paragraphs.extend(render_materials_paragraphs(entries))
    else:
        paragraphs.append(
            f"Para {date_label}, não há compromissos formais confirmados nas fontes "
            f"oficiais consultadas sobre a agenda de {SENATOR_NAME} no Senado."
        )

    news_paragraph = render_news_paragraph(news)
    if news_paragraph:
        paragraphs.append(news_paragraph)

    return "\n\n".join(paragraphs).strip()


def write_text(output_path: Path, text: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text + "\n", encoding="utf-8")


def iter_sources(collected: CollectedAgenda | tuple[AgendaEntry, ...]) -> list[str]:
    if isinstance(collected, tuple):
        entries = collected
        news: tuple[NewsSnippet, ...] = ()
    else:
        entries = collected.entries
        news = collected.news

    urls: list[str] = [PROFILE_URL, COMMITTEES_URL]
    for entry in entries:
        if entry.source_url not in urls:
            urls.append(entry.source_url)
        for material in entry.materials:
            if material.source_url and material.source_url not in urls:
                urls.append(material.source_url)
    for item in news:
        if item.url and item.url not in urls:
            urls.append(item.url)
    return urls


def main() -> int:
    args = parse_args()
    collected = load_entries(
        args.date,
        mode=args.mode,
        timeout=args.timeout,
        trust_env=args.trust_env,
        retries=args.retries,
        include_news=not args.no_news,
    )
    text = build_source_text(collected, date_label=format_date_label(args.date))
    write_text(args.output, text)

    print(text)
    print(f"\nArquivo salvo em: {args.output}")
    if collected.sources_used:
        print(f"\nFontes utilizadas: {', '.join(collected.sources_used)}")
    if collected.sources_failed:
        print(f"Fontes sem resultado: {', '.join(collected.sources_failed)}")
    if args.print_sources:
        print("\nURLs consultadas:")
        for url in iter_sources(collected):
            print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())