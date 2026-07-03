#!/usr/bin/env python3
"""Teste de locucao a partir de texto ja gerado.

Backends:
- piper-local: usa Piper local em CPU e salva WAV
- speech-dispatcher: usa `spd-say` em CPU
- gemini-tts: usa a API oficial de TTS do Google/Gemini e salva WAV
"""
from __future__ import annotations

import argparse
import base64
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import httpx

from ollama_client import OllamaClient


DEFAULT_SOURCE_TEXT = (
    "Flávio Bolsonaro tem, até o momento, dois compromissos públicos "
    "identificados para esta quarta-feira, 17 de junho de 2026. "
    "Às 9h30, a Comissão de Desenvolvimento Regional e Turismo do Senado "
    "realiza sua 10ª reunião extraordinária para deliberação de indicações "
    "de emendas RP8/2026. Às 11h, a Comissão de Direitos Humanos e "
    "Legislação Participativa realiza sua 39ª reunião extraordinária, "
    "com itens de pauta que incluem propostas com autoria ou relatoria "
    "atribuídas ao senador."
)

GEMINI_TTS_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-3.1-flash-tts-preview:generateContent"
)
PIPER_VENV_PYTHON = Path(".venv-tts-piper/bin/python")
PIPER_DATA_DIR = Path("artifacts/piper_voices")
PIPER_DEFAULT_VOICE = "pt_BR-cadu-medium"
GPU1_FALLBACK_MODELS = ("llama3.2:1b",)

DAY_WORDS_PT_BR = {
    1: "primeiro",
    2: "dois",
    3: "três",
    4: "quatro",
    5: "cinco",
    6: "seis",
    7: "sete",
    8: "oito",
    9: "nove",
    10: "dez",
    11: "onze",
    12: "doze",
    13: "treze",
    14: "quatorze",
    15: "quinze",
    16: "dezesseis",
    17: "dezessete",
    18: "dezoito",
    19: "dezenove",
    20: "vinte",
    21: "vinte e um",
    22: "vinte e dois",
    23: "vinte e três",
    24: "vinte e quatro",
    25: "vinte e cinco",
    26: "vinte e seis",
    27: "vinte e sete",
    28: "vinte e oito",
    29: "vinte e nove",
    30: "trinta",
    31: "trinta e um",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Testa locução a partir de texto pronto."
    )
    parser.add_argument(
        "--source-text",
        default=DEFAULT_SOURCE_TEXT,
        help="Texto-base usado para a locução.",
    )
    parser.add_argument(
        "--source-file",
        type=Path,
        help="Arquivo com o texto-base. Se informado, sobrescreve --source-text.",
    )
    parser.add_argument(
        "--backend",
        choices=("piper-local", "speech-dispatcher", "gemini-tts"),
        default="piper-local",
        help="Backend de síntese de voz.",
    )
    parser.add_argument(
        "--piper-voice",
        default=PIPER_DEFAULT_VOICE,
        help="Nome da voz oficial do Piper.",
    )
    parser.add_argument(
        "--voice",
        default="Annie",
        help="Voice name do speech-dispatcher/espeak-ng.",
    )
    parser.add_argument(
        "--language",
        default="pt-BR",
        help="Idioma do speech-dispatcher.",
    )
    parser.add_argument(
        "--voice-type",
        default="female1",
        help="Voice type do speech-dispatcher.",
    )
    parser.add_argument(
        "--google-voice",
        default="Kore",
        help="Nome da voz prebuilt do Gemini TTS.",
    )
    parser.add_argument(
        "--no-gpu1-expand",
        action="store_true",
        help="Desativa a expansao/contextualizacao via GPU1 antes da locucao.",
    )
    parser.add_argument(
        "--no-gpu1-rewrite",
        action="store_true",
        help="Desativa a reescrita para locucao via modelo leve na GPU1.",
    )
    parser.add_argument(
        "--ollama-host",
        default="http://192.168.15.2:11435",
        help="Host do Ollama leve usado para reescrita.",
    )
    parser.add_argument(
        "--ollama-model",
        default="gemma3:1b",
        help="Modelo principal do Ollama na GPU1 usado para expansao e reescrita.",
    )
    parser.add_argument(
        "--ollama-fallback-models",
        default="llama3.2:1b",
        help="Lista separada por virgula de modelos alternativos na GPU1.",
    )
    parser.add_argument(
        "--gpu1-max-rounds",
        type=int,
        default=3,
        help="Numero maximo de rodadas tentando a GPU1 quando houver fila/503.",
    )
    parser.add_argument(
        "--gpu1-retry-wait-seconds",
        type=int,
        default=8,
        help="Intervalo de espera entre tentativas na GPU1.",
    )
    parser.add_argument(
        "--rate",
        type=int,
        default=-20,
        help="Velocidade da fala para spd-say (-100 a 100).",
    )
    parser.add_argument(
        "--pitch",
        type=int,
        default=10,
        help="Altura da voz para spd-say (-100 a 100).",
    )
    parser.add_argument(
        "--volume",
        type=int,
        default=0,
        help="Volume da fala para spd-say (-100 a 100).",
    )
    parser.add_argument(
        "--output-text",
        type=Path,
        default=Path("artifacts/audio_cpu_test/generated_locution.txt"),
        help="Arquivo onde o texto final sera salvo.",
    )
    parser.add_argument(
        "--wav-output",
        type=Path,
        default=Path("artifacts/audio_cpu_test/generated_locution.wav"),
        help="Arquivo WAV de saída para o backend Gemini TTS.",
    )
    parser.add_argument(
        "--play-wav",
        action="store_true",
        help="Executa `aplay` no WAV gerado por um backend baseado em arquivo.",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Nao executa playback local; apenas imprime e salva os artefatos.",
    )
    parser.add_argument(
        "--no-ssml",
        action="store_true",
        help="Desativa SSML no backend speech-dispatcher.",
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Nao aplica normalizacao de texto para locucao.",
    )
    return parser.parse_args()


