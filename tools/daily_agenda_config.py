#!/usr/bin/env python3
"""Configuração persistente do painel e publicação da agenda diária."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "artifacts" / "daily_agenda" / "panel_config.json"
DEFAULT_ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "daily_agenda"
DEFAULT_JOB_PATH = DEFAULT_ARTIFACTS_DIR / "panel_job.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "defaults": {
        "mode": "auto",
        "quality": "balanced",
        "include_news": True,
        "send_telegram": True,
        "upload_youtube": True,
        "require_approval": True,
        "deep_search": True,
    },
    "search": {
        "deep_search": True,
        "timeout": 45,
        "retries": 4,
    },
    "approval": {
        "enabled": True,
        "timeout_minutes": 180,
        "max_regenerations": 2,
    },
    # Duração alvo do áudio/vídeo (painel + pipeline).
    # Com min >= modular_threshold, gera N segmentos LLM+TTS e concatena.
    "audio": {
        "min_duration_seconds": 3600,
        "max_length_retries": 1,
        # Dia sem pauta formal: teto curto, sem 2ª leva para encher 1h.
        "sem_pauta_max_duration_seconds": 720,
        "sem_pauta_max_segments": 6,
        "sem_pauta_allow_extras": False,
        "segment_target_seconds": 180,
        "segment_gap_seconds": 1.5,
        "words_per_minute": 140,
        "modular": True,
        "modular_threshold_seconds": 300,
        "max_segments": 40,
        "editor_enabled": True,
        # Lotes menores: modelos 1B/phi4 colapsam com 3 rascunhos + 1200 palavras.
        "editor_batch_size": 2,
        "llm_parallel": 3,
        # Cues de produção: vinheta, som de fundo, pausas → artefatos em cues/ + mix.
        "cues_enabled": True,
        "cues": {
            "enabled": True,
            "vinheta_open": True,
            "vinheta_close": True,
            "bed_under_speech": True,
            "bed_gain": 0.09,
            "voice_gain": 1.0,
            "pause_between_segments_seconds": 2.0,
            "default_pause_seconds": 2.0,
            "vinheta_open_seconds": 2.4,
            "vinheta_close_seconds": 1.8,
            "bed_idle_seconds": 1.5,
        },
    },
    "youtube": {
        "enabled": True,
        "channel_id": os.getenv(
            "AGENDA_YOUTUBE_CHANNEL_ID",
            "UCEyYr2YE1HLDTKT4cnMefmw",
        ),
        "channel_handle": "@AgendaDiáriaImportante",
        "channel_url": "https://www.youtube.com/channel/UCEyYr2YE1HLDTKT4cnMefmw",
        "privacy_status": "public",
        "category_id": "25",
        "default_tags": [
            "agenda diária",
            "Agenda Diária Importante",
            "Flávio Bolsonaro",
            "Senado Federal",
            "política",
        ],
        "cover_image": "artifacts/daily_agenda/youtube/cover.jpg",
        "credentials_file": "artifacts/daily_agenda/youtube/credentials.json",
        "token_file": "artifacts/daily_agenda/youtube/token.pickle",
    },
    "telegram": {
        "enabled": True,
        "chat_id": os.getenv("AGENDA_TELEGRAM_CHAT_ID", ""),
    },
    "editorial": {
        "stance": "pro_bolsonaro_allies",
        "prefer_ally_youtube": True,
        "prefer_direitaja_truths": True,
        "exclude_hostile_headlines": True,
        "include_bolsonaro_family_context": True,
    },
    # Templates LLM da Agenda Diária Importante.
    # Editáveis no painel (:8093) e lidos a cada geração — sem redeploy.
    # Placeholders: {text} = texto-base; {allies} = nomes dos canais aliados.
    "prompts": {
        "expansion_template": (
            "/no_think\n"
            "Expanda o texto-base abaixo em portugues do Brasil, com tom positivo e firme a favor da familia Bolsonaro e dos aliados verdadeiros.\n"
            "Objetivo: detalhar a agenda e valorizar a atuacao do senador e de seus aliados.\n\n"
            "Regras:\n"
            "- nao invente fatos\n"
            "- mantenha foco na agenda e atuacao de Flavio Bolsonaro no Senado Federal\n"
            "- destaque compromissos, propostas e posicionamentos de forma construtiva\n"
            "- a fonte oficial de verdades sobre Flavio Bolsonaro e a familia e o portal Direita Ja (direitaja.com); priorize-a quando estiver no texto-base\n"
            "- quando citar imprensa ou YouTube aliado ({allies}), enfatize o que reforca a pauta conservadora e o trabalho do senador\n"
            "- evite tom de ataque, ironia ou derrota; nao amplifique narrativas hostis\n"
            "- proibido reproduzir ou parafrasear enquadramentos hostis do tipo "
            "\"repete o pai\", \"ataca urnas eletrônicas\" ou equivalentes\n"
            "- mantenha data, horarios e nomes oficiais das comissoes\n"
            "- se houver materia de autoria do senador, explique em linguagem comum o que ela propoe\n"
            "- se houver materia sob relatoria, deixe claro que nao e de autoria dele\n"
            "- se houver imprensa, cite no maximo duas contextualizacoes distintas, sem repetir a mesma noticia\n"
            "- nao reproduza titulos nem listas de veiculos um a um\n"
            "- troque siglas e codigos por explicacoes curtas quando possivel\n"
            "- use texto corrido, sem listas e sem markdown\n"
            "- proibido cues de roteiro/producao "
            "(ex.: \"***Som de Fundo de Locucao***\", \"Pausa de 30 Seg\", TRILHA:, LOCUTOR:); "
            "so o que o locutor fala em voz alta\n"
            "- produza texto denso o bastante para locucao longa (boletim de radio/TV)\n"
            "- o audio da locucao deve ter pelo menos {min_duration_seconds} segundos no total; "
            "em modo modular cada segmento cobre parte desse alvo\n"
            "- nao limite artificialmente a 200 palavras; priorize densidade factual sem inventar\n"
            "- retorne apenas o texto final\n\n"
            "Texto-base:\n{text}"
        ),
        "broadcast_template": (
            "/no_think\n"
            "Reescreva o texto abaixo para locucao de jornal em portugues do Brasil.\n"
            "Objetivo: soar como boletim de radio/TV, claro, natural e positivo em relacao a Flavio Bolsonaro, a familia Bolsonaro e aliados verdadeiros.\n\n"
            "Regras:\n"
            "- nao invente fatos\n"
            "- preserve foco na agenda e atuacao de Flavio Bolsonaro no Senado Federal\n"
            "- use linguagem de apoio e respeito, sem tom derrotista ou acusatorio\n"
            "- proibido reproduzir ou parafrasear enquadramentos hostis do tipo "
            "\"repete o pai\", \"ataca urnas eletrônicas\" ou equivalentes\n"
            "- priorize a fonte oficial Direita Ja (direitaja.com) e, em seguida, aliados no YouTube ({allies}) quando estiverem no texto-base\n"
            "- preserve no maximo duas contextualizacoes da imprensa, sem repetir a mesma noticia\n"
            "- troque siglas e codigos tecnicos por explicacoes curtas em linguagem comum\n"
            "- evite jargao legislativo quando houver forma simples\n"
            "- preserve nomes oficiais de comissoes\n"
            "- use frases curtas e bem encadeadas, sem listas\n"
            "- proibido cues de roteiro/producao "
            "(ex.: \"***Som de Fundo de Locucao***\", \"Pausa de 30 Seg\", TRILHA:, LOCUTOR:); "
            "so o que o locutor fala em voz alta\n"
            "- produza texto denso o bastante para locucao longa (boletim de radio/TV)\n"
            "- o audio da locucao deve ter pelo menos {min_duration_seconds} segundos no total; "
            "se o texto estiver curto, expanda com contexto factual ja presente\n"
            "- nao limite artificialmente a 180 palavras\n"
            "- retorne apenas o texto final\n\n"
            "Texto-base:\n{text}"
        ),
        # Mesa de Editor — fecha a edição como editor-chefe de jornal.
        # Placeholders: {text}=rascunhos do lote, {source}=texto-base factual,
        # {previous_tail}, {target_words}, {min_duration_seconds}, {batch_index}, {total_batches}.
        "editor_template": (
            "/no_think\n"
            "Voce e o EDITOR-CHEFE de um jornal de radiojornalismo (Agenda Diaria Importante).\n"
            "Feche a edicao deste lote: corte repeticoes e enchimento, reorganize as materias "
            "para fluir como boletim, una trechos sobrepostos e polisce a locucao.\n\n"
            "Regras:\n"
            "- nao invente fatos; ancore-se no texto-base\n"
            "- preserve horarios, nomes oficiais de comissoes e dados factuais\n"
            "- tom positivo e firme a favor de Flavio Bolsonaro, familia Bolsonaro e aliados verdadeiros ({allies})\n"
            "- nao amplifique narrativas hostis\n"
            "- proibido reproduzir enquadramentos do tipo \"repete o pai\" / \"ataca urnas eletrônicas\"\n"
            "- texto corrido de locucao, sem markdown, sem listas, sem meta-comentario\n"
            "- proibido cues de roteiro/producao "
            "(ex.: \"***Som de Fundo***\", \"Pausa de 30 Seg\", TRILHA/LOCUTOR/colchetes)\n"
            "- alvo aproximado deste lote: {target_words} palavras "
            "(boletim total ~{min_duration_seconds}s)\n"
            "- lote {batch_index} de {total_batches}\n"
            "- se houver cauda anterior, continue com continuidade natural sem repetir\n"
            "- retorne APENAS o texto final editado deste lote\n\n"
            "Cauda do trecho ja fechado:\n{previous_tail}\n\n"
            "Texto-base factual:\n{source}\n\n"
            "Rascunhos para editar:\n{text}"
        ),
    },
    "ally_youtube": [
        {
            "name": "Kim Pain",
            "search_terms": ["Kim Pain", "Kim Pain TV"],
            "handle": "@KimPain",
            "channel_id": "",
        },
        {
            "name": "Didi Newa",
            "search_terms": ["Didi Newa", "Didi News"],
            "handle": "@DidiNewa",
            "channel_id": "",
        },
        {
            "name": "Auriverde",
            "search_terms": ["Auriverde"],
            "handle": "@Auriverde",
            "channel_id": "",
        },
        {
            "name": "Claudio Dantas",
            "search_terms": ["Claudio Dantas", "Cláudio Dantas"],
            "handle": "@ClaudioDantas",
            "channel_id": "",
        },
        {
            "name": "Ancapsu",
            "search_terms": ["Ancapsu", "Ancap Su"],
            "handle": "@ancapsu",
            "channel_id": "",
        },
        {
            "name": "Flávio Bolsonaro",
            "search_terms": [
                "Flávio Bolsonaro",
                "Senador Flávio Bolsonaro",
                "Flavio Bolsonaro oficial",
            ],
            "handle": "@flaviobolsonaro",
            "channel_id": "",
        },
    ],
}


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        raw = cfg_path.read_text(encoding="utf-8").strip()
    except OSError:
        return json.loads(json.dumps(DEFAULT_CONFIG))
    if not raw:
        # Arquivo vazio (corrida de escrita / truncagem) — usa defaults.
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Config corrompida: tenta backup .bak e, no pior caso, defaults.
        bak = cfg_path.with_suffix(cfg_path.suffix + ".bak")
        if bak.exists():
            try:
                data = json.loads(bak.read_text(encoding="utf-8"))
            except Exception:
                return json.loads(json.dumps(DEFAULT_CONFIG))
        else:
            return json.loads(json.dumps(DEFAULT_CONFIG))
    if not isinstance(data, dict):
        return json.loads(json.dumps(DEFAULT_CONFIG))
    return _deep_merge(DEFAULT_CONFIG, data)


def save_config(config: dict[str, Any], path: Path | None = None) -> Path:
    """Grava config de forma atômica (tmp + replace) para evitar JSON vazio."""
    import os
    import tempfile

    cfg_path = path or DEFAULT_CONFIG_PATH
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    merged = _deep_merge(DEFAULT_CONFIG, config)
    payload = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"

    # Backup da versão anterior (se legível)
    if cfg_path.exists():
        try:
            prev = cfg_path.read_text(encoding="utf-8").strip()
            if prev:
                bak = cfg_path.with_suffix(cfg_path.suffix + ".bak")
                bak.write_text(prev + ("\n" if not prev.endswith("\n") else ""), encoding="utf-8")
        except OSError:
            pass

    fd, tmp_name = tempfile.mkstemp(
        prefix=cfg_path.name + ".",
        suffix=".tmp",
        dir=str(cfg_path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, cfg_path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return cfg_path


def default_prompt_templates() -> dict[str, str]:
    prompts = DEFAULT_CONFIG.get("prompts") or {}
    return {
        "expansion_template": str(prompts.get("expansion_template") or ""),
        "broadcast_template": str(prompts.get("broadcast_template") or ""),
        "editor_template": str(prompts.get("editor_template") or ""),
    }


def load_prompt_templates(path: Path | None = None) -> dict[str, str]:
    """Carrega templates LLM da agenda (painel / panel_config.json)."""
    defaults = default_prompt_templates()
    cfg = load_config(path)
    prompts = cfg.get("prompts") or {}
    return {
        "expansion_template": str(prompts.get("expansion_template") or defaults["expansion_template"]),
        "broadcast_template": str(prompts.get("broadcast_template") or defaults["broadcast_template"]),
        "editor_template": str(prompts.get("editor_template") or defaults["editor_template"]),
    }


def _allies_csv() -> str:
    try:
        from daily_agenda_editorial import ally_display_names, load_editorial_config

        _, allies = load_editorial_config()
        names = ally_display_names(allies)
        return ", ".join(names) if names else "aliados no YouTube"
    except Exception:
        return "Kim Pain, Didi Newa, Auriverde, Claudio Dantas, Ancapsu, canal Flavio Bolsonaro"


def load_audio_settings(path: Path | None = None) -> dict[str, Any]:
    """Retorna settings de áudio/modular da config do painel."""
    defaults = DEFAULT_CONFIG.get("audio") or {}
    cfg = load_config(path)
    audio = {**defaults, **(cfg.get("audio") or {})}
    try:
        from daily_agenda_segments import load_modular_audio_settings

        return load_modular_audio_settings(audio)
    except Exception:
        try:
            min_duration = max(0, int(audio.get("min_duration_seconds", 3600)))
        except (TypeError, ValueError):
            min_duration = 3600
        try:
            max_retries = max(0, int(audio.get("max_length_retries", 1)))
        except (TypeError, ValueError):
            max_retries = 1
        return {
            "min_duration_seconds": min_duration,
            "max_length_retries": max_retries,
            "segment_target_seconds": 180,
            "segment_gap_seconds": 0.6,
            "words_per_minute": 140,
            "modular": True,
            "modular_threshold_seconds": 300,
            "max_segments": 40,
            "editor_enabled": True,
            "editor_batch_size": 3,
        }


def render_prompt_template(
    template: str,
    *,
    text: str,
    allies: str | None = None,
    min_duration_seconds: int | None = None,
) -> str:
    """Renderiza template com {text}, {allies} e {min_duration_seconds}."""
    allies_s = allies if allies is not None else _allies_csv()
    if min_duration_seconds is None:
        min_duration_seconds = load_audio_settings().get("min_duration_seconds", 3600)
    body = template or ""
    # Substituição simples (não usa str.format para não quebrar chaves soltas do usuário).
    rendered = (
        body.replace("{allies}", allies_s)
        .replace("{min_duration_seconds}", str(min_duration_seconds))
        .replace("{text}", text)
    )
    if "{text}" not in body and text and text not in rendered:
        rendered = rendered.rstrip() + f"\n\nTexto-base:\n{text}"
    return rendered


def build_expansion_prompt(text: str, *, path: Path | None = None) -> str:
    tpl = load_prompt_templates(path)["expansion_template"]
    return render_prompt_template(tpl, text=text)


def build_broadcast_prompt(text: str, *, path: Path | None = None) -> str:
    tpl = load_prompt_templates(path)["broadcast_template"]
    return render_prompt_template(tpl, text=text)


def resolve_repo_path(value: str | Path, *, repo_root: Path = REPO_ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def list_editions(artifacts_dir: Path | None = None) -> list[dict[str, Any]]:
    root = artifacts_dir or DEFAULT_ARTIFACTS_DIR
    if not root.exists():
        return []
    editions: list[dict[str, Any]] = []
    for day_dir in sorted(root.iterdir(), reverse=True):
        if not day_dir.is_dir():
            continue
        date_str = day_dir.name
        try:
            from datetime import datetime

            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        meta_path = day_dir / "publish_meta.json"
        meta = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        editions.append(
            {
                "date": date_str,
                "has_source": (day_dir / "source.txt").exists(),
                "has_locution": (day_dir / "locution.txt").exists(),
                "has_wav": (day_dir / "locution.wav").exists(),
                "has_mp4": (day_dir / "locution.mp4").exists(),
                "youtube_video_id": meta.get("youtube_video_id", ""),
                "youtube_url": meta.get("youtube_url", ""),
                "updated_at": meta.get("updated_at", ""),
            }
        )
    return editions