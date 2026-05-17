from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "hooks" / "wiki_sync.py"
spec = importlib.util.spec_from_file_location("wiki_sync", MODULE_PATH)
wiki_sync = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(wiki_sync)


def test_build_parent_paths_for_nested_path():
    assert wiki_sync.build_parent_paths("docs/tape-archive-paths") == ["docs"]


def test_ensure_tree_paths_creates_missing_nodes(monkeypatch):
    existing = set()
    created = []

    def fake_find_page(_bearer, path, locale="pt"):
        return (path in existing, 1 if path in existing else 0)

    def fake_create_placeholder_page(_bearer, path, locale="pt"):
        created.append(path)
        existing.add(path)
        return {"ok": True, "msg": "", "id": 10, "path": path}

    monkeypatch.setattr(wiki_sync, "find_page", fake_find_page)
    monkeypatch.setattr(wiki_sync, "create_placeholder_page", fake_create_placeholder_page)

    result = wiki_sync.ensure_tree_paths("token", "docs/tape-archive-paths")

    assert result["created"] == ["docs"]
    assert result["failed"] == []
    assert created == ["docs"]


def test_validate_tree_paths_reports_missing_nodes(monkeypatch):
    existing = {"docs"}

    def fake_find_page(_bearer, path, locale="pt"):
        return (path in existing, 1 if path in existing else 0)

    monkeypatch.setattr(wiki_sync, "find_page", fake_find_page)

    result = wiki_sync.validate_tree_paths("token", "docs/tape-archive-paths")

    assert result["ok"] is False
    assert result["missing"] == ["docs/tape-archive-paths"]
