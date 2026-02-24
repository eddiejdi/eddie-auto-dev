"""
Testes para o OpenSearch Agent.
Testa funcionalidades de conexão, indexação, busca e RAG.
"""
import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Marcar testes que requerem OpenSearch rodando
pytestmark = [pytest.mark.external]


@pytest.fixture
def mock_httpx_client():
    """Mock para httpx.AsyncClient."""
    with patch("specialized_agents.opensearch_agent.httpx.AsyncClient") as mock:
        instance = AsyncMock()
        mock.return_value = instance
        yield instance


@pytest.fixture
def agent():
    """Cria uma instância do agente para testes unitários."""
    from specialized_agents.opensearch_agent import OpenSearchAgent

    a = OpenSearchAgent(
        host="localhost",
        port=9200,
        user="admin",
        password="test",
        use_ssl=False,
    )
    return a


class TestOpenSearchAgentUnit:
    """Testes unitários (sem dependência de OpenSearch rodando)."""

    def test_agent_creation(self, agent):
        """Testa criação do agente."""
        assert agent.host == "localhost"
        assert agent.port == 9200
        assert agent.base_url == "http://localhost:9200"
        assert agent.scheme == "http"

    def test_agent_creation_ssl(self):
        """Testa criação com SSL."""
        from specialized_agents.opensearch_agent import OpenSearchAgent

        a = OpenSearchAgent(host="secure.host", use_ssl=True)
        assert a.scheme == "https"
        assert a.base_url == "https://secure.host:9200"

    def test_metrics_initial(self, agent):
        """Testa métricas iniciais."""
        m = agent.get_metrics()
        assert m["requests_total"] == 0
        assert m["index_operations"] == 0
        assert m["search_operations"] == 0
        assert m["errors_total"] == 0
        assert "timestamp" in m

    def test_chunk_text_short(self, agent):
        """Testa chunking de texto curto."""
        chunks = agent._chunk_text("hello world", 1500, 300)
        assert len(chunks) == 1
        assert chunks[0] == "hello world"

    def test_chunk_text_long(self, agent):
        """Testa chunking de texto longo."""
        text = "a" * 3000
        chunks = agent._chunk_text(text, 1500, 300)
        assert len(chunks) >= 2
        assert len(chunks[0]) == 1500

    def test_chunk_text_overlap(self, agent):
        """Testa que overlap funciona."""
        text = "a" * 2000
        chunks = agent._chunk_text(text, 1000, 200)
        assert len(chunks) >= 2
        # Com overlap de 200, o segundo chunk começa 800 chars depois
        assert len(chunks) == 3  # 0-1000, 800-1800, 1600-2000

    def test_singleton(self):
        """Testa pattern singleton."""
        from specialized_agents.opensearch_agent import get_opensearch_agent

        import specialized_agents.opensearch_agent as mod
        mod._opensearch_agent = None  # Reset singleton

        a1 = get_opensearch_agent()
        a2 = get_opensearch_agent()
        assert a1 is a2

        mod._opensearch_agent = None  # Cleanup


