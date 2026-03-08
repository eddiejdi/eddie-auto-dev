#!/usr/bin/env python3
"""
Script para coletar e treinar o LLM local com dados de conversa.
Colete dados, indexe no RAG, e opcionalmente faça fine-tuning do Ollama.
"""

import json
import os
import sys
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Adicionar ao path
sys.path.insert(0, str(Path(__file__).parent))

from specialized_agents.rag_manager import RAGManagerFactory


class ConversationCollector:
    """Coletor de conversas para treinamento."""
    
    def __init__(self, data_dir: str = "artifacts"):
        self.data_dir = Path(data_dir)
        self.conversations: List[Dict[str, Any]] = []
        
    def collect_from_json(self, filepath: Path) -> int:
        """Coletar conversas de arquivo JSON."""
        logger.info(f"📥 Coletando de: {filepath}")
        
        if not filepath.exists():
            logger.warning(f"⚠️  Arquivo não encontrado: {filepath}")
            return 0
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse multiples JSON objects separated by lines
            conversations_added = 0
            for line in content.split('\n'):
                if not line.strip() or line.startswith('==='):
                    continue
                try:
                    data = json.loads(line)
                    if isinstance(data, dict) and 'messages' in data:
                        self.conversations.append(data)
                        conversations_added += 1
                except json.JSONDecodeError:
                    # Tentar parse de bloco
                    pass
            
            logger.info(f"✅ {conversations_added} conversas coletadas")
            return conversations_added
        
        except Exception as e:
            logger.error(f"❌ Erro ao coletar: {e}")
            return 0
    
    def collect_all(self) -> int:
        """Coletar de múltiplas fontes."""
        total = 0
        
        # JSON principal
        json_file = self.data_dir / "agent_conversations.json"
        total += self.collect_from_json(json_file)
        
        logger.info(f"📊 Total de conversas coletadas: {total}")
        return total
    
    def extract_training_docs(self) -> List[str]:
        """Extrair documentos de treinamento das conversas."""
        docs = []
        
        for conv in self.conversations:
            conv_id = conv.get('conversation_id', 'unknown')
            messages = conv.get('messages', [])
            
            for msg in messages:
                msg_type = msg.get('type', 'unknown')
                content = msg.get('content', '')
                
                if content and len(content) > 10:  # Filtrar muito curto
                    # Formatar como documento para RAG
                    doc = f"""
[Conversation: {conv_id}]
[Type: {msg_type}]
[Model: {msg.get('metadata', {}).get('model', 'unknown')}]

{content}
"""
                    docs.append(doc)
        
        logger.info(f"📝 {len(docs)} documentos de treinamento extraídos")
        return docs


async def train_rag(docs: List[str], language: str = "python") -> bool:
    """Treinar RAG Manager com documentos."""
    try:
        logger.info(f"🧠 Iniciando treinamento RAG ({language})...")
        
        # Inicializar RAG Manager
        rag = RAGManagerFactory.get_manager(language)
        
        # Indexar documentos
        for i, doc in enumerate(docs, 1):
            try:
                await rag.index_code(
                    code=doc,
                    language=language,
                    description=f"Training doc #{i} from conversations"
                )
                if i % 10 == 0:
                    logger.info(f"  ✓ {i}/{len(docs)} documentos indexados")
            except Exception as e:
                logger.warning(f"  ⚠️  Erro ao indexar doc {i}: {e}")
                continue
        
        logger.info(f"✅ RAG treinado com {len(docs)} documentos")
        return True
    
    except Exception as e:
        logger.error(f"❌ Erro durante treinamento RAG: {e}")
        return False


async def test_rag(query: str, language: str = "python") -> List[Dict[str, Any]]:
    """Testar RAG com query de busca."""
    try:
        logger.info(f"🔍 Testando RAG com query: {query}")
        
        rag = RAGManagerFactory.get_manager(language)
        results = await rag.search(query)
        
        logger.info(f"✅ {len(results)} resultados encontrados")
        return results
    
    except Exception as e:
        logger.error(f"❌ Erro ao testar RAG: {e}")
        return []


async def main():
    """Main execution."""
    print("\n" + "="*60)
    print("🚀 TREINAMENTO DE LLM COM CONVERSAS")
    print("="*60 + "\n")
    
    # Verificar ambiente
    logger.info("📋 Verificando ambiente...")
    
    if not os.getenv("DATABASE_URL"):
        logger.warning("⚠️  DATABASE_URL não configurado, usando SQLite local")
    
    if not os.getenv("OLLAMA_HOST"):
        logger.warning("⚠️  OLLAMA_HOST não configurado, usando padrão local")
    
    # Coletar conversas
    logger.info("\n📥 ETAPA 1: Coletando conversas...")
    collector = ConversationCollector()
    total = collector.collect_all()
    
    if total == 0:
        logger.error("❌ Nenhuma conversa encontrada. Abortando.")
        return 1
    
    # Extrair documentos
    logger.info("\n📝 ETAPA 2: Extraindo documentos de treinamento...")
    docs = collector.extract_training_docs()
    
    if not docs:
        logger.error("❌ Nenhum documento para treinar. Abortando.")
        return 1
    
    # Treinar RAG
    logger.info("\n🧠 ETAPA 3: Treinando RAG Manager...")
    languages = ["python", "javascript", "general"]
    
    for lang in languages:
        logger.info(f"\n  Treinando {lang}...")
        success = await train_rag(docs, language=lang)
        if not success:
            logger.warning(f"  ⚠️  Falha ao treinar {lang}")
    
    # Teste RAG
    logger.info("\n🔍 ETAPA 4: Testando RAG...")
    test_queries = [
        "quicksort algorithm implementation",
        "auto-scaling agents",
        "error handling in python"
    ]
    
    for query in test_queries:
        results = await test_rag(query)
        if results:
            logger.info(f"  ✅ Query '{query}' retornou {len(results)} resultado(s)")
        else:
            logger.warning(f"  ⚠️  Query '{query}' sem resultados")
    
    # Resumo
    logger.info("\n" + "="*60)
    logger.info("✅ TREINAMENTO COMPLETO")
    logger.info(f"  📊 Conversas coletadas: {total}")
    logger.info(f"  📝 Documentos indexados: {len(docs)}")
    logger.info(f"  🧠 RAG pronto para queries")
    logger.info("="*60 + "\n")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
