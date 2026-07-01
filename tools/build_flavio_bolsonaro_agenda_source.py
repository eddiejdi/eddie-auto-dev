#!/usr/bin/env python3
"""Gera texto-fonte contextualizado para locucao sobre a agenda publica.

Modo de operacao:
- `auto`: tenta coleta ao vivo nas paginas oficiais do Senado e cai para snapshot
- `live`: exige coleta ao vivo
- `snapshot`: usa dados consolidados locais
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


DEFAULT_DATE = "2026-06-17"
DEFAULT_OUTPUT = Path("artifacts/audio_cpu_test/generated_locution_source.txt")
SENATOR_NAME = "Flávio Bolsonaro"
PROFILE_URL = "https://www25.senado.leg.br/web/senadores/senador/-/perfil/5894"
CDR_URL = "https://legis.senado.leg.br/atividade/comissoes/comissao/1306/"
CDH_URL = "https://legis.senado.leg.br/atividade/comissoes/comissao/834/"

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
            source_url=CDR_URL,
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
        default=20,
        help="Timeout HTTP em segundos para coleta ao vivo.",
    )
    parser.add_argument(
        "--trust-env",
        action="store_true",
        help="Permite que requests use proxies e configuracoes do ambiente.",
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


def fetch_html(url: str, *, timeout: int, trust_env: bool) -> str:
    session = requests.Session()
    session.trust_env = trust_env
    response = session.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0 agenda-source-bot"},
    )
    response.raise_for_status()
    return response.text


def find_meeting_link(html: str, *, date_token: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        label = normalize_whitespace(anchor.get_text(" ", strip=True))
        if date_token in label and "Reunião" in label:
            return urljoin(CDH_URL, anchor["href"])
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
    time_label = match.group(1).replace(" ", "")
    meeting_label = match.group(2)
    return AgendaEntry(
        time_label=time_label,
        committee_name=committee_name,
        committee_sigla=committee_sigla,
        summary=summarize_committee_meeting(meeting_label, committee_sigla),
        source_url=source_url,
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


def load_live_entries(date_str: str, *, timeout: int, trust_env: bool) -> tuple[AgendaEntry, ...]:
    date_token = date_to_ddmm(date_str)

    cdr_html = fetch_html(CDR_URL, timeout=timeout, trust_env=trust_env)
    cdr_entry = extract_committee_entry(
        cdr_html,
        date_token=date_token,
        committee_name="Comissão de Desenvolvimento Regional e Turismo",
        committee_sigla="CDR",
        source_url=CDR_URL,
    )

    cdh_html = fetch_html(CDH_URL, timeout=timeout, trust_env=trust_env)
    cdh_entry = extract_committee_entry(
        cdh_html,
        date_token=date_token,
        committee_name="Comissão de Direitos Humanos e Legislação Participativa",
        committee_sigla="CDH",
        source_url=CDH_URL,
    )
    meeting_url = find_meeting_link(cdh_html, date_token=date_token)
    if not meeting_url:
        raise ValueError(f"Link da reunião da CDH não encontrado para {date_token}")

    meeting_html = fetch_html(meeting_url, timeout=timeout, trust_env=trust_env)
    materials: list[MaterialContext] = []
    for item in extract_matter_blocks(meeting_html, meeting_url=meeting_url):
        matter_url = item.get("matter_url")
        if not matter_url:
            continue
        detail_html = fetch_html(matter_url, timeout=timeout, trust_env=trust_env)
        material = build_material_context(item, extract_matter_detail(detail_html))
        if material is not None:
            materials.append(material)

    return (
        cdr_entry,
        AgendaEntry(
            time_label=cdh_entry.time_label,
            committee_name=cdh_entry.committee_name,
            committee_sigla=cdh_entry.committee_sigla,
            summary=cdh_entry.summary,
            source_url=meeting_url,
            materials=tuple(materials),
        ),
    )


def load_entries(
    date_str: str,
    *,
    mode: str,
    timeout: int,
    trust_env: bool,
) -> tuple[AgendaEntry, ...]:
    if mode == "snapshot":
        entries = AGENDA_BY_DATE.get(date_str)
        if entries is None:
            raise ValueError(f"Sem agenda consolidada para {date_str}")
        return entries

    if mode == "live":
        return load_live_entries(date_str, timeout=timeout, trust_env=trust_env)

    try:
        return load_live_entries(date_str, timeout=timeout, trust_env=trust_env)
    except Exception:
        entries = AGENDA_BY_DATE.get(date_str)
        if entries is None:
            raise
        return entries


def build_source_text(entries: tuple[AgendaEntry, ...], *, date_label: str) -> str:
    if len(entries) < 2:
        raise ValueError("Era esperado ao menos dois compromissos para montar a materia.")

    cdr_entry = entries[0]
    cdh_entry = entries[1]
    authored = [item for item in cdh_entry.materials if item.role == "autoria"]
    reported = [item for item in cdh_entry.materials if item.role == "relatoria"]

    paragraphs = [
        (
            f"No Senado Federal, Flávio Bolsonaro tem dois compromissos públicos "
            f"previstos para {date_label}. O primeiro ocorre às {cdr_entry.time_label}, "
            f"na {cdr_entry.committee_name}. {cdr_entry.summary}"
        ),
        (
            f"O segundo compromisso está previsto para as {cdh_entry.time_label}, na "
            f"{cdh_entry.committee_name}. {cdh_entry.summary}"
        ),
    ]

    if authored:
        paragraphs.append(
            "Entre as matérias de sua autoria em pauta, estão duas propostas. "
            + " ".join(item.plain_summary for item in authored)
        )

    if reported:
        paragraphs.append(
            "Há também matéria sob sua relatoria, distinta das propostas de sua autoria. "
            + " ".join(item.plain_summary for item in reported)
        )

    return "\n\n".join(paragraphs).strip()


def write_text(output_path: Path, text: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text + "\n", encoding="utf-8")


def iter_sources(entries: tuple[AgendaEntry, ...]) -> list[str]:
    urls: list[str] = [PROFILE_URL]
    for entry in entries:
        if entry.source_url not in urls:
            urls.append(entry.source_url)
        for material in entry.materials:
            if material.source_url and material.source_url not in urls:
                urls.append(material.source_url)
    return urls


def main() -> int:
    args = parse_args()
    entries = load_entries(
        args.date,
        mode=args.mode,
        timeout=args.timeout,
        trust_env=args.trust_env,
    )
    text = build_source_text(entries, date_label=format_date_label(args.date))
    write_text(args.output, text)

    print(text)
    print(f"\nArquivo salvo em: {args.output}")
    if args.print_sources:
        print("\nFontes oficiais:")
        for url in iter_sources(entries):
            print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
