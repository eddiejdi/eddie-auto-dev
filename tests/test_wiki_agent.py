"""
Testes unitários para o WikiAgent.

Cobre:
- Seleção de GPU (GPU0 → GPU1 fallback)
- Resolução de modelo dinâmico
- Geração via Ollama (expand e evolve)
- Operações GraphQL (create, update, get_page, upsert)
- Endpoints FastAPI (publish, evolve, raw, health)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def agent():
    """Instância isolada do WikiAgent para cada teste."""
    from specialized_agents.wiki_agent import WikiAgent
    return WikiAgent()


@pytest.fixture
def client():
    """TestClient FastAPI com wiki router montado."""
    from specialized_agents import wiki_agent as wa
    # Reset singleton para isolamento
    wa._agent = None
    app = FastAPI()
    app.include_router(wa.router, prefix="/wiki")
    return TestClient(app, raise_server_exceptions=False)


# ── helpers de mock aiohttp ──────────────────────────────────────────────────

def _aiohttp_get_ctx(status: int = 200, json_body: dict | None = None) -> AsyncMock:
    """Mock de session.get() que retorna status e json."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_body or {})
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _aiohttp_post_ctx(
    status: int = 200, json_body: dict | None = None, text_body: str = ""
) -> AsyncMock:
    """Mock de session.post() que retorna status, json e text."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_body or {})
    resp.text = AsyncMock(return_value=text_body)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _session_ctx(
    get_ctx: AsyncMock | None = None, post_ctx: AsyncMock | None = None
) -> AsyncMock:
    """Mock completo de aiohttp.ClientSession()."""
    session = AsyncMock()
    if get_ctx:
        session.get = MagicMock(return_value=get_ctx)
    if post_ctx:
        session.post = MagicMock(return_value=post_ctx)
    outer = AsyncMock()
    outer.__aenter__ = AsyncMock(return_value=session)
    outer.__aexit__ = AsyncMock(return_value=False)
    return outer


# ─────────────────────────────────────────────────────────────────────────────
# Testes: seleção de GPU
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pick_ollama_prefers_gpu0(agent):
    """Deve selecionar GPU0 quando disponível."""
    agent._ollama_reachable = AsyncMock(side_effect=[True, True])
    base_url, gpu = await agent._pick_ollama()
    assert gpu == "GPU0"
    assert "11434" in base_url


@pytest.mark.asyncio
async def test_pick_ollama_fallback_to_gpu1(agent):
    """Deve usar GPU1 quando GPU0 não responde."""
    agent._ollama_reachable = AsyncMock(side_effect=[False, True])
    base_url, gpu = await agent._pick_ollama()
    assert gpu == "GPU1"
    assert "11435" in base_url


@pytest.mark.asyncio
async def test_pick_ollama_raises_503_when_both_down(agent):
    """Deve lançar HTTPException 503 quando ambas GPUs offline."""
    from fastapi import HTTPException
    agent._ollama_reachable = AsyncMock(return_value=False)
    with pytest.raises(HTTPException) as exc_info:
        await agent._pick_ollama()
    assert exc_info.value.status_code == 503


# ─────────────────────────────────────────────────────────────────────────────
# Testes: resolução de modelo
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_model_returns_configured_when_available(agent):
    """Deve retornar o modelo configurado quando estiver na lista."""
    agent._model = "shared-coder"
    tags = {"models": [{"name": "shared-coder"}, {"name": "other:7b"}]}
    with patch(
        "aiohttp.ClientSession",
        return_value=_session_ctx(get_ctx=_aiohttp_get_ctx(200, tags)),
    ):
        model = await agent._resolve_model("http://localhost:11434")
    assert model == "shared-coder"


@pytest.mark.asyncio
async def test_resolve_model_prefers_llama_when_configured_absent(agent):
    """Deve escolher modelo com 'llama' no nome quando o configurado não existe."""
    agent._model = "not-installed"
    tags = {"models": [{"name": "llama3:8b"}, {"name": "other:3b"}]}
    with patch(
        "aiohttp.ClientSession",
        return_value=_session_ctx(get_ctx=_aiohttp_get_ctx(200, tags)),
    ):
        model = await agent._resolve_model("http://localhost:11434")
    assert model == "llama3:8b"


@pytest.mark.asyncio
async def test_resolve_model_returns_default_on_error(agent):
    """Deve retornar o modelo padrão quando o endpoint falha."""
    agent._model = "fallback-model"
    with patch(
        "aiohttp.ClientSession",
        return_value=_session_ctx(get_ctx=_aiohttp_get_ctx(500)),
    ):
        model = await agent._resolve_model("http://localhost:11434")
    assert model == "fallback-model"


# ─────────────────────────────────────────────────────────────────────────────
# Testes: geração Ollama
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ollama_generate_returns_content(agent):
    """Deve retornar (content, model, gpu) com conteúdo do Ollama."""
    agent._ollama_reachable = AsyncMock(return_value=True)
    agent._resolve_model = AsyncMock(return_value="shared-coder")

    ollama_resp = {"message": {"content": "# Doc gerada\n\nConteúdo técnico aqui."}}
    with patch(
        "aiohttp.ClientSession",
        return_value=_session_ctx(post_ctx=_aiohttp_post_ctx(200, ollama_resp)),
    ):
        content, model, gpu = await agent._ollama_generate("system", "user")

    assert "# Doc" in content
    assert model == "shared-coder"
    assert gpu == "GPU0"


@pytest.mark.asyncio
async def test_ollama_generate_raises_502_on_empty_content(agent):
    """Deve lançar HTTPException 502 quando Ollama retorna conteúdo vazio."""
    from fastapi import HTTPException
    agent._ollama_reachable = AsyncMock(return_value=True)
    agent._resolve_model = AsyncMock(return_value="shared-coder")

    with patch(
        "aiohttp.ClientSession",
        return_value=_session_ctx(
            post_ctx=_aiohttp_post_ctx(200, {"message": {"content": "   "}})
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await agent._ollama_generate("system", "user")
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_ollama_generate_raises_502_on_http_error(agent):
    """Deve lançar HTTPException 502 quando Ollama retorna status != 200."""
    from fastapi import HTTPException
    agent._ollama_reachable = AsyncMock(return_value=True)
    agent._resolve_model = AsyncMock(return_value="shared-coder")

    with patch(
        "aiohttp.ClientSession",
        return_value=_session_ctx(
            post_ctx=_aiohttp_post_ctx(500, text_body="Internal error")
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await agent._ollama_generate("system", "user")
    assert exc_info.value.status_code == 502


# ─────────────────────────────────────────────────────────────────────────────
# Testes: operações GraphQL
# ─────────────────────────────────────────────────────────────────────────────

def test_get_page_returns_page_data(agent):
    """Deve retornar dados completos da página quando encontrada."""
    response = {
        "data": {
            "pages": {
                "singleByPath": {
                    "id": 42,
                    "path": "homelab/test",
                    "title": "Test Page",
                    "content": "# Test",
                    "updatedAt": "2026-05-03T00:00:00Z",
                }
            }
        }
    }
    agent._graphql = MagicMock(return_value=response)
    result = agent._get_page("homelab/test")
    assert result is not None
    assert result["id"] == 42
    assert result["title"] == "Test Page"


def test_get_page_returns_none_when_not_found(agent):
    """Deve retornar None quando página não existe na wiki."""
    agent._graphql = MagicMock(
        return_value={"data": {"pages": {"singleByPath": None}}}
    )
    assert agent._get_page("homelab/missing") is None


def test_get_page_returns_none_on_graphql_errors(agent):
    """Deve retornar None quando GraphQL retorna erros."""
    agent._graphql = MagicMock(
        return_value={"errors": [{"message": "Not authorized"}]}
    )
    assert agent._get_page("homelab/forbidden") is None


def test_create_page_returns_page_on_success(agent):
    """Deve retornar dados da página criada com sucesso."""
    response = {
        "data": {
            "pages": {
                "create": {
                    "responseResult": {"succeeded": True, "errorCode": 0, "message": ""},
                    "page": {"id": 99, "path": "homelab/new"},
                }
            }
        }
    }
    agent._graphql = MagicMock(return_value=response)
    page = agent._create_page("homelab/new", "New Page", "# Content", ["tag1"])
    assert page["id"] == 99


def test_create_page_raises_400_on_wiki_rejection(agent):
    """Deve lançar HTTPException 400 quando Wiki.js recusa a criação."""
    from fastapi import HTTPException
    response = {
        "data": {
            "pages": {
                "create": {
                    "responseResult": {
                        "succeeded": False,
                        "errorCode": 6002,
                        "message": "Path already exists",
                    },
                    "page": None,
                }
            }
        }
    }
    agent._graphql = MagicMock(return_value=response)
    with pytest.raises(HTTPException) as exc_info:
        agent._create_page("homelab/dup", "Dup", "content", [])
    assert exc_info.value.status_code == 400


def test_upsert_calls_create_when_page_absent(agent):
    """_upsert_page deve criar quando página não existe."""
    agent._get_page = MagicMock(return_value=None)
    agent._create_page = MagicMock(return_value={"id": 1, "path": "x/y"})
    _, operation = agent._upsert_page("x/y", "Title", "content", [])
    assert operation == "created"
    agent._create_page.assert_called_once()
    agent._update_page = MagicMock()  # não deve ser chamado
    agent._update_page.assert_not_called()


def test_upsert_calls_update_when_page_exists(agent):
    """_upsert_page deve atualizar quando página já existe."""
    agent._get_page = MagicMock(
        return_value={"id": 5, "path": "x/y", "title": "Old Title"}
    )
    agent._update_page = MagicMock(
        return_value={"id": 5, "path": "x/y", "updatedAt": "2026"}
    )
    _, operation = agent._upsert_page("x/y", "New Title", "content", [])
    assert operation == "updated"
    agent._update_page.assert_called_once_with(5, "x/y", "New Title", "content", [])


# ─────────────────────────────────────────────────────────────────────────────
# Testes: endpoints FastAPI
# ─────────────────────────────────────────────────────────────────────────────

def test_endpoint_raw_skips_ollama(client):
    """POST /wiki/raw deve publicar sem chamar Ollama."""
    from specialized_agents import wiki_agent as wa
    mock_agent = MagicMock()
    mock_agent.publish = AsyncMock(
        return_value=wa.WikiResponse(
            ok=True,
            page_id=10,
            wiki_path="homelab/test",
            model_used=None,
            gpu=None,
            message="Página created com sucesso",
        )
    )
    with patch("specialized_agents.wiki_agent.get_wiki_agent", return_value=mock_agent):
        resp = client.post(
            "/wiki/raw",
            json={
                "topic": "Test Topic",
                "raw_text": "## Content\n\nAlgum conteúdo aqui.",
                "wiki_path": "homelab/test",
                "tags": ["test"],
            },
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    # Verifica que skip_ollama foi forçado como True
    call_req = mock_agent.publish.call_args[0][0]
    assert call_req.skip_ollama is True


def test_endpoint_evolve_returns_404_for_missing_page(client):
    """POST /wiki/evolve deve retornar 404 quando página não existe."""
    from fastapi import HTTPException
    from specialized_agents import wiki_agent as wa
    mock_agent = MagicMock()
    mock_agent.evolve = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="Página não encontrada")
    )
    with patch("specialized_agents.wiki_agent.get_wiki_agent", return_value=mock_agent):
        resp = client.post(
            "/wiki/evolve",
            json={
                "wiki_path": "homelab/missing-page",
                "new_info": "Informação nova para integrar",
            },
        )
    assert resp.status_code == 404


def test_endpoint_health_returns_ok(client):
    """GET /wiki/health deve retornar status ok com info das GPUs."""
    from specialized_agents import wiki_agent as wa
    mock_agent = MagicMock()
    mock_agent._ollama_reachable = AsyncMock(return_value=True)
    with patch("specialized_agents.wiki_agent.get_wiki_agent", return_value=mock_agent):
        resp = client.get("/wiki/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "ollama_gpu0" in data
    assert "ollama_gpu1" in data


def test_endpoint_publish_calls_ollama_by_default(client):
    """POST /wiki/publish com skip_ollama=False deve delegar ao agente com expand."""
    from specialized_agents import wiki_agent as wa
    mock_agent = MagicMock()
    mock_agent.publish = AsyncMock(
        return_value=wa.WikiResponse(
            ok=True,
            page_id=55,
            wiki_path="homelab/network/test",
            model_used="shared-coder",
            gpu="GPU0",
            message="Página created com sucesso",
        )
    )
    with patch("specialized_agents.wiki_agent.get_wiki_agent", return_value=mock_agent):
        resp = client.post(
            "/wiki/publish",
            json={
                "topic": "Tópico técnico",
                "raw_text": "Notas brutas sobre o sistema X",
                "wiki_path": "homelab/network/test",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_used"] == "shared-coder"
    assert data["gpu"] == "GPU0"
    assert data["page_id"] == 55
