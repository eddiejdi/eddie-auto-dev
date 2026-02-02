#!/usr/bin/env python3
"""
RAG MCP Server - Expõe APIs RAG como ferramentas MCP
Para uso com Continue, Cline, Roo Code, Claude Desktop e VS Code Chat
"""

import os
import json
import asyncio
import httpx
from mcp.server import Server
from mcp.types import (
    Tool,
    TextContent,
)
from mcp.server.stdio import stdio_server

# Configuração
RAG_API_BASE = os.environ.get("RAG_API_BASE", "http://192.168.15.2:8001/api/v1")

# Servidor MCP
server = Server("rag-mcp-server")

# Cliente HTTP
http_client = httpx.AsyncClient(timeout=60.0)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Lista todas as ferramentas RAG disponíveis"""
    return [
        Tool(
            name="rag_search",
            description="Busca semântica no RAG. Retorna documentos relevantes para a query. Use para encontrar código, conversas anteriores, documentação ou feedback.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A busca semântica a realizar",
                    },
                    "collection": {
                        "type": "string",
                        "description": "Collection para buscar: 'default', 'chat_history', 'code', 'conversations', 'feedback'",
                        "default": "chat_history",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Número de resultados (1-20)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="rag_get_context",
            description="Obtém contexto RAG formatado para augmentar prompts. Ideal para enriquecer perguntas com conhecimento prévio.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A query para buscar contexto",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Número de resultados",
                        "default": 3,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="rag_index_document",
            description="Indexa um novo documento no RAG para consulta futura. Use para salvar código, conversas ou documentação.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Conteúdo do documento",
                    },
                    "doc_type": {
                        "type": "string",
                        "description": "Tipo: 'code', 'conversation', 'documentation', 'feedback'",
                        "default": "documentation",
                    },
                    "source": {
                        "type": "string",
                        "description": "Fonte/origem do documento",
                    },
                    "collection": {
                        "type": "string",
                        "description": "Collection para armazenar",
                        "default": "default",
                    },
                },
                "required": ["content", "source"],
            },
        ),
        Tool(
            name="rag_stats",
            description="Retorna estatísticas do sistema RAG: total de documentos, collections, etc.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="rag_list_collections",
            description="Lista todas as collections disponíveis no RAG.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="rag_search_chat_history",
            description="Busca específica no histórico de chats indexados. Ideal para encontrar conversas anteriores sobre um tópico.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "O que buscar nas conversas anteriores",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Número de resultados",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="rag_search_code",
            description="Busca específica em código indexado. Ideal para encontrar implementações, funções ou padrões.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "O que buscar no código",
                    },
                    "language": {
                        "type": "string",
                        "description": "Filtrar por linguagem (opcional)",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Número de resultados",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="rag_submit_feedback",
            description="Envia feedback sobre uma resposta da IA para melhorar o sistema.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Pergunta original"},
                    "response": {"type": "string", "description": "Resposta da IA"},
                    "rating": {
                        "type": "string",
                        "description": "Avaliação: 'positive', 'negative', 'neutral'",
                        "enum": ["positive", "negative", "neutral"],
                    },
                    "correction": {
                        "type": "string",
                        "description": "Correção se a resposta estava errada (opcional)",
                    },
                },
                "required": ["query", "response", "rating"],
            },
        ),
        Tool(
            name="rag_index_project",
            description="Indexa um projeto inteiro de código para consulta RAG.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Caminho absoluto do projeto",
                    },
                    "project_id": {
                        "type": "string",
                        "description": "Identificador único do projeto",
                    },
                },
                "required": ["project_path", "project_id"],
            },
        ),
        Tool(
            name="rag_trigger_learning",
            description="Dispara manualmente o agente de aprendizado para processar feedback e melhorar o sistema.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Executa uma ferramenta RAG"""
    try:
        if name == "rag_search":
            return await rag_search(arguments)
        elif name == "rag_get_context":
            return await rag_get_context(arguments)
        elif name == "rag_index_document":
            return await rag_index_document(arguments)
        elif name == "rag_stats":
            return await rag_stats()
        elif name == "rag_list_collections":
            return await rag_list_collections()
        elif name == "rag_search_chat_history":
            arguments["collection"] = "chat_history"
            return await rag_search(arguments)
        elif name == "rag_search_code":
            arguments["collection"] = "code"
            return await rag_search(arguments)
        elif name == "rag_submit_feedback":
            return await rag_submit_feedback(arguments)
        elif name == "rag_index_project":
            return await rag_index_project(arguments)
        elif name == "rag_trigger_learning":
            return await rag_trigger_learning()
        else:
            return [TextContent(type="text", text=f"Ferramenta desconhecida: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Erro: {str(e)}")]


async def rag_search(args: dict) -> list[TextContent]:
    """Busca semântica no RAG"""
    query = args.get("query", "")
    collection = args.get("collection", "chat_history")
    n_results = args.get("n_results", 5)

    response = await http_client.post(
        f"{RAG_API_BASE}/rag/search",
        json={"query": query, "collection": collection, "n_results": n_results},
    )

    if response.status_code != 200:
        return [TextContent(type="text", text=f"Erro na busca: {response.status_code}")]

    data = response.json()
    results = data.get("results", [])

    if not results:
        return [
            TextContent(type="text", text=f"Nenhum resultado encontrado para: {query}")
        ]

    output = f"## 🔍 Resultados RAG para: {query}\n\n"
    output += f"**Collection:** {collection} | **Total:** {len(results)} resultados\n\n"

    for i, result in enumerate(results, 1):
        content = result.get("content", "")[:500]
        score = result.get("relevance_score", "N/A")
        metadata = result.get("metadata", {})
        source = metadata.get("source", "Desconhecido")

        output += f"### Resultado {i} (Score: {score})\n"
        output += f"**Fonte:** {source}\n\n"
        output += f"```\n{content}\n```\n\n"

    return [TextContent(type="text", text=output)]


