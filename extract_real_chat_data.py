#!/usr/bin/env python3
"""
Extrator de dados de conversa real do PostgreSQL para treinamento de LLM.
Extrai 1939+ mensagens do banco de dados do sistema.
"""

import json
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import subprocess

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


class RealChatExtractor:
    """Extrator de mensagens reais do PostgreSQL."""
    
    def __init__(self, homelab_host: str = "homelab@192.168.15.2"):
        self.homelab_host = homelab_host
        self.messages: List[Dict[str, Any]] = []
    
    def execute_remote_query(self, query: str) -> str:
        """Executar query no PostgreSQL remoto via SSH."""
        cmd = [
            "ssh", "-o", "ConnectTimeout=5", self.homelab_host,
            f'docker exec eddie-postgres psql -U eddie -d postgres -t -c "{query}"'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.stdout
        except subprocess.TimeoutExpired:
            logger.error("❌ Timeout ao executar query remota")
            return ""
        except Exception as e:
            logger.error(f"❌ Erro ao executar query: {e}")
            return ""
    
    def extract_messages(self) -> int:
        """Extrair mensagens real do PostgreSQL."""
        logger.info("📥 Extraindo mensagens reais do PostgreSQL...")
        
        # Query para extrair todas as mensagens em JSON
        query = """
        SELECT json_agg(json_build_object(
            'id', id,
            'timestamp', timestamp,
            'message_type', message_type,
            'source', source,
            'target', target,
            'content', content
        ) ORDER BY timestamp DESC)
        FROM messages;
        """
        
        output = self.execute_remote_query(query)
        
        if not output or output.strip() == "":
            logger.warning("⚠️  Nenhuma mensagem retornada")
            return 0
        
        try:
            # Parse da resposta JSON
            data = json.loads(output.strip())
            
            if isinstance(data, list):
                self.messages = data
                logger.info(f"✅ {len(self.messages)} mensagens extraídas")
                return len(self.messages)
            else:
                logger.warning(f"⚠️  Formato inesperado: {type(data)}")
                return 0
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erro ao parsear JSON: {e}")
            logger.error(f"   Output: {output[:200]}")
            return 0
    
    def save_to_file(self, filepath: Path) -> bool:
        """Salvar mensagens em arquivo JSON."""
        logger.info(f"💾 Salvando {len(self.messages)} mensagens em {filepath}...")
        
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            output = {
                "source": "PostgreSQL - Real Chat Data",
                "extracted_at": datetime.now().isoformat(),
                "total_messages": len(self.messages),
                "messages": self.messages
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Arquivo salvo: {filepath}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Erro ao salvar: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obter estatísticas dos dados."""
        if not self.messages:
            return {}
        
        message_types = {}
        sources = {}
        targets = {}
        
        for msg in self.messages:
            msg_type = msg.get('message_type', 'unknown')
            source = msg.get('source', 'unknown')
            target = msg.get('target', 'unknown')
            
            message_types[msg_type] = message_types.get(msg_type, 0) + 1
            sources[source] = sources.get(source, 0) + 1
            targets[target] = targets.get(target, 0) + 1
        
        return {
            "total_messages": len(self.messages),
            "message_types": message_types,
            "sources": sources,
            "targets": targets,
            "date_range": {
                "first": self.messages[-1] if self.messages else None,
                "last": self.messages[0] if self.messages else None
            }
        }


async def main():
    """Execução principal."""
    print("\n" + "=" * 70)
    print("  🔍 EXTRATOR DE CHAT REAL - PostgreSQL → Treinamento")
    print("=" * 70 + "\n")
    
    extractor = RealChatExtractor()
    
    # Extrair
    logger.info("📋 ETAPA 1: Extraindo mensagens reais...")
    count = extractor.extract_messages()
    
    if count == 0:
        logger.error("❌ Nenhuma mensagem extraída. Abortando.")
        return 1
    
    # Estatísticas
    logger.info("\n📊 ETAPA 2: Analisando dados...")
    stats = extractor.get_statistics()
    
    print(f"\n✅ Estatísticas dos dados:")
    print(f"   Total: {stats['total_messages']} mensagens")
    print(f"\n   Tipos de mensagem:")
    for msg_type, count in sorted(stats['message_types'].items(), key=lambda x: x[1], reverse=True):
        pct = (count / stats['total_messages']) * 100
        print(f"     • {msg_type:20} {count:4d} ({pct:5.1f}%)")
    
    print(f"\n   Fontes (top 10):")
    for source, count in sorted(stats['sources'].items(), key=lambda x: x[1], reverse=True)[:10]:
        pct = (count / stats['total_messages']) * 100
        print(f"     • {source:30} {count:4d} ({pct:5.1f}%)")
    
    # Salvar
    logger.info("\n💾 ETAPA 3: Salvando em arquivo...")
    output_file = Path("artifacts/real_chat_data.json")
    success = extractor.save_to_file(output_file)
    
    if not success:
        logger.error("❌ Erro ao salvar arquivo.")
        return 1
    
    print(f"\n✅ Arquivo pronto para treinamento: {output_file}")
    print(f"   Tamanho: {output_file.stat().st_size / 1024 / 1024:.1f} MB")
    
    print("\n" + "=" * 70)
    print("  ✅ EXTRAÇÃO CONCLUÍDA")
    print("=" * 70)
    print(f"\n💡 Próximo passo:")
    print(f"   python3 train_llm_on_real_chats.py\n")
    
    return 0


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
