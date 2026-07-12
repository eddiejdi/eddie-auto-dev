"""Testes de política para o hook post-commit.

Garante que a publicação de documentação na wiki ocorre via wiki_sync.py
(publicação automática real), não apenas enfileiramento sem consumidor.
"""

from __future__ import annotations

from pathlib import Path


def test_post_commit_publica_via_wiki_sync() -> None:
    """Post-commit deve invocar wiki_sync.py para publicar na Wiki RPA4All."""
    hook_path = Path(__file__).resolve().parents[2] / ".githooks" / "post-commit"
    content = hook_path.read_text(encoding="utf-8")

    assert "tools/hooks/wiki_sync.py" in content
    assert "wiki-sync" in content
    assert "^\\.claude/" in content


def test_post_commit_nao_enfileira_apenas_ipc() -> None:
    """Post-commit não deve depender só de agent_ipc sem publish."""
    hook_path = Path(__file__).resolve().parents[2] / ".githooks" / "post-commit"
    content = hook_path.read_text(encoding="utf-8")

    assert "tools/agent_ipc.py" not in content