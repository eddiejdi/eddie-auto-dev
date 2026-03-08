#!/usr/bin/env python3
"""
Script para indexar toda a documentação no RAG (ChromaDB)
Indexa:
- Documentação do sistema (docs/)
- Código fonte com comentários
- Conhecimento do homelab
- Soluções anteriores
"""

import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Adicionar ao path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError:
    print("Instalando chromadb...")
    os.system("pip install chromadb sentence-transformers")
    import chromadb
    from chromadb.utils import embedding_functions


# Configurações
CHROMA_PATH = Path(__file__).parent / "chroma_db"
DOCS_PATH = Path(__file__).parent / "docs"
CODE_PATH = Path(__file__).parent

# Extensões de código para indexar
CODE_EXTENSIONS = {'.py', '.js', '.ts', '.go', '.rs', '.java', '.cs', '.php', '.sh', '.md'}

# Arquivos importantes para indexar
IMPORTANT_FILES = [
    'telegram_bot.py',
    'web_search.py',
    'specialized_agents/api.py',
    'specialized_agents/agent_manager.py',
    'specialized_agents/language_agents.py',
    'specialized_agents/rag_manager.py',
    'specialized_agents/docker_orchestrator.py',
    'specialized_agents/github_client.py',
    'homelab_documentation.md',
]


