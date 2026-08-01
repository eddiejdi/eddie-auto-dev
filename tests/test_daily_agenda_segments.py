"""Testes do pipeline modular de segmentos da agenda diária."""
from __future__ import annotations

import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import daily_agenda_segments as segs  # noqa: E402


def _write_silent_wav(path: Path, *, seconds: float = 1.0, rate: int = 16000) -> None:
    nframes = int(rate * seconds)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(struct.pack("<" + "h" * nframes, *([0] * nframes)))


def test_words_for_duration() -> None:
    # 180s @ 140 wpm ≈ 420 palavras
    assert segs.words_for_duration(180, words_per_minute=140) == 420
    assert segs.words_for_duration(3600, words_per_minute=140) == 8400


def test_plan_segment_count_one_hour() -> None:
    # 3600 / 180 = 20
    assert segs.plan_segment_count(3600, segment_target_seconds=180) == 20
    assert segs.plan_segment_count(45, segment_target_seconds=180) == 1
    assert segs.plan_segment_count(400, segment_target_seconds=180) == 3


def test_plan_segments_roles_and_targets() -> None:
    source = (
        "Para esta segunda, 1 de janeiro de 2026, Flávio Bolsonaro participa "
        "da Comissão de Direitos Humanos às 10h.\n"
        "Na cobertura de aliados, Kim Pain destacou a pauta conservadora."
    )
    plan = segs.plan_segments(
        source,
        target_seconds=900,  # 15 min → 5 segmentos de 180s
        segment_target_seconds=180,
        words_per_minute=140,
    )
    assert len(plan) == 5
    assert plan[0].role == "abertura"
    assert plan[-1].role == "encerramento"
    assert sum(s.target_seconds for s in plan) == 900
    assert all(s.target_words > 0 for s in plan)
    assert plan[0].mode == segs.MODE_COM_PAUTA


def test_classify_source_mode_sem_pauta() -> None:
    empty = (
        "Para esta quinta-feira, 30 de julho de 2026, não há compromissos formais "
        "confirmados nas fontes oficiais consultadas sobre a agenda de Flávio Bolsonaro no Senado.\n"
        "Na cobertura de aliados no YouTube, destacam-se títulos X e Y."
    )
    assert segs.classify_source_mode(empty) == segs.MODE_SEM_PAUTA
    busy = (
        "Flávio Bolsonaro participa da Comissão de Constituição e Justiça às 10h "
        "e preside reunião da subcomissão às 14h30."
    )
    assert segs.classify_source_mode(busy) == segs.MODE_COM_PAUTA


def test_plan_segments_sem_pauta_grade_capped() -> None:
    empty = (
        "Para esta quinta-feira, 30 de julho de 2026, não há compromissos formais "
        "confirmados nas fontes oficiais consultadas sobre a agenda de Flávio Bolsonaro no Senado."
    )
    plan = segs.plan_segments(
        empty,
        target_seconds=3600,
        segment_target_seconds=180,
        words_per_minute=140,
    )
    # SEM_PAUTA: teto ~12 min / ≤6 blocos — não força 20×180s
    assert len(plan) <= 6
    assert sum(s.target_seconds for s in plan) <= 720
    assert plan[0].role == "abertura"
    assert plan[-1].role == "encerramento"
    assert all(s.mode == segs.MODE_SEM_PAUTA for s in plan)
    roles = {s.role for s in plan}
    assert "panorama_ausencia" in roles or "desenvolvimento_ancora" in roles or "leitura_silencio" in roles


def test_strip_date_echo_mid_blocks() -> None:
    text = (
        "Para esta sexta-feira, trinta e um de julho de dois mil e vinte e seis, "
        "o senador segue sem compromissos formais. A cobertura continua."
    )
    cleaned = segs.strip_date_echo(text, allow_date=False)
    assert "trinta e um" not in cleaned.lower()
    assert "cobertura continua" in cleaned.lower()
    assert segs.strip_date_echo(text, allow_date=True) == text


