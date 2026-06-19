"""Testes de política para o hook post-commit.

Garante que a publicação de documentação na wiki seja roteada
apenas via agent wiki_rpa4all (sem publish direto).
"""

from __future__ import annotations

from pathlib import Path


def test_post_commit_usa_agent_wiki_sem_publish_direto() -> None:
    """Post-commit deve despachar para agent wiki e não chamar wiki_sync.py."""
    hook_path = Path(__file__).resolve().parents[2] / ".githooks" / "post-commit"
    content = hook_path.read_text(encoding="utf-8")

    assert "tools/agent_ipc.py" in content
    assert "--agent wiki_rpa4all" in content
    assert "tools/hooks/wiki_sync.py" not in content
