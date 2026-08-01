#!/usr/bin/env python3
"""Geração modular de locução longa: segmentos LLM + mesa de Editor + TTS + concat.

Problema resolvido:
  Um único prompt LLM + um único TTS não consegue produzir ~1h de áudio
  (limites de tokens, validadores curtos e timeouts). Este módulo:
    1. classifica o dia: COM_PAUTA | SEM_PAUTA
    2. planeja N segmentos (por matéria OU grade fixa de 1h)
    3. gera rascunhos (draft) de cada segmento
    4. mesa de Editor: COM_PAUTA corta/une; SEM_PAUTA preserva volume (meta 1h)
    5. sintetiza TTS só sobre os blocos já editados
    6. concatena WAVs (com silêncio entre partes) no locution.wav final

Modos:
  COM_PAUTA  — há compromissos/itens oficiais; plano por blocos-fonte.
  SEM_PAUTA  — “não há compromissos formais”; grade CURTA de radiojornalismo
               de serviço (teto ~12 min / poucos blocos). Não inventa fatos;
               data só na abertura; sem “extras” para forçar 1h.

Config (panel_config.json → audio):
  min_duration_seconds      alvo total COM_PAUTA (default 3600)
  sem_pauta_max_duration_seconds  teto SEM_PAUTA (default 720)
  sem_pauta_max_segments    máx. blocos SEM_PAUTA (default 6)
  sem_pauta_allow_extras    se false, não alonga com 2ª leva (default false)
  segment_target_seconds    duração alvo por segmento (default 180)
  segment_gap_seconds       silêncio entre segmentos (default 0.6)
  words_per_minute          estimativa PT-BR locução (default 140)
  modular                   força modular (default true se min >= threshold)
  modular_threshold_seconds acima disto usa pipeline modular (default 300)
  editor_enabled            mesa de Editor no final (default true)
  editor_batch_size         quantos rascunhos o Editor revisa por vez (default 2;
                            forçado a 1 em SEM_PAUTA)
"""
from __future__ import annotations

import json
import logging
import re
import struct
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Estimativa conservadora de locução jornalística em PT-BR.
DEFAULT_WPM = 140
DEFAULT_SEGMENT_SECONDS = 180
DEFAULT_GAP_SECONDS = 0.6
DEFAULT_MODULAR_THRESHOLD = 300
DEFAULT_MIN_SEGMENT_SECONDS = 90
DEFAULT_MAX_SEGMENTS = 40
DEFAULT_EDITOR_BATCH_SIZE = 2
# Dia vazio: não forçar 1h de eco. ~12 min / ≤6 blocos.
DEFAULT_SEM_PAUTA_MAX_DURATION = 720
DEFAULT_SEM_PAUTA_MAX_SEGMENTS = 6

# Ordem preferencial de fechamento de um boletim (mesa de Editor).
EDITOR_ROLE_ORDER = (
    "abertura",
    "panorama",
    "panorama_ausencia",
    "leitura_silencio",
    "fonte_oficial",
    "compromisso",
    "atuacao",
    "atuacao_acompanhamento",
    "aprofundamento",
    "desenvolvimento_ancora",
    "contexto_aliado",
    "cobertura_aliada",
    "familia_aliados",
    "imprensa",
    "imprensa_reenquadramento",
    "repercussao",
    "monitoramento",
    "processo_cobertura",
    "eleitor_contexto",
    "disciplina_fontes",
    "ponte_amanha",
    "fechamento_tematico",
    "assinatura_canal",
    "encerramento",
)

MODE_COM_PAUTA = "com_pauta"
MODE_SEM_PAUTA = "sem_pauta"

# Grade de serviço para dia sem compromissos formais (meta de 1h mesmo assim).
SEM_PAUTA_ROLE_CYCLE = (
    "abertura",
    "panorama_ausencia",
    "leitura_silencio",
    "fonte_oficial",
    "contexto_aliado",
    "cobertura_aliada",
    "imprensa_reenquadramento",
    "atuacao_acompanhamento",
    "desenvolvimento_ancora",
    "monitoramento",
    "processo_cobertura",
    "eleitor_contexto",
    "familia_aliados",
    "repercussao",
    "disciplina_fontes",
    "ponte_amanha",
    "aprofundamento",
    "fechamento_tematico",
    "assinatura_canal",
    "encerramento",
)

SEM_PAUTA_TITLES = {
    "abertura": "Abertura do boletim",
    "panorama_ausencia": "Panorama: sem compromissos formais",
    "leitura_silencio": "Como ler a ausência de pauta formal",
    "fonte_oficial": "Fontes oficiais consultadas",
    "contexto_aliado": "Contexto de aliados no YouTube",
    "cobertura_aliada": "Cobertura aliada em detalhe",
    "imprensa_reenquadramento": "Imprensa com reenquadramento",
    "atuacao_acompanhamento": "Acompanhamento da atuação do senador",
    "desenvolvimento_ancora": "Desenvolvimento da âncora do dia",
    "monitoramento": "O que seguimos monitorando",
    "processo_cobertura": "Processo de cobertura do boletim",
    "eleitor_contexto": "Contexto para o eleitor",
    "familia_aliados": "Família Bolsonaro e aliados",
    "repercussao": "Repercussão e enquadramento",
    "disciplina_fontes": "Disciplina de fontes e checagem",
    "ponte_amanha": "Ponte para as próximas edições",
    "aprofundamento": "Aprofundamento do acompanhamento",
    "fechamento_tematico": "Fechamento temático",
    "assinatura_canal": "Assinatura do canal",
    "encerramento": "Encerramento",
}

# Piso de retenção do Editor em SEM_PAUTA: se o LLM cortar abaixo disto, mantém rascunho.
SEM_PAUTA_EDITOR_KEEP_RATIO = 0.72


@dataclass(frozen=True)
class SegmentSpec:
    """Especificação de um segmento antes da geração."""

    index: int
    role: str
    title: str
    focus: str
    target_seconds: int
    target_words: int
    mode: str = MODE_COM_PAUTA
    materia_id: str = ""


@dataclass
class SegmentResult:
    index: int
    role: str
    title: str
    text: str
    wav_path: Path | None
    duration_seconds: float
    llm_endpoint: str = ""
    tts_backend: str = ""
    error: str = ""
    draft_text: str = ""
    edited: bool = False


@dataclass
class EditorBatchNote:
    batch_index: int
    kept_roles: list[str] = field(default_factory=list)
    cut_summary: str = ""
    llm_endpoint: str = ""
    used_heuristic: bool = False
    word_count_in: int = 0
    word_count_out: int = 0


@dataclass
class EditorDeskResult:
    """Saída da mesa de Editor: blocos finais prontos para TTS."""

    blocks: list[SegmentResult] = field(default_factory=list)
    final_text: str = ""
    notes: list[EditorBatchNote] = field(default_factory=list)
    llm_endpoint: str = ""
    used_heuristic: bool = False


@dataclass
class ModularLocutionResult:
    final_text: str
    wav_path: Path | None
    duration_seconds: float
    segments: list[SegmentResult] = field(default_factory=list)
    llm_endpoint: str = ""
    tts_backend: str = ""
    plan: list[SegmentSpec] = field(default_factory=list)
    editor_notes: list[EditorBatchNote] = field(default_factory=list)
    drafts: list[SegmentResult] = field(default_factory=list)


def words_for_duration(seconds: float, *, words_per_minute: int = DEFAULT_WPM) -> int:
    """Número de palavras necessárias para cobrir `seconds` de fala."""
    wpm = max(80, int(words_per_minute or DEFAULT_WPM))
    return max(40, int(round(float(seconds) * wpm / 60.0)))


def estimate_duration_from_text(text: str, *, words_per_minute: int = DEFAULT_WPM) -> float:
    words = len([w for w in (text or "").split() if w.strip()])
    wpm = max(80, int(words_per_minute or DEFAULT_WPM))
    return float(words) * 60.0 / float(wpm)