def test_editor_sem_pauta_preserva_rascunho_se_llm_enxugar() -> None:
    """Se o LLM devolver texto curto, SEM_PAUTA mantém o rascunho longo."""
    long_draft = " ".join(["Flávio Bolsonaro no Senado sem compromissos formais confirmados."] * 40)
    assert len(long_draft.split()) > 200
    drafts = [
        segs.SegmentResult(
            index=1,
            role="panorama_ausencia",
            title="Panorama",
            text=long_draft,
            wav_path=None,
            duration_seconds=0.0,
            draft_text=long_draft,
        )
    ]
    tts_mod = MagicMock()
    # Editor LLM devolve resumo curto (comportamento antigo que matava a 1h)
    tts_mod.generate_with_llm_chain.return_value = (
        "Hoje não há agenda formal. Fim.",
        "mock:gemma",
    )
    tts_mod.clean_generated_text.side_effect = lambda t: t
    tts_mod.normalize_for_speech.side_effect = lambda t: t

    desk = segs.run_editor_desk(
        drafts,
        source_text="não há compromissos formais confirmados nas fontes oficiais.",
        min_duration_seconds=3600,
        batch_size=2,
        tts_mod=tts_mod,
        llm_endpoints=(MagicMock(model="gemma3:1b", name="x", host="http://h", fallback_models=()),),
        mode=segs.MODE_SEM_PAUTA,
    )
    assert desk.blocks
    # Deve preservar volume (rascunho), não o resumo de ~6 palavras
    assert len(desk.blocks[0].text.split()) > 100
    assert any("preservado" in n.cut_summary for n in desk.notes) or any(
        n.used_heuristic for n in desk.notes
    )


def test_concat_wav_files_with_gap(tmp_path: Path) -> None:
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    out = tmp_path / "out.wav"
    _write_silent_wav(a, seconds=1.0, rate=16000)
    _write_silent_wav(b, seconds=1.0, rate=22050)
    duration = segs.concat_wav_files([a, b], out, gap_seconds=0.5)
    assert out.exists()
    # ~1 + 0.5 + 1 = 2.5s (resample do b para rate dominante)
    assert 2.3 <= duration <= 2.8


def test_heuristic_segment_reaches_word_target() -> None:
    source = "Flávio Bolsonaro tem agenda no Senado Federal nesta quarta-feira."
    spec = segs.SegmentSpec(
        index=1,
        role="abertura",
        title="Abertura",
        focus=source,
        target_seconds=60,
        target_words=140,
    )
    text = segs.heuristic_segment_text(source, spec)
    assert len(text.split()) >= 100


def test_is_valid_editor_rejeita_lixo_phi4() -> None:
    ok, reason = segs.is_valid_editor_text("( ( ( ( ( ( ( [ [", min_words=100)
    assert ok is False
    assert "lixo" in reason or "letras" in reason
    ok2, _ = segs.is_valid_editor_text(
        "Bom dia. Hoje o senador Flávio Bolsonaro segue a agenda no Senado Federal. "
        "Não há compromissos formais confirmados nas fontes oficiais. "
        "Aliados no YouTube destacam a pauta conservadora e a defesa da família. "
        "A imprensa registra o debate político do dia com tom de acompanhamento. "
        "Encerramos este trecho com clareza e respeito aos fatos já conhecidos.",
        min_words=40,
    )
    assert ok2 is True


def test_is_valid_segment_aceita_cues_conhecidos_e_valida_fala() -> None:
    # Cues conhecidos são extraídos; a fala restante precisa ser válida.
    ok, reason = segs.is_valid_segment_text(
        "***Som de Fundo de Locução*** Bom dia. "
        "Hoje o senador Flávio Bolsonaro segue a agenda no Senado Federal. "
        "Pausa de 30 Seg. Não há compromissos formais confirmados nas fontes oficiais. "
        "A cobertura destaca o acompanhamento institucional e a constância do mandato. "
        "Encerramos este trecho com clareza e respeito aos fatos já conhecidos.",
        min_words=40,
    )
    assert ok is True, reason


def test_filter_endpoints_for_editor_remove_nas_phi4() -> None:
    from agenda_media_router import LlmEndpoint

    chain = (
        LlmEndpoint("a", "http://x:11437", "gemma3:1b", ("lfm2.5-fast:gpu1", "phi4-mini:nas")),
        LlmEndpoint("b", "http://x:11437", "phi4-mini:nas", ("gemma3:1b",)),
        LlmEndpoint("c", "http://x:11437", "gemma3-fast:gpu1", ("phi4-mini:latest",)),
    )
    filtered = segs.filter_endpoints_for_editor(chain)
    models = [e.model for e in filtered]
    assert "phi4-mini:nas" not in models
    assert "gemma3:1b" in models or "gemma3-fast:gpu1" in models
    for e in filtered:
        assert all("phi4-mini" not in fb and ":nas" not in fb for fb in e.fallback_models)


