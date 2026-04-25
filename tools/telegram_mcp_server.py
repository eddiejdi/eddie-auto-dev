#!/usr/bin/env python3
"""
Telegram MCP Server — Agente de pré-processamento com IA local (Ollama/homelab)
Baixa texto, fotos, documentos, áudio e vídeo do Telegram.
Analisa tudo com visão (moondream) e linguagem (qwen2.5) antes de entregar
ao chamador — retorno já "mastigado" para reduzir tokens e tempo.
"""

import asyncio
import base64
import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# ── Configuração ─────────────────────────────────────────────────────────────
TG_TOKEN   = os.environ.get("TG_TOKEN", "1105143633:AAG5BrfOsGbV88BFztljR7fH5ekmszFnulA")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "948686300")
TG_BASE    = f"https://api.telegram.org/bot{TG_TOKEN}"
TG_FILE    = f"https://api.telegram.org/file/bot{TG_TOKEN}"

OLLAMA_BASE    = os.environ.get("OLLAMA_BASE", "http://192.168.15.2:11434")
TEXT_MODEL     = os.environ.get("TEXT_MODEL", "qwen2.5:3b")
VISION_MODEL   = os.environ.get("VISION_MODEL", "moondream:latest")
MEDIA_DIR      = Path(os.environ.get("MEDIA_DIR", "/tmp/tg_media"))
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = httpx.Timeout(60.0, connect=10.0)

server = Server("telegram-agent")

# ── Helpers ───────────────────────────────────────────────────────────────────

async def tg_get(client: httpx.AsyncClient, method: str, **params) -> dict:
    r = await client.get(f"{TG_BASE}/{method}", params=params, timeout=TIMEOUT)
    return r.json()


async def tg_download(client: httpx.AsyncClient, file_id: str) -> Path | None:
    """Baixa um arquivo do Telegram e salva em MEDIA_DIR. Retorna o path local."""
    info = await tg_get(client, "getFile", file_id=file_id)
    if not info.get("ok"):
        return None
    fp = info["result"]["file_path"]
    ext = Path(fp).suffix or ".bin"
    dest = MEDIA_DIR / f"{file_id}{ext}"
    if dest.exists():
        return dest
    resp = await client.get(f"{TG_FILE}/{fp}", timeout=TIMEOUT)
    dest.write_bytes(resp.content)
    return dest


async def ollama_chat(client: httpx.AsyncClient, model: str, prompt: str,
                      image_b64: str | None = None) -> str:
    """Envia para Ollama; suporta imagem em base64 para modelos de visão."""
    messages: list[dict] = []
    if image_b64:
        messages.append({"role": "user", "content": prompt,
                         "images": [image_b64]})
    else:
        messages.append({"role": "user", "content": prompt})
    payload = {"model": model, "messages": messages, "stream": False,
               "options": {"temperature": 0.1}}
    try:
        r = await client.post(f"{OLLAMA_BASE}/api/chat",
                              json=payload, timeout=TIMEOUT)
        data = r.json()
        return data.get("message", {}).get("content", "").strip()
    except Exception as e:
        return f"[ollama error: {e}]"


def _vision_available(client: httpx.AsyncClient) -> bool:
    # verificado dinamicamente no primeiro uso
    return True


