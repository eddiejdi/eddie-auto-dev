"""
Gerenciador de RAG por Linguagem
Cada agente tem sua própria coleção no ChromaDB
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from .config import RAG_CONFIG, RAG_DIR


class LanguageRAGManager:
    """
    Gerenciador de RAG com coleções separadas por linguagem.
    Cada agente tem sua própria base de conhecimento.
    """

    def __init__(self, language: str):
        self.language = language
        self.collection_name = f"agent_{language}_knowledge"
        self.rag_path = RAG_DIR / language
        self.rag_path.mkdir(parents=True, exist_ok=True)

        self.client = None
        self.collection = None
        self.embedder = None

        if CHROMADB_AVAILABLE:
            self._init_chromadb()

        if SENTENCE_TRANSFORMERS_AVAILABLE:
            self._init_embedder()

    def _init_chromadb(self):
        """Inicializa ChromaDB"""
        try:
            persist_path = str(self.rag_path / "chromadb")
            self.client = chromadb.PersistentClient(path=persist_path)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name, metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            print(f"[RAG] Erro ao inicializar ChromaDB: {e}")

    def _init_embedder(self):
        """Inicializa modelo de embeddings"""
        try:
            model_name = RAG_CONFIG.get("embedding_model", "all-MiniLM-L6-v2")
            self.embedder = SentenceTransformer(model_name)
        except Exception as e:
            print(f"[RAG] Erro ao carregar embedder: {e}")

    def _generate_id(self, content: str) -> str:
        """Gera ID único para documento"""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _chunk_text(
        self, text: str, chunk_size: int = None, overlap: int = None
    ) -> List[str]:
        """Divide texto em chunks"""
        chunk_size = chunk_size or RAG_CONFIG.get("chunk_size", 1500)
        overlap = overlap or RAG_CONFIG.get("chunk_overlap", 300)

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # Tentar quebrar em linha
            if end < len(text):
                last_newline = chunk.rfind("\n")
                if last_newline > chunk_size // 2:
                    chunk = chunk[:last_newline]
                    end = start + last_newline

            chunks.append(chunk.strip())
            start = end - overlap

        return [c for c in chunks if c]

    async def index_code(
        self,
        code: str,
        language: str,
        description: str = "",
        source_id: str = "",
        metadata: Dict = None,
    ) -> bool:
        """Indexa código no RAG"""
        if not self.collection:
            return False

        try:
            chunks = self._chunk_text(code)

            for i, chunk in enumerate(chunks):
                doc_id = f"{source_id}_{i}" if source_id else self._generate_id(chunk)

                doc_metadata = {
                    "language": language,
                    "description": description[:500],
                    "source_id": source_id,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "indexed_at": datetime.now().isoformat(),
                    "type": "code",
                    **(metadata or {}),
                }

                # Gerar embedding se disponível
                embedding = None
                if self.embedder:
                    embedding = self.embedder.encode(chunk).tolist()

                self.collection.upsert(
                    ids=[doc_id],
                    documents=[chunk],
                    metadatas=[doc_metadata],
                    embeddings=[embedding] if embedding else None,
                )

            return True
        except Exception as e:
            print(f"[RAG] Erro ao indexar: {e}")
            return False

    async def index_documentation(
        self, content: str, title: str, source: str = "", metadata: Dict = None
    ) -> bool:
        """Indexa documentação no RAG"""
        if not self.collection:
            return False

        try:
            chunks = self._chunk_text(content)

            for i, chunk in enumerate(chunks):
                doc_id = self._generate_id(f"{title}_{i}_{chunk[:50]}")

                doc_metadata = {
                    "language": self.language,
                    "title": title,
                    "source": source,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "indexed_at": datetime.now().isoformat(),
                    "type": "documentation",
                    **(metadata or {}),
                }

                embedding = None
                if self.embedder:
                    embedding = self.embedder.encode(chunk).tolist()

                self.collection.upsert(
                    ids=[doc_id],
                    documents=[chunk],
                    metadatas=[doc_metadata],
                    embeddings=[embedding] if embedding else None,
                )

            return True
        except Exception as e:
            print(f"[RAG] Erro ao indexar documentação: {e}")
            return False

    async def index_conversation(
        self, question: str, answer: str, context: str = "", metadata: Dict = None
    ) -> bool:
        """Indexa uma conversa Q&A no RAG"""
        if not self.collection:
            return False

        try:
            content = f"PERGUNTA: {question}\n\nRESPOSTA: {answer}"
            if context:
                content = f"CONTEXTO: {context}\n\n{content}"

            doc_id = self._generate_id(content)

            doc_metadata = {
                "language": self.language,
                "question": question[:500],
                "indexed_at": datetime.now().isoformat(),
                "type": "conversation",
                **(metadata or {}),
            }

            embedding = None
            if self.embedder:
                embedding = self.embedder.encode(content).tolist()

            self.collection.upsert(
                ids=[doc_id],
                documents=[content],
                metadatas=[doc_metadata],
                embeddings=[embedding] if embedding else None,
            )

            return True
        except Exception as e:
            print(f"[RAG] Erro ao indexar conversa: {e}")
            return False

    async def search(
        self, query: str, language: str = None, n_results: int = 5, doc_type: str = None
    ) -> List[str]:
        """Busca no RAG"""
        if not self.collection:
            return []

        try:
            # Filtros
            where = {}
            if language:
                where["language"] = language
            if doc_type:
                where["type"] = doc_type

            # Gerar embedding da query
            query_embedding = None
            if self.embedder:
                query_embedding = self.embedder.encode(query).tolist()

            # Buscar
            if query_embedding:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=where if where else None,
                )
            else:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    where=where if where else None,
                )

            documents = results.get("documents", [[]])[0]
            return documents
        except Exception as e:
            print(f"[RAG] Erro na busca: {e}")
            return []

    async def search_with_metadata(
        self, query: str, n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Busca retornando metadados"""
        if not self.collection:
            return []

        try:
            query_embedding = None
            if self.embedder:
                query_embedding = self.embedder.encode(query).tolist()

            if query_embedding:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"],
                )
            else:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"],
                )

            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            return [
                {
                    "content": doc,
                    "metadata": meta,
                    "score": 1 - dist,  # Converter distância em score
                }
                for doc, meta, dist in zip(documents, metadatas, distances)
            ]
        except Exception as e:
            print(f"[RAG] Erro na busca: {e}")
            return []

    async def get_context_for_prompt(self, query: str, n_results: int = 3) -> str:
        """Retorna contexto formatado para augmentar prompts"""
        results = await self.search_with_metadata(query, n_results)

        if not results:
            return ""

        context_parts = []
        for i, result in enumerate(results, 1):
            meta = result.get("metadata", {})
            content = result.get("content", "")
            doc_type = meta.get("type", "unknown")

            context_parts.append(f"[{i}] ({doc_type}):\n{content[:1000]}")

        return "\n\n---\n\n".join(context_parts)

    async def delete_by_source(self, source_id: str) -> bool:
        """Remove documentos por source_id"""
        if not self.collection:
            return False

        try:
            self.collection.delete(where={"source_id": source_id})
            return True
        except Exception as e:
            print(f"[RAG] Erro ao deletar: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas da coleção"""
        if not self.collection:
            return {"available": False}

        try:
            count = self.collection.count()
            return {
                "available": True,
                "language": self.language,
                "collection_name": self.collection_name,
                "document_count": count,
                "embedder_available": self.embedder is not None,
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    async def export_to_json(self, output_path: Path = None) -> str:
        """Exporta coleção para JSON"""
        if not self.collection:
            return ""

        try:
            results = self.collection.get(include=["documents", "metadatas"])

            export_data = {
                "language": self.language,
                "collection_name": self.collection_name,
                "exported_at": datetime.now().isoformat(),
                "documents": [
                    {"id": id_, "content": doc, "metadata": meta}
                    for id_, doc, meta in zip(
                        results.get("ids", []),
                        results.get("documents", []),
                        results.get("metadatas", []),
                    )
                ],
            }

            output_path = output_path or (
                self.rag_path
                / f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            output_path.write_text(
                json.dumps(export_data, indent=2, ensure_ascii=False)
            )

            return str(output_path)
        except Exception as e:
            print(f"[RAG] Erro ao exportar: {e}")
            return ""

    async def import_from_json(self, input_path: Path) -> bool:
        """Importa coleção de JSON"""
        if not self.collection:
            return False

        try:
            data = json.loads(input_path.read_text())

            for doc in data.get("documents", []):
                embedding = None
                if self.embedder:
                    embedding = self.embedder.encode(doc["content"]).tolist()

                self.collection.upsert(
                    ids=[doc["id"]],
                    documents=[doc["content"]],
                    metadatas=[doc.get("metadata", {})],
                    embeddings=[embedding] if embedding else None,
                )

            return True
        except Exception as e:
            print(f"[RAG] Erro ao importar: {e}")
            return False


class RAGManagerFactory:
    """Factory para criar/gerenciar RAG managers por linguagem"""

    _instances: Dict[str, LanguageRAGManager] = {}

    @classmethod
    def get_manager(cls, language: str) -> LanguageRAGManager:
        """Retorna manager para a linguagem (singleton por linguagem)"""
        if language not in cls._instances:
            cls._instances[language] = LanguageRAGManager(language)
        return cls._instances[language]

    @classmethod
    def get_all_managers(cls) -> Dict[str, LanguageRAGManager]:
        """Retorna todos os managers ativos"""
        return cls._instances

    @classmethod
    async def global_search(cls, query: str, n_results: int = 5) -> List[Dict]:
        """Busca em todas as coleções"""
        all_results = []

        for lang, manager in cls._instances.items():
            results = await manager.search_with_metadata(query, n_results)
            for r in results:
                r["language"] = lang
            all_results.extend(results)

        # Ordenar por score
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return all_results[:n_results]