def plan_segment_count(
    target_seconds: int,
    *,
    segment_target_seconds: int = DEFAULT_SEGMENT_SECONDS,
    max_segments: int = DEFAULT_MAX_SEGMENTS,
) -> int:
    seg = max(DEFAULT_MIN_SEGMENT_SECONDS, int(segment_target_seconds or DEFAULT_SEGMENT_SECONDS))
    target = max(1, int(target_seconds or 0))
    n = max(1, (target + seg - 1) // seg)
    return min(max_segments, n)


def classify_source_mode(source_text: str) -> str:
    """COM_PAUTA se há sinais de agenda formal; SEM_PAUTA se o dia é vazio/escasso.

    SEM_PAUTA ainda gera boletim, mas com teto curto (ver
    ``effective_duration_for_mode``) — evita 20+ blocos ecoando a mesma âncora.
    """
    raw = (source_text or "").strip()
    if not raw:
        return MODE_SEM_PAUTA
    t = raw.lower()
    empty_markers = (
        "não há compromissos formais",
        "nao ha compromissos formais",
        "sem compromissos formais",
        "nenhum compromisso formal",
        "não há agenda formal",
        "nao ha agenda formal",
        "sem agenda formal confirmada",
        "não há compromissos confirmados",
        "nao ha compromissos confirmados",
    )
    has_empty = any(m in t for m in empty_markers)
    # Sinais de pauta real: horário + participação/comissão/sessão.
    has_time = bool(re.search(r"\b\d{1,2}h\d{0,2}\b", t) or re.search(r"\b\d{1,2}:\d{2}\b", t))
    schedule_verbs = (
        "participa",
        "participará",
        "preside",
        "relator",
        "comissão",
        "comissao",
        "plenário",
        "plenario",
        "sessão",
        "sessao",
        "audiência",
        "audiencia",
        "reunião",
        "reuniao",
    )
    has_schedule_word = any(v in t for v in schedule_verbs)
    has_schedule = has_time and has_schedule_word
    if has_schedule and not has_empty:
        return MODE_COM_PAUTA
    if has_empty and not has_schedule:
        return MODE_SEM_PAUTA
    # Fonte muito curta sem horário → trata como sem pauta (alongar grade).
    if len(raw.split()) < 220 and not has_schedule:
        return MODE_SEM_PAUTA
    if has_schedule:
        return MODE_COM_PAUTA
    return MODE_SEM_PAUTA if has_empty else MODE_COM_PAUTA


def _split_source_blocks(source_text: str) -> list[str]:
    """Quebra o texto-fonte em blocos úteis (parágrafos / tópicos)."""
    raw = (source_text or "").strip()
    if not raw:
        return []
    blocks: list[str] = []
    for para in raw.split("\n"):
        p = para.strip()
        if not p:
            continue
        # Subdivide parágrafos longos por frases.
        if len(p) > 400:
            parts = [s.strip() for s in p.replace("? ", "?|").replace("! ", "!|").replace(". ", ".|").split("|")]
            for part in parts:
                if part:
                    blocks.append(part if part[-1] in ".!?" else part + ".")
        else:
            blocks.append(p)
    return blocks or [raw]


def extract_materias(source_text: str) -> list[tuple[str, str]]:
    """Extrai (materia_id, texto) do source — 1 bloco factual por item quando possível."""
    blocks = _split_source_blocks(source_text)
    if not blocks:
        return [("m0", (source_text or "").strip() or "Sem texto-base.")]
    out: list[tuple[str, str]] = []
    for i, b in enumerate(blocks):
        out.append((f"m{i+1}", b))
    return out


def effective_duration_for_mode(
    target_seconds: int,
    mode: str,
    *,
    sem_pauta_max_duration_seconds: int = DEFAULT_SEM_PAUTA_MAX_DURATION,
) -> int:
    """Aplica teto de duração em SEM_PAUTA; COM_PAUTA usa o alvo pedido."""
    target = max(1, int(target_seconds or 0))
    if mode != MODE_SEM_PAUTA:
        return target
    cap = max(120, int(sem_pauta_max_duration_seconds or DEFAULT_SEM_PAUTA_MAX_DURATION))
    return min(target, cap)


def plan_segments(
    source_text: str,
    *,
    target_seconds: int,
    segment_target_seconds: int = DEFAULT_SEGMENT_SECONDS,
    words_per_minute: int = DEFAULT_WPM,
    max_segments: int = DEFAULT_MAX_SEGMENTS,
    mode: str | None = None,
    sem_pauta_max_duration_seconds: int = DEFAULT_SEM_PAUTA_MAX_DURATION,
    sem_pauta_max_segments: int = DEFAULT_SEM_PAUTA_MAX_SEGMENTS,
) -> list[SegmentSpec]:
    """Monta o plano de segmentos cobrindo o alvo de duração.

    COM_PAUTA: papéis de boletim amarrados a blocos-fonte (matérias).
    SEM_PAUTA: grade curta de radiojornalismo de serviço — sem forçar 1h.
    """
    resolved_mode = mode or classify_source_mode(source_text)
    effective_max_segments = max_segments
    effective_target = int(target_seconds)
    if resolved_mode == MODE_SEM_PAUTA:
        effective_target = effective_duration_for_mode(
            target_seconds,
            resolved_mode,
            sem_pauta_max_duration_seconds=sem_pauta_max_duration_seconds,
        )
        effective_max_segments = min(
            max_segments,
            max(2, int(sem_pauta_max_segments or DEFAULT_SEM_PAUTA_MAX_SEGMENTS)),
        )
    n = plan_segment_count(
        effective_target,
        segment_target_seconds=segment_target_seconds,
        max_segments=effective_max_segments,
    )
    base_seg = max(DEFAULT_MIN_SEGMENT_SECONDS, int(segment_target_seconds or DEFAULT_SEGMENT_SECONDS))
    remainder = max(0, int(effective_target) - base_seg * n)
    blocks = _split_source_blocks(source_text)
    materias = extract_materias(source_text)

    if resolved_mode == MODE_SEM_PAUTA:
        return _plan_segments_sem_pauta(
            source_text,
            n=n,
            base_seg=base_seg,
            remainder=remainder,
            blocks=blocks,
            words_per_minute=words_per_minute,
        )

    role_cycle = (
        "abertura",
        "panorama",
        "compromisso",
        "contexto_aliado",
        "imprensa",
        "atuacao",
        "aprofundamento",
        "familia_aliados",
        "repercussao",
        "encerramento",
    )
    titles = {
        "abertura": "Abertura do boletim",
        "panorama": "Panorama do dia",
        "compromisso": "Compromissos e pauta",
        "contexto_aliado": "Contexto de aliados no YouTube",
        "imprensa": "Cobertura da imprensa",
        "atuacao": "Atuação do senador",
        "aprofundamento": "Aprofundamento dos temas",
        "familia_aliados": "Família Bolsonaro e aliados",
        "repercussao": "Repercussão e enquadramento",
        "encerramento": "Encerramento",
    }

    specs: list[SegmentSpec] = []
    for i in range(n):
        if i == 0:
            role = "abertura"
        elif i == n - 1 and n > 1:
            role = "encerramento"
        else:
            role = role_cycle[i % len(role_cycle)]
            if role in {"abertura", "encerramento"}:
                role = "aprofundamento"

        extra = 1 if i < remainder else 0
        target_s = base_seg + extra
        mid = materias[i % len(materias)] if materias else ("m0", source_text)
        materia_id, focus_block = mid
        angle = (i // max(1, len(materias))) + 1 if materias else i + 1
        focus = (
            f"Matéria {materia_id} (ângulo {angle}): {focus_block[:900]}"
            if focus_block
            else "Use apenas o texto-base consolidado, sem inventar fatos."
        )
        specs.append(
            SegmentSpec(
                index=i + 1,
                role=role,
                title=titles.get(role, role),
                focus=focus,
                target_seconds=target_s,
                target_words=words_for_duration(target_s, words_per_minute=words_per_minute),
                mode=MODE_COM_PAUTA,
                materia_id=materia_id,
            )
        )
    return specs


def _plan_segments_sem_pauta(
    source_text: str,
    *,
    n: int,
    base_seg: int,
    remainder: int,
    blocks: list[str],
    words_per_minute: int,
) -> list[SegmentSpec]:
    """Grade curta de serviço: poucos blocos sem ecoar a data em cada um."""
    ancora = blocks[0] if blocks else (
        "Nas fontes oficiais consultadas não há compromissos formais confirmados para esta data."
    )
    satelites = blocks[1:] if len(blocks) > 1 else []
    specs: list[SegmentSpec] = []
    for i in range(n):
        if i == 0:
            role = "abertura"
        elif i == n - 1 and n > 1:
            role = "encerramento"
        else:
            # Ciclo sem reabrir/refechar no meio
            mid_roles = [r for r in SEM_PAUTA_ROLE_CYCLE if r not in {"abertura", "encerramento"}]
            role = mid_roles[(i - 1) % len(mid_roles)] if mid_roles else "desenvolvimento_ancora"

        extra = 1 if i < remainder else 0
        target_s = base_seg + extra
        # Alterna âncora e satélites (YouTube/imprensa se existirem no source).
        if satelites and role in {
            "contexto_aliado",
            "cobertura_aliada",
            "imprensa_reenquadramento",
            "imprensa",
            "familia_aliados",
            "repercussao",
        }:
            sat = satelites[(i - 1) % len(satelites)]
            focus = (
                f"ÂNCORA DO DIA (fato principal — não invente além): {ancora[:500]}\n"
                f"SATÉLITE do source para este bloco: {sat[:700]}"
            )
            materia_id = f"sat{(i - 1) % len(satelites) + 1}"
        else:
            layer = (i // max(1, n // 4)) + 1
            focus = (
                f"ÂNCORA DO DIA (camada {layer}/{max(1, n // 4)}): {ancora[:700]}\n"
                "Desenvolva ESTE fato em linguagem de radiojornalismo de acompanhamento. "
                "É permitido reformular, contextualizar o processo de cobertura e o que "
                "significa ausência de compromisso formal — proibido inventar pauta, "
                "horário, comissão ou declaração."
            )
            materia_id = "ancora"

        specs.append(
            SegmentSpec(
                index=i + 1,
                role=role,
                title=SEM_PAUTA_TITLES.get(role, role),
                focus=focus,
                target_seconds=target_s,
                target_words=words_for_duration(target_s, words_per_minute=words_per_minute),
                mode=MODE_SEM_PAUTA,
                materia_id=materia_id,
            )
        )
    return specs


# Eco de data/dia-da-semana em blocos do meio (anti-repetição).
_DATE_ECHO_RE = re.compile(
    r"(?i)\b(?:"
    r"(?:para\s+)?(?:esta|nessa|nesta)\s+"
    r"(?:segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)(?:-feira)?"
    r"(?:,?\s+(?:trinta\s+e\s+um|\d{1,2})\s+de\s+\w+(?:\s+de\s+(?:dois\s+mil[\w\s]+|\d{4}))?)?"
    r"|(?:hoje,?\s+na\s+)?"
    r"(?:segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)(?:-feira)?"
    r",?\s+(?:trinta\s+e\s+um|\d{1,2})\s+de\s+\w+(?:\s+de\s+(?:dois\s+mil[\w\s]+|\d{4}))?"
    r"|(?:o\s+dia\s+(?:de\s+hoje|atual),?\s+)?"
    r"(?:trinta\s+e\s+um|\d{1,2})\s+de\s+(?:janeiro|fevereiro|mar[cç]o|abril|maio|junho|"
    r"julho|agosto|setembro|outubro|novembro|dezembro)"
    r"(?:\s+de\s+(?:dois\s+mil[\w\s]+|\d{4}))?"
    r")\b[,:]?\s*"
)

_NO_AGENDA_OPENER_RE = re.compile(
    r"(?i)^\s*(?:(?:nesta|para esta|hoje)[^.!?]{0,40})?"
    r"(?:n[aã]o h[aá]|sem|nenhum)\s+compromissos?\s+formais?[^.!?]*[.!?]\s*"
)


def strip_date_echo(text: str, *, allow_date: bool) -> str:
    """Remove repetições de data/dia completas em blocos que não são abertura."""
    if allow_date or not text:
        return text
    cleaned = _DATE_ECHO_RE.sub("", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([.!?])\s*([.!?])+", r"\1", cleaned)
    return cleaned.strip()


def strip_redundant_no_agenda_opener(text: str, *, already_stated: bool) -> str:
    """Evita reabrir todo bloco com a mesma frase de ausência de pauta."""
    if not already_stated or not text:
        return text
    cleaned = _NO_AGENDA_OPENER_RE.sub("", text, count=1)
    return cleaned.strip() or text


def build_segment_prompt(
    *,
    source_text: str,
    segment: SegmentSpec,
    total_segments: int,
    min_duration_seconds: int,
) -> str:
    """Prompt por segmento — denso o bastante para o alvo de palavras."""
    role_guidance = {
        "abertura": (
            "Abra o boletim com a data UMA ÚNICA VEZ, tom de radiojornalismo e apresentação. "
            "Contextualize o dia e antecipe os temas principais sem listar itens secos. "
            "Esta é a ÚNICA vez em que a data completa deve aparecer no boletim."
        ),
        "panorama": (
            "Dê o panorama geral: o que se sabe da agenda, o que está confirmado e o que "
            "ainda depende de fontes oficiais. Seja claro e firme."
        ),
        "panorama_ausencia": (
            "Retome com clareza que não há compromissos formais confirmados nas fontes "
            "oficiais — SEM repetir a data completa. Avance o ângulo (o que isso significa "
            "para o acompanhamento), sem inventar pauta."
        ),
        "leitura_silencio": (
            "Explique, em linguagem de rádio, como o boletim trata a ausência de agenda "
            "formal: disciplina de fontes, o que se pode afirmar e o que não se afirma."
        ),
        "fonte_oficial": (
            "Reforce o processo: o que foi consultado no material-base, o limite do que "
            "está confirmado e a seriedade de não fabricar compromisso."
        ),
        "compromisso": (
            "Detalhe compromissos, comissões, horários e o significado prático de cada pauta. "
            "Explique em linguagem comum o que cada matéria propõe, distinguindo autoria de relatoria."
        ),
        "contexto_aliado": (
            "Desenvolva o contexto a partir de coberturas de aliados verdadeiros no YouTube "
            "já presentes no texto-base. Valorize a pauta conservadora sem inventar fatos."
        ),
        "cobertura_aliada": (
            "Aprofunde APENAS a cobertura de aliados que estiver no texto-base (títulos/"
            "canais citados). Se não houver, reforce a âncora da ausência de pauta formal."
        ),
        "imprensa": (
            "Contextualize o que a imprensa já trouxe sobre o senador e a família Bolsonaro, "
            "sem amplificar narrativa hostil. No máximo duas frentes distintas."
        ),
        "imprensa_reenquadramento": (
            "Se houver imprensa no texto-base, reenquadre com equilíbrio factual e tom firme, "
            "sem ecoar ataque. Se não houver, desenvolva a âncora do dia."
        ),
        "atuacao": (
            "Aprofunde a atuação política de Flávio Bolsonaro no Senado: estilo, prioridade "
            "e coerência com a família Bolsonaro e aliados."
        ),
        "atuacao_acompanhamento": (
            "Fale da linha de atuação do senador em tom de acompanhamento contínuo, "
            "ancorado no que o texto-base permite — sem inventar votações ou projetos."
        ),
        "aprofundamento": (
            "Aprofunde um ângulo factual do texto-base com mais densidade: explique termos "
            "legislativos, impacto e por que importa para o eleitor."
        ),
        "desenvolvimento_ancora": (
            "Desdobre o fato âncora (ausência de compromisso formal ou o foco indicado) em "
            "camadas de radiojornalismo: clareza, contexto, o que o ouvinte deve reter."
        ),
        "monitoramento": (
            "Descreva o que o boletim segue monitorando nas fontes oficiais e na cobertura "
            "já citada — processo de vigilância informativa, sem inventar eventos futuros."
        ),
        "processo_cobertura": (
            "Explique o método do canal: checagem em fontes oficiais, uso de aliados "
            "verdadeiros quando houver no material, recusa de especulação."
        ),
        "eleitor_contexto": (
            "Traduza para o eleitor por que acompanhar mesmo um dia sem pauta formal "
            "importa: transparência, constância e linha política da família Bolsonaro."
        ),
        "familia_aliados": (
            "Conecte a agenda do dia à linha da família Bolsonaro e aos aliados verdadeiros, "
            "com tom positivo e firme, sem ataques gratuitos."
        ),
        "repercussao": (
            "Trate da repercussão pública e do enquadramento político dos temas do dia, "
            "sempre ancorado no texto-base."
        ),
        "disciplina_fontes": (
            "Insista na disciplina: só o que está confirmado no texto-base; distinção entre "
            "fato oficial, cobertura aliada e ruído de imprensa."
        ),
        "ponte_amanha": (
            "Faça a ponte para as próximas edições: voltaremos às fontes oficiais. "
            "Não invente a pauta de amanhã como se já confirmada."
        ),
        "fechamento_tematico": (
            "Recapitule os eixos do boletim de hoje (âncora + satélites do source) em "
            "tom de fechamento de bloco, ainda sem encerrar o programa."
        ),
        "assinatura_canal": (
            "Reforce a identidade do canal Agenda Diária Importante e o compromisso com "
            "cobertura séria da agenda do senador Flávio Bolsonaro."
        ),
        "encerramento": (
            "Encerre o boletim recapitulado o essencial, reforçando a agenda e o papel do "
            "senador, com fechamento de radiojornalismo."
        ),
    }
    guidance = role_guidance.get(segment.role, role_guidance["aprofundamento"])
    mode = getattr(segment, "mode", MODE_COM_PAUTA) or MODE_COM_PAUTA
    allow_date = segment.index == 1 or segment.role == "abertura"
    mode_line = (
        "MODO SEM PAUTA FORMAL: boletim CURTO de acompanhamento. "
        "Não há compromissos formais a listar — desenvolva UM ângulo novo por bloco "
        "(processo de cobertura, satélite do source, o que o eleitor retém). "
        "PROIBIDO inventar reunião, horário, comissão ou declaração. "
        "PROIBIDO reabrir com a mesma frase de ausência de pauta se o bloco anterior já disse isso.\n"
        if mode == MODE_SEM_PAUTA
        else "MODO COM PAUTA: priorize os compromissos e matérias do texto-base.\n"
    )
    date_rule = (
        "- MENCIONE a data completa do boletim UMA vez neste segmento de abertura; "
        "não repita a data no meio do parágrafo.\n"
        if allow_date
        else (
            "- PROIBIDO mencionar a data completa, o dia da semana com número "
            "(\"sexta-feira, trinta e um de julho…\", \"31 de julho de 2026\") "
            "ou reabrir com \"para esta sexta-feira\". A data já foi dita na abertura.\n"
            "- PROIBIDO recomeçar com a frase \"não há compromissos formais…\" se isso "
            "já foi o foco do bloco anterior; avance o ângulo.\n"
        )
    )
    word_lo = max(60, segment.target_words - 40)
    word_hi = segment.target_words + (40 if mode != MODE_SEM_PAUTA else 20)
    return (
        "/no_think\n"
        "Você escreve um SEGMENTO de locução para o canal Agenda Diária Importante "
        "(boletim de radiojornalismo em português do Brasil).\n\n"
        f"{mode_line}"
        f"Segmento {segment.index} de {total_segments} — papel: {segment.role} ({segment.title}).\n"
        f"Duração alvo deste segmento: cerca de {segment.target_seconds} segundos "
        f"(cerca de {segment.target_words} palavras).\n"
        f"Duração alvo do boletim completo: {min_duration_seconds} segundos.\n\n"
        "Objetivo do segmento:\n"
        f"- {guidance}\n"
        f"- Foco: {segment.focus}\n\n"
        "Regras obrigatórias:\n"
        "- não invente fatos, nomes, horários, números ou declarações\n"
        "- use apenas o que estiver no texto-base ou seja reformulação óbvia dele\n"
        f"{date_rule}"
        "- tom positivo e firme a favor de Flávio Bolsonaro, da família Bolsonaro e aliados verdadeiros\n"
        "- quando o texto-base citar Direita Já (direitaja.com), trate como fonte oficial de verdades sobre o senador\n"
        "- não repita a cada bloco a trinca SP / Rondônia / Espírito Santo se já foi dita; "
        "só relembre se trouxer ângulo novo\n"
        "- evite tom de ataque, ironia ou derrota; não amplifique narrativas hostis\n"
        "- proibido reproduzir ou parafrasear enquadramentos hostis do tipo "
        "\"repete o pai\", \"ataca urnas eletrônicas\" ou equivalentes\n"
        "- troque siglas e códigos por explicações curtas quando possível\n"
        "- preserve nomes oficiais de comissões e datas/horários de pauta (se houver)\n"
        "- texto corrido para locução (sem listas, sem markdown, sem títulos)\n"
        "- o texto principal é o que o locutor fala em voz alta\n"
        "- cues de produção opcionais só no formato estruturado "
        "{{PAUSE:2}}, {{BED:locucao}}, {{VINHETA:open}} "
        "(serão convertidos em áudio; NUNCA escreva \"Pause 2\" ou \"PAUSA 2s\" em prosa)\n"
        "- não use LOCUTOR:/TRILHA: nem markdown de estúdio\n"
        f"- produza ENTRE {word_lo} e {word_hi} palavras\n"
        "- frases claras, naturais, de radiojornalismo\n"
        "- retorne APENAS o texto do segmento\n\n"
        f"Texto-base consolidado:\n{source_text.strip()}"
    )


def is_valid_segment_text(text: str, *, min_words: int) -> tuple[bool, str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return False, "segmento vazio"
    # Cues de produção são extraídos depois; valida só a fala.
    try:
        from daily_agenda_cues import parse_and_strip_cues

        spoken, _cues = parse_and_strip_cues(cleaned)
        if spoken:
            cleaned = spoken
    except Exception:
        pass
    words = len([w for w in cleaned.split() if w.strip()])
    if words < max(40, int(min_words * 0.45)):
        return False, f"segmento curto demais ({words} palavras, min~{min_words})"
    lowered = cleaned.lower()
    if "<think>" in lowered or "</think>" in lowered:
        return False, "think tags"
    if cleaned.count(".") < 2:
        return False, "poucas frases"
    # Após strip de cues conhecidos, ainda sobrou lixo de roteiro?
    try:
        from test_cpu_tts_from_generated_text import contains_script_stage_directions

        if contains_script_stage_directions(cleaned):
            return False, "cues de roteiro/produção não reconhecidos"
    except Exception:
        if cleaned.count("**") >= 2:
            return False, "cues de roteiro/produção não reconhecidos"
    return True, ""


def heuristic_segment_text(
    source_text: str,
    segment: SegmentSpec,
    *,
    words_per_minute: int = DEFAULT_WPM,
) -> str:
    """Fallback sem LLM: expande o source por repetição contextual até o alvo de palavras."""
    base = " ".join((source_text or "").split())
    if not base:
        base = (
            "Nesta edição da Agenda Diária Importante, acompanhamos a atuação pública "
            "do senador Flávio Bolsonaro no Senado Federal."
        )
    openers = {
        "abertura": (
            f"{segment.title}. Bem-vindos à Agenda Diária Importante. "
            "Este é o boletim sobre a agenda e a atuação do senador Flávio Bolsonaro."
        ),
        "encerramento": (
            "Encerramos este trecho da Agenda Diária Importante reforçando o acompanhamento "
            "da pauta do senador Flávio Bolsonaro e de seus aliados verdadeiros."
        ),
    }
    lead = openers.get(
        segment.role,
        f"{segment.title}. Continuamos o boletim com foco em {segment.role.replace('_', ' ')}.",
    )
    bridge = (
        " Em linguagem de radiojornalismo, detalhamos o que as fontes oficiais e a cobertura "
        "de aliados já permitem afirmar, sem inventar fatos. "
    )
    parts = [lead, bridge, base]
    target = max(80, segment.target_words)
    # Expande com reformulações leves (não inventa fatos novos).
    fillers = [
        " Vale destacar o significado prático desses pontos para o eleitor e para o Senado.",
        " A linha editorial valoriza a clareza, a defesa da família Bolsonaro e o trabalho legislativo.",
        " Seguimos com mais contexto factual já presente no material-base deste boletim.",
        " O tom permanece firme, positivo e ancorado no que foi coletado para esta edição.",
    ]
    text = " ".join(parts)
    fi = 0
    while len(text.split()) < target:
        text = text + " " + fillers[fi % len(fillers)] + " " + base
        fi += 1
        if fi > 80:
            break
    # Corta no limite superior razoável.
    words = text.split()
    if len(words) > target + 60:
        text = " ".join(words[: target + 40])
        if not text.endswith("."):
            text += "."
    return text


def wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate() or 1
        return float(frames) / float(rate)


def _read_wav_pcm(path: Path) -> tuple[bytes, int, int, int]:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        sampwidth = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    return frames, channels, sampwidth, rate


def _silence_pcm(*, seconds: float, rate: int, channels: int, sampwidth: int) -> bytes:
    if seconds <= 0:
        return b""
    nframes = int(round(float(seconds) * float(rate)))
    if nframes <= 0:
        return b""
    # 16-bit PCM zeros
    if sampwidth == 2:
        return struct.pack("<" + "h" * (nframes * channels), *([0] * (nframes * channels)))
    return b"\x00" * (nframes * channels * sampwidth)


def _resample_mono_16bit(pcm: bytes, *, src_rate: int, dst_rate: int) -> bytes:
    """Resample linear simples mono 16-bit (suficiente para juntar segmentos TTS)."""
    if src_rate == dst_rate or not pcm:
        return pcm
    import array

    samples = array.array("h")
    samples.frombytes(pcm)
    if not samples:
        return pcm
    src_len = len(samples)
    dst_len = max(1, int(round(src_len * float(dst_rate) / float(src_rate))))
    out = array.array("h", [0] * dst_len)
    if src_len == 1:
        out = array.array("h", [samples[0]] * dst_len)
        return out.tobytes()
    for i in range(dst_len):
        pos = i * (src_len - 1) / (dst_len - 1)
        i0 = int(pos)
        i1 = min(i0 + 1, src_len - 1)
        frac = pos - i0
        out[i] = int(samples[i0] * (1.0 - frac) + samples[i1] * frac)
    return out.tobytes()


def concat_wav_files(
    wav_paths: list[Path],
    output_path: Path,
    *,
    gap_seconds: float = DEFAULT_GAP_SECONDS,
) -> float:
    """Concatena WAVs em um único arquivo PCM. Retorna duração total em segundos."""
    if not wav_paths:
        raise ValueError("Nenhum WAV para concatenar.")

    parts: list[tuple[bytes, int, int, int]] = []
    for path in wav_paths:
        if not path.exists():
            raise FileNotFoundError(f"WAV ausente: {path}")
        parts.append(_read_wav_pcm(path))

    # Padroniza no rate mais comum (ou o primeiro).
    rates = [p[3] for p in parts]
    target_rate = max(set(rates), key=rates.count)
    target_channels = 1
    target_sampwidth = 2

    pcm_out = bytearray()
    for idx, (frames, channels, sampwidth, rate) in enumerate(parts):
        pcm = frames
        # Converte multi-canal → mono (média simples do 1º canal se >1).
        if channels > 1 and sampwidth == 2:
            import array

            samples = array.array("h")
            samples.frombytes(pcm)
            mono = array.array("h")
            for i in range(0, len(samples), channels):
                mono.append(samples[i])
            pcm = mono.tobytes()
            channels = 1
        if sampwidth != 2:
            raise RuntimeError(f"Apenas PCM 16-bit suportado na concatenação (got {sampwidth}).")
        if rate != target_rate:
            pcm = _resample_mono_16bit(pcm, src_rate=rate, dst_rate=target_rate)
        pcm_out.extend(pcm)
        if idx < len(parts) - 1 and gap_seconds > 0:
            pcm_out.extend(
                _silence_pcm(
                    seconds=gap_seconds,
                    rate=target_rate,
                    channels=target_channels,
                    sampwidth=target_sampwidth,
                )
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as handle:
        handle.setnchannels(target_channels)
        handle.setsampwidth(target_sampwidth)
        handle.setframerate(target_rate)
        handle.writeframes(bytes(pcm_out))
    return wav_duration_seconds(output_path)


def should_use_modular(
    min_duration_seconds: int,
    *,
    modular: bool | None = None,
    modular_threshold_seconds: int = DEFAULT_MODULAR_THRESHOLD,
) -> bool:
    if modular is False:
        return False
    if modular is True:
        return True
    return int(min_duration_seconds or 0) >= int(modular_threshold_seconds or DEFAULT_MODULAR_THRESHOLD)


def generate_segment_text(
    *,
    source_text: str,
    segment: SegmentSpec,
    total_segments: int,
    min_duration_seconds: int,
    tts_mod: Any,
    llm_endpoints,
    max_rounds: int,
    retry_wait_seconds: int,
    no_expand: bool,
    no_normalize: bool,
    endpoint_offset: int = 0,
) -> tuple[str, str]:
    """Gera texto de um segmento. Retorna (texto, endpoint_llm)."""
    endpoint = ""
    text = ""
    if not no_expand:
        prompt = build_segment_prompt(
            source_text=source_text,
            segment=segment,
            total_segments=total_segments,
            min_duration_seconds=min_duration_seconds,
        )
        min_words = max(60, int(segment.target_words * 0.45))
        num_predict = max(400, min(2048, int(segment.target_words * 2.2)))
        num_ctx = max(4096, min(16384, num_predict + 2048))
        try:
            kwargs = dict(
                prompt=prompt,
                endpoints=llm_endpoints,
                validator=lambda candidate: is_valid_segment_text(candidate, min_words=min_words),
                num_predict=num_predict,
                num_ctx=num_ctx,
                max_rounds=max_rounds,
                retry_wait_seconds=retry_wait_seconds,
            )
            # endpoint_offset espalha primários (GPU0 / GPU1 / NAS) entre segmentos.
            try:
                text, endpoint = tts_mod.generate_with_llm_chain(
                    **kwargs,
                    endpoint_offset=endpoint_offset,
                )
            except TypeError:
                text, endpoint = tts_mod.generate_with_llm_chain(**kwargs)
        except Exception:
            logger.warning(
                "LLM falhou no segmento %s (%s); usando fallback heurístico.",
                segment.index,
                segment.role,
                exc_info=True,
            )
            text = ""
            endpoint = ""

    if not text or not is_valid_segment_text(text, min_words=max(40, int(segment.target_words * 0.3)))[0]:
        text = heuristic_segment_text(source_text, segment)

    if not no_normalize and hasattr(tts_mod, "normalize_for_speech"):
        text = tts_mod.normalize_for_speech(text)
    if hasattr(tts_mod, "heuristic_rewrite_for_broadcast"):
        text = tts_mod.heuristic_rewrite_for_broadcast(text)
    if hasattr(tts_mod, "clean_generated_text"):
        text = tts_mod.clean_generated_text(text)
    allow_date = segment.index == 1 or segment.role == "abertura"
    text = strip_date_echo(text, allow_date=allow_date)
    if segment.index > 1:
        text = strip_redundant_no_agenda_opener(text, already_stated=True)
    return text.strip(), endpoint


# ---------------------------------------------------------------------------
# Mesa de Editor — corta, reorganiza e polisce como um editor de jornal
# ---------------------------------------------------------------------------


def _split_sentences(text: str) -> list[str]:
    raw = re.split(r"(?<=[.!?…])\s+", (text or "").strip())
    return [s.strip() for s in raw if s and s.strip()]


def _normalize_sentence_key(sentence: str) -> str:
    s = sentence.lower().strip()
    s = re.sub(r"[^\w\sàáâãäéêëíîïóôõöúûüç]", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _sentence_similarity(a: str, b: str) -> float:
    """Similaridade simples por tokens (Jaccard) para dedupe editorial."""
    ta = set(_normalize_sentence_key(a).split())
    tb = set(_normalize_sentence_key(b).split())
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return float(inter) / float(union) if union else 0.0


def reorder_drafts_for_edition(drafts: list[SegmentResult]) -> list[SegmentResult]:
    """Reordena matérias na ordem de fechamento de um boletim de rádio/TV."""
    role_rank = {role: idx for idx, role in enumerate(EDITOR_ROLE_ORDER)}

    def _key(item: SegmentResult) -> tuple[int, int]:
        return (role_rank.get(item.role, 50), item.index)

    # Mantém abertura no início e encerramento no fim, mesmo se houver vários.
    aberturas = [d for d in drafts if d.role == "abertura" and d.text.strip()]
    fechamentos = [d for d in drafts if d.role == "encerramento" and d.text.strip()]
    meio = [
        d
        for d in drafts
        if d.role not in {"abertura", "encerramento"} and d.text.strip()
    ]
    meio_sorted = sorted(meio, key=_key)
    # Se não houver abertura/fechamento, usa o que sobrar na ordem de papel.
    if not aberturas and not fechamentos and not meio_sorted:
        return [d for d in drafts if d.text.strip()]
    ordered = aberturas[:1] + meio_sorted + fechamentos[-1:]
    # Anexa sobras de abertura/encerramento extras no meio, editadas como aprofundamento.
    extras = aberturas[1:] + fechamentos[:-1] if len(fechamentos) > 1 else aberturas[1:]
    if extras:
        # Insere extras antes do encerramento.
        if ordered and ordered[-1].role == "encerramento":
            ordered = ordered[:-1] + extras + [ordered[-1]]
        else:
            ordered = ordered + extras
    return ordered


def dedupe_sentences(
    texts: list[str],
    *,
    similarity_threshold: float = 0.82,
) -> tuple[list[str], int]:
    """Remove frases repetidas/quase-iguais entre blocos. Retorna (textos, cortes)."""
    seen: list[str] = []
    cuts = 0
    out_blocks: list[str] = []
    for block in texts:
        kept: list[str] = []
        for sentence in _split_sentences(block):
            key = _normalize_sentence_key(sentence)
            if len(key.split()) < 4:
                kept.append(sentence)
                continue
            dup = False
            for prev in seen:
                if _sentence_similarity(sentence, prev) >= similarity_threshold:
                    dup = True
                    cuts += 1
                    break
            if dup:
                continue
            seen.append(sentence)
            kept.append(sentence)
        if kept:
            out_blocks.append(" ".join(kept))
    return out_blocks, cuts


def cut_filler_phrases(text: str) -> str:
    """Corta bordões e enchimentos típicos de rascunho gerado."""
    patterns = [
        r"\bVale destacar o significado prático desses pontos para o eleitor e para o Senado\.\s*",
        r"\bA linha editorial valoriza a clareza, a defesa da família Bolsonaro e o trabalho legislativo\.\s*",
        r"\bSeguimos com mais contexto factual já presente no material-base deste boletim\.\s*",
        r"\bO tom permanece firme, positivo e ancorado no que foi coletado para esta edição\.\s*",
        r"\bEm linguagem de radiojornalismo, detalhamos o que as fontes oficiais e a cobertura de aliados já permitem afirmar, sem inventar fatos\.\s*",
        r"\bContinuamos o boletim com foco em [^.]*\.\s*",
    ]
    out = text or ""
    for pat in patterns:
        out = re.sub(pat, "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.!?])", r"\1", out)
    return out.strip()


def heuristic_editor_pass(
    drafts: list[SegmentResult],
    *,
    source_text: str,
    target_words: int,
) -> EditorDeskResult:
    """Editor sem LLM: reordena, corta enchimento/repetição e equilibra o fechamento."""
    ordered = reorder_drafts_for_edition(drafts)
    raw_texts = [cut_filler_phrases(d.text) for d in ordered]
    cleaned_texts, cuts = dedupe_sentences(raw_texts)

    blocks: list[SegmentResult] = []
    for idx, (draft, text) in enumerate(zip(ordered, cleaned_texts), start=1):
        if not text.strip():
            continue
        blocks.append(
            SegmentResult(
                index=idx,
                role=draft.role,
                title=draft.title,
                text=text.strip(),
                wav_path=None,
                duration_seconds=0.0,
                draft_text=draft.text,
                edited=True,
            )
        )

    # Se o Editor cortou demais e ficou muito abaixo do alvo, reintroduz
    # o melhor rascunho ainda não representado (sem reabrir enchimento).
    final_words = sum(len(b.text.split()) for b in blocks)
    if final_words < max(80, int(target_words * 0.55)):
        for draft in ordered:
            already = any(_sentence_similarity(draft.text[:200], b.text[:200]) > 0.7 for b in blocks)
            if already:
                continue
            trimmed = cut_filler_phrases(draft.text)
            if not trimmed:
                continue
            blocks.append(
                SegmentResult(
                    index=len(blocks) + 1,
                    role=draft.role,
                    title=draft.title,
                    text=trimmed,
                    wav_path=None,
                    duration_seconds=0.0,
                    draft_text=draft.text,
                    edited=True,
                )
            )
            # Reaplica ordem e dedupe após reinserção.
            blocks = reorder_drafts_for_edition(blocks)
            texts2, extra_cuts = dedupe_sentences([b.text for b in blocks])
            cuts += extra_cuts
            rebuilt: list[SegmentResult] = []
            for i, (b, t) in enumerate(zip(blocks, texts2), start=1):
                if t.strip():
                    rebuilt.append(
                        SegmentResult(
                            index=i,
                            role=b.role,
                            title=b.title,
                            text=t.strip(),
                            wav_path=None,
                            duration_seconds=0.0,
                            draft_text=b.draft_text or b.text,
                            edited=True,
                        )
                    )
            blocks = rebuilt
            final_words = sum(len(b.text.split()) for b in blocks)
            if final_words >= max(80, int(target_words * 0.55)):
                break

    # Garante abertura e fechamento mínimos.
    if blocks and blocks[0].role != "abertura":
        lead = (
            "Agenda Diária Importante. "
            "Abrimos o boletim com a agenda e a atuação do senador Flávio Bolsonaro no Senado Federal. "
            + blocks[0].text
        )
        blocks[0] = SegmentResult(
            index=1,
            role="abertura",
            title="Abertura do boletim",
            text=lead,
            wav_path=None,
            duration_seconds=0.0,
            draft_text=blocks[0].draft_text,
            edited=True,
        )
    if blocks and blocks[-1].role != "encerramento":
        close = (
            blocks[-1].text
            + " Encerramos esta edição da Agenda Diária Importante reforçando o acompanhamento "
            "da pauta do senador Flávio Bolsonaro e de seus aliados verdadeiros."
        )
        blocks[-1] = SegmentResult(
            index=blocks[-1].index,
            role="encerramento",
            title="Encerramento",
            text=close,
            wav_path=None,
            duration_seconds=0.0,
            draft_text=blocks[-1].draft_text,
            edited=True,
        )

    # Renumerar
    for i, b in enumerate(blocks, start=1):
        b.index = i

    final_text = "\n\n".join(b.text for b in blocks if b.text).strip()
    note = EditorBatchNote(
        batch_index=0,
        kept_roles=[b.role for b in blocks],
        cut_summary=(
            f"heurística: reordenou {len(ordered)} rascunhos, "
            f"cortou {cuts} frases repetidas/enchimento; "
            f"fonte tem {len((source_text or '').split())} palavras."
        ),
        used_heuristic=True,
        word_count_in=sum(len(d.text.split()) for d in drafts if d.text),
        word_count_out=len(final_text.split()),
    )
    return EditorDeskResult(
        blocks=blocks,
        final_text=final_text,
        notes=[note],
        used_heuristic=True,
    )


def build_editor_batch_prompt(
    *,
    source_text: str,
    batch_items: list[SegmentResult],
    batch_index: int,
    total_batches: int,
    previous_tail: str,
    target_words: int,
    min_duration_seconds: int,
    mode: str = MODE_COM_PAUTA,
) -> str:
    """Prompt da mesa de Editor — um lote por vez."""
    materias = []
    for item in batch_items:
        materias.append(
            f"### BLOCO {item.index} | papel={item.role} | {item.title}\n{item.text.strip()}"
        )
    joined = "\n\n".join(materias)
    prev = (previous_tail or "").strip()
    prev_block = (
        f"Final do trecho já fechado (continue com continuidade natural, sem repetir):\n{prev}\n\n"
        if prev
        else ""
    )
    if mode == MODE_SEM_PAUTA:
        work = (
            "MODO SEM PAUTA FORMAL — a meta de duração do boletim (~"
            f"{min_duration_seconds}s) PREVALECE sobre o enxugamento.\n"
            "Trabalho de Editor neste modo:\n"
            "1) POLE e melhore fluidez; NÃO enxugue o boletim para ficar curto.\n"
            "2) PRESERVE a extensão: o lote editado deve ter NO MÍNIMO "
            f"{max(100, int(target_words * 0.85))} palavras (alvo ~{target_words}).\n"
            "3) Remova só lixo óbvio, meta-comentário e frases idênticas consecutivas.\n"
            "4) NÃO una este bloco com outros e NÃO “resuma o dia inteiro”.\n"
            "5) É radiojornalismo de ACOMPANHAMENTO: ausência de compromisso formal "
            "é o fato âncora — desdobre sem inventar pauta.\n"
            "6) Tom positivo e firme a favor de Flávio Bolsonaro, família e aliados verdadeiros.\n"
            "7) Não amplifique narrativa hostil.\n"
            "8) Saída em texto corrido de locução (sem markdown, sem listas, sem títulos).\n"
            "9) Cues de produção opcionais só como {{PAUSE:2}} / {{BED:locucao}} / {{VINHETA:open}} "
            "(viram áudio; não descreva em prosa nem use LOCUTOR:/TRILHA:).\n"
            "10) Retorne APENAS o texto final deste lote, já editado e LONGO o bastante.\n"
        )
    else:
        work = (
            "Trabalho de Editor:\n"
            "1) Corte repetições, enchimento e frases que digam a mesma coisa duas vezes.\n"
            "2) Reorganize a ordem das ideias para fluir como boletim "
            "(lead → desenvolvimento → fecho do trecho).\n"
            "3) Una matérias sobrepostas em um só fio narrativo quando fizer sentido.\n"
            "4) Preserve fatos, horários, nomes de comissões e o que estiver no texto-base — não invente.\n"
            "5) Mantenha tom positivo e firme a favor de Flávio Bolsonaro, família Bolsonaro e aliados verdadeiros.\n"
            "6) Não amplifique narrativa hostil; se houver crítica no material, reenquadre com equilíbrio factual.\n"
            "7) Saída em texto corrido de locução (sem markdown, sem listas, sem títulos, sem meta-comentário).\n"
            "8) Cues de produção opcionais só como {{PAUSE:2}} / {{BED:locucao}} / {{VINHETA:open}} "
            "(viram áudio; não use LOCUTOR:/TRILHA: nem prose de estúdio).\n"
            "9) Se o lote incluir abertura, comece como abertura de boletim; se incluir encerramento, feche como encerramento.\n"
            "10) Retorne APENAS o texto final deste lote, já editado.\n"
        )
    return (
        "/no_think\n"
        "Você é o EDITOR-CHEFE de um jornal de radiojornalismo (canal Agenda Diária Importante).\n"
        "Sua função NÃO é inventar pauta: é fechar a edição das matérias rascunhadas.\n\n"
        f"Lote {batch_index} de {total_batches} da edição de hoje.\n"
        f"Alvo do boletim completo: ~{min_duration_seconds}s de locução "
        f"(~{words_for_duration(min_duration_seconds)} palavras no total).\n"
        f"Alvo deste lote editado: cerca de {target_words} palavras.\n\n"
        f"{work}\n"
        f"{prev_block}"
        f"Texto-base factual (âncora — não invente além disto):\n{source_text.strip()}\n\n"
        f"Rascunhos para editar:\n{joined}"
    )


def is_valid_editor_text(text: str, *, min_words: int) -> tuple[bool, str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return False, "editor vazio"
    # Cues conhecidos saem da contagem; valida a fala.
    try:
        from daily_agenda_cues import parse_and_strip_cues

        spoken, _cues = parse_and_strip_cues(cleaned)
        if spoken:
            cleaned = spoken
    except Exception:
        pass
    # Lixo típico de modelos pequenos sob pressão (phi4-mini na NAS).
    letters = sum(1 for c in cleaned if c.isalpha())
    if letters < 40:
        return False, "poucas letras (saida lixo)"
    non_space = max(1, len(cleaned.replace(" ", "")))
    if letters / non_space < 0.45:
        return False, "proporcao de lixo/simbolos alta"
    if cleaned.count("(") + cleaned.count("[") > max(8, letters // 8):
        return False, "simbolos de lixo excessivos"
    words = [w for w in cleaned.split() if any(ch.isalpha() for ch in w)]
    if len(words) < max(40, int(min_words * 0.35)):
        return False, f"editor curto demais ({len(words)} palavras)"
    lowered = cleaned.lower()
    if "<think>" in lowered or "</think>" in lowered:
        return False, "think tags"
    if cleaned.count(".") < 2:
        return False, "poucas frases"
    # Meta-comentário do modelo — rejeita.
    banned = (
        "como editor",
        "neste lote",
        "rascunhos para editar",
        "retorne apenas",
        "### matéria",
        "resposta anterior falhou",
        "reescreva a resposta",
    )
    if any(b in lowered for b in banned):
        return False, "meta-comentário do editor"
    # Markdown / timecode de roteiro de TV — rejeita.
    if "[00:" in cleaned or cleaned.count("**") >= 2 or "locutor:" in lowered:
        return False, "formato de roteiro/markdown"
    try:
        from test_cpu_tts_from_generated_text import contains_script_stage_directions

        if contains_script_stage_directions(cleaned):
            return False, "cues de roteiro/produção não reconhecidos"
    except Exception:
        pass
    return True, ""


def editor_repair_prompt(original_prompt: str, previous_text: str, reason: str) -> str:
    """Reparo curto — NÃO reenvia o lixo da resposta anterior (evita colapso do modelo)."""
    return (
        f"{original_prompt}\n\n"
        f"[CORRECAO] A tentativa anterior foi rejeitada ({reason or 'invalida'}). "
        "Escreva de novo APENAS o texto corrido da locucao em portugues, "
        "sem parenteses soltos, sem markdown, sem listar regras. "
        f"Use no minimo {80} palavras com frases completas."
    )


def filter_endpoints_for_editor(llm_endpoints) -> tuple:
    """Editor longo: evita modelos fracos da NAS (phi4-mini) que colapsam no prompt.

    Mantém primários de GPU (gemma/lfm). Se a cadeia ficar vazia, devolve a original.
    """
    eps = tuple(llm_endpoints or ())
    if not eps:
        return eps
    kept = []
    for ep in eps:
        model = str(getattr(ep, "model", None) or (ep.get("model") if isinstance(ep, dict) else "") or "")
        name = str(getattr(ep, "name", None) or (ep.get("name") if isinstance(ep, dict) else "") or "")
        low = f"{model} {name}".lower()
        if ":nas" in low or "phi4-mini" in low or low.strip().endswith("nas"):
            continue
        # Reescreve fallbacks sem NAS/phi4-mini
        if hasattr(ep, "fallback_models"):
            fb = tuple(
                m for m in (ep.fallback_models or ())
                if m and ":nas" not in m.lower() and "phi4-mini" not in m.lower()
            )
            from agenda_media_router import LlmEndpoint

            kept.append(
                LlmEndpoint(name=ep.name, host=ep.host, model=ep.model, fallback_models=fb)
            )
        elif isinstance(ep, dict):
            fb_raw = ep.get("fallback_models") or ()
            if isinstance(fb_raw, str):
                fb_items = [x.strip() for x in fb_raw.split(",") if x.strip()]
            else:
                fb_items = list(fb_raw)
            fb = [m for m in fb_items if ":nas" not in m.lower() and "phi4-mini" not in m.lower()]
            kept.append({**ep, "fallback_models": fb})
        else:
            kept.append(ep)
    return tuple(kept) if kept else eps


def load_editor_prompt_template() -> str | None:
    """Template opcional do painel (prompts.editor_template)."""
    try:
        from daily_agenda_config import load_prompt_templates

        templates = load_prompt_templates()
        tpl = (templates.get("editor_template") or "").strip()
        return tpl or None
    except Exception:
        return None


def edit_batch_with_llm(
    *,
    source_text: str,
    batch_items: list[SegmentResult],
    batch_index: int,
    total_batches: int,
    previous_tail: str,
    target_words: int,
    min_duration_seconds: int,
    tts_mod: Any,
    llm_endpoints,
    max_rounds: int,
    retry_wait_seconds: int,
    mode: str = MODE_COM_PAUTA,
) -> tuple[str, str]:
    """Chama o LLM como Editor. Retorna (texto_editado, endpoint)."""
    custom = load_editor_prompt_template()
    if custom and mode != MODE_SEM_PAUTA:
        materias = "\n\n".join(
            f"[papel={i.role}] {i.text.strip()}" for i in batch_items if i.text.strip()
        )
        allies = ""
        try:
            from daily_agenda_config import _allies_csv

            allies = _allies_csv()
        except Exception:
            allies = "aliados no YouTube"
        prompt = (
            custom.replace("{allies}", allies)
            .replace("{source}", source_text.strip())
            .replace("{previous_tail}", previous_tail or "")
            .replace("{target_words}", str(target_words))
            .replace("{min_duration_seconds}", str(min_duration_seconds))
            .replace("{batch_index}", str(batch_index))
            .replace("{total_batches}", str(total_batches))
            .replace("{text}", materias)
        )
        if "{text}" not in custom and materias not in prompt:
            prompt = prompt.rstrip() + f"\n\nRascunhos:\n{materias}"
    else:
        prompt = build_editor_batch_prompt(
            source_text=source_text,
            batch_items=batch_items,
            batch_index=batch_index,
            total_batches=total_batches,
            previous_tail=previous_tail,
            target_words=target_words,
            min_duration_seconds=min_duration_seconds,
            mode=mode,
        )

    # COM_PAUTA: cap moderado (1B). SEM_PAUTA: pede mais volume (meta 1h).
    if mode == MODE_SEM_PAUTA:
        effective_target = max(200, min(int(target_words), 420))
        min_words = max(120, int(effective_target * 0.55))
        num_predict = max(600, min(1400, int(effective_target * 2.4)))
    else:
        effective_target = max(120, min(int(target_words), 280))
        min_words = max(50, int(effective_target * 0.40))
        num_predict = max(400, min(900, int(effective_target * 2.0)))
    num_ctx = max(4096, min(8192, num_predict + 2500))
    endpoints = filter_endpoints_for_editor(llm_endpoints)
    kwargs = dict(
        prompt=prompt.replace(
            f"cerca de {target_words} palavras",
            f"cerca de {effective_target} palavras",
        ).replace(
            f"alvo aproximado deste lote: {target_words} palavras",
            f"alvo aproximado deste lote: {effective_target} palavras",
        ),
        endpoints=endpoints,
        validator=lambda candidate: is_valid_editor_text(candidate, min_words=min_words),
        num_predict=num_predict,
        num_ctx=num_ctx,
        max_rounds=max_rounds,
        retry_wait_seconds=retry_wait_seconds,
    )
    # max_attempts=1: evita o loop de reparo que reenvia lixo ao modelo (phi4-mini).
    # Se falhar, a cadeia tenta o próximo endpoint/modelo.
    try:
        text, endpoint = tts_mod.generate_with_llm_chain(
            **kwargs,
            endpoint_offset=max(0, batch_index - 1),
            max_attempts=1,
            repair_prompt_builder=editor_repair_prompt,
        )
    except TypeError:
        try:
            text, endpoint = tts_mod.generate_with_llm_chain(
                **kwargs,
                endpoint_offset=max(0, batch_index - 1),
            )
        except TypeError:
            text, endpoint = tts_mod.generate_with_llm_chain(**kwargs)
    if hasattr(tts_mod, "clean_generated_text"):
        text = tts_mod.clean_generated_text(text)
    if hasattr(tts_mod, "normalize_for_speech"):
        text = tts_mod.normalize_for_speech(text)
    # Revalida; se ainda for lixo, falha para o caller usar heurística.
    ok, reason = is_valid_editor_text(text, min_words=min_words)
    if not ok:
        raise RuntimeError(f"editor invalido apos LLM ({reason})")
    return text.strip(), endpoint


def run_editor_desk(
    drafts: list[SegmentResult],
    *,
    source_text: str,
    min_duration_seconds: int,
    words_per_minute: int = DEFAULT_WPM,
    segment_target_seconds: int = DEFAULT_SEGMENT_SECONDS,
    batch_size: int = DEFAULT_EDITOR_BATCH_SIZE,
    tts_mod: Any | None = None,
    llm_endpoints=(),
    max_rounds: int = 2,
    retry_wait_seconds: int = 6,
    no_llm: bool = False,
    mode: str | None = None,
) -> EditorDeskResult:
    """Mesa de Editor completa: reordena → edita em lotes → dedupe final.

    COM_PAUTA: corta/une sobreposições.
    SEM_PAUTA: batch=1, preserva volume (meta 1h); se LLM enxugar demais, mantém rascunho.
    """
    usable = [d for d in drafts if (d.text or "").strip()]
    if not usable:
        return EditorDeskResult(final_text="", used_heuristic=True)

    resolved_mode = mode or classify_source_mode(source_text)
    target_total_words = words_for_duration(
        min_duration_seconds, words_per_minute=words_per_minute
    )
    ordered = reorder_drafts_for_edition(usable)
    # Pré-corte de enchimento antes do LLM (leve).
    for d in ordered:
        d.text = cut_filler_phrases(d.text)

    # SEM_PAUTA: um bloco por vez — não fundir rascunhos.
    if resolved_mode == MODE_SEM_PAUTA:
        bs = 1
    else:
        bs = max(1, int(batch_size or DEFAULT_EDITOR_BATCH_SIZE))
    batches: list[list[SegmentResult]] = [
        ordered[i : i + bs] for i in range(0, len(ordered), bs)
    ]
    edited_blocks: list[SegmentResult] = []
    notes: list[EditorBatchNote] = []
    previous_tail = ""
    last_endpoint = ""
    any_heuristic = False

    if resolved_mode == MODE_SEM_PAUTA:
        # Alvo por lote ≈ palavras do segmento (~420), não cap 280.
        words_per_batch = max(
            200,
            int(round(target_total_words / max(1, len(batches)))),
        )
        words_per_batch = min(words_per_batch, 480)
    else:
        # Cap por lote: prompts enormes + 1B colapsam.
        words_per_batch = max(
            120,
            min(280, int(round(target_total_words / max(1, len(batches))))),
        )

    for b_idx, batch in enumerate(batches, start=1):
        words_in = sum(len(x.text.split()) for x in batch)
        draft_joined = " ".join(x.text.strip() for x in batch if x.text.strip())
        edited_text = ""
        endpoint = ""
        used_h = False
        kept_draft = False

        if not no_llm and tts_mod is not None and llm_endpoints is not None:
            try:
                edited_text, endpoint = edit_batch_with_llm(
                    source_text=source_text,
                    batch_items=batch,
                    batch_index=b_idx,
                    total_batches=len(batches),
                    previous_tail=previous_tail,
                    target_words=words_per_batch,
                    min_duration_seconds=min_duration_seconds,
                    tts_mod=tts_mod,
                    llm_endpoints=llm_endpoints,
                    max_rounds=max_rounds,
                    retry_wait_seconds=retry_wait_seconds,
                    mode=resolved_mode,
                )
                last_endpoint = endpoint or last_endpoint
            except Exception:
                logger.warning(
                    "Editor LLM falhou no lote %s/%s; usando heurística do lote.",
                    b_idx,
                    len(batches),
                    exc_info=True,
                )
                edited_text = ""

        if not edited_text:
            used_h = True
            any_heuristic = True
            joined = cut_filler_phrases(draft_joined)
            if resolved_mode == MODE_SEM_PAUTA:
                # SEM_PAUTA: não dedupe agressivo — preserva volume do rascunho.
                edited_text = joined
            else:
                parts, _cuts = dedupe_sentences([joined])
                edited_text = parts[0] if parts else joined

        edited_text = cut_filler_phrases(edited_text)

        # SEM_PAUTA: se o LLM matou o volume, descarta o corte e mantém rascunho.
        if (
            resolved_mode == MODE_SEM_PAUTA
            and draft_joined
            and edited_text
            and words_in > 0
        ):
            out_w = len(edited_text.split())
            if out_w < max(80, int(words_in * SEM_PAUTA_EDITOR_KEEP_RATIO)):
                logger.info(
                    "Editor SEM_PAUTA lote %s: LLM enxugou %s→%s palavras; "
                    "preservando rascunho (piso %.0f%%).",
                    b_idx,
                    words_in,
                    out_w,
                    SEM_PAUTA_EDITOR_KEEP_RATIO * 100,
                )
                edited_text = cut_filler_phrases(draft_joined)
                kept_draft = True

        role = batch[0].role if len(batch) == 1 else "edicao"
        if b_idx == 1:
            role = "abertura" if any(x.role == "abertura" for x in batch) else role
        if b_idx == len(batches):
            role = "encerramento" if any(x.role == "encerramento" for x in batch) else role

        block = SegmentResult(
            index=b_idx,
            role=role,
            title=f"Edição lote {b_idx}",
            text=edited_text.strip(),
            wav_path=None,
            duration_seconds=0.0,
            llm_endpoint=endpoint,
            draft_text="\n\n".join(x.text for x in batch),
            edited=True,
        )
        edited_blocks.append(block)
        note_extra = ""
        if kept_draft:
            note_extra = " [rascunho preservado]"
        notes.append(
            EditorBatchNote(
                batch_index=b_idx,
                kept_roles=[x.role for x in batch],
                cut_summary=(
                    f"lote {b_idx}: {words_in}→{len(edited_text.split())} palavras"
                    + (" (heurística)" if used_h else f" (llm:{endpoint})")
                    + note_extra
                    + f" mode={resolved_mode}"
                ),
                llm_endpoint=endpoint,
                used_heuristic=used_h or kept_draft,
                word_count_in=words_in,
                word_count_out=len(edited_text.split()),
            )
        )
        # Cauda para continuidade do próximo lote.
        tail_words = edited_text.split()
        previous_tail = " ".join(tail_words[-80:]) if tail_words else ""

    # Dedupe cruzado: em SEM_PAUTA só remove quase-idênticos (threshold alto).
    if resolved_mode == MODE_SEM_PAUTA:
        cross_texts, cross_cuts = dedupe_sentences(
            [b.text for b in edited_blocks],
            similarity_threshold=0.94,
        )
    else:
        cross_texts, cross_cuts = dedupe_sentences([b.text for b in edited_blocks])
    final_blocks: list[SegmentResult] = []
    for i, (block, text) in enumerate(zip(edited_blocks, cross_texts), start=1):
        if not text.strip():
            continue
        # SEM_PAUTA: se o dedupe cruzado esvaziou demais, volta ao texto do bloco.
        if (
            resolved_mode == MODE_SEM_PAUTA
            and block.text
            and len(text.split()) < max(40, int(len(block.text.split()) * 0.5))
        ):
            text = block.text
        final_blocks.append(
            SegmentResult(
                index=i,
                role=block.role,
                title=block.title,
                text=text.strip(),
                wav_path=None,
                duration_seconds=0.0,
                llm_endpoint=block.llm_endpoint,
                draft_text=block.draft_text,
                edited=True,
            )
        )

    if cross_cuts:
        notes.append(
            EditorBatchNote(
                batch_index=0,
                cut_summary=f"dedupe final entre lotes: {cross_cuts} frases cortadas",
                used_heuristic=True,
                word_count_in=sum(n.word_count_out for n in notes if n.batch_index),
                word_count_out=sum(len(b.text.split()) for b in final_blocks),
            )
        )

    # Se o Editor LLM falhou em tudo e o volume ficou ridículo, heurística global.
    # SEM_PAUTA: NÃO roda heurística global agressiva se já há texto longo (preserva 1h).
    total_out = sum(len(b.text.split()) for b in final_blocks)
    if not final_blocks or (
        resolved_mode != MODE_SEM_PAUTA
        and any_heuristic
        and all(n.used_heuristic for n in notes if n.batch_index)
        and total_out < max(60, int(target_total_words * 0.2))
    ):
        logger.info("Editor: aplicando passagem heurística global de fechamento.")
        return heuristic_editor_pass(
            drafts,
            source_text=source_text,
            target_words=target_total_words,
        )

    final_text = "\n\n".join(b.text for b in final_blocks if b.text).strip()
    logger.info(
        "Mesa de Editor [%s]: %s rascunhos → %s blocos editados (%s palavras, cortes cruzados=%s)",
        resolved_mode,
        len(usable),
        len(final_blocks),
        len(final_text.split()),
        cross_cuts,
    )
    return EditorDeskResult(
        blocks=final_blocks,
        final_text=final_text,
        notes=notes,
        llm_endpoint=last_endpoint,
        used_heuristic=any_heuristic,
    )


def split_text_for_tts(
    text: str,
    *,
    target_words: int,
) -> list[str]:
    """Parte o texto editado em blocos de ~target_words para o TTS."""
    sentences = _split_sentences(text)
    if not sentences:
        return [text] if text.strip() else []
    target = max(80, int(target_words or 200))
    chunks: list[str] = []
    buf: list[str] = []
    count = 0
    for sent in sentences:
        w = len(sent.split())
        if buf and count + w > target:
            chunks.append(" ".join(buf).strip())
            buf = [sent]
            count = w
        else:
            buf.append(sent)
            count += w
    if buf:
        chunks.append(" ".join(buf).strip())
    return chunks


def generate_modular_locution(
    source_text: str,
    *,
    day_dir: Path,
    wav_output: Path,
    tts_mod: Any,
    llm_endpoints,
    tts_settings,
    synthesize_fn: Callable[..., str | None],
    min_duration_seconds: int,
    segment_target_seconds: int = DEFAULT_SEGMENT_SECONDS,
    segment_gap_seconds: float = DEFAULT_GAP_SECONDS,
    words_per_minute: int = DEFAULT_WPM,
    max_rounds: int = 2,
    retry_wait_seconds: int = 6,
    no_expand: bool = False,
    no_normalize: bool = False,
    skip_audio: bool = False,
    max_segments: int = DEFAULT_MAX_SEGMENTS,
    editor_enabled: bool = True,
    editor_batch_size: int = DEFAULT_EDITOR_BATCH_SIZE,
    llm_parallel: int = 3,
    sem_pauta_max_duration_seconds: int = DEFAULT_SEM_PAUTA_MAX_DURATION,
    sem_pauta_max_segments: int = DEFAULT_SEM_PAUTA_MAX_SEGMENTS,
) -> ModularLocutionResult:
    """Pipeline: planeja → rascunhos → mesa de Editor → TTS nos blocos editados → concatena."""
    source_mode = classify_source_mode(source_text)
    effective_min = effective_duration_for_mode(
        min_duration_seconds,
        source_mode,
        sem_pauta_max_duration_seconds=sem_pauta_max_duration_seconds,
    )
    if effective_min != min_duration_seconds:
        logger.info(
            "SEM_PAUTA: teto de duração %ss → %ss (evita eco forçado para 1h)",
            min_duration_seconds,
            effective_min,
        )
    min_duration_seconds = effective_min
    plan = plan_segments(
        source_text,
        target_seconds=min_duration_seconds,
        segment_target_seconds=segment_target_seconds,
        words_per_minute=words_per_minute,
        max_segments=max_segments,
        mode=source_mode,
        sem_pauta_max_duration_seconds=sem_pauta_max_duration_seconds,
        sem_pauta_max_segments=sem_pauta_max_segments,
    )
    segments_dir = day_dir / "segments"
    drafts_dir = segments_dir / "drafts"
    edited_dir = segments_dir / "edited"
    segments_dir.mkdir(parents=True, exist_ok=True)
    drafts_dir.mkdir(parents=True, exist_ok=True)
    edited_dir.mkdir(parents=True, exist_ok=True)

    drafts: list[SegmentResult] = []
    last_llm = ""
    last_tts = ""
    workers = max(1, min(int(llm_parallel or 1), len(plan) or 1))

    logger.info(
        "Pipeline modular: mode=%s, %s segmentos, alvo total=%ss, alvo/seg~%ss, editor=%s, llm_parallel=%s",
        source_mode,
        len(plan),
        min_duration_seconds,
        segment_target_seconds,
        "on" if editor_enabled else "off",
        workers,
    )
    (segments_dir / "source_mode.txt").write_text(source_mode + "\n", encoding="utf-8")

    # --- Fase 1: rascunhos em paralelo (sem TTS) → coordinator espalha nas GPUs ---
    def _draft_one(spec: SegmentSpec) -> SegmentResult:
        draft_path = drafts_dir / f"draft_{spec.index:02d}_{spec.role}.txt"
        logger.info(
            "Rascunho %s/%s [%s] alvo=%ss (~%s palavras) offset=%s",
            spec.index,
            len(plan),
            spec.role,
            spec.target_seconds,
            spec.target_words,
            spec.index - 1,
        )
        try:
            text, endpoint = generate_segment_text(
                source_text=source_text,
                segment=spec,
                total_segments=len(plan),
                min_duration_seconds=min_duration_seconds,
                tts_mod=tts_mod,
                llm_endpoints=llm_endpoints,
                max_rounds=max_rounds,
                retry_wait_seconds=retry_wait_seconds,
                no_expand=no_expand,
                no_normalize=no_normalize,
                endpoint_offset=spec.index - 1,
            )
            draft_path.write_text(text + "\n", encoding="utf-8")
            return SegmentResult(
                index=spec.index,
                role=spec.role,
                title=spec.title,
                text=text,
                wav_path=None,
                duration_seconds=0.0,
                llm_endpoint=endpoint,
                draft_text=text,
            )
        except Exception as exc:
            logger.exception("Falha gerando rascunho do segmento %s", spec.index)
            return SegmentResult(
                index=spec.index,
                role=spec.role,
                title=spec.title,
                text="",
                wav_path=None,
                duration_seconds=0.0,
                error=str(exc),
            )

    if workers <= 1 or len(plan) <= 1:
        drafts = [_draft_one(spec) for spec in plan]
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        by_index: dict[int, SegmentResult] = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_draft_one, spec): spec.index for spec in plan}
            for fut in as_completed(futures):
                result = fut.result()
                by_index[result.index] = result
                if result.llm_endpoint:
                    last_llm = result.llm_endpoint
        drafts = [by_index[s.index] for s in plan if s.index in by_index]

    for d in drafts:
        if d.llm_endpoint:
            last_llm = d.llm_endpoint

    # --- Fase 2: mesa de Editor ---
    editor_notes: list[EditorBatchNote] = []
    if editor_enabled:
        logger.info(
            "Mesa de Editor [%s]: revisando %s rascunhos…",
            source_mode,
            len(drafts),
        )
        desk = run_editor_desk(
            drafts,
            source_text=source_text,
            min_duration_seconds=min_duration_seconds,
            words_per_minute=words_per_minute,
            segment_target_seconds=segment_target_seconds,
            batch_size=editor_batch_size,
            tts_mod=tts_mod,
            llm_endpoints=llm_endpoints,
            max_rounds=max_rounds,
            retry_wait_seconds=retry_wait_seconds,
            no_llm=no_expand,  # --no-llm-expand também desliga LLM do editor
            mode=source_mode,
        )
        final_blocks = desk.blocks
        final_text = desk.final_text
        editor_notes = desk.notes
        if desk.llm_endpoint:
            last_llm = desk.llm_endpoint
        (segments_dir / "editor_notes.json").write_text(
            json.dumps(
                [
                    {
                        "batch_index": n.batch_index,
                        "kept_roles": n.kept_roles,
                        "cut_summary": n.cut_summary,
                        "llm_endpoint": n.llm_endpoint,
                        "used_heuristic": n.used_heuristic,
                        "word_count_in": n.word_count_in,
                        "word_count_out": n.word_count_out,
                    }
                    for n in editor_notes
                ],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        # Sem editor: usa rascunhos na ordem planejada.
        final_blocks = [d for d in drafts if d.text.strip()]
        final_text = "\n\n".join(d.text.strip() for d in final_blocks)

    (segments_dir / "locution_edited.txt").write_text(final_text + "\n", encoding="utf-8")
    for block in final_blocks:
        (edited_dir / f"edit_{block.index:02d}_{block.role}.txt").write_text(
            block.text + "\n", encoding="utf-8"
        )

    # --- Fase 3: TTS só nos blocos editados (reparte se ainda longos) ---
    # Cues de produção (pausa/fundo/vinheta) saem da fala e viram áudio depois.
    try:
        from daily_agenda_cues import load_cue_settings_from_audio_cfg, parse_and_strip_cues

        _audio_for_cues = load_modular_audio_settings(
            {
                "segment_gap_seconds": segment_gap_seconds,
                "cues_enabled": True,
            }
        )
        # Preferência: config do painel se disponível.
        try:
            from daily_agenda_config import load_audio_settings

            _audio_for_cues = load_audio_settings()
        except Exception:
            pass
        cue_settings = load_cue_settings_from_audio_cfg(_audio_for_cues)
    except Exception:
        cue_settings = None

    results: list[SegmentResult] = []
    wav_parts: list[Path] = []
    # (role, text_for_cues_or_spoken, wav)
    production_units: list[tuple[str, str, Path]] = []
    tts_word_target = words_for_duration(
        segment_target_seconds, words_per_minute=words_per_minute
    )

    tts_units: list[tuple[str, str, str, str]] = []  # role, title, spoken, original
    for block in final_blocks:
        if not block.text.strip():
            continue
        original = block.text
        spoken = original
        try:
            from daily_agenda_cues import parse_and_strip_cues

            spoken_only, _ = parse_and_strip_cues(original)
            if spoken_only.strip():
                spoken = spoken_only
        except Exception:
            pass
        pieces = split_text_for_tts(spoken, target_words=tts_word_target)
        if not pieces:
            pieces = [spoken]
        for pi, piece in enumerate(pieces):
            suffix = f"/{pi + 1}" if len(pieces) > 1 else ""
            # Cues do bloco ficam no 1º pedaço (para não duplicar pausas/beds).
            orig_piece = original if pi == 0 else piece
            tts_units.append((block.role, f"{block.title}{suffix}", piece, orig_piece))

    for unit_idx, (role, title, text, original_text) in enumerate(tts_units, start=1):
        wav_path = segments_dir / f"seg_{unit_idx:02d}_{role}.wav"
        text_path = segments_dir / f"seg_{unit_idx:02d}_{role}.txt"
        text_path.write_text(text + "\n", encoding="utf-8")
        duration = 0.0
        backend = ""
        seg_wav: Path | None = None
        err = ""

        if not skip_audio:
            try:
                backend = (
                    synthesize_fn(
                        text,
                        tts_mod=tts_mod,
                        wav_output=wav_path,
                        tts_settings=tts_settings,
                    )
                    or ""
                )
                if wav_path.exists():
                    seg_wav = wav_path
                    duration = wav_duration_seconds(wav_path)
                    wav_parts.append(wav_path)
                    production_units.append((role, original_text, wav_path))
                    last_tts = backend or last_tts
                    logger.info(
                        "TTS bloco editado %s/%s [%s]: %.1fs backend=%s",
                        unit_idx,
                        len(tts_units),
                        role,
                        duration,
                        backend,
                    )
            except Exception as exc:
                logger.warning(
                    "TTS falhou no bloco editado %s: %s",
                    unit_idx,
                    exc,
                    exc_info=True,
                )
                err = f"tts: {exc}"

        results.append(
            SegmentResult(
                index=unit_idx,
                role=role,
                title=title,
                text=text,
                wav_path=seg_wav,
                duration_seconds=duration,
                tts_backend=backend,
                error=err,
                draft_text="",
                edited=editor_enabled,
            )
        )

    total_duration = 0.0
    final_wav: Path | None = None
    if not skip_audio and wav_parts:
        cues_applied = False
        if cue_settings is not None and getattr(cue_settings, "enabled", False) and production_units:
            try:
                from daily_agenda_cues import apply_cues_to_production

                prod = apply_cues_to_production(
                    speech_units=production_units,
                    day_dir=day_dir,
                    settings=cue_settings,
                    output_wav=wav_output,
                )
                if prod.get("enabled") and wav_output.exists():
                    total_duration = float(prod.get("duration_seconds") or 0.0)
                    if total_duration <= 0:
                        total_duration = wav_duration_seconds(wav_output)
                    final_wav = wav_output
                    cues_applied = True
                    logger.info(
                        "Mix com cues de produção: %s itens → %.1fs em %s",
                        prod.get("timeline_items"),
                        total_duration,
                        wav_output,
                    )
            except Exception:
                logger.exception("Falha no mix de cues; caindo para concat simples.")

        if not cues_applied:
            try:
                total_duration = concat_wav_files(
                    wav_parts,
                    wav_output,
                    gap_seconds=segment_gap_seconds,
                )
                final_wav = wav_output if wav_output.exists() else None
                logger.info(
                    "WAV concatenado: %s blocos editados → %.1fs em %s",
                    len(wav_parts),
                    total_duration,
                    wav_output,
                )
            except Exception:
                logger.exception("Falha ao concatenar segmentos WAV")
                if wav_parts[0].exists():
                    import shutil

                    shutil.copy2(wav_parts[0], wav_output)
                    final_wav = wav_output
                    total_duration = wav_duration_seconds(wav_output)

    manifest = {
        "source_mode": source_mode,
        "target_seconds": min_duration_seconds,
        "segment_target_seconds": segment_target_seconds,
        "gap_seconds": segment_gap_seconds,
        "words_per_minute": words_per_minute,
        "editor_enabled": editor_enabled,
        "editor_batch_size": editor_batch_size,
        "drafts_count": len(drafts),
        "edited_blocks": len(final_blocks),
        "tts_units": len(results),
        "total_duration_seconds": round(total_duration, 2),
        "final_words": len(final_text.split()),
        "editor_notes": [
            {
                "batch_index": n.batch_index,
                "cut_summary": n.cut_summary,
                "used_heuristic": n.used_heuristic,
                "word_count_in": n.word_count_in,
                "word_count_out": n.word_count_out,
            }
            for n in editor_notes
        ],
        "segments": [
            {
                "index": r.index,
                "role": r.role,
                "title": r.title,
                "words": len(r.text.split()) if r.text else 0,
                "duration_seconds": round(r.duration_seconds, 2),
                "llm_endpoint": r.llm_endpoint,
                "tts_backend": r.tts_backend,
                "error": r.error,
                "edited": r.edited,
                "wav": str(r.wav_path.name) if r.wav_path else "",
            }
            for r in results
        ],
    }
    (segments_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return ModularLocutionResult(
        final_text=final_text,
        wav_path=final_wav,
        duration_seconds=total_duration,
        segments=results,
        llm_endpoint=last_llm,
        tts_backend=last_tts,
        plan=plan,
        editor_notes=editor_notes,
        drafts=drafts,
    )


def load_modular_audio_settings(audio_cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normaliza chaves de config modular a partir de audio{} do painel."""
    cfg = dict(audio_cfg or {})
    def _int(key: str, default: int) -> int:
        try:
            return int(cfg.get(key, default))
        except (TypeError, ValueError):
            return default

    def _float(key: str, default: float) -> float:
        try:
            return float(cfg.get(key, default))
        except (TypeError, ValueError):
            return default

    modular_raw = cfg.get("modular")
    modular: bool | None
    if modular_raw is None:
        modular = None
    else:
        modular = bool(modular_raw)

    editor_raw = cfg.get("editor_enabled")
    if editor_raw is None:
        editor_enabled = True
    else:
        editor_enabled = bool(editor_raw)

    return {
        "min_duration_seconds": max(0, _int("min_duration_seconds", 3600)),
        "max_length_retries": max(0, _int("max_length_retries", 1)),
        "segment_target_seconds": max(
            DEFAULT_MIN_SEGMENT_SECONDS,
            _int("segment_target_seconds", DEFAULT_SEGMENT_SECONDS),
        ),
        "segment_gap_seconds": max(0.0, _float("segment_gap_seconds", DEFAULT_GAP_SECONDS)),
        "words_per_minute": max(80, _int("words_per_minute", DEFAULT_WPM)),
        "modular": modular,
        "modular_threshold_seconds": max(
            60,
            _int("modular_threshold_seconds", DEFAULT_MODULAR_THRESHOLD),
        ),
        "max_segments": max(1, min(DEFAULT_MAX_SEGMENTS, _int("max_segments", DEFAULT_MAX_SEGMENTS))),
        "editor_enabled": editor_enabled,
        "editor_batch_size": max(1, min(8, _int("editor_batch_size", DEFAULT_EDITOR_BATCH_SIZE))),
        "llm_parallel": max(1, min(8, _int("llm_parallel", 3))),
        "cues_enabled": bool(cfg.get("cues_enabled", True)),
        "cues": dict(cfg.get("cues") or {}),
    }
