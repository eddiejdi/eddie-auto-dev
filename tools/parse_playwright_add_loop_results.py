#!/usr/bin/env python3
"""Ferramenta para agregar resultados do add-loop do Playwright.

Analisa os arquivos `content.txt` em uma sessão do VS Code (`chat-session-resources/.../call_*`) e
gera um resumo com contagens de itens adicionados, já presentes e falhas.

Uso:
  python tools/parse_playwright_add_loop_results.py --session <session_path>

Saída:
  - Imprime um resumo conciso em JSON no stdout
  - Escreve `.add_loop_summary.json` na pasta da sessão
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import re
import json
import argparse
from urllib.parse import urlparse, parse_qs


def is_playlist_url(url: str) -> bool:
    """Retorna True se a URL aparenta ser relacionada a playlists do YouTube Music.

    Heurística simples baseada em termos na URL.
    """
    u = url.lower()
    return (
        "playlist" in u
        or "playlistitems" in u
        or "/playlist?" in u
        or "youtubei/v1/playlist" in u
    )


def extract_docid(url: str) -> Optional[str]:
    """Extrai parâmetros comuns de id de vídeo (docid, v, videoId) de uma URL.

    Retorna None se não encontrar.
    """
    try:
        p = urlparse(url)
        qs = parse_qs(p.query)
        for k in ("docid", "v", "videoId", "video_id", "id"):
            if k in qs and qs[k]:
                return qs[k][0]
    except Exception:
        return None
    return None


def parse_content_text(text: str) -> Dict[str, Any]:
    """Analisa o texto de um content.txt e retorna estruturas com eventos relevantes.

    Campos retornados:
      - playlist_requests: lista de dicts com chaves (url, error, docid, status)
      - console_adds: lista de dicts com chaves (level, msg, category, vid)
      - other_request_failed: lista de dicts com (url, error, docid)
    """
    out: Dict[str, Any] = {
        "playlist_requests": [],
        "console_adds": [],
        "other_request_failed": [],
    }

    # Captura linhas de requestFailed: '(requestFailed) POST request to <url> failed: "<err>"'
    req_failed_re = re.compile(r"\(requestFailed\)\s+(?:GET|POST) request to\s+(\S+) failed: \"([^\"]+)\"", re.IGNORECASE)
    for m in req_failed_re.finditer(text):
        url = m.group(1)
        err = m.group(2)
        docid = extract_docid(url) or ""
        entry = {"url": url, "error": err, "docid": docid}
        if is_playlist_url(url):
            entry["status"] = "failed"
            out["playlist_requests"].append(entry)
        else:
            out["other_request_failed"].append(entry)

    # Captura blocos de 'responses' com status 200 (quando presentes no snapshot JSON)
    # Busca por padrões "url": "..." e "status": <num> próximos
    responses_block_re = re.compile(r'"responses"\s*:\s*\[(.*?)\]', re.S)
    block_m = responses_block_re.search(text)
    if block_m:
        block = block_m.group(1)
        for m in re.finditer(r'"url"\s*:\s*"([^"]+)"[\s\S]{0,200}?"status"\s*:\s*(\d+)', block):
            url = m.group(1)
            status = int(m.group(2))
            if is_playlist_url(url) and status == 200:
                out["playlist_requests"].append({"url": url, "status": "ok", "docid": extract_docid(url) or ""})

    # Captura mensagens de console: '(console) [level] message'
    console_re = re.compile(r"\(console\)\s*\[([^\]]+)\]\s*(.+)", re.IGNORECASE)
    for m in console_re.finditer(text):
        level = m.group(1)
        msg = m.group(2).strip()
        msg_low = msg.lower()
        category = None
        if any(k in msg_low for k in ("added", "adicionado", "salvo", "saved")):
            category = "added"
        elif any(k in msg_low for k in ("already", "já está", "já na", "já adicionado")):
            category = "already"
        if category:
            vid = ""
            vid_m = re.search(r"v=([A-Za-z0-9_\-]{11})", msg)
            if vid_m:
                vid = vid_m.group(1)
            out["console_adds"].append({"level": level, "msg": msg, "category": category, "vid": vid})

    return out


def summarize_session(session_path: Path) -> Dict[str, Any]:
    """Varre os `call_*` em `session_path` e agrega um resumo.

    Retorna um dicionário com contagens e exemplos.
    """
    calls = sorted([p for p in session_path.iterdir() if p.is_dir() and p.name.startswith("call_")])
    summary: Dict[str, Any] = {
        "total_calls": len(calls),
        "added": 0,
        "already": 0,
        "playlist_failed": 0,
        "other_failed": 0,
        "samples": [],
    }

    for call in calls:
        content_file = call / "content.txt"
        if not content_file.exists():
            continue
        text = content_file.read_text(errors="ignore")
        parsed = parse_content_text(text)

        for c in parsed["console_adds"]:
            if c["category"] == "added":
                summary["added"] += 1
            elif c["category"] == "already":
                summary["already"] += 1
            summary["samples"].append({"type": "console", **c})

        for pr in parsed["playlist_requests"]:
            if pr.get("status") == "failed":
                summary["playlist_failed"] += 1
                summary["samples"].append({"type": "playlist_failed", **pr})
            elif pr.get("status") == "ok":
                summary["added"] += 1
                summary["samples"].append({"type": "playlist_ok", **pr})

        summary["other_failed"] += len(parsed["other_request_failed"])

    return summary


def main() -> None:
    """Entrada principal do script.

    Argumentos:
      --session: caminho para a pasta da sessão (padrão definido automaticamente)
    """
    default_session = Path(
        "/home/edenilson/.config/Code/User/workspaceStorage/76f8845b0ed394e778733b67669998cb/GitHub.copilot-chat/chat-session-resources/3788fc31-6d1b-4216-9109-97df3d7ef256"
    )
    parser = argparse.ArgumentParser(description="Resumo do add-loop a partir dos captures do Playwright")
    parser.add_argument("--session", type=Path, default=default_session, help="Pasta da sessão com call_*/content.txt")
    args = parser.parse_args()

    if not args.session.exists():
        print(f"Erro: sessão não encontrada em {args.session}")
        raise SystemExit(1)

    summary = summarize_session(args.session)
    out_file = args.session / "add_loop_summary.json"
    out_file.write_text(json.dumps({"summary": summary}, indent=2))
    print(json.dumps({"summary": summary}, indent=2))


if __name__ == "__main__":
    main()