def test_should_use_modular() -> None:
    assert segs.should_use_modular(3600) is True
    assert segs.should_use_modular(45) is False
    assert segs.should_use_modular(45, modular=True) is True
    assert segs.should_use_modular(3600, modular=False) is False


def test_generate_modular_locution_skip_audio(tmp_path: Path) -> None:
    tts_mod = MagicMock()
    tts_mod.generate_with_llm_chain.side_effect = RuntimeError("sem LLM")
    tts_mod.normalize_for_speech.side_effect = lambda t: t
    tts_mod.heuristic_rewrite_for_broadcast.side_effect = lambda t: t
    tts_mod.clean_generated_text.side_effect = lambda t: t

    def _synth(*args, **kwargs):
        raise AssertionError("não deveria sintetizar com skip_audio")

    result = segs.generate_modular_locution(
        "Texto fonte da agenda do senador Flávio Bolsonaro no Senado.",
        day_dir=tmp_path,
        wav_output=tmp_path / "locution.wav",
        tts_mod=tts_mod,
        llm_endpoints=(),
        tts_settings=MagicMock(),
        synthesize_fn=_synth,
        min_duration_seconds=360,  # 2 segmentos de 180s
        segment_target_seconds=180,
        no_expand=True,
        skip_audio=True,
    )
    assert len(result.plan) == 2
    assert result.final_text
    assert result.wav_path is None
    assert (tmp_path / "segments" / "manifest.json").exists()
    assert len(result.segments) == 2
    assert all(s.text for s in result.segments)


def test_generate_modular_locution_with_tts(tmp_path: Path) -> None:
    tts_mod = MagicMock()
    tts_mod.generate_with_llm_chain.side_effect = RuntimeError("sem LLM")
    tts_mod.normalize_for_speech.side_effect = lambda t: t
    tts_mod.heuristic_rewrite_for_broadcast.side_effect = lambda t: t
    tts_mod.clean_generated_text.side_effect = lambda t: t

    def _synth(text, *, tts_mod, wav_output, tts_settings):
        # 2s por segmento
        _write_silent_wav(wav_output, seconds=2.0, rate=22050)
        return "piper-cpu"

    result = segs.generate_modular_locution(
        "Agenda de Flávio Bolsonaro com comissão às 10h e cobertura de aliados.",
        day_dir=tmp_path,
        wav_output=tmp_path / "locution.wav",
        tts_mod=tts_mod,
        llm_endpoints=(),
        tts_settings=MagicMock(),
        synthesize_fn=_synth,
        min_duration_seconds=360,
        segment_target_seconds=180,
        segment_gap_seconds=0.2,
        no_expand=True,
        skip_audio=False,
    )
    assert result.wav_path is not None
    assert result.wav_path.exists()
    # 2 segmentos * 2s + 0.2 gap ≈ 4.2s
    assert result.duration_seconds >= 4.0
    assert result.tts_backend == "piper-cpu"
    assert len(list((tmp_path / "segments").glob("seg_*.wav"))) == 2


def test_reorder_and_dedupe_editor_heuristic() -> None:
    drafts = [
        segs.SegmentResult(
            index=2,
            role="imprensa",
            title="Imprensa",
            text=(
                "A imprensa noticiou a agenda do senador. "
                "Flávio Bolsonaro tem compromisso no Senado Federal nesta quarta. "
                "Vale destacar o significado prático desses pontos para o eleitor e para o Senado."
            ),
            wav_path=None,
            duration_seconds=0.0,
        ),
        segs.SegmentResult(
            index=1,
            role="abertura",
            title="Abertura",
            text=(
                "Bem-vindos à Agenda Diária. "
                "Flávio Bolsonaro tem compromisso no Senado Federal nesta quarta."
            ),
            wav_path=None,
            duration_seconds=0.0,
        ),
        segs.SegmentResult(
            index=3,
            role="encerramento",
            title="Fim",
            text="Encerramos o boletim com o essencial da pauta do senador.",
            wav_path=None,
            duration_seconds=0.0,
        ),
    ]
    desk = segs.heuristic_editor_pass(
        drafts,
        source_text="Flávio Bolsonaro tem compromisso no Senado Federal nesta quarta.",
        target_words=200,
    )
    assert desk.blocks
    assert desk.blocks[0].role == "abertura"
    assert desk.blocks[-1].role == "encerramento"
    # Frase repetida + filler devem ter sido cortados.
    joined = desk.final_text.lower()
    assert joined.count("compromisso no senado federal nesta quarta") <= 1
    assert "vale destacar o significado prático" not in joined


