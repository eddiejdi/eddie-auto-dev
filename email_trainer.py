#!/usr/bin/env python3
"""
Módulo de Treinamento de Emails para Eddie Assistant
Extrai conhecimento dos emails antes de excluí-los

Autor: Eddie Assistant
Data: 2026
"""

import os
import json
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('EmailTrainer')

# Configurações
BASE_DIR = Path(__file__).parent
TRAINING_DIR = BASE_DIR / "training_data"
CHROMA_DIR = BASE_DIR / "chroma_db"
EMAIL_TRAINING_DIR = BASE_DIR / "email_training_data"
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")

# Criar diretórios
TRAINING_DIR.mkdir(exist_ok=True)
EMAIL_TRAINING_DIR.mkdir(exist_ok=True)

# Tentar importar ChromaDB
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("ChromaDB não disponível - treinamento via RAG desabilitado")


class EmailTrainer:
    """Treina a IA com conteúdo dos emails antes de excluir"""
    
    def __init__(self):
        self.ollama_url = OLLAMA_URL
        self.chroma_client = None
        self.collection = None
        self._init_chromadb()
    
    def _init_chromadb(self):
        """Inicializa ChromaDB"""
        if not CHROMADB_AVAILABLE:
            return
        
        try:
            CHROMA_DIR.mkdir(exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            
            try:
                self.collection = self.chroma_client.get_collection("eddie_emails")
                logger.info(f"Coleção existente: {self.collection.count()} emails")
            except:
                self.collection = self.chroma_client.create_collection(
                    name="eddie_emails",
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info("Nova coleção de emails criada")
                
        except Exception as e:
            logger.error(f"Erro ao inicializar ChromaDB: {e}")
    
    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Gera embedding usando Ollama"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text[:8000]},  # Limitar tamanho
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("embedding")
        except Exception as e:
            logger.warning(f"Erro ao gerar embedding: {e}")
        return None
    
    def extract_email_knowledge(self, email_data: Dict[str, Any]) -> Dict[str, str]:
        """Extrai conhecimento útil de um email"""
        subject = email_data.get('subject', '')
        sender = email_data.get('sender', '')
        sender_email = email_data.get('sender_email', '')
        body = email_data.get('body', '') or email_data.get('snippet', '')
        date = email_data.get('date', '')
        
        # Criar ID único
        email_id = hashlib.md5(f"{sender_email}{subject}{date}".encode()).hexdigest()[:12]
        
        # Criar documento para indexação
        document = f"""Email de {sender} ({sender_email})
Assunto: {subject}
Data: {date}

Conteúdo:
{body[:2000]}
"""
        
        # Metadados
        metadata = {
            'type': 'email',
            'sender': sender,
            'sender_email': sender_email,
            'subject': subject[:200],
            'date': str(date),
            'indexed_at': datetime.now().isoformat()
        }
        
        return {
            'id': f"email_{email_id}",
            'document': document,
            'metadata': metadata
        }
    
    def is_worth_training(self, email_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Verifica se o email vale a pena ser treinado"""
        
        # Emails classificados como spam/promocional não vale treinar
        if email_data.get('is_spam') or email_data.get('is_promotional'):
            return False, "Spam/Promocional - não treinar"
        
        # Emails muito curtos não tem valor
        body = email_data.get('body', '') or email_data.get('snippet', '')
        if len(body) < 50:
            return False, "Conteúdo muito curto"
        
        # Emails importantes/pessoais valem treinar
        if email_data.get('is_important') or email_data.get('is_personal'):
            return True, "Email importante/pessoal"
        
        # Emails normais podem ter valor
        subject = email_data.get('subject', '').lower()
        
        # Verificar se contém informações úteis
        useful_keywords = [
            'projeto', 'reunião', 'meeting', 'proposta', 'contrato',
            'pagamento', 'fatura', 'relatório', 'report',
            'código', 'code', 'deploy', 'servidor', 'server',
            'bug', 'erro', 'issue', 'problema',
            'update', 'atualização', 'versão', 'release',
            'github', 'pull request', 'commit', 'merge',
            'edenilson', 'eddie', 'pessoal'
        ]
        
        content = f"{subject} {body}".lower()
        
        for kw in useful_keywords:
            if kw in content:
                return True, f"Contém informação útil: {kw}"
        
        # Score baseado na classificação
        spam_score = email_data.get('spam_score', 0)
        if spam_score <= 0:
            return True, "Score indica email relevante"
        
        return False, "Sem valor de treinamento identificado"
    
    def train_single_email(self, email_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Treina com um único email"""
        
        # Verificar se vale treinar
        worth, reason = self.is_worth_training(email_data)
        if not worth:
            return False, f"Ignorado: {reason}"
        
        # Extrair conhecimento
        knowledge = self.extract_email_knowledge(email_data)
        
        # Indexar no ChromaDB
        if self.collection:
            try:
                embedding = self.get_embedding(knowledge['document'])
                
                if embedding:
                    self.collection.upsert(
                        ids=[knowledge['id']],
                        documents=[knowledge['document']],
                        embeddings=[embedding],
                        metadatas=[knowledge['metadata']]
                    )
                    return True, f"Indexado no RAG: {knowledge['id']}"
                else:
                    # Salvar localmente se embedding falhar
                    return self._save_locally(knowledge)
                    
            except Exception as e:
                logger.error(f"Erro ao indexar: {e}")
                return self._save_locally(knowledge)
        else:
            # Sem ChromaDB, salvar localmente
            return self._save_locally(knowledge)
    
    def _save_locally(self, knowledge: Dict) -> Tuple[bool, str]:
        """Salva conhecimento localmente como fallback"""
        try:
            file_path = EMAIL_TRAINING_DIR / f"{knowledge['id']}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(knowledge, f, ensure_ascii=False, indent=2)
            return True, f"Salvo localmente: {file_path.name}"
        except Exception as e:
            return False, f"Erro ao salvar: {e}"
    
    def train_batch(self, emails: List[Dict[str, Any]], 
                   progress_callback=None) -> Dict[str, Any]:
        """Treina com um lote de emails"""
        
        results = {
            'total': len(emails),
            'trained': 0,
            'skipped': 0,
            'failed': 0,
            'details': []
        }
        
        for i, email_data in enumerate(emails):
            success, reason = self.train_single_email(email_data)
            
            detail = {
                'subject': email_data.get('subject', 'N/A')[:50],
                'success': success,
                'reason': reason
            }
            results['details'].append(detail)
            
            if success:
                results['trained'] += 1
            elif 'Ignorado' in reason:
                results['skipped'] += 1
            else:
                results['failed'] += 1
            
            if progress_callback:
                progress_callback(i + 1, len(emails), detail)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do treinamento"""
        stats = {
            'chromadb_available': CHROMADB_AVAILABLE,
            'emails_indexed': 0,
            'local_files': 0
        }
        
        if self.collection:
            stats['emails_indexed'] = self.collection.count()
        
        if EMAIL_TRAINING_DIR.exists():
            stats['local_files'] = len(list(EMAIL_TRAINING_DIR.glob('*.json')))
        
        return stats
    
    def search_emails(self, query: str, n_results: int = 5) -> List[Dict]:
        """Busca emails treinados por similaridade"""
        if not self.collection:
            return []
        
        try:
            embedding = self.get_embedding(query)
            if not embedding:
                return []
            
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=n_results
            )
            
            emails = []
            for i, doc in enumerate(results.get('documents', [[]])[0]):
                metadata = results.get('metadatas', [[]])[0][i] if results.get('metadatas') else {}
                distance = results.get('distances', [[]])[0][i] if results.get('distances') else None
                
                emails.append({
                    'document': doc,
                    'metadata': metadata,
                    'relevance': 1 - distance if distance else 0
                })
            
            return emails
            
        except Exception as e:
            logger.error(f"Erro na busca: {e}")
            return []


class EmailCleanerWithTraining:
    """Limpador de emails que treina antes de excluir"""
    
    def __init__(self):
        self.trainer = EmailTrainer()
        self._gmail_client = None
        self._cleaner = None
    
    def _get_gmail(self):
        """Obtém cliente Gmail"""
        if not self._gmail_client:
            from gmail_integration import get_gmail_client, get_email_cleaner
            self._gmail_client = get_gmail_client()
            self._cleaner = get_email_cleaner()
        return self._gmail_client, self._cleaner
    
    async def clean_with_training(self, 
                                   max_emails: int = 100,
                                   dry_run: bool = True,
                                   train_important: bool = True) -> Dict[str, Any]:
        """Limpa emails, treinando os importantes primeiro"""
        
        gmail, cleaner = self._get_gmail()
        
        # 1. Analisar emails
        stats = await cleaner.analyze_inbox(max_emails)
        
        if 'error' in stats:
            return {'error': stats['error']}
        
        result = {
            'analyzed': stats['total'],
            'spam_found': len(stats['spam']),
            'promotional_found': len(stats['promotional']),
            'important_found': len(stats['important']),
            'training_results': None,
            'cleanup_results': None,
            'dry_run': dry_run
        }
        
        # 2. Treinar com emails importantes (antes de qualquer exclusão)
        if train_important and (stats['important'] or stats['normal']):
            emails_to_train = stats['important'] + stats['normal']
            
            # Converter para dict para treinamento
            emails_data = [e.to_dict() for e in emails_to_train]
            
            training_results = self.trainer.train_batch(emails_data)
            result['training_results'] = {
                'total': training_results['total'],
                'trained': training_results['trained'],
                'skipped': training_results['skipped'],
                'failed': training_results['failed']
            }
        
        # 3. Limpar spam e promoções (se não for dry run)
        to_delete = stats['spam'] + stats['promotional']
        result['to_delete'] = len(to_delete)
        
        if not dry_run and to_delete:
            ids_to_delete = [e.id for e in to_delete]
            success, msg = await gmail.move_to_trash(ids_to_delete)
            result['cleanup_results'] = {
                'success': success,
                'message': msg,
                'deleted': len(ids_to_delete) if success else 0
            }
        
        return result
    
    async def generate_report(self, max_emails: int = 100) -> str:
        """Gera relatório completo"""
        
        result = await self.clean_with_training(max_emails, dry_run=True)
        
        if 'error' in result:
            return f"❌ {result['error']}"
        
        report = f"""📊 **Análise de Emails com Treinamento**

📬 **Resumo:**
• Total analisado: {result['analyzed']}
• 🚫 Spam: {result['spam_found']}
• 📢 Promoções: {result['promotional_found']}
• ⭐ Importantes: {result['important_found']}
• 🗑️ A excluir: {result['to_delete']}

"""
        
        if result.get('training_results'):
            tr = result['training_results']
            report += f"""🧠 **Treinamento (prévia):**
• Total para treinar: {tr['total']}
• Serão indexados: {tr['trained']}
• Ignorados: {tr['skipped']}
• Falhas: {tr['failed']}

"""
        
        stats = self.trainer.get_stats()
        report += f"""📚 **Base de Conhecimento:**
• ChromaDB: {'✅' if stats['chromadb_available'] else '❌'}
• Emails indexados: {stats['emails_indexed']}
• Arquivos locais: {stats['local_files']}

"""
        
        report += """💡 **Para executar:**
`/gmail treinar_limpar confirmar` - Treina IA e limpa spam"""
        
        return report


# Instância global
_trainer: Optional[EmailTrainer] = None
_cleaner_with_training: Optional[EmailCleanerWithTraining] = None


def get_email_trainer() -> EmailTrainer:
    """Obtém instância do treinador"""
    global _trainer
    if _trainer is None:
        _trainer = EmailTrainer()
    return _trainer


def get_cleaner_with_training() -> EmailCleanerWithTraining:
    """Obtém instância do limpador com treinamento"""
    global _cleaner_with_training
    if _cleaner_with_training is None:
        _cleaner_with_training = EmailCleanerWithTraining()
    return _cleaner_with_training


async def process_email_training_command(command: str, args: str = "") -> str:
    """Processa comandos de treinamento de email"""
    
    cleaner = get_cleaner_with_training()
    trainer = get_email_trainer()
    
    command = command.lower().strip()
    
    if command in ['analisar', 'analyze', 'relatorio', 'report']:
        return await cleaner.generate_report(max_emails=100)
    
    if command in ['treinar_limpar', 'train_clean', 'limpar']:
        if 'confirmar' in args.lower() or 'confirm' in args.lower():
            # Executar treinamento e limpeza
            result = await cleaner.clean_with_training(
                max_emails=100, 
                dry_run=False,
                train_important=True
            )
            
            if 'error' in result:
                return f"❌ {result['error']}"
            
            msg = f"""🧠🧹 **Treinamento e Limpeza Executados!**

📊 **Análise:**
• Emails analisados: {result['analyzed']}
• Importantes: {result['important_found']}
• Spam: {result['spam_found']}
• Promoções: {result['promotional_found']}

"""
            
            if result.get('training_results'):
                tr = result['training_results']
                msg += f"""🧠 **Treinamento:**
• Emails processados: {tr['total']}
• Indexados na IA: {tr['trained']}
• Ignorados: {tr['skipped']}

"""
            
            if result.get('cleanup_results'):
                cr = result['cleanup_results']
                msg += f"""🗑️ **Limpeza:**
• {cr.get('message', 'Executada')}
"""
            
            return msg
        else:
            # Prévia
            return await cleaner.generate_report(max_emails=100)
    
    if command in ['stats', 'estatisticas']:
        stats = trainer.get_stats()
        return f"""📊 **Estatísticas de Treinamento**

🗄️ ChromaDB: {'✅ Disponível' if stats['chromadb_available'] else '❌ Não disponível'}
📧 Emails indexados: {stats['emails_indexed']}
💾 Arquivos locais: {stats['local_files']}
"""
    
    if command in ['buscar', 'search', 'pesquisar']:
        if not args:
            return "❓ Use: /gmail buscar <termo>"
        
        results = trainer.search_emails(args, n_results=5)
        
        if not results:
            return f"🔍 Nenhum email encontrado para: '{args}'"
        
        msg = f"🔍 **Emails relacionados a '{args}':**\n\n"
        for i, r in enumerate(results, 1):
            meta = r.get('metadata', {})
            relevance = r.get('relevance', 0) * 100
            msg += f"{i}. **{meta.get('subject', 'N/A')[:40]}...**\n"
            msg += f"   De: {meta.get('sender', 'N/A')}\n"
            msg += f"   Relevância: {relevance:.0f}%\n\n"
        
        return msg
    
    if command in ['ajuda', 'help']:
        return """🧠 **Comandos de Treinamento de Email:**

📊 **Análise:**
• `/gmail analisar` - Relatório completo

🧠🧹 **Treinar e Limpar:**
• `/gmail treinar_limpar` - Prévia
• `/gmail treinar_limpar confirmar` - Executar

🔍 **Buscar:**
• `/gmail buscar <termo>` - Buscar nos emails indexados

📈 **Estatísticas:**
• `/gmail stats` - Ver estatísticas

💡 **Processo:**
1. Emails importantes são indexados na IA
2. Spam e promoções são movidos para lixeira
3. Conhecimento é preservado antes da exclusão"""
    
    return f"❓ Comando '{command}' não reconhecido. Use `/gmail ajuda`"


# Teste
if __name__ == "__main__":
    import asyncio
    
    async def test():
        trainer = get_email_trainer()
        
        print("📊 Estatísticas:")
        stats = trainer.get_stats()
        print(f"  ChromaDB: {stats['chromadb_available']}")
        print(f"  Emails indexados: {stats['emails_indexed']}")
        
        # Testar treinamento com email fake
        fake_email = {
            'subject': 'Reunião importante sobre projeto Python',
            'sender': 'João Silva',
            'sender_email': 'joao@gmail.com',
            'body': 'Oi Edenilson, vamos discutir o deploy do servidor amanhã às 14h.',
            'date': '2026-01-11',
            'is_important': True,
            'spam_score': -20
        }
        
        success, msg = trainer.train_single_email(fake_email)
        print(f"\n📧 Teste treinamento: {msg}")
    
    asyncio.run(test())