def _parse_message(msg: dict) -> dict:
    """Extrai campos relevantes de uma mensagem Telegram bruta."""
    ts = datetime.fromtimestamp(msg.get("date", 0)).strftime("%Y-%m-%d %H:%M:%S")
    sender = msg.get("from", {}) or msg.get("chat", {})
    name = (sender.get("first_name", "") + " " + sender.get("last_name", "")).strip() \
           or sender.get("username", "unknown")
    out: dict[str, Any] = {
        "id":        msg.get("message_id"),
        "timestamp": ts,
        "from":      name,
        "type":      "unknown",
    }
    # Texto
    if "text" in msg:
        out["type"] = "text"
        out["text"] = msg["text"]
    # Foto (escolhe maior resolução)
    elif "photo" in msg:
        out["type"]    = "photo"
        out["file_id"] = msg["photo"][-1]["file_id"]
        out["caption"] = msg.get("caption", "")
    # Documento
    elif "document" in msg:
        doc = msg["document"]
        out["type"]      = "document"
        out["file_id"]   = doc["file_id"]
        out["filename"]  = doc.get("file_name", "arquivo")
        out["mime_type"] = doc.get("mime_type", "")
        out["caption"]   = msg.get("caption", "")
    # Áudio / Voice
    elif "voice" in msg:
        out["type"]     = "voice"
        out["file_id"]  = msg["voice"]["file_id"]
        out["duration"] = msg["voice"].get("duration", 0)
    elif "audio" in msg:
        out["type"]     = "audio"
        out["file_id"]  = msg["audio"]["file_id"]
        out["title"]    = msg["audio"].get("title", "")
        out["duration"] = msg["audio"].get("duration", 0)
    # Vídeo
    elif "video" in msg:
        out["type"]     = "video"
        out["file_id"]  = msg["video"]["file_id"]
        out["duration"] = msg["video"].get("duration", 0)
        out["caption"]  = msg.get("caption", "")
    elif "video_note" in msg:
        out["type"]     = "video_note"
        out["file_id"]  = msg["video_note"]["file_id"]
    # Sticker
    elif "sticker" in msg:
        out["type"]   = "sticker"
        out["emoji"]  = msg["sticker"].get("emoji", "")
    # Localização
    elif "location" in msg:
        out["type"] = "location"
        out["lat"]  = msg["location"]["latitude"]
        out["lng"]  = msg["location"]["longitude"]
    return out


async def _analyze_message(client: httpx.AsyncClient, parsed: dict,
                            analyze_media: bool = True) -> dict:
    """Enriquece `parsed` com análise de IA. Retorna o dict atualizado."""
    mtype = parsed["type"]

    if mtype == "text":
        prompt = (
            "Analise esta mensagem de usuário em português. "
            "Identifique: (1) intenção principal, (2) ação solicitada, "
            "(3) contexto técnico se houver, (4) urgência (baixa/média/alta). "
            "Seja conciso, máximo 4 linhas.\n\n"
            f"Mensagem: {parsed['text']}"
        )
        parsed["ai_analysis"] = await ollama_chat(client, TEXT_MODEL, prompt)
        parsed["intent"] = await ollama_chat(
            client, TEXT_MODEL,
            f"Em uma frase curta, qual é a intenção desta mensagem: {parsed['text']}"
        )

    elif mtype == "photo" and analyze_media:
        path = await tg_download(client, parsed["file_id"])
        if path:
            parsed["local_path"] = str(path)
            img_b64 = base64.b64encode(path.read_bytes()).decode()
            # Tentativa de análise com moondream (visão)
            vision_prompt = (
                "Descreva detalhadamente o que está visível nesta imagem. "
                "Se for uma tela de computador/terminal: transcreva TODO o texto visível "
                "literalmente (especialmente mensagens de erro, menus, logs). "
                "Identifique o sistema operacional/software mostrado. "
                "Destaque qualquer erro ou problema visível."
            )
            vision_result = await ollama_chat(
                client, VISION_MODEL, vision_prompt, img_b64
            )
            # Fallback para modelo de texto se visão falhar
            if "[ollama error" in vision_result or not vision_result:
                vision_result = "[visão indisponível — moondream não carregado ainda]"
            parsed["ai_analysis"]       = vision_result
            parsed["vision_text"]       = vision_result
            # Síntese de intenção baseada na visão
            if "[" not in vision_result[:5]:
                intent_prompt = (
                    f"Com base nesta descrição de imagem: '{vision_result[:400]}'\n"
                    "Em uma frase: o que o usuário está mostrando/pedindo?"
                )
                parsed["intent"] = await ollama_chat(client, TEXT_MODEL, intent_prompt)

    elif mtype == "document" and analyze_media:
        path = await tg_download(client, parsed["file_id"])
        if path:
            parsed["local_path"] = str(path)
            # Tentar ler como texto se for texto/json/log
            if parsed.get("mime_type", "").startswith("text") or \
               path.suffix in (".txt", ".log", ".json", ".py", ".sh", ".cfg", ".conf"):
                try:
                    content = path.read_text(errors="replace")[:2000]
                    prompt = (
                        f"Arquivo: {parsed['filename']}\n"
                        f"Conteúdo (primeiros 2000 chars):\n{content}\n\n"
                        "Resuma em 3 linhas: o que é este arquivo e o que contém."
                    )
                    parsed["ai_analysis"] = await ollama_chat(client, TEXT_MODEL, prompt)
                except Exception:
                    parsed["ai_analysis"] = f"[arquivo binário: {path.stat().st_size} bytes]"
            else:
                parsed["ai_analysis"] = f"[arquivo {parsed['mime_type']}: {path.stat().st_size} bytes, salvo em {path}]"

    elif mtype in ("voice", "audio") and analyze_media:
        path = await tg_download(client, parsed["file_id"])
        if path:
            parsed["local_path"] = str(path)
            parsed["ai_analysis"] = f"[áudio {parsed.get('duration', '?')}s — transcrição requer whisper]"

    return parsed