def test_run_editor_desk_heuristic_without_llm() -> None:
    drafts = [
        segs.SegmentResult(
            index=1,
            role="abertura",
            title="Abertura",
            text="Abertura do boletim sobre Flávio Bolsonaro no Senado. Há comissão às dez horas.",
            wav_path=None,
            duration_seconds=0.0,
        ),
        segs.SegmentResult(
            index=2,
            role="compromisso",
            title="Pauta",
            text=(
                "O senador participa da Comissão de Direitos Humanos. "
                "O senador participa da Comissão de Direitos Humanos. "
                "A pauta inclui projetos de autoria e relatoria."
            ),
            wav_path=None,
            duration_seconds=0.0,
        ),
        segs.SegmentResult(
            index=3,
            role="encerramento",
            title="Fim",
            text="Fechamos com a agenda do senador Flávio Bolsonaro.",
            wav_path=None,
            duration_seconds=0.0,
        ),
    ]
    desk = segs.run_editor_desk(
        drafts,
        source_text="Comissão de Direitos Humanos às 10h com Flávio Bolsonaro.",
        min_duration_seconds=360,
        no_llm=True,
    )
    assert desk.final_text
    assert desk.blocks
    assert "direitos humanos" in desk.final_text.lower() or "senador" in desk.final_text.lower()


def test_generate_modular_runs_editor_before_tts(tmp_path: Path) -> None:
    tts_mod = MagicMock()
    tts_mod.generate_with_llm_chain.side_effect = RuntimeError("sem LLM")
    tts_mod.normalize_for_speech.side_effect = lambda t: t
    tts_mod.heuristic_rewrite_for_broadcast.side_effect = lambda t: t
    tts_mod.clean_generated_text.side_effect = lambda t: t

    synth_texts: list[str] = []

    def _synth(text, *, tts_mod, wav_output, tts_settings):
        synth_texts.append(text)
        _write_silent_wav(wav_output, seconds=1.0, rate=22050)
        return "piper-cpu"

    result = segs.generate_modular_locution(
        "Agenda de Flávio Bolsonaro com comissão às 10h.",
        day_dir=tmp_path,
        wav_output=tmp_path / "locution.wav",
        tts_mod=tts_mod,
        llm_endpoints=(),
        tts_settings=MagicMock(),
        synthesize_fn=_synth,
        min_duration_seconds=360,
        segment_target_seconds=180,
        no_expand=True,
        skip_audio=False,
        editor_enabled=True,
    )
    assert result.editor_notes
    assert (tmp_path / "segments" / "editor_notes.json").exists()
    assert (tmp_path / "segments" / "locution_edited.txt").exists()
    assert (tmp_path / "segments" / "drafts").is_dir()
    assert (tmp_path / "segments" / "edited").is_dir()
    assert synth_texts  # TTS só depois do editor
    assert result.wav_path and result.wav_path.exists()


def test_prepare_locution_uses_modular_when_long(tmp_path, monkeypatch) -> None:
    sys.path.insert(0, str(TOOLS_DIR))
    import importlib.util

    path = TOOLS_DIR / "run_daily_agenda_broadcast.py"
    spec = importlib.util.spec_from_file_location("run_daily_agenda_broadcast_mod", path)
    assert spec and spec.loader
    broadcast = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = broadcast
    spec.loader.exec_module(broadcast)

    called = {"modular": False}

    def _fake_modular(*args, **kwargs):
        called["modular"] = True
        return segs.ModularLocutionResult(
            final_text="texto modular",
            wav_path=None,
            duration_seconds=0.0,
            llm_endpoint="coord:m",
            tts_backend="",
        )

    monkeypatch.setattr(broadcast, "generate_modular_locution", _fake_modular)
    text, endpoint, wav, backend, dur = broadcast.prepare_locution_and_audio(
        "fonte",
        tts_mod=MagicMock(),
        llm_endpoints=(),
        max_rounds=1,
        retry_wait_seconds=0,
        no_expand=True,
        no_rewrite=True,
        no_normalize=True,
        skip_audio=True,
        wav_output=tmp_path / "out.wav",
        tts_settings=MagicMock(),
        min_duration_seconds=3600,
        max_length_retries=0,
        day_dir=tmp_path,
        audio_settings={"modular": True, "segment_target_seconds": 180},
    )
    assert called["modular"] is True
    assert text == "texto modular"
    assert endpoint == "coord:m"