class TestOpenSearchAgentHealth:
    """Testes de health check (mockados)."""

    @pytest.mark.asyncio
    async def test_health_success(self, agent):
        """Testa health check com sucesso."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "cluster_name": "eddie-cluster",
            "status": "green",
            "number_of_nodes": 1,
            "active_shards": 5,
            "unassigned_shards": 0,
        }
        mock_response.raise_for_status = MagicMock()
        agent._client.get = AsyncMock(return_value=mock_response)

        result = await agent.health()
        assert result["connected"] is True
        assert result["status"] == "green"
        assert result["cluster_name"] == "eddie-cluster"

    @pytest.mark.asyncio
    async def test_health_failure(self, agent):
        """Testa health check quando cluster está fora."""
        agent._client.get = AsyncMock(side_effect=Exception("Connection refused"))

        result = await agent.health()
        assert result["connected"] is False
        assert result["status"] == "unreachable"
        assert "error" in result


class TestOpenSearchAgentIndexing:
    """Testes de indexação (mockados)."""

    @pytest.mark.asyncio
    async def test_index_document(self, agent):
        """Testa indexação de documento."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"_id": "test1", "result": "created"}
        mock_response.raise_for_status = MagicMock()
        agent._client.put = AsyncMock(return_value=mock_response)

        result = await agent.index_document("test-index", {"key": "value"}, doc_id="test1")
        assert result["_id"] == "test1"
        assert agent._metrics["index_operations"] == 1

    @pytest.mark.asyncio
    async def test_index_code(self, agent):
        """Testa indexação de código."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"_id": "abc123", "result": "created"}
        mock_response.raise_for_status = MagicMock()
        agent._client.put = AsyncMock(return_value=mock_response)

        result = await agent.index_code(
            code="print('hello')",
            language="python",
            filename="hello.py",
            agent="test_agent",
        )
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_index_log(self, agent):
        """Testa indexação de log."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"_id": "log1", "result": "created"}
        mock_response.raise_for_status = MagicMock()
        agent._client.post = AsyncMock(return_value=mock_response)

        result = await agent.index_log(
            message="Test log message",
            level="INFO",
            service="test-service",
            agent="test_agent",
        )
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_bulk_index(self, agent):
        """Testa indexação em bulk."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"took": 10, "errors": False, "items": [{}]}
        mock_response.raise_for_status = MagicMock()
        agent._client.post = AsyncMock(return_value=mock_response)

        result = await agent.bulk_index(
            "test-index",
            [{"field": "value1"}, {"field": "value2"}],
        )
        assert result["errors"] is False
        assert result["items_count"] == 1


class TestOpenSearchAgentSearch:
    """Testes de busca (mockados)."""

    @pytest.mark.asyncio
    async def test_search_code(self, agent):
        """Testa busca de código."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "took": 5,
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_id": "1",
                        "_score": 1.5,
                        "_source": {
                            "language": "python",
                            "filename": "main.py",
                            "filepath": "src/main.py",
                            "description": "Main module",
                            "lines": 50,
                            "agent": "python_agent",
                        },
                    }
                ],
            },
        }
        mock_response.raise_for_status = MagicMock()
        agent._client.post = AsyncMock(return_value=mock_response)

        result = await agent.search_code("FastAPI", language="python")
        assert result["total"] == 1
        assert len(result["hits"]) == 1
        assert result["hits"][0]["language"] == "python"

    @pytest.mark.asyncio
    async def test_search_logs(self, agent):
        """Testa busca de logs."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "took": 3,
            "hits": {"total": {"value": 0}, "hits": []},
        }
        mock_response.raise_for_status = MagicMock()
        agent._client.post = AsyncMock(return_value=mock_response)

        result = await agent.search_logs(query_text="error", level="ERROR")
        assert result["total"] == 0


class TestOpenSearchEmbeddings:
    """Testes de embeddings (mockados)."""

    @pytest.mark.asyncio
    async def test_generate_embedding(self, agent):
        """Testa geração de embedding."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "embeddings": [[0.1, 0.2, 0.3, 0.4, 0.5]]
        }
        mock_response.raise_for_status = MagicMock()
        agent._ollama.post = AsyncMock(return_value=mock_response)

        result = await agent.generate_embedding("test text")
        assert len(result) == 5
        assert result[0] == 0.1

    @pytest.mark.asyncio
    async def test_generate_embedding_failure(self, agent):
        """Testa falha na geração de embedding."""
        agent._ollama.post = AsyncMock(side_effect=Exception("Ollama down"))

        result = await agent.generate_embedding("test text")
        assert result == []
        assert agent._metrics["errors_total"] >= 1


