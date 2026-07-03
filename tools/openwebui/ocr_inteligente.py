"""
title: OCR Inteligente
author: homelab
author_url: http://192.168.15.2
version: 1.0.0
description: |
  Extrai e interpreta texto de imagens com modelos de visão locais (Ollama).
  Suporta documentos, notas, capturas de tela, tabelas e formulários.
  Estágio 1: extração de texto bruto via modelo de visão (moondream).
  Estágio 2: estruturação semântica via LLM de texto (gemma3).
  Modelos rodam 100% local — nenhum dado sai da rede.
required_open_webui_version: 0.3.0
"""

from __future__ import annotations

import os
import re
import json
import urllib.request
import urllib.error
from typing import Iterator
from pydantic import BaseModel, Field


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ollama_generate(host: str, model: str, prompt: str,
                     images: list[str] | None = None,
                     temperature: float = 0.1,
                     timeout: int = 120) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if images:
        payload["images"] = images

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{host}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read()).get("response", "").strip()


def _available_models(host: str) -> list[str]:
    try:
        req = urllib.request.Request(f"{host}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return [m["name"] for m in json.loads(resp.read()).get("models", [])]
    except Exception:
        return []


def _pick_vision_model(host: str, preferred: str) -> str:
    if preferred:
        return preferred
    models = _available_models(host)
    for candidate in ["moondream:latest", "llava:latest", "llava-phi3:latest",
                      "minicpm-v:latest", "gemma3:4b"]:
        if candidate in models:
            return candidate
    # fallback: qualquer modelo com "vision" ou "llava" no nome
    for m in models:
        if any(k in m.lower() for k in ["llava", "vision", "moondream", "minicpm"]):
            return m
    return preferred or "moondream:latest"


def _pick_text_model(host: str, preferred: str) -> str:
    if preferred:
        return preferred
    models = _available_models(host)
    for candidate in ["gemma3:1b", "gemma3:1b", "gemma3:1b",
                      "gemma3:1b", "phi3:latest", "llama3.2:1b"]:
        if candidate in models:
            return candidate
    return preferred or "gemma3:1b"


def _extract_images_and_text(messages: list[dict]) -> tuple[list[str], str]:
    """Extrai imagens base64 e texto da última mensagem do usuário."""
    images: list[str] = []
    user_text = ""
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, list):
            for part in content:
                t = part.get("type", "")
                if t == "image_url":
                    url = part.get("image_url", {}).get("url", "")
                    if "," in url:          # data:image/...;base64,<data>
                        images.append(url.split(",", 1)[1])
                    elif url:
                        images.append(url)
                elif t == "text":
                    user_text = part.get("text", "").strip()
        elif isinstance(content, str):
            user_text = content.strip()
        break
    return images, user_text


_OCR_SYSTEM_PROMPT = (
    "Extract ALL visible text from this image exactly as it appears. "
    "Preserve line breaks, indentation, table structure, bullet points, "
    "numbers, dates, labels, headers, and every character. "
    "Do NOT summarize or paraphrase — return the literal text. "
    "If a region is unclear, transcribe your best guess with [?]. "
    "If there is no text, respond only with: [SEM TEXTO]"
)

_STRUCTURE_SYSTEM_PROMPT = """Você é um assistente de pós-processamento OCR.
Recebeu texto extraído de uma imagem via OCR. Sua tarefa:
1. Corrija erros óbvios de OCR (letras trocadas, espaços extras).
2. Formate tabelas como tabelas Markdown.
3. Formate listas como listas Markdown.
4. Preserve todo o conteúdo original — não omita nada.
5. Se a instrução do usuário pedir algo específico (traduzir, resumir, extrair campos),
   execute essa tarefa APÓS formatar o texto.
Responda apenas com o resultado — sem comentários sobre o processo."""


# ── Pipe ─────────────────────────────────────────────────────────────────────

