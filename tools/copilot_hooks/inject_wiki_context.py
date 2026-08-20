"""Hook RPA4All — injeta conhecimento/knowledge do wiki (local + Wiki.js) como additionalContext.

Injeta contexto da wiki nos três pontos relevantes:
  - `--mode=session` → início da sessão (SessionStart / before_agent_start): injeta o
    índice completo das páginas (local + remoto via pages.list).
  - `--mode=block`   → cada bloqueio do agente (Stop bloqueado por trabalho incompleto):
    extrai keywords do diff/achados de incompletude e busca no wiki (local + pages.search)
    por conhecimento que ajude o agente a evoluir a atividade.
  - `--mode=tool`    → (uso pontual) busca por keywords do tool input, como no antigo PreToolUse.

Design:
  - Fail-open: qualquer falha retorna {"continue": true} sem context — nunca bloqueia.
  - Detecção de bloqueio (mode=block) reutiliza incomplete_markers (mesma fonte do
    block_incomplete_stop), então só injeta contexto quando o agente está realmente travado.

Configuração via env:
  - RPA4ALL_WIKI_MAX_CHARS   total máx. de contexto (default 6000)
  - RPA4ALL_WIKI_MAX_PAGES   páginas por chamada (default 2)
  - RPA4ALL_WIKI_TTL         cache remoto em segundos (default 60)
  - RPA4ALL_WIKI_MODE        "off" desliga (default "on")
  - RPA4ALL_WIKI_URL         URL GraphQL da Wiki.js
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wiki_search_lib as wsl

MAX_CHARS = int(os.environ.get("RPA4ALL_WIKI_MAX_CHARS", "6000"))
MODE_GLOBAL = os.environ.get("RPA4ALL_WIKI_MODE", "on").strip().lower()


def _load_input() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else {}


def _payload_get(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return default


def _repo_root(payload: dict[str, Any]) -> Path:
    env_root = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if env_root:
        return Path(env_root)
    cwd = _payload_get(payload, "cwd", "project_path", "workspace", default="")
    if isinstance(cwd, str) and cwd and Path(cwd).is_dir():
        return Path(cwd)
    return Path("/workspace/eddie-auto-dev")


def _extract_query_text(payload: dict[str, Any]) -> str:
    """Extrai texto de busca do tool input (mode=tool)."""
    tool_input = _payload_get(payload, "tool_input", "toolInput", "input", default={})
    chunks: list[str] = []

    tool_name = str(_payload_get(payload, "tool_name", "toolName", "tool", default=""))
    if tool_name:
        chunks.append(tool_name.replace("_", " "))

    if isinstance(tool_input, str):
        chunks.append(tool_input)
    elif isinstance(tool_input, dict):
        for key in (
            "command", "cmd", "script", "filePath", "file_path", "path",
            "newString", "content", "new_string", "text", "goal", "query",
            "prompt", "explanation", "description",
        ):
            val = tool_input.get(key)
            if isinstance(val, str) and val:
                chunks.append(val)
    return "\n".join(chunks)


def _block_keywords(root: Path) -> str:
    """Extrai keywords do trabalho incompleto no working tree (modo block).

    Usa o próprio detector de incompletude para só atuar no cenário de bloqueio real:
    paths + reason + snippet dos achados. Ecoa a lógica do block_incomplete_stop.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))
    import incomplete_markers as im

    try:
        import os as _os
        cwd = _os.getcwd()
        if (root / ".git").exists() or (root / ".git").is_file():
            _os.chdir(str(root))
        findings = im.find_incomplete(im.working_tree_diff(), im.read_worktree_file)
        _os.chdir(cwd)
    except Exception:
        return ""

    if not findings:
        return ""

    parts: list[str] = []
    for f in findings:
        parts.append(f.path)
        # Segmentos do path ("trading_agent.py" → trading, agent, py) para a busca
        # casar com títulos/páginas cujo nome usa outra separação.
        for seg in re.split(r"[._/\-]+", f.path):
            if len(seg) >= 3:
                parts.append(seg)
        parts.append(f.reason)
        parts.append(f.snippet)
    return "\n".join(parts)


def _session_context(root: Path, token: str) -> str | None:
    body = wsl.session_index(root, token)
    if not body.strip():
        return None
    return body


def _search_context(query_text: str, root: Path, token: str) -> str | None:
    if not query_text.strip():
        return None
    result = wsl.search_wiki(query_text, root, token, include_remote=bool(token))
    if not result["body"]:
        return None
    return result["body"]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = "block"
    if "--" in argv:
        argv.remove("--")
    for arg in argv:
        if arg.startswith("--mode="):
            mode = arg.split("=", 1)[1]
        elif arg in ("session", "block", "tool"):
            mode = arg

    payload = _load_input()

    if MODE_GLOBAL == "off":
        print(json.dumps({"continue": True}))
        return 0

    root = _repo_root(payload)
    token = wsl.load_wiki_token(root)

    context: str | None = None
    if mode == "session":
        context = _session_context(root, token)
    elif mode == "block":
        keywords = _block_keywords(root)
        if keywords:
            context = _search_context(keywords, root, token)
    else:  # "tool"
        query = _extract_query_text(payload)
        context = _search_context(query, root, token)

    if not context:
        print(json.dumps({"continue": True}))
        return 0

    print(json.dumps({
        "continue": True,
        "additionalContext": context,
        "hookSpecificOutput": {
            "hookEventName": _payload_get(
                payload, "hook_event_name", "hookEventName", default="PreToolUse"
            ),
            "additionalContext": context,
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # fail-open: bug no hook nunca deve travar sessão/stop.
        print(f"[inject_wiki_context] aviso: hook falhou, liberando ({exc})", file=sys.stderr)
        print(json.dumps({"continue": True}))
        raise SystemExit(0)