class TestOpenSearchRAG:
    """Testes do pipeline RAG (mockados)."""

    @pytest.mark.asyncio
    async def test_semantic_search(self, agent):
        """Testa busca semântica."""
        # Mock embedding
        mock_embed_resp = AsyncMock()
        mock_embed_resp.json.return_value = {"embeddings": [[0.1] * 768]}
        mock_embed_resp.raise_for_status = MagicMock()
        agent._ollama.post = AsyncMock(return_value=mock_embed_resp)

        # Mock search
        mock_search_resp = AsyncMock()
        mock_search_resp.json.return_value = {
            "took": 10,
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_id": "v1",
                        "_score": 0.95,
                        "_source": {
                            "text": "OpenSearch é incrível",
                            "language": "python",
                            "source": "docs",
                            "metadata": {},
                        },
                    }
                ],
            },
        }
        mock_search_resp.raise_for_status = MagicMock()
        agent._client.post = AsyncMock(return_value=mock_search_resp)

        result = await agent.semantic_search("O que é OpenSearch?")
        assert result["total"] == 1
        assert result["hits"][0]["text"] == "OpenSearch é incrível"

    @pytest.mark.asyncio
    async def test_rag_query(self, agent):
        """Testa pipeline RAG completo."""
        # Mock embedding
        mock_embed_resp = AsyncMock()
        mock_embed_resp.json.return_value = {"embeddings": [[0.1] * 768]}
        mock_embed_resp.raise_for_status = MagicMock()

        # Mock LLM response
        mock_llm_resp = AsyncMock()
        mock_llm_resp.json.return_value = {
            "message": {"content": "OpenSearch é um motor de busca open-source."}
        }
        mock_llm_resp.raise_for_status = MagicMock()

        # Configure ollama mock para diferentes chamadas
        async def ollama_side_effect(*args, **kwargs):
            json_data = kwargs.get("json", {})
            if "input" in json_data:
                return mock_embed_resp
            return mock_llm_resp

        agent._ollama.post = AsyncMock(side_effect=ollama_side_effect)

        # Mock OpenSearch search
        mock_search_resp = AsyncMock()
        mock_search_resp.json.return_value = {
            "took": 10,
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_id": "v1",
                        "_score": 0.9,
                        "_source": {
                            "text": "OpenSearch é um fork do Elasticsearch mantido pela Linux Foundation.",
                            "language": "",
                            "source": "docs",
                            "metadata": {},
                        },
                    }
                ],
            },
        }
        mock_search_resp.raise_for_status = MagicMock()
        agent._client.post = AsyncMock(return_value=mock_search_resp)

        result = await agent.rag_query("O que é OpenSearch?")
        assert "answer" in result
        assert "sources" in result
        assert result["question"] == "O que é OpenSearch?"


class TestOpenSearchRoutes:
    """Testes das rotas FastAPI."""

    @pytest.fixture
    def test_client(self):
        """Cria client de teste FastAPI."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from specialized_agents.opensearch_routes import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_health_endpoint(self, test_client):
        """Testa endpoint /opensearch/health."""
        with patch("specialized_agents.opensearch_routes._get_agent") as mock_get:
            mock_agent = AsyncMock()
            mock_agent.health.return_value = {"status": "green", "connected": True}
            mock_get.return_value = mock_agent

            resp = test_client.get("/opensearch/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is True

    def test_metrics_endpoint(self, test_client):
        """Testa endpoint /opensearch/metrics."""
        with patch("specialized_agents.opensearch_routes._get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.get_metrics.return_value = {
                "requests_total": 10,
                "errors_total": 0,
                "timestamp": "2026-02-22T00:00:00Z",
            }
            mock_get.return_value = mock_agent

            resp = test_client.get("/opensearch/metrics")
            assert resp.status_code == 200
            data = resp.json()
            assert data["requests_total"] == 10

    def test_search_code_endpoint(self, test_client):
        """Testa endpoint /opensearch/search/code."""
        with patch("specialized_agents.opensearch_routes._get_agent") as mock_get:
            mock_agent = AsyncMock()
            mock_agent.search_code.return_value = {
                "total": 0,
                "hits": [],
                "took_ms": 5,
            }
            mock_get.return_value = mock_agent

            resp = test_client.get("/opensearch/search/code?q=FastAPI")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 0

    def test_delete_index_protection(self, test_client):
        """Testa que índices não-eddie são protegidos."""
        with patch("specialized_agents.opensearch_routes._get_agent") as mock_get:
            mock_agent = AsyncMock()
            mock_get.return_value = mock_agent

            resp = test_client.delete("/opensearch/index/system-index")
            assert resp.status_code == 400
            assert "eddie-" in resp.json()["detail"]
