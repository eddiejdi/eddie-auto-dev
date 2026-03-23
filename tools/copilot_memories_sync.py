#!/usr/bin/env python3
"""CLI para sincronizar memórias locais do Copilot com o PostgreSQL do homelab.

Uso:
    # Sync completo (user + repo)
    python tools/copilot_memories_sync.py

    # Apenas repo
    python tools/copilot_memories_sync.py --scope repo

    # Buscar memórias
    python tools/copilot_memories_sync.py --search "grafana"

    # Listar todas
    python tools/copilot_memories_sync.py --list

    # Exportar do DB para arquivos
    python tools/copilot_memories_sync.py --export /tmp/memories_backup
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.copilot_memories import CopilotMemoryStore

# Caminhos das memórias locais do Copilot
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
USER_MEMORIES_DIR = Path.home() / ".config/Code/User/globalStorage/github.copilot-chat/memories"
REPO_MEMORIES_DIR = WORKSPACE_ROOT / ".copilot" / "memories" / "repo"

# Fallback: procurar memórias no padrão do VS Code Copilot
COPILOT_MEMORIES_DIRS = [
    USER_MEMORIES_DIR,
    Path.home() / ".config/Code/User/globalStorage/github.copilot-chat/plan-agent",
]


def find_memory_files(scope: str) -> Path | None:
    """Encontra o diretório de memórias para o scope dado."""
    if scope == "repo":
        # Memórias de repo ficam no workspace
        for candidate in [
            WORKSPACE_ROOT / ".copilot" / "memories" / "repo",
            WORKSPACE_ROOT / ".github" / "copilot-memories",
        ]:
            if candidate.exists():
                return candidate
        return None
    elif scope == "user":
        for candidate in COPILOT_MEMORIES_DIRS:
            if candidate.exists():
                return candidate
        return None
    return None


def do_sync(store: CopilotMemoryStore, scope: str | None = None) -> None:
    """Sincroniza memórias locais para o PostgreSQL."""
    scopes = [scope] if scope else ["user", "repo"]
    total = 0

    for s in scopes:
        mem_dir = find_memory_files(s)
        if mem_dir:
            count = store.sync_from_files(mem_dir, s)
            print(f"  [{s}] Synced {count} memories from {mem_dir}")
            total += count
        else:
            print(f"  [{s}] No local directory found, skipping")

    print(f"\nTotal synced: {total}")


def do_list(store: CopilotMemoryStore, scope: str | None = None) -> None:
    """Lista memórias armazenadas no DB."""
    if scope:
        memories = store.list_by_scope(scope)
    else:
        memories = store.list_all()

    if not memories:
        print("Nenhuma memória encontrada.")
        return

    for mem in memories:
        updated = mem["updated_at"].strftime("%Y-%m-%d %H:%M") if mem.get("updated_at") else "?"
        tags_str = ", ".join(mem.get("tags") or [])
        print(f"  [{mem['scope']}] {mem['key']} (tags: {tags_str}) — updated: {updated}")
        # Primeira linha do conteúdo como preview
        first_line = mem["content"].strip().split("\n")[0][:80]
        print(f"    {first_line}")


def do_search(store: CopilotMemoryStore, query: str, scope: str | None = None) -> None:
    """Busca full-text nas memórias."""
    results = store.search(query, scope=scope)
    if not results:
        print(f"Nenhum resultado para: '{query}'")
        return

    print(f"Encontrados {len(results)} resultado(s):")
    for mem in results:
        print(f"\n  [{mem['scope']}] {mem['key']} (rank: {mem.get('rank', 0):.4f})")
        # Preview do conteúdo
        preview = mem["content"].strip()[:200]
        print(f"    {preview}")


def do_export(store: CopilotMemoryStore, output_dir: str, scope: str | None = None) -> None:
    """Exporta memórias do DB para arquivos."""
    out = Path(output_dir)
    scopes = [scope] if scope else ["user", "repo"]

    for s in scopes:
        scope_dir = out / s
        count = store.export_to_files(scope_dir, s)
        print(f"  [{s}] Exported {count} files to {scope_dir}")


def main() -> None:
    """Ponto de entrada do CLI."""
    parser = argparse.ArgumentParser(
        description="Sync/query Copilot memories com PostgreSQL do homelab"
    )
    parser.add_argument("--scope", choices=["user", "repo", "session"], help="Filtrar por scope")
    parser.add_argument("--search", type=str, help="Busca full-text")
    parser.add_argument("--list", action="store_true", help="Listar memórias")
    parser.add_argument("--export", type=str, help="Exportar para diretório")
    parser.add_argument("--db-url", type=str, help="Override DATABASE_URL")

    args = parser.parse_args()
    store = CopilotMemoryStore(db_url=args.db_url)

    if args.search:
        do_search(store, args.search, scope=args.scope)
    elif args.list:
        do_list(store, scope=args.scope)
    elif args.export:
        do_export(store, args.export, scope=args.scope)
    else:
        do_sync(store, scope=args.scope)


if __name__ == "__main__":
    main()
