#!/usr/bin/env python3
"""
Índice RAG — GPU Optimization Knowledge Base
Carrega documentação de otimização de GPU no sistema RAG
"""
import asyncio
import sys
from pathlib import Path

# Adicionar ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from specialized_agents.rag_manager import RAGManagerFactory


async def index_gpu_optimization_docs():
    """Indexa documentação de otimização de GPU no RAG"""
    
    print("📚 Indexando GPU Optimization Knowledge Base no RAG...")
    print()
    
    # Docs a indexar
    docs = [
        {
            "title": "GPU Optimization Complete — Dual GPU Setup",
            "language": "infrastructure",
            "file": "docs/GPU_OPTIMIZATION_COMPLETE.md",
            "description": "Análise técnica completa de otimização de GPUs (RTX 2060 SUPER + GTX 1050) para longevidade, eficiência térmica e performance no homelab",
            "tags": ["gpu", "nvidia", "optimization", "longevity", "thermal", "power-limit", "ollama", "homelab"],
        },
        {
            "title": "GPU Optimization Script — Tool for Setup/Validate/Reset",
            "language": "infrastructure",
            "file": "tools/gpu_optimize.sh",
            "description": "Script bash interativo para aplicar, validar ou resetar otimizações de GPU no homelab. Suporta comandos: setup (aplicar), validate (verificar status), reset (volta aos defaults)",
            "tags": ["gpu", "bash", "automation", "nvidia-smi", "systemd", "homelab"],
        },
        {
            "title": "Dual GPU Implementation — Architecture & Routing",
            "language": "infrastructure",
            "file": "DUAL_GPU_IMPLEMENTATION.md",
            "description": "Implementação completa do pipeline dual-GPU com estratégias de roteamento baseadas em tamanho de contexto. GPU0 para tarefas complexas, GPU1 para preprocessamento",
            "tags": ["dual-gpu", "architecture", "routing", "ollama", "strategy", "context-management"],
        },
    ]
    
    # Carregar cada documento
    for doc in docs:
        try:
            file_path = Path(__file__).parent.parent / doc["file"]
            
            if not file_path.exists():
                print(f"⚠️  Arquivo não encontrado: {doc['file']}")
                continue
            
            # Ler conteúdo
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Truncar para 4KB (limite prático do RAG)
            max_chars = 4000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n\n[... truncado por tamanho]"
            
            # Indexar no RAG
            rag_manager = RAGManagerFactory.get_manager(doc["language"])
            
            await rag_manager.index_code(
                code=content,
                language=doc["language"],
                description=doc["description"],
                metadata={
                    "title": doc["title"],
                    "source_file": doc["file"],
                    "tags": doc["tags"],
                }
            )
            
            print(f"✅ Indexado: {doc['title']}")
            print(f"   📄 {doc['file']}")
            print(f"   📌 Tags: {', '.join(doc['tags'])}")
            print()
            
        except Exception as e:
            print(f"❌ Erro ao indexar {doc['title']}: {e}")
            print()
    
    print("✅ GPU Optimization Knowledge Base indexada no RAG!")
    print()
    print("💡 Use no RAG:")
    print('   python_rag.search("GPU optimization longevity")')
    print('   python_rag.search("RTX 2060 SUPER power limit")')
    print('   python_rag.search("GTX 1050 thermal management")')
    print('   rag_manager = RAGManagerFactory.get_manager("infrastructure")')
    print('   results = await rag_manager.search("dual-GPU setup")')


if __name__ == "__main__":
    try:
        asyncio.run(index_gpu_optimization_docs())
    except KeyboardInterrupt:
        print("\n\n⚠️  Cancelado pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro: {e}", file=sys.stderr)
        sys.exit(1)
