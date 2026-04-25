import importlib.util
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "reconcile_ytmusic_playwright.py"
    spec = importlib.util.spec_from_file_location("reconcile_ytmusic_playwright", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    return module


def test_chunk_videoids_basic():
    mod = _load_module()
    vids = [f"id{i}" for i in range(20)]
    batch = mod.chunk_videoids(vids, start=5, batch_size=10)
    assert batch == vids[5:15]


def test_chunk_videoids_edge():
    mod = _load_module()
    vids = ["a", "b", "c"]
    assert mod.chunk_videoids(vids, 0, 2) == ["a", "b"]
    assert mod.chunk_videoids(vids, 2, 5) == ["c"]
