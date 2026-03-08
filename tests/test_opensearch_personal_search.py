"""
Teste de integração do OpenSearch Agent — Busca de informações pessoais.
Indexa dados pessoais, realiza buscas full-text, semânticas e RAG.

Uso:
    python tests/test_opensearch_personal_search.py
    # Ou via pytest:
    pytest tests/test_opensearch_personal_search.py -v
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

# Adicionar raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from specialized_agents.opensearch_agent import OpenSearchAgent, get_opensearch_agent

# ──────────── Dados de teste ────────────

PESSOA_INFO = {
    "nome_completo": "Edenilson Teixeira Paschoa",
    "cpf": "36843012809",
    "cpf_formatado": "368.430.128-09",
    "descricao": (
        "Edenilson Teixeira Paschoa, CPF 368.430.128-09, é desenvolvedor de software "
        "e administrador do projeto Shared Auto-Dev. Especializado em Python, DevOps, "
        "inteligência artificial e automação de infraestrutura. "
        "Responsável pela manutenção do homelab e integração de agentes especializados."
    ),
    "dados_profissionais": {
        "profissao": "Desenvolvedor de Software / DevOps Engineer",
        "projeto_principal": "Shared Auto-Dev",
        "linguagens": ["Python", "JavaScript", "TypeScript", "Go", "Rust"],
        "especialidades": ["IA/ML", "DevOps", "Automação", "Infraestrutura"],
        "homelab": "192.168.15.2",
    },
}

INDEX_TEST = "shared-test-personal"


async def run_test():
    """Executa ciclo completo: setup → indexar → buscar → RAG → cleanup."""
    agent = OpenSearchAgent()
    results = {}

    print("=" * 70)
    print("🔍 TESTE OPENSEARCH AGENT — Busca de Informações Pessoais")
    print(f"   Data: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    # ──── 1. Health check ────
    print("\n[1/7] Verificando saúde do OpenSearch...")
    health = await agent.health()
    results["health"] = health
    if not health.get("connected"):
        print(f"   ❌ OpenSearch inacessível: {health.get('error', 'desconhecido')}")
        print(f"   URL: {agent.base_url}")
        print("   Certifique-se que o OpenSearch está rodando no homelab.")
        await agent.close()
        return results
    print(f"   ✅ Cluster: {health.get('cluster_name')} | Status: {health.get('status')}")
    print(f"   Nós: {health.get('number_of_nodes')} | Shards ativos: {health.get('active_shards')}")

    # ──── 2. Criar índice de teste ────
    print("\n[2/7] Criando índice de teste...")
    idx_result = await agent.create_index(
        INDEX_TEST,
        settings={"index": {"number_of_shards": 1, "number_of_replicas": 0}},
        mappings={
            "properties": {
                "nome": {"type": "text", "analyzer": "standard"},
                "cpf": {"type": "keyword"},
                "descricao": {"type": "text", "analyzer": "standard"},
                "profissao": {"type": "text"},
                "linguagens": {"type": "keyword"},
                "especialidades": {"type": "keyword"},
                "projeto": {"type": "keyword"},
                "tipo": {"type": "keyword"},
                "timestamp": {"type": "date"},
            }
        },
    )
    results["create_index"] = idx_result
    print(f"   {'✅' if 'error' not in idx_result else '⚠️'} {json.dumps(idx_result, indent=2)}")

    # ──── 3. Indexar dados pessoais ────
    print("\n[3/7] Indexando dados pessoais...")
    
    # Documento principal
    doc_principal = {
        "nome": PESSOA_INFO["nome_completo"],
        "cpf": PESSOA_INFO["cpf"],
        "descricao": PESSOA_INFO["descricao"],
        "profissao": PESSOA_INFO["dados_profissionais"]["profissao"],
        "linguagens": PESSOA_INFO["dados_profissionais"]["linguagens"],
        "especialidades": PESSOA_INFO["dados_profissionais"]["especialidades"],
        "projeto": PESSOA_INFO["dados_profissionais"]["projeto_principal"],
        "tipo": "pessoa",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    idx1 = await agent.index_document(INDEX_TEST, doc_principal, doc_id="edenilson-001")
    results["index_principal"] = idx1
    print(f"   ✅ Doc principal indexado: {idx1.get('result', idx1.get('error', '?'))}")

    # Segundo documento com mais contexto
    doc_bio = {
        "nome": "Edenilson Teixeira Paschoa",
        "cpf": "36843012809",
        "descricao": (
            "Edenilson é o criador e mantenedor do sistema multi-agente Shared Auto-Dev. "
            "O sistema utiliza Docker, Ollama, OpenSearch e ChromaDB para orquestrar "
            "agentes de desenvolvimento especializados em múltiplas linguagens. "
            "Edenilson gerencia o homelab em 192.168.15.2 onde os serviços rodam, "
            "incluindo Telegram Bot, API FastAPI, dashboards Streamlit e pipelines CI/CD. "
            "CPF: 368.430.128-09."
        ),
        "profissao": "Engenheiro de Software e Arquiteto de Sistemas",
        "linguagens": ["Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "C#", "PHP"],
        "especialidades": ["Multi-agent Systems", "DevOps", "RAG", "LLM Integration", "Docker"],
        "projeto": "Shared Auto-Dev",
        "tipo": "biografia_tecnica",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    idx2 = await agent.index_document(INDEX_TEST, doc_bio, doc_id="edenilson-002")
    results["index_bio"] = idx2
    print(f"   ✅ Doc bio indexado: {idx2.get('result', idx2.get('error', '?'))}")

    # Terceiro documento — dados complementares
    doc_complement = {
        "nome": "Edenilson Teixeira Paschoa",
        "cpf": "36843012809",
        "descricao": (
            "Informações técnicas: Edenilson Teixeira Paschoa é responsável pela "
            "arquitetura de comunicação inter-agentes via Bus de mensagens, "
            "sistema de memory para decisões, integração com GitHub Actions "
            "e orquestração distribuída entre Copilot local e agents homelab."
        ),
        "profissao": "Arquiteto de Software / SRE",
        "linguagens": ["Python", "Bash", "YAML"],
        "especialidades": ["SRE", "Observability", "OpenSearch", "Prometheus", "Grafana"],
        "projeto": "Shared Auto-Dev",
        "tipo": "dados_complementares",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    idx3 = await agent.index_document(INDEX_TEST, doc_complement, doc_id="edenilson-003")
    results["index_complement"] = idx3
    print(f"   ✅ Doc complementar indexado: {idx3.get('result', idx3.get('error', '?'))}")

    # Pequena pausa para refresh
    await asyncio.sleep(1)

    # ──── 4. Busca por nome (full-text) ────
    print("\n[4/7] Buscando por nome: 'Edenilson Teixeira Paschoa'...")
    search_nome = await agent.search(
        INDEX_TEST,
        {"multi_match": {"query": "Edenilson Teixeira Paschoa", "fields": ["nome^3", "descricao"]}},
        size=10,
    )
    results["search_nome"] = search_nome
    print(f"   🔎 Resultados: {search_nome.get('total', 0)} hits ({search_nome.get('took_ms', 0)}ms)")
    for hit in search_nome.get("hits", []):
        score = hit.get("_score", 0)
        nome = hit.get("nome", "?")
        tipo = hit.get("tipo", "?")
        print(f"      → [{score:.2f}] {nome} (tipo: {tipo})")

    # ──── 5. Busca por CPF (exact match) ────
    print("\n[5/7] Buscando por CPF: '36843012809'...")
    search_cpf = await agent.search(
        INDEX_TEST,
        {"term": {"cpf": "36843012809"}},
        size=10,
    )
    results["search_cpf"] = search_cpf
    print(f"   🔎 Resultados: {search_cpf.get('total', 0)} hits ({search_cpf.get('took_ms', 0)}ms)")
    for hit in search_cpf.get("hits", []):
        nome = hit.get("nome", "?")
        cpf = hit.get("cpf", "?")
        desc = hit.get("descricao", "")[:100]
        print(f"      → {nome} | CPF: {cpf}")
        print(f"        {desc}...")

    # ──── 6. Busca combinada (nome + CPF) ────
    print("\n[6/7] Busca combinada (nome + CPF + especialidades)...")
    search_combined = await agent.search(
        INDEX_TEST,
        {
            "bool": {
                "must": [
                    {"match": {"nome": "Edenilson"}},
                    {"term": {"cpf": "36843012809"}},
                ],
                "should": [
                    {"match": {"descricao": "Shared Auto-Dev"}},
                    {"match": {"especialidades": "DevOps"}},
                ],
            }
        },
        size=10,
    )
    results["search_combined"] = search_combined
    print(f"   🔎 Resultados: {search_combined.get('total', 0)} hits ({search_combined.get('took_ms', 0)}ms)")
    for hit in search_combined.get("hits", []):
        score = hit.get("_score", 0)
        nome = hit.get("nome", "?")
        tipo = hit.get("tipo", "?")
        desc = hit.get("descricao", "")[:120]
        print(f"      → [{score:.2f}] {nome} ({tipo})")
        print(f"        {desc}...")

    # ──── 7. Indexar no RAG e testar RAG Query ────
    print("\n[7/7] Testando RAG Pipeline (indexação + query com LLM)...")
    
    # Indexar para RAG (com embeddings)
    rag_texts = [
        PESSOA_INFO["descricao"],
        doc_bio["descricao"],
        doc_complement["descricao"],
    ]
    
    rag_result = await agent.ingest_for_rag(
        texts=rag_texts,
        language="pt-br",
        source="test-personal-search",
    )
    results["rag_ingest"] = rag_result
    print(f"   📚 RAG Ingestão: {rag_result.get('indexed', 0)} chunks indexados")
    
    if rag_result.get("indexed", 0) > 0:
        await asyncio.sleep(1)
        
        # Query RAG
        rag_answer = await agent.rag_query(
            question="Quem é Edenilson Teixeira Paschoa e qual é o CPF dele? Quais são suas especialidades?",
            language="pt-br",
            top_k=3,
        )
        results["rag_query"] = rag_answer
        print(f"   🤖 Modelo: {rag_answer.get('model', '?')}")
        print(f"   📊 Fontes encontradas: {rag_answer.get('search_hits', 0)}")
        print(f"   💬 Resposta LLM:")
        answer = rag_answer.get("answer", "Sem resposta")
        for line in answer.split("\n"):
            print(f"      {line}")
    else:
        print("   ⚠️ RAG ingest falhou (Ollama embeddings offline?)")
        results["rag_query"] = {"error": "Embeddings não disponíveis"}

    # ──── Resumo ────
    print("\n" + "=" * 70)
    print("📋 RESUMO DO TESTE")
    print("=" * 70)
    print(f"   Health:          {'✅' if health.get('connected') else '❌'} {health.get('status', '?')}")
    print(f"   Docs indexados:  3")
    print(f"   Busca nome:      {search_nome.get('total', 0)} hits")
    print(f"   Busca CPF:       {search_cpf.get('total', 0)} hits")
    print(f"   Busca combinada: {search_combined.get('total', 0)} hits")
    print(f"   RAG chunks:      {rag_result.get('indexed', 0)}")
    print(f"   RAG resposta:    {'✅' if results.get('rag_query', {}).get('answer') else '⚠️'}")
    print("=" * 70)

    # Cleanup: deletar índice de teste
    print("\n🧹 Limpando índice de teste...")
    del_result = await agent.delete_index(INDEX_TEST)
    print(f"   {del_result}")

    await agent.close()
    return results


# ──────────── pytest integration ────────────

import pytest

@pytest.mark.integration
def test_opensearch_personal_search():
    """Teste via pytest — requer OpenSearch rodando."""
    results = asyncio.run(run_test())
    health = results.get("health", {})
    if not health.get("connected"):
        pytest.skip("OpenSearch não disponível")
    
    # Validações
    assert results["search_nome"]["total"] >= 1, "Busca por nome deve retornar pelo menos 1 resultado"
    assert results["search_cpf"]["total"] >= 1, "Busca por CPF deve retornar pelo menos 1 resultado"
    assert results["search_combined"]["total"] >= 1, "Busca combinada deve retornar pelo menos 1 resultado"


if __name__ == "__main__":
    asyncio.run(run_test())