async def rag_get_context(args: dict) -> list[TextContent]:
    """Obtém contexto formatado"""
    query = args.get("query", "")
    n_results = args.get("n_results", 3)

    response = await http_client.get(
        f"{RAG_API_BASE}/rag/context", params={"query": query, "n_results": n_results}
    )

    if response.status_code != 200:
        return [
            TextContent(
                type="text", text=f"Erro ao obter contexto: {response.status_code}"
            )
        ]

    data = response.json()
    return [
        TextContent(
            type="text",
            text=f"## 📚 Contexto RAG\n\n{json.dumps(data, indent=2, ensure_ascii=False)}",
        )
    ]


async def rag_index_document(args: dict) -> list[TextContent]:
    """Indexa documento no RAG"""
    import uuid
    from datetime import datetime

    doc_id = f"mcp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    document = {
        "id": doc_id,
        "content": args.get("content", ""),
        "metadata": {
            "source": args.get("source", "mcp-server"),
            "doc_type": args.get("doc_type", "documentation"),
            "created_at": datetime.now().isoformat(),
        },
    }

    response = await http_client.post(
        f"{RAG_API_BASE}/rag/index",
        json={"documents": [document], "collection": args.get("collection", "default")},
    )

    if response.status_code == 200:
        data = response.json()
        return [
            TextContent(
                type="text",
                text=f"✅ Documento indexado!\n- ID: {doc_id}\n- Collection: {args.get('collection', 'default')}\n- Mensagem: {data.get('message', 'OK')}",
            )
        ]
    else:
        return [
            TextContent(
                type="text",
                text=f"❌ Erro ao indexar: {response.status_code} - {response.text}",
            )
        ]


async def rag_stats() -> list[TextContent]:
    """Retorna estatísticas do RAG"""
    response = await http_client.get(f"{RAG_API_BASE}/rag/stats")

    if response.status_code != 200:
        return [
            TextContent(
                type="text", text=f"Erro ao obter stats: {response.status_code}"
            )
        ]

    data = response.json()

    output = "## 📊 Estatísticas RAG\n\n"
    output += f"- **Total de Documentos:** {data.get('total_documents', 0)}\n"
    output += f"- **Total de Conversas:** {data.get('total_conversations', 0)}\n"
    output += f"- **Total de Feedback:** {data.get('total_feedback', 0)}\n"
    output += (
        f"- **Taxa Feedback Positivo:** {data.get('positive_feedback_rate', 0):.1%}\n"
    )
    output += f"- **Collections:** {', '.join(data.get('collections', []))}\n"
    output += f"- **Último Aprendizado:** {data.get('last_learning_run', 'Nunca')}\n"

    return [TextContent(type="text", text=output)]


async def rag_list_collections() -> list[TextContent]:
    """Lista collections"""
    response = await http_client.get(f"{RAG_API_BASE}/rag/stats")

    if response.status_code != 200:
        return [TextContent(type="text", text=f"Erro: {response.status_code}")]

    data = response.json()
    collections = data.get("collections", [])

    output = "## 📁 Collections RAG Disponíveis\n\n"
    for col in collections:
        output += f"- `{col}`\n"

    return [TextContent(type="text", text=output)]


async def rag_submit_feedback(args: dict) -> list[TextContent]:
    """Submete feedback"""
    import uuid

    payload = {
        "conversation_id": f"mcp_{uuid.uuid4().hex[:8]}",
        "message_index": 0,
        "query": args.get("query", ""),
        "response": args.get("response", ""),
        "rating": args.get("rating", "neutral"),
        "correction": args.get("correction"),
    }

    response = await http_client.post(f"{RAG_API_BASE}/rag/feedback", json=payload)

    if response.status_code == 200:
        data = response.json()
        return [
            TextContent(
                type="text",
                text=f"✅ Feedback registrado!\n- ID: {data.get('feedback_id', 'N/A')}\n- Aprendizado disparado: {data.get('learning_triggered', False)}",
            )
        ]
    else:
        return [TextContent(type="text", text=f"❌ Erro: {response.status_code}")]


async def rag_index_project(args: dict) -> list[TextContent]:
    """Indexa projeto inteiro"""
    response = await http_client.post(
        f"{RAG_API_BASE}/rag/index/project",
        params={
            "project_path": args.get("project_path", ""),
            "project_id": args.get("project_id", ""),
        },
    )

    if response.status_code == 200:
        data = response.json()
        return [
            TextContent(
                type="text",
                text=f"✅ Projeto indexado!\n{json.dumps(data, indent=2, ensure_ascii=False)}",
            )
        ]
    else:
        return [
            TextContent(
                type="text", text=f"❌ Erro: {response.status_code} - {response.text}"
            )
        ]


async def rag_trigger_learning() -> list[TextContent]:
    """Dispara aprendizado manual"""
    response = await http_client.post(f"{RAG_API_BASE}/rag/agent/learn")

    if response.status_code == 200:
        data = response.json()
        return [
            TextContent(
                type="text",
                text=f"✅ Aprendizado disparado!\n{json.dumps(data, indent=2, ensure_ascii=False)}",
            )
        ]
    else:
        return [TextContent(type="text", text=f"❌ Erro: {response.status_code}")]


async def main():
    """Inicia o servidor MCP"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
