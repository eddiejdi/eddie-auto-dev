"""Biblioteca compartilhada de busca no wiki RPA4All (local + Wiki.js remoto).

Usada pelo hook inject_wiki_context.py nas modalidades:
  - session → índice completo (local + pages.list remoto) para o início da sessão
  - block   → busca remota (pages.search) + local, por keywords do contexto de bloqueio
  - tool    → busca por keywords do tool input (uso pontual)

Design:
  - Fail-open: erro de rede/token/fuso degrada para o que está disponível (nunca bloqueia).
  - Cache em disco (/tmp) com TTL (RPA4ALL_WIKI_TTL, default 60s). Hooks são processos
    independentes → cache em memória não persiste entre invocações.
  - Token: WIKI_TOKEN env → .env do repo → secrets agent (best-effort, mesmo padrão do wiki_sync).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

WIKI_URL_DEFAULT = "http://192.168.15.2:3009/graphql"
WIKI_LOCALE_DEFAULT = "en"  # páginas remotas da Wiki.js estão em locale "en"
WIKI_GLOB = "wiki_*.md"
WIKI_INDEX_FILE = "wiki_pages.json"
CACHE_FILE = Path("/tmp/rpa4all_wiki_cache.json")

STOPWORDS = {
    "com", "para", "que", "uma", "um", "dos", "das", "não", "nao", "esta", "está",
    "mas", "por", "como", "mais", "also", "with", "from", "into", "when", "does", "what", "your", "this", "that", "have", "been", "the",
    "and", "are", "was", "for", "not", "but", "you", "all", "can", "has", "its",
    "project", "2026", "2025", "rpa4all",
}


def _ttl() -> int:
    return int(os.environ.get("RPA4ALL_WIKI_TTL", "60"))


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------
def load_wiki_token(repo_root: Path | None = None) -> str:
    """WIKI_TOKEN env → .env do repo → secrets agent (best-effort)."""
    val = os.environ.get("WIKI_TOKEN", "")
    if val:
        return val.strip()

    root = repo_root or Path.cwd()
    env_f = root / ".env"
    if env_f.exists():
        try:
            for line in env_f.read_text().splitlines():
                if line.startswith("WIKI_TOKEN="):
                    return line.split("=", 1)[1].strip().strip("\"'")
        except OSError:
            pass

    try:
        endpoint = "http://192.168.15.2:8088/secret/wikijs/token"
        r = subprocess.run(
            ["curl", "-sf", "--max-time", "4", endpoint],
            capture_output=True,
            text=True,
            timeout=6,
        )
        if r.returncode == 0:
            return json.loads(r.stdout).get("value", "")
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Cache em disco
# ---------------------------------------------------------------------------
def _cache_store() -> dict[str, Any]:
    try:
        return json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}
    except Exception:
        return {}


def _cache_write(data: dict[str, Any]) -> None:
    try:
        CACHE_FILE.write_text(json.dumps(data))
    except OSError:
        pass


def cache_get(key: str) -> Any | None:
    now = time.time()
    store = _cache_store()
    entry = store.get(key)
    if not isinstance(entry, dict):
        return None
    if now - float(entry.get("ts", 0)) > _ttl():
        return None
    return entry.get("value")


def cache_set(key: str, value: Any) -> None:
    now = time.time()
    store = _cache_store()
    store[key] = {"ts": now, "value": value}
    # Poda simples: limpa entradas velhas para não crescer sem limite.
    store = {k: v for k, v in store.items() if now - float(v.get("ts", 0)) <= _ttl()}
    _cache_write(store)


# ---------------------------------------------------------------------------
# GraphQL
# ---------------------------------------------------------------------------
def _wiki_url() -> str:
    return os.environ.get("RPA4ALL_WIKI_URL", WIKI_URL_DEFAULT).strip() or WIKI_URL_DEFAULT


def gql(query: str, variables: dict[str, Any], token: str, url: str | None = None) -> dict[str, Any]:
    """Executa GraphQL na Wiki.js. Lança exceção em erro HTTP/JSON para o chamador decidir."""
    payload = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        url or _wiki_url(),
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read())
    if data.get("errors"):
        raise RuntimeError(f"GraphQL errors: {data['errors'][0].get('message')}")
    return data.get("data", {})


def remote_list_pages(token: str) -> list[dict[str, Any]]:
    """Retorna todas as páginas remotas via pages.list (com cache)."""
    cache_key = "list_pages"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    query = """
    query ListPages($orderBy: PageOrderBy!) {
      pages { list(orderBy: $orderBy) { id path title locale updatedAt } }
    }"""
    data = gql(query, {"orderBy": "TITLE"}, token)
    pages = data.get("pages", {}).get("list", []) or []
    cache_set(cache_key, pages)
    return pages


def remote_search(query: str, token: str) -> list[dict[str, Any]]:
    """Busca textual na Wiki.js via pages.search (com cache por query)."""
    q = " ".join(query.split())
    if not q.strip():
        return []
    cache_key = f"search:{q.lower()}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    gql_query = """
    query SearchPages($q: String!, $locale: String) {
      pages { search(query: $q, locale: $locale) {
        results { id path title description locale }
      } }
    }"""
    data = gql(gql_query, {"q": q, "locale": WIKI_LOCALE_DEFAULT}, token)
    results = data.get("pages", {}).get("search", {}).get("results", []) or []
    cache_set(cache_key, results)
    return results


def remote_page_content(path: str, locale: str = WIKI_LOCALE_DEFAULT, token: str = "") -> str:
    """Conteúdo completo de uma página remota via singleByPath (com cache por path+locale)."""
    key = f"page:{path}:{locale}"
    cached = cache_get(key)
    if cached is not None:
        return cached
    query = """
    query GetPage($path: String!, $locale: String!) {
      pages { singleByPath(path: $path, locale: $locale) { path title content } }
    }"""
    data = gql(query, {"path": path, "locale": locale}, token)
    page = data.get("pages", {}).get("singleByPath") or {}
    content = page.get("content", "") or ""
    cache_set(key, content)
    return content


# ---------------------------------------------------------------------------
# Páginas locais
# ---------------------------------------------------------------------------
def local_pages(root: Path) -> list[dict[str, Any]]:
    """Enumera páginas do wiki local: índice wiki_pages.json + arquivos wiki_*.md."""
    pages: list[dict[str, Any]] = []
    idx = root / WIKI_INDEX_FILE
    try:
        data = json.loads(idx.read_text(encoding="utf-8"))
        if isinstance(data, list):
            pages = [p for p in data if isinstance(p, dict) and p.get("file")]
    except Exception:
        pass

    seen = {p.get("file") for p in pages}
    for md in sorted(root.glob(WIKI_GLOB)):
        if md.name in seen:
            continue
        pages.append({
            "file": md.name,
            "path": md.stem,
            "title": _heading_title(md) or md.stem,
        })
    return pages


def _heading_title(md_path: Path) -> str:
    try:
        for line in md_path.read_text(encoding="utf-8", errors="replace").splitlines()[:10]:
            m = re.match(r"^\s*#+\s+(.+)$", line)
            if m:
                return m.group(1).strip()
    except Exception:
        pass
    return ""


def local_page_text(root: Path, page: dict[str, Any], max_chars: int = 4000) -> str:
    content = ""
    for cand in (root / page["file"], root / f"{page.get('path', '')}.md"):
        try:
            if cand.is_file():
                content = cand.read_text(encoding="utf-8", errors="replace")
                break
        except Exception:
            continue
    if len(content) > max_chars:
        return content[:max_chars] + "\n... [truncado pelo hook]"
    return content


# ---------------------------------------------------------------------------
# Tokens / scoring
# ---------------------------------------------------------------------------
def tokenize(text: str) -> set[str]:
    text = (text or "").lower()
    text = re.sub(r"[^\wà-ÿç-]", " ", text)
    toks: set[str] = set()
    for tok in re.split(r"\s+", text):
        tok = tok.strip()
        if len(tok) < 3 or tok in STOPWORDS:
            continue
        if tok.endswith("s") and len(tok) > 4:
            toks.add(tok[:-1])
        toks.add(tok)
    return toks


def score(query_tokens: set[str], title: str, body_tokens: set[str]) -> int:
    head = tokenize(f"{title}") if title else set()
    head_hits = query_tokens & head
    body_hits = query_tokens & (body_tokens or set())
    return len(head_hits) * 2 + len(body_hits)


# ---------------------------------------------------------------------------
# Orquestração da busca (usada pelo hook)
# ---------------------------------------------------------------------------
def search_wiki(
    query_text: str,
    root: Path,
    token: str = "",
    include_remote: bool = True,
) -> dict[str, Any]:
    """Busca local + remota por keywords e devolve { pages, body } prontos para injetar.

    pages: lista de dicts {title, ref, text, source} com as melhores (≤ max_pages).
    body:  texto formatado (índice + páginas) truncado em max_chars.
    """
    max_chars = int(os.environ.get("RPA4ALL_WIKI_MAX_CHARS", "6000"))
    max_pages = int(os.environ.get("RPA4ALL_WIKI_MAX_PAGES", "2"))

    q_tokens = tokenize(query_text)
    if not q_tokens or len(q_tokens) < 2:
        return {"pages": [], "body": ""}

    scored: list[tuple[int, dict[str, Any]]] = []

    # Local
    for page in local_pages(root):
        text = local_page_text(root, page)
        s = score(q_tokens, page.get("title", ""), tokenize(text))
        if s >= 3:
            scored.append((s, {
                "title": page.get("title", page["file"]),
                "ref": page["file"],
                "text": text[:max_chars // max(1, max_pages * 2)],
                "source": "local",
            }))

    # Remota
    if include_remote and token:
        try:
            for r in remote_search(query_text, token):
                body_tokens = tokenize(r.get("title", ""))
                s = score(q_tokens, r.get("title", ""), body_tokens)
                path = r.get("path", "")
                title = r.get("title", path) or path
                if _already_scored(scored, title, path):
                    continue
                if s < 3:
                    continue
                content = remote_page_content(path, r.get("locale") or WIKI_LOCALE_DEFAULT, token) or ""
                scored.append((s, {
                    "title": title,
                    "ref": path,
                    "text": content[:max_chars // max(1, max_pages * 2)],
                    "source": "remote",
                }))
        except Exception:
            pass  # fail-open: sem remoto, segue só com local

    if not scored:
        return {"pages": [], "body": ""}

    scored.sort(key=lambda x: -x[0])
    best = [p for _, p in scored[:max_pages]]

    index_lines = ["- `{ref}` — {title}".format(**p) for p in best]
    body_parts = [
        "# Conhecimento Wiki RPA4All",
        "Páginas relevantes:",
        "```",
        "\n".join(index_lines),
        "```",
        "",
    ]
    for p in best:
        body_parts.append(f"## {p['title']}  (`{p['ref']}`, fonte: {p['source']})")
        body_parts.append(p["text"])
        body_parts.append("")

    body = "\n".join(body_parts)
    if len(body) > max_chars:
        body = body[:max_chars] + "\n... [truncado]"
    return {"pages": best, "body": body}


def _already_scored(scored: list[tuple[int, dict[str, Any]]], title: str, path: str) -> bool:
    for _, p in scored:
        if p.get("ref") == path or p.get("title") == title:
            return True
    return False


# ---------------------------------------------------------------------------
# Índice de sessão (local + remoto)
# ---------------------------------------------------------------------------
def session_index(root: Path, token: str = "") -> str:
    """Índice compacto de todas as páginas do wiki (local + remoto) para início de sessão."""
    max_chars = int(os.environ.get("RPA4ALL_WIKI_MAX_CHARS", "6000"))
    entries: dict[str, str] = {}

    for p in local_pages(root):
        entries[p.get("path", p.get("file"))] = p.get("title", p.get("file"))

    if token:
        try:
            for p in remote_list_pages(token):
                path = p.get("path", "")
                title = p.get("title", path) or path
                entries.setdefault(path, title)
        except Exception:
            pass

    lines = [f"- `{path}` — {title}" for path, title in sorted(entries.items())]
    header = "# Índice Wiki RPA4All (início de sessão)\nPáginas disponíveis (local + Wiki.js):\n```\n"
    body = header + "\n".join(lines) + "\n```"
    if len(body) > max_chars:
        body = body[:max_chars] + "\n... [truncado]"
    return body