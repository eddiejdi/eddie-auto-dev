from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from specialized_agents.wiki_client import WikiJsClient
from specialized_agents.wiki_refactor import WikiRefactorRequest, WikiRefactorSkill


class FakeWikiClient(WikiJsClient):
    def __init__(self, pages: list[dict], page_details: dict[str, dict]) -> None:
        super().__init__("http://wiki.local/graphql", "token", "pt")
        self.pages = pages
        self.page_details = page_details
        self.updated: list[dict] = []
        self.created: list[dict] = []
        self.archived: list[dict] = []

    def list_pages(self, order_by: str = "TITLE") -> list[dict]:
        return list(self.pages)

    def get_page(self, wiki_path: str, locale: str | None = None) -> dict | None:
        return self.page_details.get(wiki_path)

    def update_page(
        self,
        page_id: int,
        wiki_path: str,
        title: str,
        content: str,
        tags: list[str] | None = None,
        locale: str | None = None,
        description: str = "",
    ) -> dict:
        payload = {
            "id": page_id,
            "path": wiki_path,
            "title": title,
            "content": content,
            "updatedAt": "2026-05-21T12:00:00Z",
        }
        self.updated.append(payload)
        self.page_details[wiki_path] = payload
        return {"id": page_id, "path": wiki_path, "updatedAt": payload["updatedAt"]}

    def create_page(
        self,
        wiki_path: str,
        title: str,
        content: str,
        tags: list[str] | None = None,
        locale: str | None = None,
        description: str = "",
    ) -> dict:
        page_id = 900 + len(self.created)
        payload = {"id": page_id, "path": wiki_path, "title": title, "content": content}
        self.created.append(payload)
        self.page_details[wiki_path] = payload
        return {"id": page_id, "path": wiki_path}

    def archive_page(
        self,
        page_id: int,
        archive_path: str,
        archived_title: str,
        content: str,
        locale: str | None = None,
        description: str = "",
    ) -> dict:
        payload = {"id": page_id, "path": archive_path, "title": archived_title, "content": content}
        self.archived.append(payload)
        self.page_details[archive_path] = payload
        return {"id": page_id, "path": archive_path}


def _build_skill(tmp_path: Path) -> tuple[WikiRefactorSkill, FakeWikiClient]:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "tape-archive-paths.md").write_text(
        "# Sistema de Gerenciamento de Fitas LTO-6\n\nConteúdo canônico.\n",
        encoding="utf-8",
    )
    (docs_dir / "INCIDENTS").mkdir(parents=True, exist_ok=True)
    (docs_dir / "INCIDENTS" / "LTO_SG0_CONCURRENCY_AND_TIMER_RECOVERY_2026-05-21.md").write_text(
        "# Incidente SG0\n\nIncidente canônico.\n",
        encoding="utf-8",
    )

    pages = [
        {"id": 630, "path": "docs/tape-archive-paths", "title": "Sistema de Gerenciamento de Fitas LTO-6 — Documentação Técnica", "locale": "pt", "updatedAt": "2026-05-21T10:00:00Z"},
        {"id": 573, "path": "docs/docs/tape-archive-paths", "title": "Tape Archive Paths", "locale": "pt", "updatedAt": "2026-05-19T10:00:00Z"},
        {"id": 631, "path": "home", "title": "RPA4All Wiki", "locale": "pt", "updatedAt": "2026-05-21T09:00:00Z"},
        {"id": 592, "path": "docs", "title": "Docs", "locale": "pt", "updatedAt": "2026-05-20T10:00:00Z"},
    ]
    details = {
        "docs/tape-archive-paths": {
            "id": 630,
            "path": "docs/tape-archive-paths",
            "title": "Sistema de Gerenciamento de Fitas LTO-6 — Documentação Técnica",
            "content": "# Sistema de Gerenciamento de Fitas LTO-6\n\nConteúdo canônico vivo.\n",
        },
        "docs/docs/tape-archive-paths": {
            "id": 573,
            "path": "docs/docs/tape-archive-paths",
            "title": "Tape Archive Paths",
            "content": "# Tape Archive Paths\n\nInformação adicional da duplicata.\n",
        },
        "home": {
            "id": 631,
            "path": "home",
            "title": "RPA4All Wiki",
            "content": "# Home\n",
        },
        "docs": {
            "id": 592,
            "path": "docs",
            "title": "Docs",
            "content": "# Docs\n",
        },
    }
    client = FakeWikiClient(pages=pages, page_details=details)
    skill = WikiRefactorSkill(client, repo_root=tmp_path)
    return skill, client


@pytest.mark.asyncio
async def test_refactor_audit_returns_plan_without_mutation(tmp_path: Path) -> None:
    skill, client = _build_skill(tmp_path)
    response = await skill.run(WikiRefactorRequest(mode="audit"))

    assert response.ok is True
    assert response.mode == "audit"
    assert response.inventory_summary["duplicate_clusters"] >= 1
    assert any(cluster["canonical"]["target_path"] == "docs/tape-archive-paths" for cluster in response.duplicate_clusters)
    assert client.updated == []
    assert client.created == []
    assert client.archived == []