class Pipe:
    class Valves(BaseModel):
        OLLAMA_HOST: str = Field(
            default="http://192.168.15.2:11437",
            description="Host do Ollama para inferência (coordinator)",
        )
        VISION_MODEL: str = Field(
            default="",
            description="Modelo de visão para OCR (deixe vazio para auto-detectar)",
        )
        TEXT_MODEL: str = Field(
            default="",
            description="Modelo de texto para estruturação (deixe vazio para auto-detectar)",
        )
        SKIP_STRUCTURE_STAGE: bool = Field(
            default=False,
            description="Se True, retorna o texto bruto sem pós-processamento LLM",
        )
        VISION_TIMEOUT: int = Field(
            default=120,
            description="Timeout em segundos para o modelo de visão",
        )
        TEXT_TIMEOUT: int = Field(
            default=60,
            description="Timeout em segundos para o modelo de texto",
        )

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self) -> list[dict]:
        return [{"id": "ocr-inteligente", "name": "🔍 OCR Inteligente"}]

    def pipe(self, body: dict) -> str | Iterator:
        messages: list[dict] = body.get("messages", [])
        images, user_text = _extract_images_and_text(messages)

        if not images:
            return self._help_message()

        host = self.valves.OLLAMA_HOST
        # Se valve aponta para localhost (valor salvo de instalação antiga),
        # substitui pelo OLLAMA_BASE_URL do container que aponta ao coordinator.
        if "localhost" in host or "127.0.0.1" in host:
            host = os.environ.get("OLLAMA_BASE_URL", host).rstrip("/")
        vision_model = _pick_vision_model(host, self.valves.VISION_MODEL)
        text_model = _pick_text_model(host, self.valves.TEXT_MODEL)

        results: list[str] = []
        n = len(images)

        for idx, img_b64 in enumerate(images):
            header = f"### Imagem {idx + 1}/{n}\n\n" if n > 1 else ""

            # ── Estágio 1: extração de texto via visão ──────────────────────
            try:
                raw_text = _ollama_generate(
                    host=host,
                    model=vision_model,
                    prompt=_OCR_SYSTEM_PROMPT,
                    images=[img_b64],
                    temperature=0.05,
                    timeout=self.valves.VISION_TIMEOUT,
                )
            except Exception as exc:
                results.append(f"{header}⚠️ Erro no modelo de visão (`{vision_model}`): {exc}")
                continue

            if raw_text.strip() == "[SEM TEXTO]":
                results.append(f"{header}🖼️ Nenhum texto detectado na imagem.")
                continue

            # ── Estágio 2: estruturação semântica ───────────────────────────
            if self.valves.SKIP_STRUCTURE_STAGE:
                results.append(f"{header}```\n{raw_text}\n```")
                continue

            user_instruction = (
                f"\n\nInstrução adicional do usuário: {user_text}"
                if user_text and user_text.lower() not in {"ocr", "extrair", "extract", ""}
                else ""
            )
            structure_prompt = (
                f"{_STRUCTURE_SYSTEM_PROMPT}{user_instruction}\n\n"
                f"Texto OCR bruto:\n{raw_text}"
            )

            try:
                structured = _ollama_generate(
                    host=host,
                    model=text_model,
                    prompt=structure_prompt,
                    temperature=0.15,
                    timeout=self.valves.TEXT_TIMEOUT,
                )
                # Remove <think> blocks (chain-of-thought)
                structured = re.sub(r"<think>.*?</think>", "", structured,
                                    flags=re.DOTALL).strip()
                results.append(f"{header}{structured}")
            except Exception:
                # Estruturação falhou — retorna texto bruto formatado
                results.append(f"{header}```\n{raw_text}\n```")

        separator = "\n\n---\n\n" if n > 1 else ""
        return separator.join(results)

    # ── Helpers internos ─────────────────────────────────────────────────────

    def _help_message(self) -> str:
        host = self.valves.OLLAMA_HOST
        vision = _pick_vision_model(host, self.valves.VISION_MODEL)
        text = _pick_text_model(host, self.valves.TEXT_MODEL)
        return (
            "## 🔍 OCR Inteligente\n\n"
            "Faça upload de uma imagem para extrair e estruturar o texto.\n\n"
            "**Como usar:**\n"
            "- Arraste e solte a imagem no campo de mensagem\n"
            "- Clique no ícone 📎 e selecione a imagem\n"
            "- Você pode combinar imagem + instrução:\n"
            "  - *\"extraia e converta para tabela CSV\"*\n"
            "  - *\"traduza o texto para inglês\"*\n"
            "  - *\"identifique os campos do formulário\"*\n"
            "  - *\"extraia apenas os valores numéricos\"*\n\n"
            "**Pipeline:**\n"
            f"1. 👁️ Extração: `{vision}` → texto bruto\n"
            f"2. 🧠 Estruturação: `{text}` → Markdown formatado\n\n"
            "**Modelos 100% locais** — nenhum dado sai da rede."
        )
