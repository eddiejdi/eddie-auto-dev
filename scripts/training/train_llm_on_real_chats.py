#!/usr/bin/env python3
"""
Treinar LLM com dados REAIS de chat extraídos do PostgreSQL.
1939 mensagens de conversa real do sistema.
"""

import json
import os
import sys
import asyncio
from pathlib import Path
from typing import List, Dict, Any
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from specialized_agents.rag_manager import RAGManagerFactory


class RealChatTrainer:
    """Treina RAG com dados reais de chat."""
    
    def __init__(self, data_file: str = "artifacts/real_chat_data.json"):
        self.data_file = Path(data_file)
        self.messages: List[Dict[str, Any]] = []
    
    def load_data(self) -> bool:
        """Carregar dados do arquivo JSON."""
        logger.info(f"📂 Carregando dados de {self.data_file}...")
        
        if not self.data_file.exists():
            logger.error(f"❌ Arquivo não encontrado: {self.data_file}")
            return False
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict) and 'messages' in data:
                self.messages = data['messages']
            else:
                self.messages = data if isinstance(data, list) else []
            
            logger.info(f"✅ {len(self.messages)} mensagens carregadas")
            return len(self.messages) > 0
        
        except Exception as e:
            logger.error(f"❌ Erro ao carregar: {e}")
            return False
    
    def extract_training_docs(self) -> List[str]:
        """Extrair documentos de treinamento das mensagens."""
        logger.info("📝 Extracting training documents...")
        docs = []
        
        # Agrupar por tipo de mensagem e fonte
        message_groups = {}
        
        for msg in self.messages:
            msg_type = msg.get('message_type', 'unknown')
            source = msg.get('source', 'unknown')
            content = msg.get('content', '')
            timestamp = msg.get('timestamp', '')
            
            if not content or len(content) < 5:
                continue
            
            # Criar chave de grupo (usar | como separador para evitar conflitos com UUID)
            group_key = f"{msg_type}|{source}"
            if group_key not in message_groups:
                message_groups[group_key] = []
            
            message_groups[group_key].append({
                'content': content,
                'timestamp': timestamp,
                'target': msg.get('target', '')
            })
        
        # Converter grupos para documentos
        for i, (group_key, group_msgs) in enumerate(message_groups.items()):
            parts = group_key.split('|')
            msg_type = parts[0]
            source = parts[1] if len(parts) > 1 else 'unknown'
            
            # Preparar documento com contexto
            doc = f"""
[Message Type: {msg_type}]
[Source: {source}]

Messages ({len(group_msgs)} total):
"""
            
            # Adicionar amostra de mensagens do grupo
            for msg in group_msgs[:3]:  # Primeiras 3 de cada grupo
                doc += f"\n- {msg['content'][:200]}..."
            
            docs.append(doc)
        
        logger.info(f"✅ {len(docs)} documentos de treinamento criados")
        return docs
    
    async def train_rag(self, docs: List[str]) -> int:
        """Treinar RAG com documentos."""
        logger.info("🧠 Iniciando treinamento RAG...")
        
        languages = ["python", "general"]
        total_indexed = 0
        
        for language in languages:
            logger.info(f"\n  📚 Treinando {language}...")
            
            try:
                rag = RAGManagerFactory.get_manager(language)
                
                for i, doc in enumerate(docs, 1):
                    try:
                        await rag.index_code(
                            code=doc,
                            language=language,
                            description=f"Real chat doc #{i} - {len(doc)} chars"
                        )
                        total_indexed += 1
                        
                        if i % 50 == 0:
                            logger.info(f"     ✓ {i}/{len(docs)} documentos")
                    
                    except Exception as e:
                        logger.warning(f"     ⚠️  Doc {i}: {e}")
                        continue
                
                logger.info(f"  ✅ {language.upper()} treinado com {total_indexed} docs")
            
            except Exception as e:
                logger.error(f"  ❌ Erro ao treinar {language}: {e}")
                continue
        
        return total_indexed
    
    async def test_rag(self) -> Dict[str, Any]:
        """Testar RAG com queries relevantes."""
        logger.info("🔍 Testando RAG com queries reais...")
        
        test_queries = [
            "coordinator auto-scaling",
            "agent responder communication",
            "error handling and recovery",
            "task execution and monitoring",
            "llm integration"
        ]
        
        results = {}
        
        try:
            rag = RAGManagerFactory.get_manager("python")
            
            for query in test_queries:
                search_results = await rag.search(query)
                results[query] = len(search_results)
                status = "✅" if len(search_results) > 0 else "⚠️"
                logger.info(f"  {status} '{query}' → {len(search_results)} resultados")
        
        except Exception as e:
            logger.error(f"  ❌ Erro ao testar: {e}")
        
        return results


async def main():
    """Execução principal."""
    print("\n" + "=" * 70)
    print("  🚀 TREINAMENTO COM DADOS REAIS DE CHAT")
    print("=" * 70 + "\n")
    
    trainer = RealChatTrainer()
    
    # Carregar dados
    if not trainer.load_data():
        logger.error("❌ Falha ao carregar dados. Abortando.")
        return 1
    
    # Extrair documentos
    logger.info("\n📝 ETAPA 1: Preparando documentos de treinamento...")
    docs = trainer.extract_training_docs()
    
    if not docs:
        logger.error("❌ Nenhum documento para treinar. Abortando.")
        return 1
    
    # Treinar RAG
    logger.info("\n🧠 ETAPA 2: Treinando RAG com dados reais...")
    indexed = await trainer.train_rag(docs)
    
    if indexed == 0:
        logger.error("❌ Nenhum documento foi indexado.")
        return 1
    
    # Testar
    logger.info("\n🔍 ETAPA 3: Testando RAG...")
    test_results = await trainer.test_rag()
    
    # Resumo
    print("\n" + "=" * 70)
    print("  ✅ TREINAMENTO COM DADOS REAIS COMPLETO")
    print("=" * 70)
    print(f"\n📊 Resultados:")
    print(f"  • Mensagens originais: {len(trainer.messages)}")
    print(f"  • Documentos criados: {len(docs)}")
    print(f"  • Documentos indexados: {indexed}")
    print(f"  • Queries testadas: {len(test_results)}")
    print(f"  • Querys com resultados: {sum(1 for v in test_results.values() if v > 0)}")
    
    print(f"\n🎯 Status:")
    print(f"  🟢 RAG pronto para consultas com dados REAIS do sistema")
    
    print("\n" + "=" * 70 + "\n")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
