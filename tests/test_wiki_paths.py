from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from specialized_agents.wiki_paths import canonical_wiki_path


def test_canonical_wiki_path_preserves_docs_root_file() -> None:
    repo_root = Path("/workspace/eddie-auto-dev")
    assert canonical_wiki_path("docs/tape-archive-paths.md", repo_root=repo_root) == "docs/tape-archive-paths"


def test_canonical_wiki_path_routes_incidents_subtree() -> None:
    repo_root = Path("/workspace/eddie-auto-dev")
    path = "docs/INCIDENTS/LTO_SG0_CONCURRENCY_AND_TIMER_RECOVERY_2026-05-21.md"
    assert canonical_wiki_path(path, repo_root=repo_root) == "docs/incidents/lto-sg0-concurrency-and-timer-recovery"


def test_canonical_wiki_path_routes_agents_subtree() -> None:
    repo_root = Path("/workspace/eddie-auto-dev")
    assert canonical_wiki_path("docs/agents/agent_memory.md", repo_root=repo_root) == "docs/agents/agent-memory"


def test_canonical_wiki_path_preserves_nested_docs_subtree() -> None:
    repo_root = Path("/workspace/eddie-auto-dev")
    assert canonical_wiki_path("docs/confluence/pages/OPERATIONS.md", repo_root=repo_root) == "docs/confluence/pages/operations"


def test_canonical_wiki_path_keeps_domain_hints() -> None:
    repo_root = Path("/workspace/eddie-auto-dev")
    assert canonical_wiki_path("LTFS_SELFHEAL_2026-04-26.md", repo_root=repo_root) == "homelab/storage/ltfs/ltfs-selfheal"