def load_source_text(args: argparse.Namespace) -> str:
    if args.source_file is None:
        return args.source_text.strip()
    return args.source_file.read_text(encoding="utf-8").strip()


def normalize_for_speech(text: str) -> str:
    text = re.sub(
        r"(\d{1,2}) de (\w+) de (2026)",
        lambda m: f"{DAY_WORDS_PT_BR.get(int(m.group(1)), m.group(1))} de {m.group(2)} de dois mil e vinte e seis",
        text,
    )
    text = re.sub(r"\b(\d{1,2})h(\d{2})\b", r"\1 horas e \2 minutos", text)
    text = re.sub(r"\b(\d{1,2})h\b", r"\1 horas", text)
    text = text.replace("17 de junho de 2026", "dezessete de junho de dois mil e vinte e seis")
    text = text.replace("RP8/2026", "RP 8 de 2026")
    text = text.replace(
        "RP 8 de 2026",
        "recursos de emendas do orçamento federal para 2026",
    )
    text = text.replace("10ª reunião", "décima reunião")
    text = text.replace("39ª reunião", "trigésima nona reunião")
    text = text.replace(
        "Comissão de Desenvolvimento Regional e Turismo",
        "Comissão de Desenvolvimento Regional e Turismo",
    )
    text = text.replace(
        "Comissão de Direitos Humanos e Legislação Participativa",
        "Comissão de Direitos Humanos e Legislação Participativa",
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text


def heuristic_rewrite_for_broadcast(text: str) -> str:
    text = text.replace("No Senado Federal,", "No Senado,")
    text = text.replace("está marcado para", "ocorre às")
    text = text.replace("está previsto para", "ocorre às")
    text = text.replace(
        "A reunião extraordinária deve tratar da deliberação de indicações de emendas do orçamento federal para 2026.",
        "A reunião é extraordinária e trata da deliberação de indicações de emendas do orçamento federal para 2026.",
    )
    text = text.replace(
        "Na pauta, há projetos ligados ao senador, incluindo propostas de sua autoria e uma matéria sob sua relatoria.",
        "A pauta inclui projetos ligados ao senador, com propostas de sua autoria e uma matéria sob sua relatoria.",
    )
    text = text.replace("ocorre às as ", "ocorre às ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_generated_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = cleaned.replace("<think>", " ").replace("</think>", " ")
    cleaned = re.sub(r"```(?:text|markdown|md)?", " ", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" `\n\t")


def is_transient_gpu1_error(exc: Exception) -> bool:
    message = str(exc).lower()
    transient_markers = (
        "maximum pending requests exceeded",
        "server busy",
        "503",
        "timed out",
        "timeout",
    )
    return any(marker in message for marker in transient_markers)


def iter_gpu1_models(primary_model: str, fallback_models_arg: str) -> list[str]:
    models = [primary_model.strip()]
    for item in fallback_models_arg.split(","):
        candidate = item.strip()
        if candidate and candidate not in models:
            models.append(candidate)
    for candidate in GPU1_FALLBACK_MODELS:
        if candidate not in models:
            models.append(candidate)
    return models


def build_gpu1_expansion_prompt(text: str) -> str:
    return (
        "/no_think\n"
        "Expanda o texto-base abaixo em portugues do Brasil, com estilo de noticiario imparcial.\n"
        "Objetivo: detalhar a agenda e contextualizar as materias ligadas ao senador.\n\n"
        "Regras:\n"
        "- nao invente fatos\n"
        "- mantenha data, horarios e nomes oficiais das comissoes\n"
        "- se houver materia de autoria do senador, explique em linguagem comum o que ela propoe\n"
        "- se houver materia sob relatoria, deixe claro que nao e de autoria dele\n"
        "- troque siglas e codigos por explicacoes curtas quando possivel\n"
        "- use texto corrido, sem listas e sem markdown\n"
        "- use de 140 a 220 palavras\n"
        "- retorne apenas o texto final\n\n"
        f"Texto-base:\n{text}"
    )


def build_gpu1_broadcast_prompt(text: str) -> str:
    return (
        "/no_think\n"
        "Reescreva o texto abaixo para locucao de jornal em portugues do Brasil.\n"
        "Objetivo: soar como boletim de radio/TV, claro, natural e imparcial.\n\n"
        "Regras:\n"
        "- nao invente fatos\n"
        "- preserve as contextualizacoes relevantes das materias\n"
        "- troque siglas e codigos tecnicos por explicacoes curtas em linguagem comum\n"
        "- evite jargao legislativo quando houver forma simples\n"
        "- preserve nomes oficiais de comissoes\n"
        "- use frases curtas e bem encadeadas\n"
        "- use de 120 a 180 palavras\n"
        "- retorne apenas o texto final\n\n"
        f"Texto-base:\n{text}"
    )


def is_valid_expansion_text(text: str, original_text: str) -> tuple[bool, str]:
    cleaned = clean_generated_text(text)
    if len(cleaned) < max(140, len(original_text) + 40):
        return False, "expansao curta demais"
    if re.search(r"[\u0600-\u06FF]", cleaned):
        return False, "saida com caracteres invalidos"
    lowered = cleaned.lower()
    if "<think>" in lowered or "</think>" in lowered:
        return False, "saida contem think tags"
    if cleaned.count(".") < 3:
        return False, "expansao com poucas frases"
    return True, ""


def is_valid_broadcast_text(text: str) -> bool:
    cleaned = clean_generated_text(text)
    if len(cleaned) < 80:
        return False
    lowered = cleaned.lower()
    if "</think>" in lowered or "<think>" in lowered:
        return False
    if "none" in lowered and len(cleaned) < 140:
        return False
    if re.search(r"[\u0600-\u06FF]", cleaned):
        return False
    if cleaned.count(".") < 2:
        return False
    return True


def generate_with_gpu1_models(
    *,
    prompt: str,
    host: str,
    primary_model: str,
    fallback_models_arg: str,
    validator,
    num_predict: int,
    num_ctx: int,
    max_rounds: int,
    retry_wait_seconds: int,
) -> str:
    last_error: Exception | None = None
    models = iter_gpu1_models(primary_model, fallback_models_arg)
    for round_index in range(max_rounds):
        for model in models:
            client = OllamaClient(host=host, model=model, keep_alive="5m")
            try:
                text = client.generate_validated(
                    prompt,
                    validator=validator,
                    max_attempts=2,
                    num_predict=num_predict,
                    num_ctx=num_ctx,
                    timeout=90,
                    host=host,
                    model=model,
                )
                return clean_generated_text(text)
            except Exception as exc:
                last_error = exc
            finally:
                client.close()
        if round_index + 1 < max_rounds and last_error and is_transient_gpu1_error(last_error):
            time.sleep(max(1, retry_wait_seconds))
            continue
        break
    if last_error is None:
        raise RuntimeError("Falha desconhecida ao consultar a GPU1.")
    raise last_error


def expand_details_with_gpu1(
    text: str,
    *,
    host: str,
    primary_model: str,
    fallback_models_arg: str,
    max_rounds: int,
    retry_wait_seconds: int,
) -> str:
    prompt = build_gpu1_expansion_prompt(text)
    return generate_with_gpu1_models(
        prompt=prompt,
        host=host,
        primary_model=primary_model,
        fallback_models_arg=fallback_models_arg,
        validator=lambda candidate: is_valid_expansion_text(candidate, text),
        num_predict=360,
        num_ctx=3072,
        max_rounds=max_rounds,
        retry_wait_seconds=retry_wait_seconds,
    )


def rewrite_for_broadcast_with_gpu1(
    text: str,
    *,
    host: str,
    primary_model: str,
    fallback_models_arg: str,
    max_rounds: int,
    retry_wait_seconds: int,
) -> str:
    prompt = build_gpu1_broadcast_prompt(text)
    return generate_with_gpu1_models(
        prompt=prompt,
        host=host,
        primary_model=primary_model,
        fallback_models_arg=fallback_models_arg,
        validator=lambda candidate: (is_valid_broadcast_text(candidate), "texto final invalido"),
        num_predict=300,
        num_ctx=3072,
        max_rounds=max_rounds,
        retry_wait_seconds=retry_wait_seconds,
    )


def build_ssml(text: str) -> str:
    parts = [segment.strip() for segment in text.split(". ") if segment.strip()]
    ssml_parts = []
    for index, part in enumerate(parts):
        if not part.endswith("."):
            part = f"{part}."
        escaped = (
            part.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        pause = "" if index == 0 else "<break time=\"650ms\"/>"
        ssml_parts.append(
            f"{pause}<prosody rate=\"-10%\" pitch=\"+2st\">{escaped}</prosody>"
        )
    return "<speak>" + "".join(ssml_parts) + "</speak>"


def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def run_spd_say(
    text: str,
    *,
    language: str,
    voice_type: str,
    rate: int,
    pitch: int,
    volume: int,
    voice: str | None,
    use_ssml: bool,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        "spd-say",
        "-l",
        language,
        "-t",
        voice_type,
        "-r",
        str(rate),
        "-p",
        str(pitch),
        "-i",
        str(volume),
    ]
    if use_ssml:
        cmd.append("-x")
    if voice:
        cmd.extend(["-y", voice])
    cmd.append(text)
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def ensure_piper_voice(voice_name: str, data_dir: Path) -> tuple[Path, Path]:
    if not PIPER_VENV_PYTHON.exists():
        raise RuntimeError(
            f"Python do Piper não encontrado em {PIPER_VENV_PYTHON}. "
            "Crie o venv .venv-tts-piper e instale piper-tts."
        )

    data_dir.mkdir(parents=True, exist_ok=True)
    model_path = data_dir / f"{voice_name}.onnx"
    config_path = data_dir / f"{voice_name}.onnx.json"
    if model_path.exists() and config_path.exists():
        return model_path, config_path

    subprocess.run(
        [
            str(PIPER_VENV_PYTHON),
            "-m",
            "piper.download_voices",
            voice_name,
            "--data-dir",
            str(data_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if not model_path.exists() or not config_path.exists():
        raise RuntimeError(f"Download da voz Piper falhou para {voice_name}")
    return model_path, config_path


def write_wav_file(path: Path, pcm_data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(24000)
        wav_file.writeframes(pcm_data)


def synthesize_piper_local(text: str, voice_name: str, wav_output: Path) -> None:
    model_path, config_path = ensure_piper_voice(voice_name, PIPER_DATA_DIR)
    wav_output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as tmp:
        tmp.write(text)
        tmp.write("\n")
        input_path = tmp.name
    try:
        subprocess.run(
            [
                str(PIPER_VENV_PYTHON),
                "-m",
                "piper",
                "-m",
                str(model_path),
                "-c",
                str(config_path),
                "-i",
                input_path,
                "-f",
                str(wav_output),
                "--sentence-silence",
                "0.4",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        try:
            os.unlink(input_path)
        except FileNotFoundError:
            pass


def synthesize_gemini_tts(text: str, voice_name: str, wav_output: Path) -> None:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY/GOOGLE_API_KEY nao definido; backend gemini-tts indisponivel."
        )

    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice_name,
                    }
                }
            },
        },
        "model": "gemini-3.1-flash-tts-preview",
    }
    response = httpx.post(
        GEMINI_TTS_URL,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    inline_data = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("inlineData", {})
        .get("data")
    )
    if not inline_data:
        raise RuntimeError(f"Resposta sem audio: {data}")
    write_wav_file(wav_output, base64.b64decode(inline_data))


def run_aplay(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["aplay", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )


def main() -> int:
    args = parse_args()
    source_text = load_source_text(args)
    expanded_text = source_text
    if not args.no_gpu1_expand:
        try:
            expanded_text = expand_details_with_gpu1(
                source_text,
                host=args.ollama_host,
                primary_model=args.ollama_model,
                fallback_models_arg=args.ollama_fallback_models,
                max_rounds=args.gpu1_max_rounds,
                retry_wait_seconds=args.gpu1_retry_wait_seconds,
            )
        except Exception:
            expanded_text = source_text
    normalized_text = expanded_text if args.no_normalize else normalize_for_speech(expanded_text)
    final_text = heuristic_rewrite_for_broadcast(normalized_text)
    if not args.no_gpu1_rewrite:
        try:
            candidate_text = rewrite_for_broadcast_with_gpu1(
                final_text,
                host=args.ollama_host,
                primary_model=args.ollama_model,
                fallback_models_arg=args.ollama_fallback_models,
                max_rounds=args.gpu1_max_rounds,
                retry_wait_seconds=args.gpu1_retry_wait_seconds,
            )
            if is_valid_broadcast_text(candidate_text):
                final_text = candidate_text
        except Exception:
            pass
    local_speech_text = build_ssml(final_text) if not args.no_ssml else final_text
    save_text(args.output_text, final_text)

    print("Texto-base:")
    print(source_text)
    print("\nTexto final para locucao:")
    print(final_text)
    print(f"\nArquivo de texto salvo em: {args.output_text}")

    if args.backend == "piper-local":
        synthesize_piper_local(final_text, args.piper_voice, args.wav_output)
        print(f"Arquivo WAV salvo em: {args.wav_output}")

        if args.print_only or not args.play_wav:
            return 0

        completed = run_aplay(args.wav_output)
        if completed.returncode != 0:
            sys.stderr.write(completed.stderr)
            return completed.returncode
        print("\nPlayback do WAV Piper concluido com sucesso.")
        return 0

    if args.backend == "speech-dispatcher":
        if args.print_only:
            cmd_preview = [
                "spd-say",
                "-l",
                args.language,
                "-t",
                args.voice_type,
                "-r",
                str(args.rate),
                "-p",
                str(args.pitch),
                "-i",
                str(args.volume),
            ]
            if not args.no_ssml:
                cmd_preview.append("-x")
            if args.voice:
                cmd_preview.extend(["-y", args.voice])
            cmd_preview.append(local_speech_text)
            print("\nComando de playback:")
            print(shlex.join(cmd_preview))
            return 0

        completed = run_spd_say(
            local_speech_text,
            language=args.language,
            voice_type=args.voice_type,
            rate=args.rate,
            pitch=args.pitch,
            volume=args.volume,
            voice=args.voice,
            use_ssml=not args.no_ssml,
        )
        if completed.returncode != 0:
            sys.stderr.write(completed.stderr)
            return completed.returncode
        print("\nPlayback enviado ao speech-dispatcher com sucesso.")
        return 0

    synthesize_gemini_tts(final_text, args.google_voice, args.wav_output)
    print(f"Arquivo WAV salvo em: {args.wav_output}")

    if args.print_only or not args.play_wav:
        return 0

    completed = run_aplay(args.wav_output)
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        return completed.returncode
    print("\nPlayback do WAV concluido com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