@pytest.mark.asyncio
async def test_refactor_apply_updates_canonical_and_archives_duplicate(tmp_path: Path) -> None:
    skill, client = _build_skill(tmp_path)
    skill._gpu_availability = AsyncMock(return_value={"GPU0": False, "GPU1": False})  # type: ignore[method-assign]

    response = await skill.run(WikiRefactorRequest(mode="apply"))

    assert response.mode == "apply"
    assert any(item["to_path"] == "docs/tape-archive-paths" for item in response.updated_pages)
    assert any(item["to_path"].startswith("archive/wiki-refactor/") for item in response.archived_pages)
    assert any(item["path"] == "home" for item in response.updated_indexes)
    assert any("GPU0 indisponível" in warning or "merge por GPU0 falhou" in warning for warning in response.warnings)


@pytest.mark.asyncio
async def test_refactor_does_not_bridge_unrelated_readmes(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "tape-component-quality-page.md").write_text(
        "# Tape Component Quality Page\n\nConteúdo canônico.\n",
        encoding="utf-8",
    )

    pages = [
        {"id": 612, "path": "docs/tape-component-quality-page", "title": "Tape Component Quality Page", "locale": "pt", "updatedAt": "2026-05-21T10:00:00Z"},
        {"id": 546, "path": "docs/tape-component-quality-page/readme", "title": "Tape Component Quality Page", "locale": "pt", "updatedAt": "2026-05-21T10:01:00Z"},
        {"id": 161, "path": "docs/blueprism/readme", "title": "Blue Prism - Excel to Web Input Automation", "locale": "pt", "updatedAt": "2026-05-19T10:00:00Z"},
        {"id": 220, "path": "docs/docs/readme", "title": "README", "locale": "pt", "updatedAt": "2026-05-18T10:00:00Z"},
    ]
    details = {
        "docs/tape-component-quality-page": {
            "id": 612,
            "path": "docs/tape-component-quality-page",
            "title": "Tape Component Quality Page",
            "content": "# Tape Component Quality Page\n\nConteúdo canônico vivo.\n",
        },
        "docs/tape-component-quality-page/readme": {
            "id": 546,
            "path": "docs/tape-component-quality-page/readme",
            "title": "Tape Component Quality Page",
            "content": "# Tape Component Quality Page\n\nDuplicata local.\n",
        },
        "docs/blueprism/readme": {
            "id": 161,
            "path": "docs/blueprism/readme",
            "title": "Blue Prism - Excel to Web Input Automation",
            "content": "# Blue Prism\n",
        },
        "docs/docs/readme": {
            "id": 220,
            "path": "docs/docs/readme",
            "title": "README",
            "content": "# README\n",
        },
    }
    client = FakeWikiClient(pages=pages, page_details=details)
    skill = WikiRefactorSkill(client, repo_root=tmp_path)

    response = await skill.run(
        WikiRefactorRequest(
            mode="audit",
            repo_globs=["docs/tape-component-quality-page.md"],
            rebuild_indexes=False,
        )
    )

    assert response.duplicate_clusters == []


@pytest.mark.asyncio
async def test_refactor_only_links_readme_to_placeholder_parent(tmp_path: Path) -> None:
    pages = [
        {"id": 603, "path": "docs/docs", "title": "Docs", "locale": "pt", "updatedAt": "2026-05-21T10:00:00Z"},
        {"id": 220, "path": "docs/docs/readme", "title": "README", "locale": "pt", "updatedAt": "2026-05-18T10:00:00Z"},
        {"id": 415, "path": "docs/docs/index", "title": "Indice Completo", "locale": "pt", "updatedAt": "2026-05-18T11:00:00Z"},
    ]
    details = {
        "docs/docs": {
            "id": 603,
            "path": "docs/docs",
            "title": "Docs",
            "content": "# Docs\n\n## Navegação\n\n- [docs/docs/index](/pt/docs/docs/index)\n",
        },
        "docs/docs/readme": {
            "id": 220,
            "path": "docs/docs/readme",
            "title": "README",
            "content": "# README\n",
        },
        "docs/docs/index": {
            "id": 415,
            "path": "docs/docs/index",
            "title": "Indice Completo",
            "content": "# Índice\n",
        },
    }
    client = FakeWikiClient(pages=pages, page_details=details)
    skill = WikiRefactorSkill(client, repo_root=tmp_path)

    response = await skill.run(WikiRefactorRequest(mode="audit", rebuild_indexes=False))

    assert len(response.duplicate_clusters) == 1
    cluster = response.duplicate_clusters[0]
    assert cluster["canonical"]["target_path"] == "docs/docs"
    assert [dup["path"] for dup in cluster["duplicates"]] == ["docs/docs/index", "docs/docs/readme"]
