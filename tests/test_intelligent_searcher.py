"""Testes unitarios para tools/intelligent_searcher.py."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
MODULE_PATH = TOOLS_DIR / "intelligent_searcher.py"
sys.path.insert(0, str(TOOLS_DIR))

_SPEC = importlib.util.spec_from_file_location("intelligent_searcher", MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
mod = importlib.util.module_from_spec(_SPEC)
sys.modules["intelligent_searcher"] = mod
_SPEC.loader.exec_module(mod)


def test_analyze_request_usa_json_da_gpu1() -> None:
    """Deve aproveitar JSON valido retornado pela GPU1."""
    searcher = mod.IntelligentSearcher()

    async def fake_generate(**_: object) -> dict[str, object]:
        return {
            "response": '{"intent":"search_docs","keywords":["laudo","cid"],"file_types":["pdf"],"priority":"high"}'
        }

    searcher._ollama_generate = fake_generate  # type: ignore[method-assign]
    result = asyncio.run(searcher._analyze_request_with_gpu1("busque laudo medico"))

    assert result["intent"] == "search_docs"
    assert result["keywords"] == ["laudo", "cid"]


def test_analyze_request_fallback_quando_json_invalido() -> None:
    """Quando a GPU1 nao retornar JSON valido, fallback deve ser aplicado."""
    searcher = mod.IntelligentSearcher()

    async def fake_generate(**_: object) -> dict[str, object]:
        return {"response": "texto nao estruturado"}

    searcher._ollama_generate = fake_generate  # type: ignore[method-assign]
    result = asyncio.run(searcher._analyze_request_with_gpu1("quero meu atestado medico"))

    assert result["intent"] == "document_search"
    assert "atestado" in result["keywords"]


def test_find_candidates_pontua_por_keywords(tmp_path: Path) -> None:
    """Arquivos com keywords no nome devem vir primeiro."""
    target = tmp_path / "laudo_medico_pcd.pdf"
    other = tmp_path / "arquivo_generico.txt"
    target.write_text("x", encoding="utf-8")
    other.write_text("y", encoding="utf-8")

    searcher = mod.IntelligentSearcher()
    results = asyncio.run(searcher._find_candidates(tmp_path, ["laudo", "medico"], limit=5))

    assert results
    assert results[0][0].name == "laudo_medico_pcd.pdf"
    assert results[0][1] > results[-1][1]


def test_interpret_content_text_file(tmp_path: Path) -> None:
    """Arquivo textual deve ser retornado sem uso de visao."""
    fpath = tmp_path / "info.txt"
    fpath.write_text("conteudo de teste", encoding="utf-8")

    searcher = mod.IntelligentSearcher()
    result = asyncio.run(searcher._interpret_content_with_gpu0(fpath))

    assert "conteudo de teste" in result


def test_interpret_content_image_usa_vision_gpu0(tmp_path: Path) -> None:
    """Imagem deve chamar pipeline de visao/OCR na GPU0."""
    image_path = tmp_path / "laudo.jpg"
    image_path.write_bytes(b"fake-image")
    searcher = mod.IntelligentSearcher()

    async def fake_vision(path: Path) -> str:
        assert path == image_path
        return "OCR: CID M21.7"

    searcher._vision_summary = fake_vision  # type: ignore[method-assign]
    result = asyncio.run(searcher._interpret_content_with_gpu0(image_path))

    assert result == "OCR: CID M21.7"


def test_search_pipeline_completo(tmp_path: Path) -> None:
    """Pipeline completo deve retornar resultados estruturados."""
    doc_path = tmp_path / "laudo_medico_1.jpg"
    doc_path.write_bytes(b"img")
    searcher = mod.IntelligentSearcher()

    async def fake_analyze(_: str) -> dict[str, object]:
        return {
            "intent": "search_docs",
            "keywords": ["laudo", "medico"],
            "file_types": ["jpg"],
            "priority": "high",
        }

    async def fake_interpret(_: Path) -> str:
        return "conteudo interpretado"

    searcher._analyze_request_with_gpu1 = fake_analyze  # type: ignore[method-assign]
    searcher._interpret_content_with_gpu0 = fake_interpret  # type: ignore[method-assign]
    result = asyncio.run(searcher.search("buscar laudo", tmp_path, limit=5))

    assert result["keywords"] == ["laudo", "medico"]
    assert result["results"]
    assert result["results"][0]["summary"] == "conteudo interpretado"
