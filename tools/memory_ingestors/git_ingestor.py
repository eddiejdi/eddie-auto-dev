#!/usr/bin/env python3
"""
Git post-commit hook — indexa o último commit na memória compartilhada dos agentes.

Instalar:
    cp tools/memory_ingestors/git_ingestor.py .git/hooks/post-commit
    chmod +x .git/hooks/post-commit

Ou via symlink (atualiza automaticamente):
    ln -sf ../../tools/memory_ingestors/git_ingestor.py .git/hooks/post-commit

Funciona silenciosamente — nunca bloqueia o commit em caso de falha.
Env var: CHROMA_DB_PATH (default: /home/homelab/myClaude/chroma_db)
"""
from __future__ import annotations

import os
import subprocess
import sys

# Adiciona raiz do repo ao path para import de tools/
_REPO_ROOT = subprocess.check_output(
    ["git", "rev-parse", "--show-toplevel"], text=True
).strip()
sys.path.insert(0, _REPO_ROOT)


def _git(*args: str) -> str:
    return subprocess.check_output(["git"] + list(args), text=True, stderr=subprocess.DEVNULL).strip()


def _ingest() -> None:
    commit_hash  = _git("rev-parse", "HEAD")
    short_hash   = commit_hash[:8]
    author       = _git("log", "-1", "--format=%an <%ae>")
    date_iso     = _git("log", "-1", "--format=%cI")
    subject      = _git("log", "-1", "--format=%s")
    body         = _git("log", "-1", "--format=%b").strip()
    branch       = _git("rev-parse", "--abbrev-ref", "HEAD")
    files_raw    = _git("diff-tree", "--no-commit-id", "-r", "--name-only", "HEAD")
    files        = [f for f in files_raw.splitlines() if f]

    # Classificação de tipo pelo prefixo convencional do subject
    prefix = subject.split(":")[0].lower().strip() if ":" in subject else ""
    commit_type = prefix if prefix in {"feat", "fix", "chore", "docs", "refactor", "test", "ci"} else "commit"

    # Fato principal: uma linha legível por humanos e pelo buscador semântico
    files_summary = ", ".join(files[:6]) + (f" (+{len(files) - 6})" if len(files) > 6 else "")
    fact = (
        f"[{branch}] {subject} "
        f"(commit {short_hash}, {author}, {date_iso[:10]}"
        + (f") — arquivos: {files_summary}" if files else ")")
    )
    if body:
        fact += f" | Detalhes: {body[:300]}"

    tags = [commit_type, branch]
    if any(kw in subject.lower() for kw in ("trading", "btc", "crypto")):
        tags.append("trading")
    if any(kw in subject.lower() for kw in ("ltfs", "fita", "tape", "lto")):
        tags.append("tape")
    if any(kw in subject.lower() for kw in ("vpn", "proton", "wireguard")):
        tags.append("vpn")
    if any(kw in subject.lower() for kw in ("authentik", "sso", "oauth")):
        tags.append("auth")

    from tools.memory_layer.agent_memory import store
    mem_id = store(
        fact,
        source="git",
        tags=tags,
        agent_id="git-ingestor",
    )
    print(f"[memory] commit indexado → {mem_id} ({fact[:80]}…)")


def main() -> int:
    try:
        _ingest()
    except Exception as exc:
        # Nunca falhar o commit por causa do ingestor
        print(f"[memory] aviso: git_ingestor falhou silenciosamente — {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