class RAGIndexer:
    """Indexador de documentação para o RAG"""
    
    def __init__(self):
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        
        # Usar função de embedding padrão (sentence-transformers)
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        
        self.client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        
        # Coleções
        self.docs_collection = self.client.get_or_create_collection(
            name="system_documentation",
            embedding_function=self.embedding_fn,
            metadata={"description": "Documentação do sistema Shared Auto-Dev"}
        )
        
        self.code_collection = self.client.get_or_create_collection(
            name="system_code",
            embedding_function=self.embedding_fn,
            metadata={"description": "Código fonte do sistema"}
        )
        
        self.knowledge_collection = self.client.get_or_create_collection(
            name="homelab_knowledge",
            embedding_function=self.embedding_fn,
            metadata={"description": "Conhecimento do homelab"}
        )
        
        self.solutions_collection = self.client.get_or_create_collection(
            name="solutions",
            embedding_function=self.embedding_fn,
            metadata={"description": "Soluções desenvolvidas"}
        )
        
    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> list:
        """Divide texto em chunks com overlap"""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Tentar terminar em fim de linha ou parágrafo
            if end < len(text):
                last_newline = chunk.rfind('\n')
                if last_newline > chunk_size // 2:
                    end = start + last_newline + 1
                    chunk = text[start:end]
            
            chunks.append(chunk)
            start = end - overlap
            
        return chunks
    
    def index_documentation(self):
        """Indexa arquivos de documentação"""
        print("\n📚 Indexando documentação...")
        
        if not DOCS_PATH.exists():
            print(f"   Diretório {DOCS_PATH} não existe")
            return
        
        indexed = 0
        for doc_file in DOCS_PATH.glob("*.md"):
            content = doc_file.read_text(encoding='utf-8')
            chunks = self._chunk_text(content)
            
            for i, chunk in enumerate(chunks):
                doc_id = f"doc_{doc_file.stem}_{i}"
                
                try:
                    self.docs_collection.upsert(
                        ids=[doc_id],
                        documents=[chunk],
                        metadatas=[{
                            "source": str(doc_file),
                            "filename": doc_file.name,
                            "type": "documentation",
                            "chunk": i,
                            "indexed_at": datetime.now().isoformat()
                        }]
                    )
                    indexed += 1
                except Exception as e:
                    print(f"   ❌ Erro indexando {doc_file.name}: {e}")
        
        print(f"   ✅ {indexed} chunks de documentação indexados")
        
    def index_code(self):
        """Indexa código fonte importante"""
        print("\n💻 Indexando código fonte...")
        
        indexed = 0
        for rel_path in IMPORTANT_FILES:
            file_path = CODE_PATH / rel_path
            
            if not file_path.exists():
                print(f"   ⚠️ Arquivo não encontrado: {rel_path}")
                continue
            
            try:
                content = file_path.read_text(encoding='utf-8')
            except Exception as e:
                print(f"   ❌ Erro lendo {rel_path}: {e}")
                continue
            
            # Extrair docstrings e comentários importantes
            chunks = self._extract_code_chunks(content, file_path.suffix)
            
            for i, (chunk, chunk_type) in enumerate(chunks):
                doc_id = f"code_{file_path.stem}_{i}"
                
                try:
                    self.code_collection.upsert(
                        ids=[doc_id],
                        documents=[chunk],
                        metadatas=[{
                            "source": str(file_path),
                            "filename": file_path.name,
                            "language": self._get_language(file_path.suffix),
                            "type": chunk_type,
                            "chunk": i,
                            "indexed_at": datetime.now().isoformat()
                        }]
                    )
                    indexed += 1
                except Exception as e:
                    print(f"   ❌ Erro indexando {rel_path}: {e}")
        
        print(f"   ✅ {indexed} chunks de código indexados")
    
    def _extract_code_chunks(self, content: str, extension: str) -> list:
        """Extrai chunks significativos do código"""
        chunks = []
        
        # Dividir em chunks gerais
        general_chunks = self._chunk_text(content)
        for chunk in general_chunks:
            chunks.append((chunk, "code"))
        
        # Extrair docstrings (Python)
        if extension == '.py':
            import re
            docstrings = re.findall(r'"""(.*?)"""', content, re.DOTALL)
            for doc in docstrings:
                if len(doc.strip()) > 50:  # Ignorar docstrings muito pequenas
                    chunks.append((doc.strip(), "docstring"))
        
        return chunks
    
    def _get_language(self, extension: str) -> str:
        """Retorna a linguagem baseada na extensão"""
        mapping = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.go': 'go',
            '.rs': 'rust',
            '.java': 'java',
            '.cs': 'csharp',
            '.php': 'php',
            '.sh': 'bash',
            '.md': 'markdown'
        }
        return mapping.get(extension, 'unknown')
    
    def index_homelab_knowledge(self):
        """Indexa conhecimento específico do homelab"""
        print("\n🏠 Indexando conhecimento do homelab...")
        
        # Conhecimento do sistema
        knowledge_items = [
            {
                "id": "homelab_arch",
                "content": """
                Shared Homelab Architecture:
                
                - Servidor principal: 192.168.15.2 (homelab)
                  - Ollama LLM (shared-coder model)
                  - Docker containers para desenvolvimento
                  
                - WSL2 Ubuntu local
                  - Telegram Bot (telegram_bot.py)
                  - Specialized Agents API (FastAPI :8503)
                  - ChromaDB para RAG
                  
                - Integrações:
                  - Telegram Bot API
                  - GitHub API
                  - DuckDuckGo Search
                """,
                "type": "architecture"
            },
            {
                "id": "homelab_commands",
                "content": """
                Comandos úteis do homelab:
                
                # Ver status dos serviços
                systemctl status shared-telegram-bot
                systemctl status specialized-agents
                
                # Ver logs
                journalctl -u shared-telegram-bot -f
                journalctl -u specialized-agents -f
                
                # Reiniciar serviços
                sudo systemctl restart shared-telegram-bot
                sudo systemctl restart specialized-agents
                
                # Testar API
                curl http://localhost:8503/health
                
                # Testar Ollama
                curl http://192.168.15.2:11434/api/tags
                """,
                "type": "commands"
            },
            {
                "id": "homelab_telegram",
                "content": """
                Telegram Bot Configuration:
                
                Token: Definido em TELEGRAM_BOT_TOKEN
                Admin Chat ID: 948686300
                
                Comandos disponíveis:
                /start - Inicia o bot
                /help - Mostra ajuda
                /status - Status do sistema
                /dev - Solicitar desenvolvimento
                /web - Buscar na web
                /agents - Listar agentes
                
                O bot detecta automaticamente quando não consegue responder
                e inicia o processo de auto-desenvolvimento.
                """,
                "type": "configuration"
            },
            {
                "id": "homelab_agents",
                "content": """
                Agentes Especializados:
                
                Python Agent - python:3.12-slim - Porta 8000-8100
                JavaScript Agent - node:20-slim - Porta 3000-3100
                TypeScript Agent - node:20-slim - Porta 3100-3200
                Go Agent - golang:1.22-alpine - Porta 4000-4100
                Rust Agent - rust:1.75-slim - Porta 4100-4200
                Java Agent - eclipse-temurin:21-jdk - Porta 8080-8180
                C# Agent - dotnet/sdk:8.0 - Porta 5000-5100
                PHP Agent - php:8.3-cli - Porta 9000-9100
                
                Cada agente tem:
                - Ambiente Docker isolado
                - RAG específico da linguagem
                - Capacidade de gerar, testar e push código
                """,
                "type": "agents"
            }
        ]
        
        for item in knowledge_items:
            try:
                self.knowledge_collection.upsert(
                    ids=[item["id"]],
                    documents=[item["content"]],
                    metadatas=[{
                        "type": item["type"],
                        "indexed_at": datetime.now().isoformat()
                    }]
                )
            except Exception as e:
                print(f"   ❌ Erro indexando {item['id']}: {e}")
        
        print(f"   ✅ {len(knowledge_items)} itens de conhecimento indexados")
    
    def index_solutions(self):
        """Indexa soluções anteriores"""
        print("\n💡 Indexando soluções...")
        
        solutions_path = CODE_PATH / "solutions"
        if not solutions_path.exists():
            print("   Diretório de soluções não existe")
            return
        
        indexed = 0
        for solution_dir in solutions_path.iterdir():
            if not solution_dir.is_dir():
                continue
            
            readme = solution_dir / "README.md"
            if readme.exists():
                content = readme.read_text(encoding='utf-8')
                
                try:
                    self.solutions_collection.upsert(
                        ids=[f"solution_{solution_dir.name}"],
                        documents=[content],
                        metadatas=[{
                            "solution_name": solution_dir.name,
                            "path": str(solution_dir),
                            "indexed_at": datetime.now().isoformat()
                        }]
                    )
                    indexed += 1
                except Exception as e:
                    print(f"   ❌ Erro indexando {solution_dir.name}: {e}")
        
        print(f"   ✅ {indexed} soluções indexadas")
    
    def show_stats(self):
        """Mostra estatísticas do RAG"""
        print("\n📊 Estatísticas do RAG:")
        print(f"   Documentação: {self.docs_collection.count()} documentos")
        print(f"   Código: {self.code_collection.count()} documentos")
        print(f"   Conhecimento: {self.knowledge_collection.count()} documentos")
        print(f"   Soluções: {self.solutions_collection.count()} documentos")
        
    def search(self, query: str, n_results: int = 5) -> dict:
        """Busca em todas as coleções"""
        results = {}
        
        for name, collection in [
            ("documentation", self.docs_collection),
            ("code", self.code_collection),
            ("knowledge", self.knowledge_collection),
            ("solutions", self.solutions_collection)
        ]:
            try:
                result = collection.query(
                    query_texts=[query],
                    n_results=n_results
                )
                results[name] = result
            except Exception as e:
                results[name] = {"error": str(e)}
        
        return results


def main():
    print("=" * 60)
    print("🚀 Shared Auto-Dev RAG Indexer")
    print("=" * 60)
    
    indexer = RAGIndexer()
    
    # Indexar tudo
    indexer.index_documentation()
    indexer.index_code()
    indexer.index_homelab_knowledge()
    indexer.index_solutions()
    
    # Mostrar estatísticas
    indexer.show_stats()
    
    # Teste de busca
    print("\n🔍 Teste de busca: 'como criar API FastAPI'")
    results = indexer.search("como criar API FastAPI", n_results=2)
    
    for collection_name, result in results.items():
        if "error" not in result and result.get("documents"):
            print(f"\n   [{collection_name}]")
            for i, doc in enumerate(result["documents"][0][:1]):
                preview = doc[:200].replace('\n', ' ')
                print(f"   {i+1}. {preview}...")
    
    print("\n" + "=" * 60)
    print("✅ Indexação completa!")
    print(f"📁 Dados salvos em: {CHROMA_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