# ── Tools MCP ─────────────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="tg_latest",
            description=(
                "Busca as últimas N mensagens do Telegram (padrão 5). "
                "Suporta todos os tipos: texto, fotos, documentos, áudio, vídeo, localização. "
                "Para fotos: baixa e analisa com IA de visão (moondream) extraindo texto/descrição da tela. "
                "Para textos: classifica intenção com Ollama. "
                "Retorna JSON já pré-processado com análise completa — usa para reduzir tokens."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "n":              {"type": "integer", "default": 5,
                                       "description": "Número de mensagens a buscar (1-50)"},
                    "analyze_media":  {"type": "boolean", "default": True,
                                       "description": "Se True, baixa e analisa mídia com IA"},
                    "only_new":       {"type": "boolean", "default": False,
                                       "description": "Se True, retorna apenas mensagens não vistas antes"},
                },
            },
        ),
        Tool(
            name="tg_send",
            description="Envia mensagem de texto para o chat Telegram configurado.",
            inputSchema={
                "type": "object",
                "required": ["text"],
                "properties": {
                    "text":       {"type": "string", "description": "Mensagem a enviar"},
                    "parse_mode": {"type": "string", "default": "Markdown",
                                   "description": "Markdown ou HTML"},
                },
            },
        ),
        Tool(
            name="tg_analyze",
            description=(
                "Analisa uma imagem/arquivo específico via file_id do Telegram. "
                "Usa moondream (visão) para extrair texto de telas e descrever conteúdo. "
                "Ideal para re-analisar uma foto já recebida."
            ),
            inputSchema={
                "type": "object",
                "required": ["file_id"],
                "properties": {
                    "file_id": {"type": "string", "description": "file_id do Telegram"},
                    "prompt":  {"type": "string",
                                "description": "Pergunta específica sobre a imagem (opcional)"},
                },
            },
        ),
        Tool(
            name="tg_context",
            description=(
                "Gera um resumo de contexto completo das últimas N mensagens. "
                "Usa Ollama para sintetizar o que o usuário está pedindo/mostrando. "
                "Retorna: histórico estruturado + síntese de intenção + próxima ação sugerida."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "n": {"type": "integer", "default": 10,
                          "description": "Número de mensagens para gerar contexto"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    async with httpx.AsyncClient() as client:
        if name == "tg_latest":
            n    = min(int(arguments.get("n", 5)), 50)
            analyze = bool(arguments.get("analyze_media", True))
            only_new = bool(arguments.get("only_new", False))

            data = await tg_get(client, "getUpdates", limit=100, offset=-100)
            updates = data.get("result", [])

            messages = []
            for u in updates:
                msg = u.get("message") or u.get("channel_post")
                if msg:
                    messages.append(msg)

            # Ordenar por data e pegar os N mais recentes
            messages.sort(key=lambda m: m.get("date", 0))
            recent = messages[-n:]

            results = []
            for msg in recent:
                parsed = _parse_message(msg)
                if analyze:
                    parsed = await _analyze_message(client, parsed, analyze_media=True)
                results.append(parsed)

            summary = {
                "total_fetched": len(results),
                "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "messages":      results,
            }
            return [TextContent(type="text", text=json.dumps(summary, ensure_ascii=False, indent=2))]

        elif name == "tg_send":
            text       = arguments["text"]
            parse_mode = arguments.get("parse_mode", "Markdown")
            r = await client.post(f"{TG_BASE}/sendMessage", json={
                "chat_id":    TG_CHAT_ID,
                "text":       text,
                "parse_mode": parse_mode,
            }, timeout=TIMEOUT)
            resp = r.json()
            ok = resp.get("ok", False)
            return [TextContent(type="text",
                                text=json.dumps({"ok": ok, "message_id": resp.get("result", {}).get("message_id")}))]

        elif name == "tg_analyze":
            file_id     = arguments["file_id"]
            user_prompt = arguments.get("prompt", "")
            path = await tg_download(client, file_id)
            if not path:
                return [TextContent(type="text", text='{"error": "file not found"}')]

            img_b64 = base64.b64encode(path.read_bytes()).decode()
            base_prompt = (
                "Descreva esta imagem detalhadamente. Se for tela de terminal/computador, "
                "transcreva TODO o texto visível literalmente."
            )
            prompt = f"{base_prompt}\n\nPergunta adicional: {user_prompt}" if user_prompt else base_prompt
            result = await ollama_chat(client, VISION_MODEL, prompt, img_b64)

            return [TextContent(type="text", text=json.dumps({
                "file_id":     file_id,
                "local_path":  str(path),
                "analysis":    result,
            }, ensure_ascii=False, indent=2))]

        elif name == "tg_context":
            n    = min(int(arguments.get("n", 10)), 50)

            data = await tg_get(client, "getUpdates", limit=100, offset=-100)
            updates = data.get("result", [])
            messages = [u.get("message") or u.get("channel_post")
                        for u in updates if u.get("message") or u.get("channel_post")]
            messages.sort(key=lambda m: m.get("date", 0))
            recent = messages[-n:]

            # Pré-processar cada mensagem
            parsed_list = []
            for msg in recent:
                p = _parse_message(msg)
                p = await _analyze_message(client, p, analyze_media=True)
                parsed_list.append(p)

            # Montar histórico textual para síntese
            history_lines = []
            for p in parsed_list:
                ts   = p["timestamp"]
                mtype = p["type"]
                if mtype == "text":
                    history_lines.append(f"[{ts}] texto: {p.get('text', '')}")
                elif mtype == "photo":
                    desc = p.get("ai_analysis", "")[:200]
                    history_lines.append(f"[{ts}] foto — IA viu: {desc}")
                elif mtype == "document":
                    history_lines.append(f"[{ts}] doc {p.get('filename', '')} — {p.get('ai_analysis', '')[:150]}")
                else:
                    history_lines.append(f"[{ts}] {mtype}")
            history_str = "\n".join(history_lines)

            # Síntese com Ollama
            synthesis_prompt = (
                "Você é um assistente técnico. Analise este histórico de mensagens de um usuário "
                "e responda em português:\n"
                "1. O que o usuário está fazendo/tentando resolver?\n"
                "2. Qual foi o último estado/problema reportado?\n"
                "3. Qual seria a próxima ação lógica a tomar?\n\n"
                f"Histórico:\n{history_str}"
            )
            synthesis = await ollama_chat(client, TEXT_MODEL, synthesis_prompt)

            return [TextContent(type="text", text=json.dumps({
                "messages":     parsed_list,
                "synthesis":    synthesis,
                "history_text": history_str,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }, ensure_ascii=False, indent=2))]

        return [TextContent(type="text", text='{"error": "tool not found"}')]


# ── Entry point ───────────────────────────────────────────────────────────────
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream,
                         server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
